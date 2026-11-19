from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(r"G:\抖音视频")
SPEC = importlib.util.spec_from_file_location("douyin_workbench_http", ROOT / "workbench" / "server.py")
SERVER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SERVER)


class WorkbenchHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        temp_root = Path(cls.temp.name)
        cls.original_store = SERVER.task_runner.JOB_STORE
        cls.original_output = SERVER.task_runner.JOB_OUTPUT
        SERVER.task_runner.JOB_STORE = temp_root / "workbench_jobs.json"
        SERVER.task_runner.JOB_OUTPUT = temp_root / "jobs"
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), SERVER.WorkbenchHandler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)
        SERVER.task_runner.JOB_STORE = cls.original_store
        SERVER.task_runner.JOB_OUTPUT = cls.original_output
        cls.temp.cleanup()

    def get_json(self, path: str) -> dict:
        with urlopen(self.base + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = Request(self.base + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_action_and_integration_catalogs_are_live(self) -> None:
        actions = self.get_json("/api/actions")
        integrations = self.get_json("/api/integrations")
        dispatch = self.get_json("/api/dispatch")
        providers = self.get_json("/api/video-providers")
        self.assertEqual(12, len(actions["items"]))
        self.assertIn("GENERATE_FLOVA_VIDEO", {item["id"] for item in actions["items"]})
        self.assertEqual({"MoneyPrinterTurbo", "Pixelle-Video", "social-auto-upload"}, {item["name"] for item in integrations["items"]})
        pixelle = next(item for item in integrations["items"] if item["id"] == "pixelle-video")
        self.assertTrue(pixelle["runtimeReady"])
        self.assertIn("apiHealthy", pixelle)

        skills = self.get_json("/api/skills")
        self.assertTrue(skills)
        self.assertTrue(all(item["category"] in {"视觉风格", "视频制作", "声音字幕", "设计工具", "其他"} for item in skills))
        self.assertIn("items", dispatch)
        self.assertEqual("FLOVA_CONTROLLED_PILOT", providers["decision"])
        projects = self.get_json("/api/projects?all=1")
        self.assertTrue(all("providerTarget" in item["skillPlan"] for item in projects))
        self.assertTrue(all("providerSkillName" in item["skillPlan"] for item in projects))
        self.assertTrue(all("promptPackageReady" in item["skillPlan"] for item in projects))

    def test_job_create_run_and_poll_is_functional(self) -> None:
        job = self.post_json("/api/jobs/create", {"actionId": "WORKFLOW_AUDIT", "videoId": "", "parameters": {}})
        self.post_json(f"/api/jobs/{job['job_id']}/run", {})
        current = job
        for _ in range(50):
            current = self.get_json(f"/api/jobs/{job['job_id']}")
            if current["status"] not in {"QUEUED", "RUNNING"}:
                break
            time.sleep(0.1)
        self.assertEqual("SUCCEEDED", current["status"])
        self.assertEqual(0, current["returncode"])
        self.assertFalse(current["publish_clicked"])

    def test_post_rejects_foreign_origin(self) -> None:
        request = Request(
            self.base + "/api/jobs/create",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "https://example.com"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(403, raised.exception.code)

    def test_frontend_has_handlers_for_primary_controls(self) -> None:
        html = (ROOT / "workbench" / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workbench" / "static" / "app.js").read_text(encoding="utf-8")
        for view in ("studio", "assets", "overview", "topics", "projects", "pipeline", "release", "skills", "offline"):
            self.assertIn(f'data-view="{view}"', html)
        self.assertNotIn('data-view="images"', html)
        self.assertNotIn('data-view="video"', html)
        self.assertIn("const views = {studio: showStudio, assets: showAssets", js)
        for renderer in ("showStudio", "showAssets", "showTopics", "showProjects", "showPipeline", "showRelease", "showSkills", "showOffline"):
            self.assertIn(f"async function {renderer}", js)
        self.assertNotIn("async function showImages", js)
        self.assertNotIn("async function showVideo", js)
        for control in ("#account-create", "#audit", "#job-form", "[data-engine-start]", "[data-engine-stop]", "[data-job-id]"):
            self.assertIn(control, js)
        self.assertIn("field.type === 'checkbox'", js)
        self.assertIn("document.querySelector('.sidebar').addEventListener", js)
        self.assertIn('class="workflow-steps"', js)
        self.assertIn('class="creation-grid"', js)
        self.assertIn('id="confirm-dialog"', html)
        self.assertIn("function requestConfirmation", js)
        self.assertIn('class="production-boundary"', js)
        self.assertIn('id="auto-skill-plan"', js)
        self.assertIn("plan.providerTarget", js)
        self.assertIn("plan.promptPackageReady", js)
        self.assertNotIn("field.name === 'visual_skill'", js)
        self.assertIn("action.enabled !== false", js)
        self.assertIn("field.type === 'asset_picker'", js)
        self.assertIn('data-create-route="IMAGE_CAROUSEL"', js)
        self.assertIn('data-create-route="ATMOSPHERE_VIDEO"', js)
        self.assertIn('id="studio-create-project-form"', js)
        self.assertIn("function routeFromDraft", js)

    def test_skill_trash_and_restore_round_trip(self) -> None:
        original_skills = SERVER.SKILLS
        original_trash = SERVER.TRASH
        fixture_root = Path(self.temp.name) / "skill-lifecycle"
        skills_root = fixture_root / "skills"
        trash_root = fixture_root / "trash"
        skill_root = skills_root / "temporary-style"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: temporary-style\ndescription: lifecycle fixture\n---\n",
            encoding="utf-8",
        )
        SERVER.SKILLS = skills_root
        SERVER.TRASH = trash_root
        try:
            before = self.get_json("/api/skills")
            self.assertEqual(["temporary-style"], [item["name"] for item in before])
            trashed = self.post_json(
                "/api/skills/temporary-style/trash",
                {"confirm": "temporary-style"},
            )
            self.assertFalse(skill_root.exists())
            self.assertTrue((trash_root / "skills" / trashed["trashId"] / "trash_manifest.json").exists())
            restored = self.post_json(
                "/api/trash/restore",
                {"kind": "skill", "trashId": trashed["trashId"], "confirm": trashed["trashId"]},
            )
            self.assertTrue(restored["restored"])
            self.assertTrue((skill_root / "SKILL.md").exists())
        finally:
            SERVER.SKILLS = original_skills
            SERVER.TRASH = original_trash

    @unittest.skipUnless(hasattr(Path('.'), "is_junction"), "junction detection requires Python 3.12+")
    def test_skill_junction_trash_removes_only_link_and_restores_it(self) -> None:
        original_skills = SERVER.SKILLS
        original_trash = SERVER.TRASH
        fixture_root = Path(self.temp.name) / "skill-junction-lifecycle"
        skills_root = fixture_root / "skills"
        trash_root = fixture_root / "trash"
        source_root = fixture_root / "g-source" / "linked-style"
        source_root.mkdir(parents=True)
        skills_root.mkdir(parents=True)
        (source_root / "SKILL.md").write_text(
            "---\nname: linked-style\ndescription: junction fixture\n---\n",
            encoding="utf-8",
        )
        junction = skills_root / "linked-style"
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(source_root)],
            text=True, capture_output=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(0, created.returncode, created.stderr or created.stdout)
        self.assertTrue(junction.is_junction())
        SERVER.SKILLS = skills_root
        SERVER.TRASH = trash_root
        try:
            trashed = self.post_json("/api/skills/linked-style/trash", {"confirm": "linked-style"})
            self.assertFalse(junction.exists())
            self.assertTrue((source_root / "SKILL.md").is_file())
            restored = self.post_json(
                "/api/trash/restore",
                {"kind": "skill", "trashId": trashed["trashId"], "confirm": trashed["trashId"]},
            )
            self.assertTrue(restored["restored"])
            self.assertTrue(junction.is_junction())
            self.assertEqual(source_root.resolve(), junction.resolve())
        finally:
            SERVER.SKILLS = original_skills
            SERVER.TRASH = original_trash

    def test_toolchain_status_uses_document_date_and_media_boundary(self) -> None:
        status = self.get_json("/api/toolchain")
        self.assertEqual("2026-08-24", status["updatedAt"])
        self.assertIn("Codex", status["routes"])
        self.assertIn("FLOVA_CONTROLLED_PILOT", status["routes"])


if __name__ == "__main__":
    unittest.main()
