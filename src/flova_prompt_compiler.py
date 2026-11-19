"""Compile a draft director prompt package into a prepare-only Flova task.

This module performs no network requests, uploads, project creation, generation,
or export.  Its output is a human approval boundary for the private Flova Skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


PRIVATE_SKILL = {
    "skill_id": "1115fa6bc53344ed981a261a43aada82",
    "skill_name": "抖音导演提示词编译器",
    "skill_url": "https://www.flova.ai/skill/?id=1115fa6bc53344ed981a261a43aada82",
    "visibility": "PRIVATE_UNPUBLISHED",
}
ALLOWED_RIGHTS = {"user_owned", "licensed"}
REFERENCE_PREFIX = {"image": "image", "video": "video", "audio": "audio"}
MODEL_LIMITS = {
    "Seedance 2.5": {"duration": (4, 30), "resolutions": {"480p", "720p", "1080p"}, "default_resolution": "720p"},
    "Seedance 2.0": {"duration": (4, 15), "resolutions": {"720p", "1080p", "4k"}, "default_resolution": "720p"},
    "MiniMax H3": {"duration": (4, 15), "resolutions": {"768p", "2k"}, "default_resolution": "768p"},
}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seconds(value: Any) -> float | None:
    """Read finite seconds without accepting booleans as numeric input."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def validate_timeline(data: dict[str, Any]) -> list[str]:
    """Validate ordinary contiguous shot timing before making a confirmation card.

    This validates the proposal only. A valid timeline, including one whose source
    is WAITING_PROMPT_APPROVAL, never constitutes approval to generate.
    """
    blockers: list[str] = []
    total = _seconds(data.get("duration_seconds"))
    if total is None or total <= 0:
        blockers.append("duration_seconds must be finite and positive")
    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        return blockers + ["no shots supplied"]
    previous_end = 0.0
    sum_duration = 0.0
    all_valid = True
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            blockers.append(f"shot {index + 1} must be an object")
            all_valid = False
            continue
        label = str(shot.get("shot_id") or f"shot {index + 1}")
        start, end = _seconds(shot.get("start_s")), _seconds(shot.get("end_s"))
        if start is None or end is None or start < 0 or end <= start:
            blockers.append(f"{label}: start_s/end_s must be finite, nonnegative and have positive duration")
            all_valid = False
            continue
        if not math.isclose(start, previous_end, rel_tol=0, abs_tol=1e-6):
            blockers.append(f"{label}: timeline must start at 0 and be contiguous (expected start_s={previous_end}, got {start})")
        duration = end - start
        if "duration_seconds" in shot:
            declared = _seconds(shot.get("duration_seconds"))
            if declared is None or declared <= 0 or not math.isclose(declared, duration, rel_tol=0, abs_tol=1e-6):
                blockers.append(f"{label}: duration_seconds does not match end_s - start_s")
        previous_end = end
        sum_duration += duration
    if all_valid and total is not None and total > 0:
        if not math.isclose(previous_end, total, rel_tol=0, abs_tol=1e-6) or not math.isclose(sum_duration, total, rel_tol=0, abs_tol=1e-6):
            blockers.append("shot timeline and summed durations must match duration_seconds")
    if data.get("output_mode") == "VIDEO_SINGLE_SHOT" and len(shots) != 1:
        blockers.append("VIDEO_SINGLE_SHOT requires exactly one shot")
    return blockers


def _select_mode(assets: list[dict[str, Any]]) -> str:
    roles = {str(item.get("role") or "") for item in assets}
    types = {str(item.get("type") or "") for item in assets}
    if "first_frame" in roles and "last_frame" in roles:
        return "VideoInterp"
    if types & {"video", "audio"}:
        return "MultiModalToVideo"
    if len(assets) == 1 and "first_frame" in roles:
        return "FirstFrameToVideo"
    if assets:
        return "ImagesToVideo"
    return "TextToVideo"


