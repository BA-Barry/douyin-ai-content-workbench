"""Deterministic Skill planning for the local Douyin workbench.

The browser UI does not execute instruction-only Codex Skills.  This module
turns an approved project route and production request into an auditable plan
that a Codex task can execute.  It deliberately routes only relevant Skills.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SKILLS_ROOT = Path(r"C:\Users\86135\.codex\skills")
SYSTEM_CAPABILITIES = {"imagegen"}
FLOVA_PRIVATE_SKILL = {
    "id": "1115fa6bc53344ed981a261a43aada82",
    "name": "抖音导演提示词编译器",
    "url": "https://www.flova.ai/skill/?id=1115fa6bc53344ed981a261a43aada82",
    "visibility": "PRIVATE_UNPUBLISHED",
}


STYLE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("retro-scrapbook-collage", ("拼贴", "剪贴", "贴纸", "scrapbook", "复古拼贴")),
    ("cinematic-memory-wallpaper", ("胶片", "英文诗", "短诗", "诗歌", "电影感", "cinematic")),
    ("minimal-postcard-wallpaper", ("明信片", "留白", "极简", "postcard")),
    ("travel-zine-wallpaper", ("旅行卡", "旅行杂志", "travel zine", "zine", "旅行拼贴")),
    ("photo-diary-collage-wallpaper", ("人物日记", "照片日记", "生活碎片", "虚构人物", "photo diary")),
    ("americana-roadtrip-wallpaper", ("美式", "公路", "旅馆", "汽车旅馆", "diner", "road trip", "americana")),
    ("ai-scenery-studio", ("奇幻", "异世界", "不可能", "未来城市", "赛博", "朋克", "风景", "治愈")),
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _registry_row(root: Path, video_id: str) -> dict[str, str]:
    path = root / "data" / "content_registry.csv"
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next((row for row in csv.DictReader(handle) if row.get("video_id") == video_id), {})


def _brief_text(root: Path, video_id: str) -> str:
    path = root / "content" / video_id / "brief.md"
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _installed_skills(skills_root: Path) -> set[str]:
    if not skills_root.is_dir():
        return set(SYSTEM_CAPABILITIES)
    installed = set(SYSTEM_CAPABILITIES)
    for folder in skills_root.iterdir():
        skill_md = folder / "SKILL.md"
        if not folder.is_dir() or folder.name.startswith(".") or not skill_md.is_file():
            continue
        installed.add(folder.name)
        try:
            for line in skill_md.read_text(encoding="utf-8", errors="replace").splitlines()[:12]:
                if line.startswith("name:"):
                    declared_name = line.split(":", 1)[1].strip().strip('"\'')
                    if declared_name:
                        installed.add(declared_name)
                    break
        except OSError:
            continue
    return installed


def _select_visual_skill(context: str) -> tuple[str, str]:
    # Negative constraints are not positive style requests. Preserve unrelated
    # clauses so “不要贴纸，保留美式公路” still selects the road-trip style.
    normalized = re.sub(
        r"(?:不(?:要|需要|使用|出现|添加|包含|采用|做)|无(?:需)?|避免|禁止|\b(?:no|without|avoid)\b\s*)[^，,。；;\n.!?]*",
        "",
        context.lower(),
    )
    for skill, signals in STYLE_RULES:
        hits = [signal for signal in signals if signal.lower() in normalized]
        if hits:
            return skill, f"命中视觉意图：{'、'.join(hits[:3])}"
    return "ai-scenery-studio", "未命中特定版式风格，按当前 AI 造境账号基线选择"


def _select_video_prompt_compiler(context: str, parameters: dict[str, Any]) -> tuple[str, str, str, str]:
    """Select exactly one provider compiler; never stack Seedance and H3."""
    requested = str(parameters.get("video_provider") or "AUTO").strip().upper().replace("-", "_")
    normalized = context.lower()
    h3_signals = ("minimax", "mini max", "海螺", "h3", "ref2va", "fl2va", "l2va")
    seedance_signals = ("seedance", "即梦", "豆包视频", "@image", "@video", "@audio")
    flova_signals = ("flova", "弗洛瓦", "flova skill", "flova私有skill")

    # Explicit workbench selections override historical brief wording.
    if requested in {"FLOVA", "FLOVA_PRIVATE"}:
        return "flova", "FLOVA", "AUTO", "brief 明确选择 Flova 私有导演提示词 Skill；生成前仍须完成模型、时长、清晰度与费用确认"
    if requested in {"MINIMAX_H3", "H3", "MINIMAX"}:
        return "h3-prompt-writing", "MINIMAX_H3", "AUTO", "brief 明确指向 MiniMax H3 / 海螺或 H3 专用模式"
    if requested in {"SEEDANCE_2_0", "SEEDANCE", "JIMENG"}:
        return "seedance-prompt-zh", "SEEDANCE_2_0", "AUTO", "用户在工作台明确选择即梦 / Seedance 2.0，生成前仍须确认模型、费用与素材上传范围"
    if any(signal in normalized for signal in flova_signals):
        return "flova", "FLOVA", "AUTO", "brief 明确选择 Flova 私有导演提示词 Skill；生成前仍须完成模型、时长、清晰度与费用确认"
    if any(signal in normalized for signal in h3_signals):
        return "h3-prompt-writing", "MINIMAX_H3", "AUTO", "brief 明确指向 MiniMax H3 / 海螺或 H3 专用模式"
    if any(signal in normalized for signal in seedance_signals):
        return "seedance-prompt-zh", "SEEDANCE_2_0", "AUTO", "brief 明确指向 Seedance / 即梦或 @ 多模态引用"
    return "flova", "FLOVA", "AUTO", "未指定供应端，默认由项目私有 Flova Skill 编译，并在生成前确认模型、时长、清晰度与积分消耗"


def _positive_production_intent(context: str) -> str:
    """Ignore template examples and negative constraints when routing work."""
    active_lines = []
    for line in context.splitlines():
        if re.match(r"^\s*#{1,6}\s*(?:旧模板|历史模板|模板字段|主控审核)", line):
            break
        if re.match(r"^\s*-\s*\[[ xX]\]", line):
            continue
        if re.match(r"^\s*-\s*[\w_]+\s*[:：]\s*$", line):
            continue
        active_lines.append(line)
    positive = "\n".join(active_lines).lower()
    # Keep the affirmative side of contrast clauses ("不要字幕，但需要拼接").
    positive = re.sub(r"但是|不过|而是|但|\bbut\b", "；", positive)
    return re.sub(
        r"(?:没(?:有)?|不(?:要|需要|使用|出现|添加|包含|采用|做|带|加)|不(?=合成|拼接|转场|剪辑|配音)|无(?:需)?|避免|禁止|\b(?:no|without|avoid)\b\s*)[^，,。；;\n.!?]*",
        "", positive,
    )


def _step(
    sequence: int,
    phase: str,
    skill: str,
    purpose: str,
    gate: str,
    outputs: list[str],
    installed: set[str],
    *,
    required: bool = True,
    execution: str = "codex_skill",
) -> dict[str, Any]:
    available = skill in installed
    return {
        "sequence": sequence,
        "phase": phase,
        "skill": skill,
        "purpose": purpose,
        "required": required,
        "available": available,
        "execution": execution,
        "gate": gate,
        "outputs": outputs,
        "status": "PLANNED" if available else ("BLOCKED" if required else "SKIPPED"),
    }


def build_skill_plan(
    root: Path,
    video_id: str,
    parameters: dict[str, Any],
    *,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
) -> dict[str, Any]:
    row = _registry_row(root, video_id)
    route = str(row.get("content_type") or parameters.get("content_route") or "IMAGE_CAROUSEL").strip().upper()
    if route not in {"IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO", "NARRATED_EXPLAINER"}:
        raise ValueError(f"unsupported content route: {route}")

    context = "\n".join(
        str(value or "")
        for value in (
            row.get("title"), row.get("pillar"), row.get("hypothesis"),
            parameters.get("prompt"), _brief_text(root, video_id),
        )
    )
    installed = _installed_skills(skills_root)
    visual_skill, selection_reason = _select_visual_skill(context)
    asset_decision = parameters.get("_asset_decision") if isinstance(parameters.get("_asset_decision"), dict) else {}
    requires_image_subtask = bool(asset_decision.get("requires_image_subtask"))
    needs_frame_director = any(
        signal in context.lower()
        for signal in ("电影级", "电影风格", "电影感", "cinematic", "镜头感", "焦段", "导演语言", "关键帧")
    )
    steps: list[dict[str, Any]] = []
    omitted: list[dict[str, str]] = []

    def add(phase: str, skill: str, purpose: str, gate: str, outputs: list[str], *, required: bool = True) -> None:
        steps.append(_step(len(steps) + 1, phase, skill, purpose, gate, outputs, installed, required=required))

    add("orchestration", "douyin-media-orchestrator", "冻结路线、自动组合能力并维护执行证据", "project_route_known", ["production/skill_plan.json"])

    provider_target = "IMAGEGEN"
    prompt_compiler = "imagegen"
    provider_mode = "IMAGE"
    provider_selection_reason = "图片路线由统一提示词导演输出，再交给 Codex 内置图片生成"

    if route == "IMAGE_CAROUSEL":
        add("visual_contract", visual_skill, "生成风格合同并向统一提示词包提供逐图约束", "brief_approved", ["production/route_plan.json", "production/shot_list.csv"])
        if needs_frame_director:
            add("cinematic_frame_direction", "cinematic-director-frame", "以 prompt-only 方式提供构图、单焦段、动机光、色彩与材质 Director DNA；默认适配9:16", "visual_contract_ready", ["production/cinematic_frame_contract.md"])
        add("prompt_direction", "douyin-prompt-director", "整合受众回报、风格合同、逐图结构、连续性与提示词质量门", "visual_contract_ready", ["production/prompt_package.md", "production/prompt_package.json"])
        add("generation", "imagegen", "在 Codex 端生成原始竖屏图片", "prompt_and_count_frozen", ["production/generated/"])
        add("export_qa", "douyin-wallpaper-export", "导出高清发布图并检查清晰度、尺寸与压缩风险", "images_approved", ["production/publish_images/", "qa/technical_report.json"])
        omitted.extend([
            {"skill": "hyperframes-motion-language", "reason": "静态图文不需要镜头运动"},
            {"skill": "douyin-caption-pipeline", "reason": "静态图文没有对白或旁白"},
            {"skill": "text-to-speech", "reason": "图片轮播不生成旁白"},
        ])
    else:
        prompt_compiler, provider_target, provider_mode, provider_selection_reason = _select_video_prompt_compiler(context, parameters)
        provider_output = "production/video_task_package.json"
        compiler_purpose = {
            "MINIMAX_H3": "按 MiniMax H3 官方字段与参考保留语法编译已批准提示词包",
            "FLOVA": "将已批准导演包编译为私有 Flova Skill 的 prepare-only 任务；不创建项目、不上传素材、不提交生成",
        }.get(provider_target, "按即梦 / Seedance 的时段与 @ 多模态引用语法编译已批准提示词包")
        if requires_image_subtask:
            add("visual_anchor_contract", visual_skill, "为视频关键帧或元素图生成稳定的视觉合同", "brief_approved", ["production/assets/keyframe_contract.json"])
        if needs_frame_director or requires_image_subtask:
            add("cinematic_frame_direction", "cinematic-director-frame", "以 prompt-only 方式提供关键帧的构图、单焦段、动机光、色彩与材质 Director DNA；默认适配9:16", "brief_approved", ["production/cinematic_frame_contract.md"])
        add("prompt_direction", "douyin-prompt-director", "统一受众回报、导演语言、镜头结构、连续性、声音与提示词质量门", "brief_approved", ["production/prompt_package.md", "production/prompt_package.json"])
        if requires_image_subtask:
            add("visual_anchor_generation", "imagegen", "在 Codex 端生成视频所需首帧、尾帧、角色或场景锚点", "visual_anchor_prompt_approved", ["production/assets/generated/"])
        add("motion_contract", "hyperframes-motion-language", "统一镜头运动、节拍和切点连续性", "shots_defined", ["production/motion_contract.json"])
        add("provider_prompt_compile", prompt_compiler, compiler_purpose, "prompt_and_motion_approved", [provider_output])
        voice_mode = str(parameters.get("voice_mode") or "none").lower()
        music_mode = str(parameters.get("music_mode") or "none").lower()
        positive_intent = _positive_production_intent(context)
        caption_signals = ("台词", "旁白", "对白", "字幕", "dialogue", "caption", "subtitle", "voiceover")
        needs_captions = route == "NARRATED_EXPLAINER" or voice_mode != "none" or any(signal in positive_intent for signal in caption_signals)
        assembly_signals = ("合成", "拼接", "转场", "剪辑", "多镜头", "多段", "蒙太奇", "叠加", "贴字", "overlay", "composit", "montage", "transition", "multi-shot")
        multi_character_signals = ("多人", "两人", "两个人", "双人", "多角色", "两个角色", "two people", "two characters", "multiple characters", "couple")
        simple_single_shot = (
            route == "ATMOSPHERE_VIDEO"
            and str(parameters.get("image_count", "")).strip() in {"1", "1.0"}
            and voice_mode == "none" and music_mode == "none"
            and not needs_captions
            and not any(signal in positive_intent for signal in (*assembly_signals, *multi_character_signals))
        )
        if simple_single_shot:
            omitted.extend({"skill": skill, "reason": "明确单镜头、无旁白音乐或正向字幕/合成诉求；直接验收模型返回的镜头，不建立不必要的合成工程"} for skill in (
                "remotion-best-practices", "remotion-create", "remotion-multimedia", "remotion-studio", "remotion-render",
            ))
        else:
            add("composition_rules", "remotion-best-practices", "选择可维护的 Remotion 时间线和媒体结构", "generated_shots_received", ["production/remotion/"])
            add("composition", "remotion-create", "创建竖屏合成工程和镜头序列", "motion_contract_ready", ["production/remotion/"])
            add("media_assembly", "remotion-multimedia", "接入视频、图片、声音并保持同步", "source_media_hashed", ["production/remotion/"])
        if needs_captions:
            add("captions", "douyin-caption-pipeline", "自动路由转写、字幕切分、排版、烧录与对齐 QA", "audio_or_timed_script_ready", ["production/caption_contract.json", "production/captions.json", "qa/caption_qa.json"])
        else:
            omitted.append({"skill": "douyin-caption-pipeline", "reason": "当前请求无对白、旁白或证据字幕"})

        if route == "NARRATED_EXPLAINER" and voice_mode == "sample-first":
            add("voice_sample", "text-to-speech", "只生成 8–15 秒旁白短样供自然度审核", "api_key_cost_voice_rights_approved", ["production/voice_sample/"])
        elif route == "NARRATED_EXPLAINER" and voice_mode == "user-voice":
            omitted.append({"skill": "text-to-speech", "reason": "使用用户录音，不调用合成配音"})
        elif route == "NARRATED_EXPLAINER":
            omitted.append({"skill": "text-to-speech", "reason": "声音策略为 none；讲解路线将在声音门阻断"})

        if not simple_single_shot:
            add("preview", "remotion-studio", "预览节奏、字幕安全区和镜头连续性", "composition_ready", ["production/remotion/preview_receipt.json"])
            add("render", "remotion-render", "渲染可复现的竖屏成片", "preview_approved", ["production/final.mp4"])
        add("editorial_qa", "video-use", "检查模型返回单镜头的时长、画幅、完整性与可预览性；不自动增加字幕、音乐或合成" if simple_single_shot else "完成剪辑、调色、音频、字幕和技术收口", "generated_shots_received" if simple_single_shot else "render_exists", ["qa/technical_report.json"])

    missing_required = [step["skill"] for step in steps if step["required"] and not step["available"]]
    status = "BLOCKED" if missing_required else "READY_FOR_CODEX"
    human_gates = ["brief_approval", "prompt_package_approval", "final_media_review", "release_package_approval", "prepare_only_confirmation", "manual_publish"]
    if route != "IMAGE_CAROUSEL":
        human_gates.insert(2, "video_provider_cost_and_upload_approval")
        if requires_image_subtask or asset_decision.get("bound_asset_ids"):
            human_gates.insert(2, "visual_anchor_and_reference_approval")
    if any(step["skill"] in {"text-to-speech", "speech-to-text", "music", "sound-effects"} for step in steps):
        human_gates.insert(1, "api_key_cost_upload_and_rights_approval")

    return {
        "schema_version": "1.1",
        "video_id": video_id,
        "route": route,
        "created_at": _now_iso(),
        "planner": "douyin-media-orchestrator",
        "status": status,
        "executor": "CODEX_TASK_REQUIRED",
        "selected_visual_skill": visual_skill if route == "IMAGE_CAROUSEL" or requires_image_subtask else "",
        "selection_reason": selection_reason if route == "IMAGE_CAROUSEL" or requires_image_subtask else provider_selection_reason,
        "asset_strategy": asset_decision,
        "provider_target": provider_target,
        "provider_mode": provider_mode,
        "prompt_compiler": prompt_compiler,
        "provider_skill": FLOVA_PRIVATE_SKILL if provider_target == "FLOVA" else {},
        "provider_selection_reason": provider_selection_reason,
        "steps": steps,
        "omitted": omitted,
        "missing_required_skills": missing_required,
        "human_gates": human_gates,
        "autonomy_boundary": "工作台自动规划、排队和留痕；Codex 任务执行 Skills；付费、私人素材上传、声音克隆、平台上传和发布保留人工门。",
    }
