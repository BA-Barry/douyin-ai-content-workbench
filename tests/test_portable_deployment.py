"""Exercise a new checkout without the maintainer's runtime or account data."""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_runtime import find_tool, venv_python


class PortableCheckoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "workspace").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="portable_", dir=ROOT / "workspace")
        cls.checkout = Path(cls.temp.name) / "中文 project with spaces"
        cls.checkout.mkdir()
        for name in ("src", "workbench", "config", "examples", "workflow", "skills"):
            shutil.copytree(ROOT / name, cls.checkout / name, ignore=shutil.ignore_patterns("__pycache__", "offline"))
        shutil.copy2(ROOT / "manage.py", cls.checkout / "manage.py")
        cls.env = {key: value for key, value in os.environ.items() if not key.startswith("DOUYIN_")}
        cls.env["PYTHONUTF8"] = "1"
        cls.process = None
        cls.call("init", "--venv")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            cls.port = probe.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.process = subprocess.Popen([sys.executable, str(cls.checkout / "manage.py"), "serve", "--offline", "--port", str(cls.port)],
                                       cwd=cls.temp.name, env=cls.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       start_new_session=(os.name != "nt"))
        for _ in range(100):
            try:
                with urlopen(cls.base + "/api/health", timeout=.3) as response:
                    if response.status == 200:
                        return
            except (URLError, TimeoutError, OSError):
                if cls.process.poll() is not None:
                    raise RuntimeError(cls.process.stderr.read().decode("utf-8", errors="replace"))
                time.sleep(.05)
        cls.process.terminate()
        cls.process.wait(timeout=10)
        raise RuntimeError("Fresh checkout did not become healthy")

    @classmethod
    def call(cls, *args):
        return subprocess.run([sys.executable, str(cls.checkout / "manage.py"), *args],
                              cwd=cls.temp.name, env=cls.env, check=True, capture_output=True, text=True, encoding="utf-8", timeout=60)

    @classmethod
    def tearDownClass(cls):
        if cls.process:
            # Windows venv redirects and manage.py both spawn child processes.
            # Stop only this test's known process tree before cleaning its venv.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(cls.process.pid), "/T", "/F"], capture_output=True, check=False)
            else:
                os.killpg(cls.process.pid, signal.SIGTERM)
            cls.process.wait(timeout=10)
            cls.process.stderr.close()
        cls.temp.cleanup()

    def test_fresh_venv_and_diagnostics_use_the_new_checkout(self):
        doctor = json.loads(self.call("doctor").stdout)
        self.assertEqual(self.checkout.resolve(), Path(doctor["root"]))
        self.assertEqual(venv_python(self.checkout / ".venv"), Path(doctor["python"]))
        self.assertEqual(self.checkout / "skills", Path(doctor["skills"]))
        self.assertTrue(doctor["data_initialized"])

    def test_loopback_service_uses_fresh_empty_data_and_real_static_assets(self):
        for endpoint in ("/", "/app.js", "/api/health", "/api/accounts", "/api/projects?all=1", "/api/actions", "/api/skills"):
            with urlopen(self.base + endpoint, timeout=5) as response:
                body = response.read()
                self.assertEqual(200, response.status, endpoint)
                if endpoint == "/api/health":
                    data = json.loads(body)
                    self.assertEqual(self.checkout.resolve(), Path(data["root"]))
                    self.assertEqual("offline", data["mode"])
                if endpoint == "/api/projects?all=1":
                    self.assertEqual([], json.loads(body))
        self.assertFalse((self.checkout / "envs/content").exists())

    def test_init_preserves_existing_data_and_supports_root_override(self):
        path = self.checkout / "data/workbench_drafts.json"
        path.write_text('{"sentinel":"keep"}', encoding="utf-8")
        self.call("init")
        self.assertEqual({"sentinel": "keep"}, json.loads(path.read_text(encoding="utf-8")))
        env = dict(self.env, DOUYIN_PROJECT_ROOT=str(self.checkout))
        result = subprocess.run([sys.executable, str(ROOT / "manage.py"), "doctor"], env=env,
                                capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(str(self.checkout.resolve()), json.loads(result.stdout)["root"])

    def test_project_creation_and_production_request_stay_in_fresh_checkout(self):
        def post(endpoint, data):
            request = Request(self.base + endpoint, data=json.dumps(data).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read())
        post("/api/projects/create", {"videoId": "portable-example", "title": "雨后海岸", "hypothesis": "测试本地制作要求保存", "pillar": "测试", "contentType": "IMAGE_CAROUSEL", "accountId": "demo-sandbox"})
        job = post("/api/jobs/create", {"actionId": "SAVE_PRODUCTION_REQUEST", "videoId": "portable-example", "parameters": {"prompt": "自然雨后海岸，无人物无文字", "image_count": 1, "voice_mode": "none", "music_mode": "none"}})
        post(f"/api/jobs/{job['job_id']}/run", {})
        for _ in range(100):
            with urlopen(self.base + f"/api/jobs/{job['job_id']}", timeout=5) as response:
                result = json.loads(response.read())
            if result["status"] not in {"QUEUED", "RUNNING"}:
                break
            time.sleep(.05)
        self.assertEqual("SUCCEEDED", result["status"], result)
        production = self.checkout / "content/portable-example/production"
        self.assertTrue((production / "workbench_request.json").is_file())
        plan = json.loads((production / "skill_plan.json").read_text(encoding="utf-8"))
        self.assertEqual("READY_FOR_CODEX", plan["status"])
        self.assertEqual([], plan["missing_required_skills"])
        receipt = json.loads((production / "dispatch_receipt.json").read_text(encoding="utf-8"))
        self.assertEqual("WAITING_APPROVAL", receipt["state"])


class ToolDiscoveryTests(unittest.TestCase):
    def test_explicit_missing_tool_is_not_replaced_by_an_unrelated_system_tool(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"PROJECT_FFMPEG_EXE": str(ROOT / "workspace/missing-ffmpeg")}):
            self.assertIsNone(find_tool("ffmpeg", ROOT))
