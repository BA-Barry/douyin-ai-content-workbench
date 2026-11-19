from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path("G:/抖音视频")
ROUTES = {"IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO", "NARRATED_EXPLAINER"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def artifact_path(root: Path, value: Any) -> Path | None:
    """Resolve legacy string artifacts and v3 descriptor objects."""
    if isinstance(value, (str, Path)):
        return resolve(root, value)
    if isinstance(value, dict):
        candidate = value.get("absolute_path") or value.get("path") or value.get("local_path")
        if isinstance(candidate, (str, Path)) and str(candidate).strip():
            return resolve(root, candidate)
    return None


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _route(manifest: dict[str, Any], route_plan: dict[str, Any] | None) -> str:
    if route_plan:
        route = str(route_plan.get("route", "")).upper()
        if route in ROUTES:
            return route
    explicit = str(manifest.get("route", "")).upper()
    if explicit in ROUTES:
        return explicit
    artifact_type = str(manifest.get("artifacts", {}).get("artifact_type", "")).lower()
    if artifact_type == "image_carousel":
        return "IMAGE_CAROUSEL"
    if artifact_type in {"atmosphere_video", "video_montage"}:
        return "ATMOSPHERE_VIDEO"
    if artifact_type in {"narrated_explainer", "video"}:
        return "NARRATED_EXPLAINER"
    if isinstance(manifest.get("artifacts", {}).get("images"), list):
        return "IMAGE_CAROUSEL"
    return ""


def production_errors(root: Path, video_id: str) -> list[str]:
    base = root / "content" / video_id
    manifest_path = base / "production" / "production_manifest.json"
    if not manifest_path.exists():
        return ["production/production_manifest.json missing"]
    manifest = read_json(manifest_path)
    route_path = base / "production" / "route_plan.json"
    route_plan = read_json(route_path) if route_path.exists() else None
    route = _route(manifest, route_plan)
    errors: list[str] = []
    if route not in ROUTES:
        errors.append("content route is missing or unsupported")
        return errors
    artifacts = manifest.get("artifacts", {})

    def require_file(key: str) -> None:
        value = artifacts.get(key)
        if not value:
            errors.append(f"artifacts.{key} missing for {route}")
            return
        path = artifact_path(root, value)
        if path is None:
            errors.append(f"artifacts.{key} has no usable path for {route}")
            return
        if not path.exists():
            errors.append(f"artifact missing: {path}")
        elif isinstance(value, dict) and value.get("sha256") and sha256(path).lower() != str(value["sha256"]).lower():
            errors.append(f"artifact hash mismatch: artifacts.{key}")

    if route == "IMAGE_CAROUSEL":
        images = artifacts.get("images") or []
        if not isinstance(images, list) or len(images) < 6:
            errors.append("IMAGE_CAROUSEL requires at least six ordered images")
        else:
            for index, value in enumerate(images, start=1):
                path = artifact_path(root, value)
                if path is None:
                    errors.append(f"carousel image {index} has no usable path")
                    continue
                if not path.exists():
                    errors.append(f"carousel image missing: {path}")
                elif isinstance(value, dict) and value.get("sha256") and sha256(path).lower() != str(value["sha256"]).lower():
                    errors.append(f"carousel image hash mismatch: {path}")
        require_file("cover")
    elif route == "ATMOSPHERE_VIDEO":
        require_file("video")
        require_file("cover")
        if not manifest.get("audio_policy"):
            errors.append("ATMOSPHERE_VIDEO requires audio_policy")
    else:
        for key in ("video", "cover", "captions", "narration"):
            require_file(key)

    if not manifest.get("source_inventory") and not manifest.get("generation"):
        errors.append("production manifest missing source_inventory/generation")
    rights = manifest.get("rights") if isinstance(manifest.get("rights"), dict) else {}
    if not manifest.get("copyright_status") and rights.get("status") not in {"PASS", "CLEARED"}:
        errors.append("production manifest missing copyright_status/cleared rights")
    generation = manifest.get("generation") if isinstance(manifest.get("generation"), list) else []
    has_ai_parts = bool(manifest.get("ai_generated_parts")) or bool(generation and all(item.get("ai_generated") is True for item in generation if isinstance(item, dict)))
    if not has_ai_parts:
        errors.append("production manifest missing ai_generated_parts/generation provenance")

    hashes = manifest.get("artifact_hashes", {})
    if hashes:
        for value, expected in hashes.items():
            path = resolve(root, value)
            if not path.exists():
                errors.append(f"hashed artifact missing: {path}")
            elif sha256(path).lower() != str(expected).lower():
                errors.append(f"artifact hash mismatch: {value}")
    return errors


def qa_errors(root: Path, video_id: str) -> list[str]:
    path = root / "content" / video_id / "qa" / "qa_result.json"
    if not path.exists():
        return ["qa/qa_result.json missing"]
    data = read_json(path)
    errors: list[str] = []
    conclusion = data.get("conclusion", data.get("overall_conclusion"))
    counts = data.get("counts", {})
    blocker_count = data.get("blocker_count", counts.get("blocker_open", 0))
    major_count = data.get("major_count", counts.get("major_open", 0))
    if conclusion not in {"PASS", "PASS_WITH_MINOR"}:
        errors.append(f"QA conclusion is {conclusion!r}")
    if int(blocker_count):
        errors.append("QA contains BLOCKER findings")
    if int(major_count):
        errors.append("QA contains unresolved MAJOR findings")
    expected_manifest = data.get("production_manifest_sha256")
    if not expected_manifest:
        expected_manifest = data.get("inputs", {}).get("production_manifest", {}).get("sha256")
    if expected_manifest:
        manifest = root / "content" / video_id / "production" / "production_manifest.json"
        if not manifest.exists() or sha256(manifest).lower() != str(expected_manifest).lower():
            errors.append("QA is not bound to the current production manifest")
    else:
        errors.append("QA result lacks production_manifest_sha256")
    return errors


def release_errors(root: Path, video_id: str) -> list[str]:
    base = root / "content" / video_id
    path = base / "approvals" / "release_package.json"
    if not path.exists():
        return ["approvals/release_package.json missing"]
    package = read_json(path)
    errors: list[str] = []
    for item in package.get("files", []):
        candidate = resolve(root, item.get("path", ""))
        if not candidate.exists():
            errors.append(f"release file missing: {candidate}")
        elif sha256(candidate).lower() != str(item.get("sha256", "")).lower():
            errors.append(f"release file hash mismatch: {item.get('path')}")
    if not package.get("files"):
        errors.append("release package contains no files")
    approval = base / "approvals" / "final_approval.json"
    if not approval.exists():
        errors.append("final user approval missing")
    else:
        approval_data = read_json(approval)
        expected = package.get("package_sha256")
        bound = approval_data.get("release_package_sha256")
        if expected and bound != expected:
            errors.append("final approval is not bound to this release package")
    return errors


def receipt_errors(root: Path, video_id: str, published: bool = False) -> list[str]:
    base = root / "content" / video_id / "approvals"
    prepare_path = base / "prepare_receipt.json"
    if not prepare_path.exists():
        return ["prepare receipt missing"]
    prepare = read_json(prepare_path)
    errors: list[str] = []
    if str(prepare.get("mode", "")).lower().replace("_", "-") != "prepare-only":
        errors.append("prepare receipt mode must be prepare-only")
    if prepare.get("publish_clicked") is not False:
        errors.append("prepare receipt must prove publish was not clicked")
    if published:
        publish_path = base / "publish_receipt.json"
        if not publish_path.exists():
            errors.append("publish receipt missing")
        else:
            receipt = read_json(publish_path)
            if receipt.get("published") is not True:
                errors.append("publish receipt does not confirm published=true")
            if not receipt.get("reported_at"):
                errors.append("publish receipt lacks reported_at")
    return errors


def audit_content(root: Path, video_id: str) -> dict[str, Any]:
    base = root / "content" / video_id
    required = {
        "research_delta": base / "research" / "research_delta.md",
        "hypothesis_card": base / "hypothesis_card.md",
        "brief": base / "brief.md",
        "route_plan": base / "production" / "route_plan.json",
        "shot_list": base / "production" / "shot_list.csv",
        "production_manifest": base / "production" / "production_manifest.json",
        "qa_result": base / "qa" / "qa_result.json",
        "release_package": base / "approvals" / "release_package.json",
        "prepare_receipt": base / "approvals" / "prepare_receipt.json",
        "publish_receipt": base / "approvals" / "publish_receipt.json",
        "post_snapshots": base / "metrics" / "post_snapshots.csv",
        "postmortem_72h": base / "metrics" / "postmortem_72h.md",
    }
    stages = {name: ("PRESENT" if path.exists() else "MISSING") for name, path in required.items()}
    errors = {
        "production": production_errors(root, video_id),
        "qa": qa_errors(root, video_id),
        "release": release_errors(root, video_id),
        "receipts": receipt_errors(root, video_id, published=True),
    }
    flat = [item for group in errors.values() for item in group]
    complete = not flat and all(v == "PRESENT" for v in stages.values())
    legacy = required["publish_receipt"].exists() and not required["release_package"].exists()
    return {
        "schema_version": "3.0",
        "video_id": video_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "stage_evidence": stages,
        "errors": errors,
        "trace_status": "PASS" if complete else ("LEGACY_RETROSPECTIVE" if legacy else "INCOMPLETE"),
        "legacy_note": "MISSING means historical evidence was not captured; do not reconstruct it as if contemporaneous.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Route-aware workflow evidence audit")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_content(args.root.resolve(), args.video_id)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["trace_status"] in {"PASS", "LEGACY_RETROSPECTIVE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
