"""Provider responses are simulated; final media validation uses real local FFmpeg."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(r"G:\抖音视频")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "workbench"))
import flova_runtime as runtime
import task_runner as runner


def envelope(data=None, code=0, **extra):
    return {"code": code, "message": "mock provider result", "data": data or {}, **extra}


PENDING = {"action_id": "a-1", "type": "batch_task_limit", "blocking": True,
           "message": "Confirm credits", "resume_message_id": "m-1", "payload": {"credits": 5},
           "options": [{"id": "confirm", "effect": "resume", "label": "Confirm"},
                       {"id": "cancel", "effect": "none", "label": "Cancel"}]}


class FlovaRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        cls.video = Path(cls.media_temp.name) / "synthetic-test-fixture.mp4"
        cls.short_video = Path(cls.media_temp.name) / "synthetic-short-fixture.mp4"
        cls.wide_video = Path(cls.media_temp.name) / "synthetic-wide-fixture.mp4"
        ffmpeg = next((ROOT / "tools/ffmpeg/current").rglob("ffmpeg.exe"))
        for target, size, duration in ((cls.video, "108x192", "5"), (cls.short_video, "108x192", "1"), (cls.wide_video, "192x108", "5")):
            result = subprocess.run([str(ffmpeg), "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=12",
                                     "-t", duration, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode: raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.media_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.root = Path(self.temp.name)
        (self.root / "content/pilot/production").mkdir(parents=True)
        self.task = {"status": "WAITING_GENERATION_APPROVAL", "provider_target": "FLOVA", "blockers": [],
                     "generation_spec": {"model_proposal": "Seedance 2.5", "aspect_ratio": "9:16", "total_duration_seconds": 5, "resolution": "720p"},
                     "references": [], "private_skill": {"skill_id": "private-skill"}, "shots": [{"flova_prompt": "Quiet coastline"}],
                     "negative_constraints": ["no people"]}
        self.parameters = {"generation_ack": True, "model": "Seedance 2.5", "budget_mode": "INCLUDED_ONLY", "max_credits": 10}
        self.job = {"job_id": "wb-fixture", "video_id": "pilot", "status": "RUNNING", "action_id": "GENERATE_FLOVA_VIDEO",
                    "parameters": dict(self.parameters), "confirmation": copy.deepcopy(self.task), "publish_clicked": False}
        self.commands = []
        self.saved = []
        self.current_pending = copy.deepcopy(PENDING)
        self.run_reply = envelope({"project_id": "p-1", "stream_chat_id": "s-1", "status": "completed", "terminal": True, "pending_actions": []})
        self.export_reply = envelope({"task_id": "e-1", "status": "completed", "terminal": True, "export_url": "https://cdn.example.test/final.mp4?secret=signed"})
        self.account = {"authenticated": True, "credits_balance": 100, "message": "mock included quota"}
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(runtime, "confirmation", return_value=self.task))
        self.account_api = self.stack.enter_context(patch.object(runtime, "account_status", side_effect=lambda _: self.account))
        self.cli = self.stack.enter_context(patch.object(runtime, "cli", side_effect=self.fake_cli))
        self.download = self.stack.enter_context(patch.object(runtime, "download_video", side_effect=lambda url, dest: shutil.copyfile(self.video, dest)))
        self.probe = self.stack.enter_context(patch.object(runtime, "probe_video", side_effect=lambda path, _: self.real_probe(path, ROOT)))

    real_probe = staticmethod(runtime.probe_video)

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def fake_cli(self, args, **kwargs):
        self.commands.append(args)
        command = args[:2]
        if command == ["project", "create"]: return envelope({"project_id": "p-1", "project_url": "https://www.flova.ai/project/?id=p-1"})
        if command == ["chat", "pending-actions"]: return envelope({"pending_actions": [copy.deepcopy(self.current_pending)]})
        if args[0] == "upload": return envelope({"file_id": "file-1"})
        if args[0] == "run":
            event = kwargs.get("on_event")
            if event: event({"type": "handle", "stream_chat_id": "s-1"})
            return copy.deepcopy(self.run_reply)
        if command == ["export", "readiness"]: return envelope({"can_export": True})
        if args[0] == "export": return copy.deepcopy(self.export_reply)
        raise AssertionError(f"unexpected command {args}")

    def execute(self, **kwargs):
        runtime.execute(self.job, root=self.root, persist=lambda item: self.saved.append(copy.deepcopy(item)), **kwargs)

    def test_normal_flow_requires_local_nonempty_video_and_real_media_probe(self):
        self.execute()
        self.assertEqual("SUCCEEDED", self.job["status"])
        self.assertEqual(["project", "run", "export", "export"], [c[0] for c in self.commands])
        self.assertEqual("s-1", self.job["provider"]["stream_chat_id"])
        self.assertEqual("e-1", self.job["provider"]["export_task_id"])
        self.assertEqual(2, len(self.job["artifacts"]))
        self.assertTrue((self.root / self.job["artifacts"][0]).stat().st_size > 0)
        report = json.loads((self.root / self.job["artifacts"][1]).read_text(encoding="utf-8"))
        self.assertEqual("PASS", report["status"])
        self.assertEqual(108, report["media"]["video"]["width"])
        self.assertIsNone(self.job["progress"]["percentage"])
        self.assertNotIn("signed", json.dumps(self.saved))
        self.assertFalse(self.job["publish_clicked"])

    def test_zero_or_unknown_quota_never_creates_remote_project(self):
        for balance in (0, None):
            with self.subTest(balance=balance):
                self.account["credits_balance"] = balance
                self.execute()
                self.assertEqual("BLOCKED", self.job["status"])
        self.cli.assert_not_called(); self.download.assert_not_called()

    def test_unapproved_request_never_calls_remote(self):
        self.job["parameters"]["generation_ack"] = False
        self.execute()
        self.assertEqual("BLOCKED", self.job["status"])
        self.cli.assert_not_called()

    def test_waiting_prompt_status_alone_does_not_allow_generation(self):
        self.task["status"] = "WAITING_PROMPT_APPROVAL"
        self.execute()
        self.assertEqual("BLOCKED", self.job["status"])
        self.cli.assert_not_called()

    def test_blocking_pending_action_stops_before_export_and_keeps_exact_options(self):
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(PENDING)]
        self.execute()
        self.assertEqual("WAITING_USER", self.job["status"])
        self.assertEqual("a-1", self.job["pending_actions"][0]["action_id"])
        self.assertEqual(["confirm", "cancel"], [o["id"] for o in self.job["pending_actions"][0]["options"]])
        self.assertFalse(any(c[0] == "export" for c in self.commands))
        self.download.assert_not_called()

    def test_resume_uses_exact_ids_and_never_resends_creative_content(self):
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(PENDING)]
        self.execute(); self.commands.clear(); self.saved.clear(); self.run_reply["data"]["pending_actions"] = []
        self.job["status"] = "RUNNING"
        self.execute(recover=True, resolution={"action_id": "a-1", "option_id": "confirm"})
        self.assertEqual("SUCCEEDED", self.job["status"])
        resume = next(c for c in self.commands if c[:2] == ["run", "resume"])
        self.assertEqual(["run", "resume", "p-1", "--message-id", "m-1", "--action-id", "a-1", "--option", "confirm", "--timeout", "900"], resume)
        self.assertFalse(any("--content" in c for c in self.commands))
        self.assertFalse(any(c[:2] == ["project", "create"] for c in self.commands))
        self.assertNotIn("WAITING_USER", [record["status"] for record in self.saved])

    def test_pending_refresh_cannot_reopen_duplicate_resume_submission(self):
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(PENDING)]
        self.execute()
        self.run_reply["data"]["pending_actions"] = []
        with ExitStack() as patches:
            for name, value in (("ROOT", self.root), ("JOB_STORE", self.root / "data/jobs.json"), ("JOB_OUTPUT", self.root / "workspace/jobs"), ("OFFLINE_MODE", False)):
                patches.enter_context(patch.object(runner, name, value))
            submitted = patches.enter_context(patch.object(runner._EXECUTOR, "submit"))
            runner._replace_job(self.job)
            decision = {"action_id": "a-1", "option_id": "confirm"}
            active = runner.resolve_job(self.job["job_id"], decision)
            self.assertEqual("RUNNING", active["status"])
            def persist_and_simulate_second_click(item):
                runner._replace_job(item)
                # A stale browser may resend while the same operation is in flight.
                if item["status"] == "WAITING_USER":
                    runner.resolve_job(item["job_id"], decision)
            runtime.execute(active, root=self.root, persist=persist_and_simulate_second_click, recover=True, resolution=decision)
            self.assertEqual("SUCCEEDED", active["status"])
            submitted.assert_called_once()

    def test_pending_payload_changed_requires_new_choice(self):
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(PENDING)]
        self.execute(); self.commands.clear()
        self.job["pending_actions"][0]["payload"]["credits"] = 1
        self.execute(recover=True, resolution={"action_id": "a-1", "option_id": "confirm"})
        self.assertEqual("WAITING_USER", self.job["status"])
        self.assertEqual([["chat", "pending-actions", "p-1"]], self.commands)

    def test_cancel_pending_action_does_not_send_resume(self):
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(PENDING)]
        self.execute(); self.commands.clear(); self.account_api.reset_mock()
        self.execute(recover=True, resolution={"action_id": "a-1", "option_id": "cancel"})
        self.assertEqual("WAITING_USER", self.job["status"])
        self.assertFalse(any(c[0] == "run" for c in self.commands))
        self.account_api.assert_not_called()

    def test_resume_rechecks_account_and_retains_pending_when_balance_is_insufficient(self):
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(PENDING)]
        self.execute(); self.run_reply["data"]["pending_actions"] = []
        for balance in (0, None, 5):
            with self.subTest(balance=balance):
                self.commands.clear(); self.account["credits_balance"] = balance; self.job["status"] = "RUNNING"
                self.execute(recover=True, resolution={"action_id": "a-1", "option_id": "confirm"})
                self.assertEqual("WAITING_USER", self.job["status"])
                self.assertEqual("p-1", self.job["provider"]["project_id"])
                self.assertEqual("a-1", self.job["pending_actions"][0]["action_id"])
                self.assertFalse(any(c[0] in {"run", "export"} for c in self.commands))

    def test_resume_does_not_exceed_approved_cost_from_current_pending_payload(self):
        self.current_pending["payload"]["credits"] = 15
        self.run_reply["data"]["pending_actions"] = [copy.deepcopy(self.current_pending)]
        self.execute(); self.commands.clear(); self.run_reply["data"]["pending_actions"] = []
        self.execute(recover=True, resolution={"action_id": "a-1", "option_id": "confirm"})
        self.assertEqual("WAITING_USER", self.job["status"])
        self.assertFalse(any(c[0] in {"run", "export"} for c in self.commands))

    def test_run_recovery_uses_saved_handle_without_duplicate_create_or_run(self):
        self.job.update(provider={"name": "FLOVA", "project_id": "p-1", "stream_chat_id": "s-1"}, runtime={"stage": "run"})
        self.execute(recover=True)
        self.assertEqual("SUCCEEDED", self.job["status"])
        self.assertEqual(["run", "status", "p-1", "--stream-chat-id", "s-1"], self.commands[0])
        self.assertEqual(["run", "result", "p-1", "--stream-chat-id", "s-1"], self.commands[1])
        self.assertFalse(any("--content" in c or c[:2] == ["project", "create"] for c in self.commands))

    def test_live_cli_owner_prevents_second_backend_observer(self):
        self.job.update(provider={"project_id": "p-1"}, runtime={"stage": "run", "cli_pid": 1234})
        with patch.object(runtime, "_pid_alive", return_value=True): self.execute(recover=True)
        self.assertEqual("RECOVERABLE", self.job["status"])
        self.cli.assert_not_called()

    def test_recovery_with_no_project_handle_does_not_recreate(self):
        self.job.update(runtime={"stage": "create"})
        self.execute(recover=True)
        self.assertEqual("RECOVERABLE", self.job["status"])
        self.cli.assert_not_called()

    def test_export_failure_and_missing_url_are_not_success(self):
        for reply in (envelope({"task_id": "e-1", "status": "failed", "terminal": True}),
                      envelope({"task_id": "e-1", "status": "completed", "terminal": True})):
            with self.subTest(reply=reply):
                self.export_reply = reply; self.job.pop("runtime", None)
                self.execute()
                self.assertIn(self.job["status"], {"FAILED", "RECOVERABLE"})
        self.download.assert_not_called()

    def test_export_recovery_uses_saved_task_without_reexporting(self):
        self.job.update(provider={"name": "FLOVA", "project_id": "p-1", "export_task_id": "e-1"}, runtime={"stage": "export", "creative_succeeded": True})
        self.execute(recover=True)
        self.assertEqual("SUCCEEDED", self.job["status"])
        self.assertEqual([["export", "status", "p-1", "--task-id", "e-1"]], self.commands)

    def test_unknown_export_handle_does_not_accept_old_export(self):
        self.job.update(provider={"name": "FLOVA", "project_id": "p-1"}, runtime={"stage": "export", "creative_succeeded": True, "export_attempted_at": "2026-09-28T10:00:00+08:00"})
        self.export_reply["data"]["created_at"] = "2026-09-27T10:00:00+08:00"
        self.execute(recover=True)
        self.assertEqual("RECOVERABLE", self.job["status"])
        self.assertEqual([["export", "current", "p-1"]], self.commands)
        self.download.assert_not_called()

    def test_empty_download_is_not_success(self):
        self.download.side_effect = lambda url, dest: dest.write_bytes(b"")
        self.execute()
        self.assertNotEqual("SUCCEEDED", self.job["status"])
        self.probe.assert_not_called()

    def test_corrupt_download_fails_real_ffprobe(self):
        self.download.side_effect = lambda url, dest: dest.write_bytes(b"this is not a video")
        self.execute()
        self.assertNotEqual("SUCCEEDED", self.job["status"])
        self.assertIn("ffprobe", self.job.get("stderr", "").lower())

    def test_valid_video_with_wrong_duration_is_blocked_but_kept_for_review(self):
        self.download.side_effect = lambda url, dest: shutil.copyfile(self.short_video, dest)
        self.execute()
        self.assertEqual("BLOCKED", self.job["status"])
        self.assertTrue(self.job["media"])
        self.assertTrue(self.job["artifacts"])
        self.assertTrue((self.root / self.job["artifacts"][0]).stat().st_size > 0)

    def test_valid_video_with_wrong_aspect_ratio_is_blocked_but_kept_for_review(self):
        self.download.side_effect = lambda url, dest: shutil.copyfile(self.wide_video, dest)
        self.execute()
        self.assertEqual("BLOCKED", self.job["status"])
        self.assertTrue(self.job["media"])
        self.assertTrue(self.job["artifacts"])

    def test_reference_path_cannot_escape_g_project_root(self):
        self.task["references"] = [{"path_or_label": str(self.root.parent / "outside.mp4"), "rights_status": "user_owned", "role": "reference"}]
        self.job["confirmation"] = copy.deepcopy(self.task)
        self.job["parameters"]["reference_upload_ack"] = True
        self.execute()
        self.assertNotEqual("SUCCEEDED", self.job["status"])
        self.assertFalse(any(c[0] in {"run", "upload"} for c in self.commands))

    def test_provider_credit_error_is_blocked_without_export(self):
        self.run_reply = envelope(code="insufficient_credits")
        self.execute()
        self.assertEqual("BLOCKED", self.job["status"])
        self.assertFalse(any(c[0] == "export" for c in self.commands))


class FlovaApprovalTests(unittest.TestCase):
    def test_waiting_prompt_package_needs_explicit_current_brief_approval(self):
        from video_task_compiler import compile_package
        with tempfile.TemporaryDirectory(dir=ROOT / "workspace") as folder:
            root = Path(folder); base = root / "content/pilot"
            (root / "data").mkdir(); (base / "production").mkdir(parents=True); (base / "approvals").mkdir()
            (root / "data/content_registry.csv").write_text("video_id,content_type,state\npilot,ATMOSPHERE_VIDEO,IDEA\n", encoding="utf-8")
            source = base / "production/prompt_package.json"
            source.write_text(json.dumps({"video_id": "pilot", "media_kind": "VIDEO", "provider_target": "FLOVA", "status": "WAITING_PROMPT_APPROVAL",
                "duration_seconds": 5, "shots": [{"start_s": 0, "end_s": 5}], "asset_roles": []}), encoding="utf-8")
            (base / "production/video_task_package.json").write_text(json.dumps(compile_package(source)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Brief"):
                runtime.confirmation(root, "pilot")

    def test_empty_boolean_nonfinite_budget_or_model_mismatch_is_not_approval(self):
        task = {"generation_spec": {"model_proposal": "Seedance 2.5"}, "references": []}
        good = {"generation_ack": True, "budget_mode": "INCLUDED_ONLY", "model": "Seedance 2.5", "max_credits": 10}
        runtime.validate_approval(good, task)
        for key, value in (("max_credits", 0), ("max_credits", True), ("max_credits", float("nan")), ("max_credits", float("inf")),
                           ("generation_ack", "true"), ("budget_mode", "PAID"), ("model", "other")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): runtime.validate_approval({**good, key: value}, task)
        task["references"] = [{"id": "asset"}]
        with self.assertRaises(ValueError): runtime.validate_approval(good, task)

    def test_readonly_account_status_returns_no_credentials(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "workspace") as folder:
            root = Path(folder); exe = root / "envs/flova-cli/flova.exe"; exe.parent.mkdir(parents=True); exe.write_bytes(b"mock exe not run")
            responses = [envelope({"token_stored": True, "token": "PRIVATE"}), envelope({"credits_balance": 0,
                "subscription_info": {"name": "Free", "access_token": "PRIVATE", "unknown": "PRIVATE"}, "email": "PRIVATE"})]
            with patch.object(runtime, "cli", side_effect=responses) as cli:
                status = runtime.account_status(root)
            self.assertIs(True, status["authenticated"]); self.assertEqual(0, status["credits_balance"])
            self.assertNotIn("PRIVATE", json.dumps(status))
            self.assertEqual([["auth", "status"], ["account", "user"]], [call.args[0] for call in cli.call_args_list])


class FlovaJobDeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.root = Path(self.temp.name)
        (self.root / "content/pilot").mkdir(parents=True)
        self.stack = ExitStack()
        for name, value in (("ROOT", self.root), ("JOB_STORE", self.root / "data/jobs.json"), ("JOB_OUTPUT", self.root / "workspace/jobs"), ("OFFLINE_MODE", False)):
            self.stack.enter_context(patch.object(runner, name, value))
        self.stack.enter_context(patch.object(runner.flova_runtime, "confirmation", return_value={"generation_spec": {"model_proposal": "Seedance 2.5"}, "references": []}))
        self.submit = self.stack.enter_context(patch.object(runner._EXECUTOR, "submit"))
        self.payload = {"actionId": "GENERATE_FLOVA_VIDEO", "videoId": "pilot", "parameters": {
            "generation_ack": True, "model": "Seedance 2.5", "budget_mode": "INCLUDED_ONLY", "max_credits": 10}}

    def tearDown(self):
        self.stack.close(); self.temp.cleanup()

    def test_double_click_reuses_one_job_and_submits_once(self):
        first = runner.create_job(self.payload); second = runner.create_job(self.payload)
        self.assertEqual(first["job_id"], second["job_id"])
        runner.submit_job(first["job_id"]); runner.submit_job(second["job_id"])
        self.submit.assert_called_once()
        self.assertEqual(1, len(runner.list_jobs()))

    def test_restart_exposes_recoverable_task_and_never_resubmits(self):
        job = runner.create_job(self.payload); runner.submit_job(job["job_id"]); self.submit.reset_mock()
        self.assertEqual(1, runner.recover_interrupted_jobs())
        self.assertEqual("RECOVERABLE", runner.get_job(job["job_id"])["status"])
        self.submit.assert_not_called()
        runner.recover_job(job["job_id"]); runner.recover_job(job["job_id"])
        self.submit.assert_called_once()
        self.assertIs(True, self.submit.call_args.kwargs["recover"])

    def test_offline_rejects_create_run_and_recover(self):
        job = runner.create_job(self.payload)
        with patch.object(runner, "OFFLINE_MODE", True):
            for operation in (lambda: runner.create_job(self.payload), lambda: runner.submit_job(job["job_id"]), lambda: runner.recover_job(job["job_id"])):
                with self.assertRaises(ValueError): operation()
        self.submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
