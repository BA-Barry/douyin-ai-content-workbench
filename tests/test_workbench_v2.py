from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(r"G:\抖音视频")
SPEC = importlib.util.spec_from_file_location("douyin_workbench", ROOT / "workbench" / "server.py")
WORKBENCH = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(WORKBENCH)


class WorkbenchV2Tests(unittest.TestCase):
    def test_offline_contract_has_explicit_local_and_online_boundaries(self) -> None:
        status = WORKBENCH.offline_status()
        self.assertTrue(status["offlineReady"])
        self.assertGreaterEqual(len(status["localModules"]), 5)
        self.assertGreaterEqual(len(status["onlineModules"]), 4)
        self.assertTrue(all("reason" in item and "guard" in item for item in status["onlineModules"]))

    def test_every_project_exposes_all_workflow_stages(self) -> None:
        registry = WORKBENCH.read_csv(ROOT / "data" / "content_registry.csv")
        self.assertTrue(registry)
        for row in registry:
            progress = WORKBENCH.project_stage_progress(row)
            self.assertEqual(18, progress["total"])
            self.assertEqual(18, len(progress["stages"]))
            self.assertTrue(all(stage["status"] in {"complete", "evidence_gap", "ready", "waiting_user", "pending"} for stage in progress["stages"]))

    def test_offline_snapshot_has_no_network_runtime(self) -> None:
        output = WORKBENCH.build_offline_snapshot_html()
        lower = output.lower()
        self.assertIn("offline snapshot", lower)
        self.assertNotIn("fetch(", lower)
        self.assertNotIn("xmlhttprequest", lower)
        self.assertNotIn("http://", lower)
        self.assertNotIn("https://", lower)
        self.assertNotIn("<script src=", lower)

    def test_shortlist_rejects_unsafe_candidate_id_before_writing(self) -> None:
        with self.assertRaises(ValueError):
            WORKBENCH.save_shortlist_item({"candidateId": "../bad candidate", "title": "bad"})


if __name__ == "__main__":
    unittest.main()
