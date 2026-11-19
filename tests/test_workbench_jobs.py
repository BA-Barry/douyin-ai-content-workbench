from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(r"G:\抖音视频")
SPEC = importlib.util.spec_from_file_location("workbench_task_runner", PROJECT_ROOT / "workbench" / "task_runner.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class WorkbenchJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace")
        self.root = Path(self.temp.name)
        self.video_id = "fixture-video-01"
        (self.root / "content" / self.video_id / "production").mkdir(parents=True)
        (self.root / "content" / self.video_id / "approvals").mkdir(parents=True)
        self.originals = (RUNNER.ROOT, RUNNER.JOB_STORE, RUNNER.JOB_OUTPUT)
        RUNNER.ROOT = self.root
        RUNNER.JOB_STORE = self.root / "data" / "workbench_jobs.json"
        RUNNER.JOB_OUTPUT = self.root / "workspace" / "workbench" / "jobs"

    def tearDown(self) -> None:
        RUNNER.ROOT, RUNNER.JOB_STORE, RUNNER.JOB_OUTPUT = self.originals
        RUNNER.media_library.configure(PROJECT_ROOT)
        self.temp.cleanup()

    def test_unknown_action_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RUNNER.create_job({"actionId": "SHELL", "videoId": self.video_id, "parameters": {"command": "whoami"}})

    def test_production_request_is_a_real_auditable_artifact(self) -> None:
        job = RUNNER.create_job({
            "actionId": "SAVE_PRODUCTION_REQUEST",
            "videoId": self.video_id,
            "parameters": {
                "prompt": "复古拼贴、生活碎片、成年感",
                "image_count": 6,
                "duration_seconds": 20,
                "voice_mode": "none",
                "music_mode": "platform_manual",
            },
        })
        code, _, _, artifacts = RUNNER._execute_action(job)
        self.assertEqual(0, code)
        self.assertEqual([
            f"content/{self.video_id}/production/workbench_request.json",
            f"content/{self.video_id}/production/skill_plan.json",
            f"content/{self.video_id}/production/dispatch_receipt.json",
            f"content/{self.video_id}/production/asset_strategy.json",
            f"content/{self.video_id}/production/assets/asset_bindings.json",
        ], artifacts)
        request = json.loads((self.root / artifacts[0]).read_text(encoding="utf-8"))
        plan = json.loads((self.root / artifacts[1]).read_text(encoding="utf-8"))
        self.assertEqual("WAITING_APPROVAL", request["status"])
        self.assertFalse(request["external_action"])
        self.assertNotIn("visual_skill", request["route_parameters"])
        self.assertEqual("retro-scrapbook-collage", plan["selected_visual_skill"])
        self.assertEqual("READY_FOR_CODEX", plan["status"])
        self.assertEqual("IMAGEGEN", plan["provider_target"])
        self.assertEqual("NONE", plan["asset_strategy"]["asset_strategy"])
        self.assertIn("douyin-prompt-director", [step["skill"] for step in plan["steps"]])
        self.assertIn("imagegen", [step["skill"] for step in plan["steps"]])
        self.assertNotIn("text-to-speech", [step["skill"] for step in plan["steps"]])
        dispatch = json.loads((self.root / artifacts[2]).read_text(encoding="utf-8"))
        self.assertEqual("WAITING_APPROVAL", dispatch["state"])

    def test_video_plan_defaults_to_private_flova_motion_remotion_and_editor(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "ATMOSPHERE_VIDEO",
            "prompt": "海边黄昏，两个人有一句离别对白，需要字幕",
            "duration_seconds": 14,
            "voice_mode": "user-voice",
            "music_mode": "platform_manual",
        })
        skills = [step["skill"] for step in plan["steps"]]
        for expected in (
            "douyin-prompt-director", "flova", "hyperframes-motion-language", "remotion-best-practices",
            "remotion-create", "remotion-multimedia", "douyin-caption-pipeline",
            "remotion-studio", "remotion-render", "video-use",
        ):
            self.assertIn(expected, skills)
        self.assertNotIn("ai-scenery-studio", skills)
        self.assertFalse(any(skill.startswith("patent-") for skill in skills))
        self.assertEqual("READY_FOR_CODEX", plan["status"])
        self.assertEqual("FLOVA", plan["provider_target"])
        self.assertEqual("flova", plan["prompt_compiler"])
        self.assertEqual("1115fa6bc53344ed981a261a43aada82", plan["provider_skill"]["id"])

    def test_video_plan_preserves_explicit_seedance_route(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "ATMOSPHERE_VIDEO",
            "prompt": "明确使用即梦 Seedance 2.0 生成海边黄昏",
            "duration_seconds": 10,
            "voice_mode": "none",
        })
        self.assertEqual("SEEDANCE_2_0", plan["provider_target"])
        self.assertEqual("seedance-prompt-zh", plan["prompt_compiler"])
        self.assertEqual({}, plan["provider_skill"])

    def test_video_keyframe_strategy_inserts_codex_image_subtask(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "ATMOSPHERE_VIDEO",
            "prompt": "同一人物和服装保持一致",
            "_asset_decision": {
                "asset_strategy": "GENERATE_KEYFRAMES",
                "generation_mode": "FIRST_FRAME_TO_VIDEO",
                "requires_image_subtask": True,
                "bound_asset_ids": [],
            },
        })
        phases = [step["phase"] for step in plan["steps"]]
        self.assertIn("visual_anchor_generation", phases)
        self.assertIn("imagegen", [step["skill"] for step in plan["steps"]])
        self.assertIn("visual_anchor_and_reference_approval", plan["human_gates"])

    def test_video_plan_selects_official_h3_compiler_without_stacking_seedance(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "ATMOSPHERE_VIDEO",
            "prompt": "用 MiniMax H3 Ref2VA 做一段海边黄昏参考视频",
            "duration_seconds": 10,
            "voice_mode": "none",
        })
        skills = [step["skill"] for step in plan["steps"]]
        self.assertEqual("MINIMAX_H3", plan["provider_target"])
        self.assertEqual("h3-prompt-writing", plan["prompt_compiler"])
        self.assertIn("h3-prompt-writing", skills)
        self.assertNotIn("seedance-prompt-zh", skills)

    def test_cinematic_image_route_uses_frame_director_before_prompt_package(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "IMAGE_CAROUSEL",
            "prompt": "电影感雨夜，精确焦段和动机光，做六张竖屏壁纸",
            "image_count": 6,
        })
        phases = [step["phase"] for step in plan["steps"]]
        skills = [step["skill"] for step in plan["steps"]]
        self.assertIn("cinematic-director-frame", skills)
        self.assertLess(phases.index("cinematic_frame_direction"), phases.index("prompt_direction"))
        self.assertEqual("IMAGEGEN", plan["provider_target"])

    def test_negated_style_keywords_do_not_override_natural_scenery(self) -> None:
        for prompt in ("雨后海岸，自然治愈，不出现人物、文字、贴纸", "真实海岸摄影，不要胶片/诗歌"):
            with self.subTest(prompt=prompt):
                plan = RUNNER.build_skill_plan(self.root, self.video_id, {
                    "content_route": "IMAGE_CAROUSEL", "prompt": prompt, "image_count": 1,
                })
                self.assertNotIn(plan["selected_visual_skill"], {"retro-scrapbook-collage", "cinematic-memory-wallpaper"})

    def test_positive_visual_style_keywords_still_select_their_skills(self) -> None:
        for prompt, expected in (("复古拼贴，生活碎片", "retro-scrapbook-collage"), ("胶片感风景和应景英文诗歌", "cinematic-memory-wallpaper")):
            with self.subTest(prompt=prompt):
                plan = RUNNER.build_skill_plan(self.root, self.video_id, {
                    "content_route": "IMAGE_CAROUSEL", "prompt": prompt, "image_count": 1,
                })
                self.assertEqual(expected, plan["selected_visual_skill"])

    def test_single_shot_no_audio_video_omits_composition_and_caption_skills(self) -> None:
        (self.root / "content" / self.video_id / "brief.md").write_text(
            "# 雨后海岸\n单镜头 5 秒，没有人物、字幕、对白、音乐。\n"
            "## 旧模板字段\n- 字幕示例：此处填写。\n- 旁白策略：无。\n", encoding="utf-8")
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "ATMOSPHERE_VIDEO", "image_count": 1, "duration_seconds": 5,
            "prompt": "5秒单镜头，雨后的海岸，没有人物、字幕、对白、音乐。",
            "voice_mode": "none", "music_mode": "none",
        })
        skills = [step["skill"] for step in plan["steps"]]
        self.assertFalse(any(skill.startswith("remotion") for skill in skills))
        self.assertNotIn("douyin-caption-pipeline", skills)
        for required in ("douyin-prompt-director", "flova", "video-use"):
            self.assertIn(required, skills)

    def test_multi_shot_or_explicit_composition_still_selects_composition(self) -> None:
        for prompt, count in (("两个镜头：海岸到城市", 2), ("一个镜头但需要合成图层与片尾", 1), ("两个人站在海边，交替出现", 1)):
            with self.subTest(prompt=prompt):
                plan = RUNNER.build_skill_plan(self.root, self.video_id, {
                    "content_route": "ATMOSPHERE_VIDEO", "image_count": count, "duration_seconds": 10,
                    "prompt": prompt, "voice_mode": "none", "music_mode": "none",
                })
                self.assertIn("remotion-create", [step["skill"] for step in plan["steps"]])

    def test_explicit_caption_request_selects_caption_pipeline(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "ATMOSPHERE_VIDEO", "image_count": 1, "duration_seconds": 5,
            "prompt": "海岸风景，添加一句应景字幕：雨过天晴。", "voice_mode": "none", "music_mode": "none",
        })
        self.assertIn("douyin-caption-pipeline", [step["skill"] for step in plan["steps"]])

    def test_narrated_video_keeps_composition_even_for_one_shot(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "NARRATED_EXPLAINER", "image_count": 1, "duration_seconds": 5,
            "prompt": "一个知识点的解释", "voice_mode": "user-voice", "music_mode": "none",
        })
        skills = [step["skill"] for step in plan["steps"]]
        self.assertIn("remotion-create", skills)
        self.assertIn("douyin-caption-pipeline", skills)

    def test_narrated_plan_keeps_paid_voice_behind_human_gate(self) -> None:
        plan = RUNNER.build_skill_plan(self.root, self.video_id, {
            "content_route": "NARRATED_EXPLAINER",
            "prompt": "解释一个 AI 概念",
            "voice_mode": "sample-first",
        })
        voice = next(step for step in plan["steps"] if step["skill"] == "text-to-speech")
        self.assertEqual("api_key_cost_voice_rights_approved", voice["gate"])
        self.assertIn("api_key_cost_upload_and_rights_approval", plan["human_gates"])

    def test_media_path_cannot_escape_selected_project(self) -> None:
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"fixture")
        with self.assertRaises(ValueError):
            RUNNER.create_job({
                "actionId": "PROBE_MEDIA",
                "videoId": self.video_id,
                "parameters": {"media_path": str(outside)},
            })

    def test_video_task_confirmation_stops_at_generation_approval(self) -> None:
        prompt_package = {
            "schema_version": "1.0",
            "video_id": self.video_id,
            "media_kind": "VIDEO",
            "output_mode": "VIDEO_SINGLE_SHOT",
            "aspect_ratio": "9:16",
            "duration_seconds": 8,
            "creative_intent": "雨后海岸的呼吸感",
            "audience_payoff": "八秒钟的安静出口",
            "asset_roles": [],
            "continuity_locks": ["阴天自然光方向不变"],
            "shots": [{
                "shot_id": "S01", "start_s": 0, "end_s": 8,
                "purpose": "雨后海岸逐渐恢复平静", "subject_action": "海浪缓慢退去",
                "composition": "低机位中远景", "camera": "固定镜头带轻微呼吸",
                "lens_focus": "35mm，焦点在湿润礁石", "lighting": "阴天散射光",
                "palette_material": "低饱和灰蓝与湿岩反光", "dialogue_visible_text": "",
                "soundscape": "海浪与微风", "transition": "自然结束", "reference_ids": [], "avoid": ["快速运镜"]
            }],
            "provider_target": "FLOVA",
            "provider_mode": "AUTO",
            "provider_prompt": "",
            "negative_constraints": ["霓虹色"],
            "qa_gates": {},
            "approvals_required": ["prompt_package_approval"],
            "status": "WAITING_PROMPT_APPROVAL"
        }
        source = self.root / "content" / self.video_id / "production" / "prompt_package.json"
        source.write_text(json.dumps(prompt_package, ensure_ascii=False), encoding="utf-8")
        job = RUNNER.create_job({"actionId": "COMPILE_VIDEO_TASK_PACKAGE", "videoId": self.video_id, "parameters": {}})
        code, _, stderr, artifacts = RUNNER._execute_action(job)
        self.assertEqual(0, code, stderr)
        result = json.loads((self.root / artifacts[0]).read_text(encoding="utf-8"))
        self.assertEqual("WAITING_GENERATION_APPROVAL", result["status"])
        self.assertFalse(result["preflight_confirmation"]["allows_generation"])
        self.assertEqual([], result["external_actions_performed"])
        self.assertEqual("1115fa6bc53344ed981a261a43aada82", result["private_skill"]["skill_id"])

    def test_video_task_confirmation_supports_seedance_direct_route(self) -> None:
        prompt_package = {
            "video_id": self.video_id, "media_kind": "VIDEO", "output_mode": "VIDEO_SINGLE_SHOT",
            "aspect_ratio": "9:16", "duration_seconds": 8, "asset_roles": [], "continuity_locks": [],
            "shots": [{"shot_id": "S01", "start_s": 0, "end_s": 8}], "provider_target": "SEEDANCE_2_0", "provider_prompt": "8秒竖屏雨后海岸，固定镜头，海浪缓慢退去。",
            "negative_constraints": [], "status": "WAITING_PROMPT_APPROVAL"
        }
        source = self.root / "content" / self.video_id / "production" / "prompt_package.json"
        source.write_text(json.dumps(prompt_package, ensure_ascii=False), encoding="utf-8")
        job = RUNNER.create_job({"actionId": "COMPILE_VIDEO_TASK_PACKAGE", "videoId": self.video_id, "parameters": {}})
        code, _, stderr, artifacts = RUNNER._execute_action(job)
        self.assertEqual(0, code, stderr)
        result = json.loads((self.root / artifacts[0]).read_text(encoding="utf-8"))
        self.assertEqual("SEEDANCE_2_0", result["provider_target"])
        self.assertEqual("seedance-prompt-zh", result["provider_compiler"])
        self.assertFalse(result["preflight_confirmation"]["allows_generation"])

    def test_pixelle_generation_is_retired_from_current_route(self) -> None:
        with self.assertRaisesRegex(ValueError, "即梦 / Seedance"):
            RUNNER.create_job({
                "actionId": "PIXELLE_VIDEO_GENERATE",
                "videoId": self.video_id,
                "parameters": {
                    "text": "雨夜里的安静城市",
                    "frame_template": "1080x1920/image_default.html",
                    "provider_ack": True,
                },
            })

    def test_social_adapter_generates_preview_and_never_executes(self) -> None:
        prepare = {
            "route": "IMAGE_CAROUSEL",
            "upload_artifacts": [{"absolute_path": str(self.root / "content" / self.video_id / "production" / "01.jpg")}],
        }
        (self.root / "content" / self.video_id / "approvals" / "prepare_job.json").write_text(json.dumps(prepare), encoding="utf-8")
        job = RUNNER.create_job({"actionId": "BUILD_UPLOAD_PLAN", "videoId": self.video_id, "parameters": {}})
        code, stdout, _, artifacts = RUNNER._execute_action(job)
        self.assertEqual(0, code)
        self.assertTrue(artifacts)
        plan = json.loads(stdout)
        self.assertFalse(plan["executable"])
        self.assertTrue(plan["requires_fresh_user_confirmation"])
        self.assertFalse(plan["publish_clicked"])


if __name__ == "__main__":
    unittest.main()
