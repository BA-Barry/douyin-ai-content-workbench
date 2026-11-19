from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("douyin_workbench_resilience", ROOT / "workbench" / "server.py")
SERVER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SERVER)


class ProductionRequestSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.root = Path(self.temp.name)
        self.content = self.root / "content"
        self.request = self.content / "fixture" / "production" / "workbench_request.json"
        self.request.parent.mkdir(parents=True)
        self.patches = ExitStack()
        self.patches.enter_context(patch.object(SERVER, "CONTENT", self.content))
        self.patches.enter_context(patch.object(SERVER, "ROOT", self.root))

    def tearDown(self) -> None:
        self.patches.close()
        self.temp.cleanup()

    def write_request(self, value) -> None:
        self.request.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_saved_fields_round_trip_without_private_extras(self) -> None:
        self.write_request({
            "created_at": "2026-09-25T15:00:00+08:00",
            "route_parameters": {
                "prompt": "雨后海边\n不要人物",
                "image_count": 12,
                "duration_seconds": "25.5",
                "asset_strategy": "USE_EXISTING",
                "video_mode": "FIRST_FRAME_TO_VIDEO",
                "voice_mode": "none",
                "music_mode": "platform_manual",
                "asset_ids": ["old-reference"],
                "api_key": "do-not-expose",
                "provider_credentials": {"token": "do-not-expose"},
            },
            "private_metadata": "do-not-expose",
        })
        summary = SERVER.production_request_summary("fixture", {"asset_ids": ["new-reference"]})
        self.assertEqual("雨后海边\n不要人物", summary["parameters"]["prompt"])
        self.assertEqual(12, summary["parameters"]["image_count"])
        self.assertEqual(25.5, summary["parameters"]["duration_seconds"])
        self.assertEqual("2026-09-25T15:00:00+08:00", summary["savedAt"])
        self.assertEqual(["new-reference"], summary["assetIds"])
        self.assertEqual(summary["assetIds"], summary["parameters"]["asset_ids"])
        self.assertNotIn("old-reference", json.dumps(summary))
        self.assertNotIn("do-not-expose", json.dumps(summary))

    def test_current_empty_bindings_do_not_restore_removed_assets(self) -> None:
        self.write_request({"route_parameters": {"asset_ids": ["removed-reference"], "prompt": "saved prompt"}})
        summary = SERVER.production_request_summary("fixture", {"asset_ids": []})
        self.assertEqual([], summary["assetIds"])
        self.assertEqual([], summary["parameters"]["asset_ids"])

    def test_missing_and_invalid_requests_are_safe(self) -> None:
        expected = {"parameters": {"asset_ids": []}, "savedAt": "", "assetIds": []}
        self.assertEqual(expected, SERVER.production_request_summary("fixture", {}))
        for payload in (None, [], "unexpected", {"route_parameters": []}, {"route_parameters": None, "created_at": {"token": "secret"}}):
            with self.subTest(payload=payload):
                self.write_request(payload)
                self.assertEqual(expected, SERVER.production_request_summary("fixture", {}))
        for payload in (b"{not json", b"\xff\xfe\x00"):
            with self.subTest(raw=payload):
                self.request.write_bytes(payload)
                self.assertEqual(expected, SERVER.production_request_summary("fixture", {}))

    def test_invalid_parameter_types_and_choices_are_omitted(self) -> None:
        self.write_request({"route_parameters": {
            "prompt": {"token": "secret"},
            "image_count": True,
            "duration_seconds": "NaN",
            "music_mode": "not-a-valid-choice",
            "voice_mode": ["none"],
            "video_mode": {"private": "value"},
            "asset_strategy": "NONE",
        }})
        summary = SERVER.production_request_summary("fixture", {"asset_ids": ["current", None, {"token": "secret"}, "current", ""]})
        self.assertEqual({"asset_strategy": "NONE", "asset_ids": ["current"]}, summary["parameters"])
        for invalid_number in ("Infinity", "-Infinity", "not-a-number", -1, 10001, {}, []):
            with self.subTest(number=invalid_number):
                self.write_request({"route_parameters": {"image_count": invalid_number}})
                self.assertNotIn("image_count", SERVER.production_request_summary("fixture", {})["parameters"])

    def test_project_summary_includes_editable_request(self) -> None:
        self.write_request({"created_at": "2026-09-25T15:00:00+08:00", "route_parameters": {"prompt": "saved"}})
        progress = {"verified": 0, "evidenceGaps": 0, "total": 1, "verifiedPercent": 0, "current": {}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(SERVER, "image_files", return_value=[]))
            stack.enter_context(patch.object(SERVER, "latest_metrics", return_value={}))
            stack.enter_context(patch.object(SERVER, "account_mapping", return_value={}))
            stack.enter_context(patch.object(SERVER, "project_stage_progress", return_value=progress))
            stack.enter_context(patch.object(SERVER.media_library, "bindings", return_value={"asset_ids": ["active"]}))
            stack.enter_context(patch.object(SERVER.codex_dispatcher, "list_items", return_value=[]))
            summary = SERVER.project_summary({"video_id": "fixture", "content_type": "IMAGE_CAROUSEL"})
        self.assertEqual("saved", summary["productionRequest"]["parameters"]["prompt"])
        self.assertEqual(["active"], summary["productionRequest"]["assetIds"])
        self.assertEqual(1, summary["assetCount"])


class ProjectAccountSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.root = Path(self.temp.name)
        self.accounts = self.root / "data" / "account_profiles.json"
        self.accounts.parent.mkdir(parents=True)
        self.patches = ExitStack()
        self.patches.enter_context(patch.object(SERVER, "ROOT", self.root))
        self.patches.enter_context(patch.object(SERVER, "CONTENT", self.root / "content"))
        self.patches.enter_context(patch.object(SERVER, "ACCOUNT_PROFILES", self.accounts))
        self.patches.enter_context(patch.object(SERVER, "ACCOUNT_MAP", self.root / "data" / "account_content_map.csv"))
        self.patches.enter_context(patch.object(SERVER, "detail", side_effect=lambda video_id: {
            "id": video_id, "accountId": SERVER.account_mapping()[video_id],
        }))
        self.set_active("first")
        self.payload = {
            "videoId": "account-fixture", "title": "Test", "hypothesis": "Test hypothesis",
            "contentType": "IMAGE_CAROUSEL", "pillar": "Test pillar",
        }

    def tearDown(self) -> None:
        self.patches.close()
        self.temp.cleanup()

    def set_active(self, account_id: str) -> None:
        self.accounts.write_text(json.dumps({
            "active_account_id": account_id,
            "profiles": [{"account_id": "first"}, {"account_id": "second"}],
        }), encoding="utf-8")

    def switch_during_init(self, *args, **kwargs):
        self.set_active("second")
        return Mock(returncode=0, stdout="", stderr="")

    def test_legacy_payload_keeps_initial_account_during_profile_switch(self) -> None:
        with patch.object(SERVER.subprocess, "run", side_effect=self.switch_during_init):
            item = SERVER.create_project(self.payload)
        self.assertEqual("second", SERVER.account_data()["activeAccountId"])
        self.assertEqual("first", item["accountId"])
        self.assertEqual("first", SERVER.account_mapping()["account-fixture"])

    def test_explicit_account_is_used_even_when_current_profile_differs(self) -> None:
        self.set_active("second")
        with patch.object(SERVER.subprocess, "run", side_effect=self.switch_during_init):
            item = SERVER.create_project({**self.payload, "accountId": "first"})
        self.assertEqual("first", item["accountId"])

    def test_unknown_or_malformed_account_is_rejected_before_init(self) -> None:
        for account_id in ("missing", "", None, ["first"]):
            with self.subTest(account_id=account_id), patch.object(SERVER.subprocess, "run") as init:
                with self.assertRaisesRegex(ValueError, "unknown account profile"):
                    SERVER.create_project({**self.payload, "accountId": account_id})
                init.assert_not_called()
        self.assertEqual({}, SERVER.account_mapping())


