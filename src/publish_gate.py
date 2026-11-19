from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
import os
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
MIN_REFERENCE_VIDEOS = 12
MIN_CATALOG_VIDEOS = 60
MIN_CATALOG_CATEGORIES = 6
MIN_CATALOG_CREATORS = 20
REQUIRED_RESEARCH_FIELDS = {
    "url",
    "creator",
    "captured_at",
    "duration_seconds",
    "hook_pattern",
    "first_frame",
    "visual_pattern",
    "pace_notes",
    "proof_element",
    "caption_style",
    "audio_style",
    "cta_pattern",
    "comment_signal",
    "learning_hypothesis",
    "do_not_copy",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict) -> None:
    manifest["updated_at"] = datetime.now().astimezone().isoformat()
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_artifacts(manifest: dict) -> list[str]:
    errors: list[str] = []
    video = Path(manifest["artifacts"]["video"])
    if not video.exists():
        errors.append(f"video missing: {video}")
        return errors
    expected = manifest.get("qa", {}).get("sha256")
    actual = sha256(video)
    if expected and actual.lower() != expected.lower():
        errors.append("video hash does not match manifest")
    if video.suffix.lower() != ".mp4":
        errors.append("video must be MP4")
    if manifest.get("qa", {}).get("aspect_ratio") != "9:16":
        errors.append("aspect ratio is not 9:16")
    if not manifest.get("qa", {}).get("has_audio"):
        errors.append("audio track missing")
    return errors


def read_research(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], [f"research file missing: {path}"]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_RESEARCH_FIELDS - fields)
        rows = [row for row in reader if row.get("url", "").strip()]
    errors = [f"research CSV missing fields: {', '.join(missing)}"] if missing else []
    if len(rows) < MIN_REFERENCE_VIDEOS:
        errors.append(f"need at least {MIN_REFERENCE_VIDEOS} reference videos; found {len(rows)}")
    creators = {row.get("creator", "").strip() for row in rows if row.get("creator", "").strip()}
    if len(creators) < 4:
        errors.append(f"need at least 4 distinct creators; found {len(creators)}")
    usable_comment_signals = 0
    for row in rows:
        signal = row.get("comment_signal", "").strip().lower()
        if signal and not any(marker in signal for marker in ("超时", "未读取", "unavailable")):
            usable_comment_signals += 1
    if usable_comment_signals < 8:
        errors.append(f"need at least 8 usable comment signals; found {usable_comment_signals}")
    duplicate_count = len(rows) - len({row.get("url", "").strip() for row in rows})
    if duplicate_count:
        errors.append(f"research contains {duplicate_count} duplicate URL(s)")
    for index, row in enumerate(rows, start=2):
        for field in REQUIRED_RESEARCH_FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"row {index} is missing {field}")
    return rows, errors


def read_catalog(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], [f"catalog file missing: {path}"]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"sample_group", "id", "likes", "title", "creator"}
        missing = sorted(required - fields)
        rows = [row for row in reader if row.get("id", "").strip()]
    errors = [f"catalog CSV missing fields: {', '.join(missing)}"] if missing else []
    if len(rows) < MIN_CATALOG_VIDEOS:
        errors.append(f"need at least {MIN_CATALOG_VIDEOS} catalog videos; found {len(rows)}")
    categories = {row.get("sample_group", "").strip() for row in rows if row.get("sample_group", "").strip()}
    if len(categories) < MIN_CATALOG_CATEGORIES:
        errors.append(f"need at least {MIN_CATALOG_CATEGORIES} catalog categories; found {len(categories)}")
    creators = {row.get("creator", "").strip() for row in rows if row.get("creator", "").strip()}
    if len(creators) < MIN_CATALOG_CREATORS:
        errors.append(f"need at least {MIN_CATALOG_CREATORS} catalog creators; found {len(creators)}")
    duplicate_count = len(rows) - len({row.get("id", "").strip() for row in rows})
    if duplicate_count:
        errors.append(f"catalog contains {duplicate_count} duplicate ID(s)")
    return rows, errors


