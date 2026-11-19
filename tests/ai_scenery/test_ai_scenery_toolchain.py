from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("scenery_validator_under_test", ROOT / "src/ai_scenery/generation_job_validator.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class AISceneryToolchainTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "workspace").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.root = Path(self.temp.name)
        prompt = self.root / "prompt.txt"
        prompt.write_text("Original synthetic scenery test", encoding="utf-8")
        self.job = {
            "schema_version": "1.0", "job_id": "synthetic", "series_id": "test",
            "provider": "codex", "provider_mode": "NATIVE_TOOL", "model": "native",
            "model_version": "test", "model_license_id": "test-fixture",
            "prompt_path": str(prompt), "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            "aspect_ratio": "9:16", "output_path": str(self.root / "output.jpg"),
            "human_review": "PENDING", "status": "BLOCKED", "ai_label_required": True,
            "reference_assets": [],
        }
        self.patch = patch.object(validator, "PROJECT_ROOT", self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_bundled_project_skills_have_entrypoints(self):
        for name in ("ai-scenery-studio", "douyin-prompt-director", "douyin-media-orchestrator", "douyin-wallpaper-export"):
            self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file(), name)

    def test_blocked_job_does_not_require_an_existing_generated_output(self):
        result = validator.validate(self.job)
        self.assertEqual("PASS", result["status"])
        self.assertEqual("BLOCKED", result["job_status"])

    def test_paid_api_requires_budget_approval(self):
        self.job["provider_mode"] = "PAID_API"
        result = validator.validate(self.job)
        self.assertIn("MISSING_PATH", {item["code"] for item in result["errors"]})

    def test_generated_job_requires_real_output(self):
        self.job["status"] = "GENERATED"
        result = validator.validate(self.job)
        self.assertIn("GENERATED_OUTPUT_NOT_FOUND", {item["code"] for item in result["errors"]})

    def test_project_boundary_uses_configured_root_and_rejects_outside_paths(self):
        self.job["output_path"] = str(self.root.parent / "outside.jpg")
        result = validator.validate(self.job)
        self.assertIn("PATH_OUTSIDE_PROJECT", {item["code"] for item in result["errors"]})


if __name__ == "__main__":
    unittest.main()