def _references(assets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    counters = {"image": 0, "video": 0, "audio": 0}
    references: list[dict[str, Any]] = []
    blockers: list[str] = []
    for item in assets:
        media_type = str(item.get("type") or "").lower()
        if media_type not in REFERENCE_PREFIX:
            blockers.append(f"unsupported reference type: {media_type or 'empty'}")
            continue
        counters[media_type] += 1
        tag = f"<<<{REFERENCE_PREFIX[media_type]}_{counters[media_type]}>>>"
        rights = str(item.get("rights_status") or "unknown")
        label = str(item.get("path_or_label") or "")
        if rights not in ALLOWED_RIGHTS:
            blockers.append(f"{item.get('id') or tag}: rights_status={rights}")
        if not label:
            blockers.append(f"{item.get('id') or tag}: missing path_or_label")
        references.append({
            "source_id": str(item.get("id") or ""),
            "tag": tag,
            "type": media_type,
            "role": str(item.get("role") or ""),
            "rights_status": rights,
            "retention": str(item.get("retention") or ""),
            "path_or_label": label,
        })
    return references, blockers


def _shot_prompt(shot: dict[str, Any], tag_map: dict[str, str]) -> str:
    refs = [tag_map.get(str(item), "") for item in shot.get("reference_ids", [])]
    refs = [item for item in refs if item]
    parts = [
        f"镜头：{shot.get('camera', '')}；{shot.get('composition', '')}；{shot.get('lens_focus', '')}",
        f"主体：{shot.get('subject_action', '')}",
        f"空间与状态变化：{shot.get('purpose', '')}；转场/退出：{shot.get('transition', '')}",
        f"光线与材质：{shot.get('lighting', '')}；{shot.get('palette_material', '')}",
        f"声音：{shot.get('dialogue_visible_text', '')}；{shot.get('soundscape', '')}",
    ]
    avoid = [str(item) for item in shot.get("avoid", []) if str(item).strip()]
    if refs:
        parts.insert(0, "引用：" + " ".join(refs))
    if avoid:
        parts.append("避免：" + "；".join(avoid))
    return "\n".join(part for part in parts if part.split("：", 1)[-1].strip("； "))


def compile_package(source: Path) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    if str(data.get("media_kind") or "").upper() != "VIDEO":
        raise ValueError("Flova compiler accepts VIDEO prompt packages only")
    if str(data.get("provider_target") or "").upper() != "FLOVA":
        raise ValueError("provider_target must be FLOVA")
    if str(data.get("status") or "") != "WAITING_PROMPT_APPROVAL":
        raise ValueError("prepare-only compiler requires WAITING_PROMPT_APPROVAL; this status is not generation approval")

    assets = data.get("asset_roles") if isinstance(data.get("asset_roles"), list) else []
    references, blockers = _references(assets)
    blockers.extend(validate_timeline(data))
    tag_map = {item["source_id"]: item["tag"] for item in references}
    settings = data.get("provider_settings") if isinstance(data.get("provider_settings"), dict) else {}
    model = str(settings.get("model") or "Seedance 2.5")
    if model not in MODEL_LIMITS:
        raise ValueError(f"unsupported private-skill model: {model}")
    limits = MODEL_LIMITS[model]
    resolution = str(settings.get("resolution") or limits["default_resolution"])
    if resolution not in limits["resolutions"]:
        raise ValueError(f"unsupported resolution for {model}: {resolution}")
    aspect_ratio = str(data.get("aspect_ratio") or "9:16")
    if aspect_ratio != "9:16":
        blockers.append(f"Douyin video aspect_ratio must be 9:16, got {aspect_ratio}")

    shots = data.get("shots") if isinstance(data.get("shots"), list) else []
    compiled_shots: list[dict[str, Any]] = []
    low, high = limits["duration"]
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        start, end = _seconds(shot.get("start_s")), _seconds(shot.get("end_s"))
        if start is None or end is None:
            continue
        duration = round(end - start, 3)
        if duration < low or duration > high:
            blockers.append(f"{shot.get('shot_id') or 'shot'} duration {duration}s outside {model} {low}-{high}s")
        missing_refs = [str(item) for item in shot.get("reference_ids", []) if str(item) not in tag_map]
        if missing_refs:
            blockers.append(f"{shot.get('shot_id') or 'shot'} missing reference ids: {', '.join(missing_refs)}")
        compiled_shots.append({
            "shot_id": str(shot.get("shot_id") or f"S{len(compiled_shots)+1:02d}"),
            "start_s": start,
            "end_s": end,
            "duration_seconds": duration,
            "reference_tags": [tag_map[str(item)] for item in shot.get("reference_ids", []) if str(item) in tag_map],
            "flova_prompt": _shot_prompt(shot, tag_map),
        })
    total_duration = _seconds(data.get("duration_seconds"))
    output_mode = str(data.get("output_mode") or "VIDEO_MULTI_SHOT")
    return {
        "schema_version": "1.0",
        "created_at": _now_iso(),
        "source_prompt_package": str(source.resolve()),
        "source_prompt_package_sha256": _sha256(source),
        "video_id": str(data.get("video_id") or ""),
        "provider_target": "FLOVA",
        "private_skill": PRIVATE_SKILL,
        "status": "BLOCKED" if blockers else "WAITING_GENERATION_APPROVAL",
        "generation_spec": {
            "generation_mode": _select_mode(assets),
            "model_proposal": model,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "total_duration_seconds": total_duration,
            "output_mode": output_mode,
            "credits": "VERIFY_AT_SUBMISSION",
            "membership": "VERIFY_AT_SUBMISSION",
        },
        "references": references,
        "shots": compiled_shots,
        "negative_constraints": data.get("negative_constraints") or [],
        "continuity_locks": data.get("continuity_locks") or [],
        "blockers": blockers,
        "preflight_confirmation": {
            "required": True,
            "confirmed": False,
            "allows_project_creation": False,
            "allows_asset_upload": False,
            "allows_generation": False,
            "message": "请确认模型、每镜时长、分辨率、引用素材、镜头数及可能产生的 Flova 积分/会员消耗。",
        },
        "external_actions_performed": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = compile_package(args.input)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "ok": True,
        "status": result["status"],
        "output": str(args.output.resolve()),
        "skill_id": PRIVATE_SKILL["skill_id"],
        "external_actions_performed": [],
    }, ensure_ascii=False))
    return 0 if result["status"] == "WAITING_GENERATION_APPROVAL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
