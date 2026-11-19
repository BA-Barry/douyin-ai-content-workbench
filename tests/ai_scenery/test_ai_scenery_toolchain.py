from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ai_scenery.generation_job_validator import validate  # noqa: E402


class AISceneryToolchainTests(unittest.TestCase):
    def test_installed_skills_have_entrypoints(self) -> None:
        for name in ("visual-style", "flux-best-practices", "baoyu-image-gen"):
            self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file(), name)

    def test_blocked_native_job_has_valid_contract(self) -> None:
        job_path = ROOT / "workspace" / "ai_scenery_toolchain_20260818" / "generation_job_blocked.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        result = validate(job)
        self.assertEqual("PASS", result["status"])
        self.assertEqual("BLOCKED", result["job_status"])

    def test_paid_api_requires_budget_approval(self) -> None:
        job_path = ROOT / "workspace" / "ai_scenery_toolchain_20260818" / "generation_job_blocked.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        job["provider_mode"] = "PAID_API"
        result = validate(job)
        self.assertEqual("FAIL", result["status"])
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("MISSING_PATH", codes)

    def test_smoke_media_checks_pass(self) -> None:
        results = ROOT / "workspace" / "ai_scenery_toolchain_20260818" / "results"
        for filename in ("image_qa.json", "motion_qa.json", "motion_qa_1080x1920.json"):
            payload = json.loads((results / filename).read_text(encoding="utf-8"))
            self.assertEqual("PASS", payload["status"], filename)

    def test_depthflow_cache_override_resolves_to_g_drive(self) -> None:
        python = ROOT / "envs" / "ai_scenery_motion" / "Scripts" / "python.exe"
        expected = ROOT / "cache" / "ai_scenery_motion" / "depthflow-test"
        env = os.environ.copy()
        env["DEPTHFLOW_CACHE_DIR"] = str(expected)
        env["PYTHONUTF8"] = "1"
        output = subprocess.check_output(
            [str(python), "-c", "import depthflow; print(depthflow.dirs.user_cache_path)"],
            env=env,
            text=True,
            encoding="utf-8",
        ).strip()
        self.assertEqual(expected.resolve(), Path(output).resolve())


if __name__ == "__main__":
    unittest.main()
