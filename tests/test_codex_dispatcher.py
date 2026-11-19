from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(r"G:\抖音视频")
SPEC = importlib.util.spec_from_file_location("codex_dispatcher_test", PROJECT_ROOT / "src" / "codex_dispatcher.py")
DISPATCHER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(DISPATCHER)


class CodexDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace")
        self.root = Path(self.temp.name)
        self.video_id = "dispatcher-fixture"
        self.project = self.root / "content" / self.video_id
        (self.project / "production").mkdir(parents=True)
        (self.project / "approvals").mkdir(parents=True)
        self.store = self.root / "data" / "codex_dispatch_queue.json"
        self.brief = self.project / "brief.md"
        self.brief.write_text("# 已批准 Brief\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_plan(self, route: str = "IMAGE_CAROUSEL", status: str = "READY_FOR_CODEX") -> Path:
        path = self.project / "production" / "skill_plan.json"
        path.write_text(json.dumps({
            "schema_version": "1.0",
            "video_id": self.video_id,
            "route": route,
            "status": status,
            "missing_required_skills": [] if status == "READY_FOR_CODEX" else ["fixture-skill"],
        }, ensure_ascii=False), encoding="utf-8")
        return path

    def approve_brief(self, *, lock_hash: bool = True) -> None:
        payload = {"approved": True, "approved_by": "user", "recorded_at": "2026-08-23T12:00:00+08:00"}
        if lock_hash:
            digest = hashlib.sha256(self.brief.read_bytes()).hexdigest()
            payload["approved_artifacts"] = [{
                "path": f"content/{self.video_id}/brief.md",
                "sha256": digest,
            }]
        (self.project / "approvals" / "brief_approval.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def enqueue(self, plan: Path | None = None) -> dict:
        return DISPATCHER.enqueue_plan(
            self.video_id,
            plan or self.write_plan(),
            root=self.root,
            store=self.store,
        )

    def test_same_plan_is_idempotent_and_claims_only_once(self) -> None:
        self.approve_brief()
        plan = self.write_plan()
        first = self.enqueue(plan)
        second = self.enqueue(plan)
        self.assertEqual("READY", first["state"])
        self.assertEqual(first["dispatch_id"], second["dispatch_id"])
        claimed = DISPATCHER.claim("worker-a", store=self.store)
        self.assertEqual(first["dispatch_id"], claimed["dispatch_id"])
        self.assertIsNone(DISPATCHER.claim("worker-b", store=self.store))

    def test_image_waits_when_brief_is_unapproved_or_changed(self) -> None:
        waiting = self.enqueue()
        self.assertEqual("WAITING_APPROVAL", waiting["state"])
        self.assertIn("Brief", waiting["reason"])

        self.approve_brief()
        self.brief.write_text("# 批准后被修改\n", encoding="utf-8")
        changed_plan = self.write_plan()
        changed_plan.write_text(changed_plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        changed = self.enqueue(changed_plan)
        self.assertEqual("WAITING_APPROVAL", changed["state"])
        self.assertIn("重新确认", changed["reason"])

    def test_video_routes_never_enter_ready_queue(self) -> None:
        self.approve_brief()
        item = self.enqueue(self.write_plan(route="ATMOSPHERE_VIDEO"))
        self.assertEqual("WAITING_APPROVAL", item["state"])
        self.assertIn("Seedance", item["reason"])

    def test_stale_lease_is_requeued(self) -> None:
        self.approve_brief()
        item = self.enqueue()
        claimed = DISPATCHER.claim("worker-a", store=self.store)
        data = json.loads(self.store.read_text(encoding="utf-8"))
        data["items"][0]["lease_expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        self.store.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        reclaimed = DISPATCHER.claim("worker-b", store=self.store)
        self.assertEqual(item["dispatch_id"], reclaimed["dispatch_id"])
        self.assertEqual("worker-b", reclaimed["worker_id"])
        self.assertEqual(2, reclaimed["attempts"])
        self.assertEqual(claimed["dispatch_id"], reclaimed["dispatch_id"])

    def test_completion_requires_owner_and_project_artifact(self) -> None:
        self.approve_brief()
        item = self.enqueue()
        DISPATCHER.claim("worker-a", store=self.store)
        artifact = self.project / "production" / "result.json"
        artifact.write_text("{}", encoding="utf-8")
        with self.assertRaises(PermissionError):
            DISPATCHER.complete(item["dispatch_id"], "worker-b", [str(artifact)], root=self.root, store=self.store)
        outside = self.root / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            DISPATCHER.complete(item["dispatch_id"], "worker-a", [str(outside)], root=self.root, store=self.store)
        completed = DISPATCHER.complete(item["dispatch_id"], "worker-a", [str(artifact)], root=self.root, store=self.store)
        self.assertEqual("COMPLETED", completed["state"])
        plan = json.loads((self.project / "production" / "skill_plan.json").read_text(encoding="utf-8"))
        self.assertEqual("CODEX_COMPLETED", plan["execution_status"])


if __name__ == "__main__":
    unittest.main()