class DisconnectHandlingTests(unittest.TestCase):
    def handler(self, path: str, *, method: str = "GET", body: bytes = b"", output=None):
        handler = SERVER.WorkbenchHandler.__new__(SERVER.WorkbenchHandler)
        header = f"{method} {path} HTTP/1.0\r\nHost: 127.0.0.1:8765\r\nContent-Length: {len(body)}\r\n\r\n"
        handler.rfile = io.BytesIO(header.encode("ascii") + body)
        handler.wfile = output if output is not None else io.BytesIO()
        handler.client_address = ("127.0.0.1", 10000)
        handler.close_connection = True
        handler.send_response = Mock(wraps=handler.send_response)
        return handler

    def test_disconnect_during_get_or_post_does_not_send_second_response(self) -> None:
        for exception_type in SERVER.CLIENT_DISCONNECT_ERRORS:
            for path, method in (("/api/health", "GET"), ("/api/jobs/create", "POST"), ("/api/assets/import", "POST")):
                with self.subTest(error=exception_type.__name__, path=path):
                    output = Mock()
                    output.write.side_effect = exception_type("client closed")
                    handler = self.handler(path, method=method, body=b"{}" if method == "POST" else b"", output=output)
                    with patch.object(SERVER.task_runner, "create_job", return_value={"ok": True}), patch.object(SERVER.media_library, "import_stream", return_value={"ok": True}):
                        handler.handle_one_request()
                    self.assertEqual(1, handler.send_response.call_count)
                    self.assertNotEqual(500, handler.send_response.call_args.args[0])
                    self.assertTrue(handler.close_connection)

    def test_disconnect_during_error_response_or_final_flush_is_handled(self) -> None:
        output = Mock()
        output.write.side_effect = BrokenPipeError("client closed")
        handler = self.handler("/api/jobs/create", method="POST", body=b"{}", output=output)
        with patch.object(SERVER.task_runner, "create_job", side_effect=ValueError("invalid job")):
            handler.handle_one_request()
        handler.send_response.assert_called_once_with(400)

        output = Mock()
        output.flush.side_effect = ConnectionResetError("client closed after response")
        handler = self.handler("/api/health", output=output)
        handler.handle_one_request()
        handler.send_response.assert_called_once_with(200)
        self.assertTrue(handler.close_connection)

    def test_body_disconnect_is_not_converted_to_internal_error(self) -> None:
        handler = self.handler("/api/jobs/create", method="POST", body=b"{}")
        handler.rfile = Mock(wraps=handler.rfile)
        handler.rfile.read.side_effect = ConnectionAbortedError("client closed before body")
        handler.handle_one_request()
        handler.send_response.assert_not_called()
        self.assertTrue(handler.close_connection)

    def test_business_and_filesystem_failures_still_return_500(self) -> None:
        for error in (RuntimeError("business failure"), OSError("disk failure"), ConnectionResetError("downstream reset")):
            with self.subTest(error=type(error).__name__):
                handler = self.handler("/api/dashboard")
                with patch.object(SERVER, "dashboard", side_effect=error):
                    handler.handle_one_request()
                handler.send_response.assert_called_once_with(500)
                self.assertIn(str(error).encode("utf-8"), handler.wfile.getvalue())

    def test_unexpected_boundary_error_is_not_swallowed(self) -> None:
        handler = self.handler("/api/health")
        handler.rfile = Mock()
        handler.rfile.readline.side_effect = OSError("unexpected I/O failure")
        with self.assertRaisesRegex(OSError, "unexpected I/O failure"):
            handler.handle_one_request()


if __name__ == "__main__":
    unittest.main()
