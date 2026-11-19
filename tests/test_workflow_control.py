from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "src" / "workflow_control.py"
SPEC = importlib.util.spec_from_file_location("workflow_control", MODULE_PATH)
workflow = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(workflow)


class WorkflowControlTests(unittest.TestCase):
    def test_state_machine_disallows_skipping(self) -> None:
        self.assertNotIn("PUBLISHED", workflow.TRANSITIONS["RESEARCHING"])
        self.assertIn("RESEARCHED", workflow.TRANSITIONS["RESEARCHING"])

    def test_research_gate_blocks_small_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research").mkdir()
            with (root / "research" / "douyin_sample_snapshot_2026-08-17.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=["sample_group", "id", "likes", "title", "creator"])
                writer.writeheader()
                writer.writerow({"sample_group": "知识", "id": "1", "likes": "100", "title": "x", "creator": "a"})
            with (root / "research" / "reference_videos.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted(workflow.REQUIRED_DEEP_FIELDS))
                writer.writeheader()
            with (root / "research" / "contrast_pairs.csv").open("w", encoding="utf-8", newline="") as handle:
                handle.write("pair_id,topic\n")
            _, errors = workflow.research_audit(root)
            self.assertTrue(any("目录样本不足" in error for error in errors))
            self.assertTrue(any("深看样本不足" in error for error in errors))

    def test_metrics_checkpoint_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "metrics_log.csv").write_text(
                "video_id,checkpoint\nv1,24h\n", encoding="utf-8"
            )
            self.assertTrue(workflow.metrics_has_checkpoint(root, "v1", "24h"))
            self.assertFalse(workflow.metrics_has_checkpoint(root, "v1", "72h"))


if __name__ == "__main__":
    unittest.main()
