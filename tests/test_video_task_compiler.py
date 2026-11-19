"""Proposal validation is distinct from authorization to submit generation."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(r"G:\抖音视频")
sys.path.insert(0, str(ROOT / "src"))
from video_task_compiler import compile_package


class VideoTaskCompilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "workspace")
        self.source = Path(self.temp.name) / "prompt_package.json"
        self.data = {
            "video_id": "compiler-fixture", "media_kind": "VIDEO", "status": "WAITING_PROMPT_APPROVAL",
            "duration_seconds": 10, "aspect_ratio": "9:16", "output_mode": "VIDEO_MULTI_SHOT",
            "provider_target": "FLOVA", "provider_prompt": "A calm sea in natural light.",
            "shots": [{"shot_id": "S01", "start_s": 0, "end_s": 5}, {"shot_id": "S02", "start_s": 5, "end_s": 10}],
            "asset_roles": [],
        }

    def tearDown(self):
        self.temp.cleanup()

    def compile(self, data):
        self.source.write_text(json.dumps(data), encoding="utf-8")
        return compile_package(self.source)

    def test_valid_confirmation_is_never_execution_approval(self):
        for provider in ("FLOVA", "SEEDANCE_2_0", "MINIMAX_H3"):
            with self.subTest(provider=provider):
                result = self.compile({**self.data, "provider_target": provider})
                self.assertEqual("WAITING_GENERATION_APPROVAL", result["status"])
                self.assertEqual([], result["blockers"])
                preflight = result["preflight_confirmation"]
                for key in ("confirmed", "allows_project_creation", "allows_asset_upload", "allows_generation"):
                    self.assertIs(False, preflight[key])
                self.assertEqual([], result["external_actions_performed"])

    def test_all_providers_block_invalid_timeline_instead_of_silent_defaults(self):
        mutations = [
            ("empty", lambda d: d.update(shots=[])),
            ("non-list", lambda d: d.update(shots="invalid")),
            ("bad-shot", lambda d: d.update(shots=[None])),
            ("missing-total", lambda d: d.pop("duration_seconds")),
            ("zero-total", lambda d: d.update(duration_seconds=0)),
            ("negative-total", lambda d: d.update(duration_seconds=-5)),
            ("nan-total", lambda d: d.update(duration_seconds="NaN")),
            ("infinite-total", lambda d: d.update(duration_seconds="Infinity")),
            ("boolean-total", lambda d: d.update(duration_seconds=True)),
            ("short-total", lambda d: d.update(duration_seconds=9)),
            ("long-total", lambda d: d.update(duration_seconds=11)),
            ("negative-start", lambda d: d["shots"][0].update(start_s=-1)),
            ("missing-start", lambda d: d["shots"][0].pop("start_s")),
            ("bad-start", lambda d: d["shots"][0].update(start_s="bad")),
            ("nonzero-first-start", lambda d: d["shots"][0].update(start_s=1)),
            ("gap", lambda d: d["shots"][1].update(start_s=6)),
            ("overlap", lambda d: d["shots"][1].update(start_s=4)),
            ("zero-shot-duration", lambda d: d["shots"][1].update(end_s=5)),
            ("negative-shot-duration", lambda d: d["shots"][1].update(end_s=4)),
            ("infinite-end", lambda d: d["shots"][1].update(end_s="Infinity")),
            ("incorrect-declared-shot-duration", lambda d: d["shots"][1].update(duration_seconds=6)),
            ("single-shot-has-two", lambda d: d.update(output_mode="VIDEO_SINGLE_SHOT")),
        ]
        for provider in ("FLOVA", "SEEDANCE_2_0", "MINIMAX_H3"):
            for label, mutate in mutations:
                with self.subTest(provider=provider, invalid=label):
                    data = copy.deepcopy(self.data)
                    data["provider_target"] = provider
                    mutate(data)
                    result = self.compile(data)
                    self.assertEqual("BLOCKED", result["status"])
                    self.assertTrue(result["blockers"])
                    self.assertIs(False, result["preflight_confirmation"]["allows_generation"])

    def test_approval_cannot_be_injected_through_source(self):
        data = {**self.data, "preflight_confirmation": {"confirmed": True, "allows_generation": True}, "approved": True}
        result = self.compile(data)
        self.assertIs(False, result["preflight_confirmation"]["confirmed"])
        for status in ("APPROVED", "GENERATING", "SUCCEEDED", ""):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.compile({**self.data, "status": status})

    def test_flova_model_duration_limit_still_applies(self):
        self.data.update(duration_seconds=2, output_mode="VIDEO_SINGLE_SHOT", shots=[{"start_s": 0, "end_s": 2}])
        self.assertEqual("BLOCKED", self.compile(self.data)["status"])


if __name__ == "__main__":
    unittest.main()
