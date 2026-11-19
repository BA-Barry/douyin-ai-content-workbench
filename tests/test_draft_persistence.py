from __future__ import annotations

import copy
import importlib
import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workbench"))
import draft_store


class DraftPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        (self.data / "account_profiles.json").write_text(json.dumps({"profiles": [{"account_id": "main"}, {"account_id": "second"}]}), encoding="utf-8")
        (self.data / "content_registry.csv").write_text("video_id,state,content_type\nproject-one,IDEA,ATMOSPHERE_VIDEO\nproject-two,IDEA,IMAGE_CAROUSEL\n", encoding="utf-8")
        (self.data / "account_content_map.csv").write_text("video_id,account_id\nproject-one,main\nproject-two,second\n", encoding="utf-8")
        self.payload = {"account_id": "main", "video_id": "project-one", "action": "SAVE_PRODUCTION_REQUEST",
                        "values": {"prompt": "雨后的海岸\n不出现人物", "image_count": 0, "asset_ids": []}, "expected_version": 0}
        self.store = self.data / "workbench_drafts.json"
        self.patches = [patch.object(draft_store, "ROOT", self.root), patch.object(draft_store, "STORE", self.store)]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def test_round_trip_survives_module_reload_and_stays_on_g_drive(self):
        saved = draft_store.save_draft(self.payload)
        self.assertEqual(1, saved["version"])
        self.assertTrue(saved["updated_at"])
        self.assertEqual("g:", self.store.drive.lower())
        self.assertTrue(self.store.is_file())
        # Re-import from a new module object, as a server restart would.
        spec = importlib.util.spec_from_file_location("fresh_draft_store", ROOT / "workbench/draft_store.py")
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        fresh.ROOT, fresh.STORE = self.root, self.store
        self.assertEqual(saved, fresh.load_draft("main", "project-one", "SAVE_PRODUCTION_REQUEST"))
        self.assertFalse((self.data / "workbench_jobs.json").exists())

    def test_scopes_are_isolated_and_wrong_account_cannot_read(self):
        draft_store.save_draft(self.payload)
        other = {**self.payload, "account_id": "second", "video_id": "project-two", "values": {"prompt": "second"}}
        draft_store.save_draft(other)
        self.assertEqual("second", draft_store.load_draft("second", "project-two", self.payload["action"])["values"]["prompt"])
        self.assertEqual(0, draft_store.load_draft("main", "project-one", "COMPILE_VIDEO_TASK_PACKAGE")["version"])
        for scope in (("second", "project-one"), ("main", "project-two"), ("unknown", "project-one"), ("main", "missing")):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                draft_store.load_draft(*scope, self.payload["action"])

    def test_approval_and_private_fields_are_never_persisted(self):
        payload = {**self.payload, "action": "GENERATE_FLOVA_VIDEO", "values": {
            "model": "Seedance 2.5", "max_credits": 10, "generation_ack": True,
            "reference_upload_ack": True, "api_key": "secret", "token": "secret", "cookie": "secret",
        }}
        saved = draft_store.save_draft(payload)
        self.assertEqual({"model": "Seedance 2.5", "max_credits": 10}, saved["values"])
        content = self.store.read_text(encoding="utf-8")
        for forbidden in ("generation_ack", "reference_upload_ack", "secret"):
            self.assertNotIn(forbidden, content)

    def test_stale_version_returns_current_without_overwriting(self):
        first = draft_store.save_draft(self.payload)
        with self.assertRaises(draft_store.DraftConflict) as raised:
            draft_store.save_draft({**self.payload, "values": {"prompt": "stale"}})
        self.assertEqual(first, raised.exception.current)
        self.assertEqual(first, draft_store.load_draft("main", "project-one", self.payload["action"]))
        second = draft_store.save_draft({**self.payload, "values": {"prompt": "explicit retry"}, "expected_version": first["version"]})
        self.assertEqual(2, second["version"])

    def test_simultaneous_tabs_get_one_save_and_one_conflict(self):
        def save(text):
            try: return draft_store.save_draft({**self.payload, "values": {"prompt": text}})
            except draft_store.DraftConflict: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["first", "second"]))
        self.assertEqual(1, results.count("conflict"))
        self.assertEqual(1, draft_store.load_draft("main", "project-one", self.payload["action"])["version"])

    def test_invalid_scopes_and_versions_are_rejected(self):
        for key, value in (("account_id", "../main"), ("video_id", "../escape"), ("action", "SHELL"), ("expected_version", True), ("expected_version", -1), ("expected_version", "0")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                draft_store.save_draft({**self.payload, key: value})
        self.assertFalse(self.store.exists())

    def test_failed_disk_write_preserves_previous_draft(self):
        first = draft_store.save_draft(self.payload)
        with patch.object(Path, "replace", side_effect=OSError("disk unavailable")), self.assertRaises(OSError):
            draft_store.save_draft({**self.payload, "expected_version": 1, "values": {"prompt": "do not lose old"}})
        self.assertEqual(first, draft_store.load_draft("main", "project-one", self.payload["action"]))

    def test_http_draft_refresh_conflict_and_provider_status(self):
        import server
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.WorkbenchHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        def request(path, payload=None):
            req = Request(base + path, data=json.dumps(payload).encode("utf-8") if payload is not None else None,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=5) as response: return json.loads(response.read().decode("utf-8"))
        query = urlencode({key: self.payload[key] for key in ("account_id", "video_id", "action")})
        try:
            self.assertEqual(0, request("/api/drafts?" + query)["version"])
            saved = request("/api/drafts/save", self.payload)
            self.assertEqual(saved, request("/api/drafts?" + query))
            with self.assertRaises(HTTPError) as conflict:
                request("/api/drafts/save", self.payload)
            self.assertEqual(409, conflict.exception.code)
            body = json.loads(conflict.exception.read().decode("utf-8"))
            self.assertEqual("DRAFT_CONFLICT", body["code"])
            self.assertEqual(saved, body["current"])
            with patch.object(server, "OFFLINE_MODE", False), patch.object(server.flova_runtime, "account_status", return_value={"authenticated": True, "credits_balance": 0}) as account:
                self.assertEqual(0, request("/api/providers/flova/status")["credits_balance"])
                account.assert_called_once()
            with patch.object(server, "OFFLINE_MODE", True), patch.object(server.flova_runtime, "account_status") as account:
                self.assertIsNone(request("/api/providers/flova/status")["credits_balance"])
                account.assert_not_called()
        finally:
            httpd.shutdown(); httpd.server_close(); thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
