"""Provider-neutral, prepare-only compiler for a frozen video prompt package."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flova_prompt_compiler import compile_package as compile_flova_package, validate_timeline


DIRECT_TARGETS = {
    "SEEDANCE_2_0": "seedance-prompt-zh",
    "MINIMAX_H3": "h3-prompt-writing",
}
ALLOWED_RIGHTS = {"user_owned", "licensed"}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compile_direct(source: Path, data: dict[str, Any], target: str) -> dict[str, Any]:
    if str(data.get("media_kind") or "").upper() != "VIDEO":
        raise ValueError("video task compiler accepts VIDEO prompt packages only")
    if str(data.get("status") or "") != "WAITING_PROMPT_APPROVAL":
        raise ValueError("prepare-only compiler requires WAITING_PROMPT_APPROVAL; this status is not generation approval")
    blockers = validate_timeline(data)
    if str(data.get("aspect_ratio") or "9:16") != "9:16":
        blockers.append("Douyin video aspect_ratio must be 9:16")
    prompt = str(data.get("provider_prompt") or "").strip()
    if not prompt:
        blockers.append("provider_prompt is empty; run the selected provider prompt Skill first")
    references: list[dict[str, str]] = []
    for asset in data.get("asset_roles") if isinstance(data.get("asset_roles"), list) else []:
        rights = str(asset.get("rights_status") or "unknown")
        reference = {
            "source_id": str(asset.get("id") or ""),
            "type": str(asset.get("type") or ""),
            "role": str(asset.get("role") or ""),
            "rights_status": rights,
            "path_or_label": str(asset.get("path_or_label") or ""),
        }
        if rights not in ALLOWED_RIGHTS:
            blockers.append(f"{reference['source_id'] or 'reference'}: rights_status={rights}")
        if not reference["path_or_label"]:
            blockers.append(f"{reference['source_id'] or 'reference'}: missing path_or_label")
        references.append(reference)
    return {
        "schema_version": "1.0",
        "created_at": _now_iso(),
        "source_prompt_package": str(source.resolve()),
        "source_prompt_package_sha256": _sha256(source),
        "video_id": str(data.get("video_id") or ""),
        "provider_target": target,
        "provider_compiler": DIRECT_TARGETS[target],
        "status": "BLOCKED" if blockers else "WAITING_GENERATION_APPROVAL",
        "generation_spec": {
            "aspect_ratio": "9:16",
            "duration_seconds": data.get("duration_seconds"),
            "total_duration_seconds": data.get("duration_seconds"),
            "output_mode": data.get("output_mode"),
            "model": "VERIFY_AT_SUBMISSION",
            "model_proposal": str(data.get("model_preference") or "VERIFY_AT_SUBMISSION"),
            "resolution": "VERIFY_AT_SUBMISSION",
            "credits": "VERIFY_AT_SUBMISSION",
        },
        "provider_prompt": prompt,
        "references": references,
        "shots": data.get("shots") or [],
        "negative_constraints": data.get("negative_constraints") or [],
        "continuity_locks": data.get("continuity_locks") or [],
        "blockers": blockers,
        "preflight_confirmation": {
            "required": True,
            "confirmed": False,
            "allows_project_creation": False,
            "allows_asset_upload": False,
            "allows_generation": False,
            "message": "请确认服务商、模型、镜头数、时长、分辨率、引用素材及可能的积分/会员消耗。",
        },
        "external_actions_performed": [],
    }


def compile_package(source: Path) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    target = str(data.get("provider_target") or "").upper()
    if target == "FLOVA":
        task = compile_flova_package(source)
        task["task_kind"] = "VIDEO_GENERATION_CONFIRMATION"
        return task
    if target in DIRECT_TARGETS:
        task = _compile_direct(source, data, target)
        task["task_kind"] = "VIDEO_GENERATION_CONFIRMATION"
        return task
    raise ValueError(f"unsupported provider_target: {target or 'empty'}")


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
    print(json.dumps({"ok": True, "status": result["status"], "provider_target": result["provider_target"], "output": str(args.output.resolve()), "external_actions_performed": []}, ensure_ascii=False))
    return 0 if result["status"] == "WAITING_GENERATION_APPROVAL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