def command_validate(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    errors = validate_artifacts(manifest)
    print(f"state={manifest.get('state')}")
    print(f"artifact_errors={len(errors)}")
    for error in errors:
        print(f"ERROR: {error}")
    blockers = manifest.get("publish_gate", {}).get("blocking_reasons", [])
    for blocker in blockers:
        print(f"BLOCKED: {blocker}")
    return 1 if errors or blockers else 0


def command_reference_review(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    if manifest.get("state") != "AWAITING_REFERENCE_REVIEW":
        raise RuntimeError(f"expected AWAITING_REFERENCE_REVIEW, got {manifest.get('state')}")
    rows, errors = read_research(args.research)
    catalog_rows, catalog_errors = read_catalog(args.catalog)
    errors.extend(catalog_errors)
    if errors:
        for error in errors:
            print(f"BLOCKED: {error}")
        return 2
    manifest["state"] = "AWAITING_APPROVAL"
    manifest["reference_review"] = {
        "completed_at": datetime.now().astimezone().isoformat(),
        "research_file": str(args.research.resolve()),
        "catalog_file": str(args.catalog.resolve()),
        "video_count": len(rows),
        "catalog_video_count": len(catalog_rows),
        "catalog_category_count": len({row["sample_group"].strip() for row in catalog_rows}),
        "creator_count": len({row["creator"].strip() for row in rows}),
    }
    blockers = manifest["publish_gate"].get("blocking_reasons", [])
    manifest["publish_gate"]["blocking_reasons"] = [
        item for item in blockers if item != "尚未完成同赛道参考视频学习"
    ]
    save_manifest(args.manifest, manifest)
    print("state=AWAITING_APPROVAL")
    return 0


def command_approve(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    if manifest.get("state") != "AWAITING_APPROVAL":
        raise RuntimeError(f"expected AWAITING_APPROVAL, got {manifest.get('state')}")
    if not (args.confirm_video_reviewed and args.confirm_ai_label):
        raise RuntimeError("video review and AI label confirmation are both required")
    manifest["state"] = "APPROVED"
    manifest["content"]["selected_title"] = args.title
    manifest["publish_gate"].update(
        {
            "approved": True,
            "must_not_publish": True,
            "approved_at": datetime.now().astimezone().isoformat(),
            "blocking_reasons": ["尚未在抖音发布页进行最终人工确认"],
            "allowed_next_states": ["PREPARED_IN_DOUYIN"],
        }
    )
    save_manifest(args.manifest, manifest)
    print("state=APPROVED")
    return 0


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def command_prepare(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    errors = validate_artifacts(manifest)
    if errors:
        raise RuntimeError("; ".join(errors))
    if manifest.get("state") != "APPROVED" or not manifest.get("publish_gate", {}).get("approved"):
        raise RuntimeError("manifest is not approved")
    content = manifest["content"]
    video = manifest["artifacts"]["video"]
    command = [
        str((args.root / "envs" / "publisher" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")).resolve()),
        "-m",
        "sau_cli",
        "douyin",
        "upload-video",
        "--account",
        args.account,
        "--file",
        video,
        "--title",
        content["selected_title"],
        "--desc",
        content["description"],
        "--tags",
        ",".join(content["tags"]),
        "--prepare-only",
        "--headed",
    ]
    command_path = args.root / "outputs" / "prepare_douyin_upload.ps1"
    body = (
        "$ErrorActionPreference = 'Stop'\n"
        f"Set-Location -LiteralPath {ps_quote(str((args.root / 'projects' / 'social-auto-upload').resolve()))}\n"
        + "& "
        + ps_quote(command[0])
        + " "
        + " ".join(ps_quote(item) for item in command[1:])
        + "\n"
    )
    command_path.write_text(body, encoding="utf-8-sig")
    print(f"prepare_script={command_path}")
    print("safety=prepare-only; uploader code will not click Publish")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local approval gate for the Douyin workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.set_defaults(func=command_validate)

    review = sub.add_parser("reference-review")
    review.add_argument("--manifest", type=Path, required=True)
    review.add_argument("--research", type=Path, required=True)
    review.add_argument("--catalog", type=Path, required=True)
    review.set_defaults(func=command_reference_review)

    approve = sub.add_parser("approve")
    approve.add_argument("--manifest", type=Path, required=True)
    approve.add_argument("--title", required=True)
    approve.add_argument("--confirm-video-reviewed", action="store_true")
    approve.add_argument("--confirm-ai-label", action="store_true")
    approve.set_defaults(func=command_approve)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--root", type=Path, default=ROOT)
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--account", required=True)
    prepare.set_defaults(func=command_prepare)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
