from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path("G:/抖音视频")
MODES = {"none", "platform_manual", "licensed_local", "original_local"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    mode = data.get("music_mode")
    errors: list[str] = []
    if mode not in MODES:
        errors.append(f"unsupported music_mode: {mode}")
    embedded = data.get("embedded", False)
    music_file = resolve(root, data.get("music_file_path"))
    rights = resolve(root, data.get("rights_evidence_path"))
    if mode in {"none", "platform_manual"}:
        if embedded or music_file:
            errors.append(f"{mode} must not embed a local music file")
    else:
        if not music_file or not music_file.exists():
            errors.append("local music file missing")
        elif data.get("music_sha256") != sha256(music_file):
            errors.append("local music hash mismatch")
        if not rights or not rights.exists():
            errors.append("local music requires rights evidence")
        if not embedded:
            errors.append("local music mode requires embedded=true")
    return {"schema_version": "3.0", "mode": mode, "status": "PASS" if not errors else "BLOCKED", "errors": errors}


def validate_publish_receipt(root: Path, package_path: Path, receipt_path: Path) -> dict[str, Any]:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if receipt.get("release_package_sha256") != package.get("package_sha256"):
        errors.append("music receipt is not bound to release package")
    mode = package.get("music_policy", "none")
    actual = receipt.get("actual_music")
    if mode == "platform_manual":
        if not isinstance(actual, dict) or not actual.get("selection_status"):
            errors.append("platform music selection status missing")
        elif actual.get("selection_status") == "SELECTED" and not actual.get("track_name"):
            errors.append("selected platform music requires track_name")
    return {"schema_version": "3.0", "mode": mode, "status": "PASS" if not errors else "INCOMPLETE", "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate music plan or published track record")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--file", type=Path, required=True)
    receipt = sub.add_parser("receipt")
    receipt.add_argument("--package", type=Path, required=True)
    receipt.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    result = validate_plan(root, args.file.resolve()) if args.command == "plan" else validate_publish_receipt(root, args.package.resolve(), args.receipt.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

