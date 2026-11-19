from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
import os
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def build_prepare_job(root: Path, video_id: str) -> dict[str, Any]:
    base = root / "content" / video_id
    package_path = base / "approvals" / "release_package.json"
    approval_path = base / "approvals" / "final_approval.json"
    if not package_path.exists() or not approval_path.exists():
        raise ValueError("release package and final approval are required")
    package = load(package_path)
    approval = load(approval_path)
    package_hash = package.get("package_sha256")
    if not package_hash:
        raise ValueError("release package lacks package_sha256")
    if approval.get("approved") is not True or approval.get("approved_by") != "user":
        raise ValueError("final approval is not an explicit user approval")
    if approval.get("release_package_sha256") != package_hash:
        raise ValueError("final approval is not bound to this release package")
    uploads = []
    for item in package.get("final_artifacts", []):
        path = root / item.get("path", "")
        if not path.exists() or sha256(path) != item.get("sha256"):
            raise ValueError(f"release artifact changed or missing: {path}")
        uploads.append({
            "ordinal": item["ordinal"], "absolute_path": str(path.resolve()),
            "sha256": item["sha256"], "bytes": path.stat().st_size,
        })
    expected = 6 if package.get("route") == "IMAGE_CAROUSEL" else 1
    if len(uploads) != expected:
        raise ValueError(f"{package.get('route')} requires {expected} upload artifact(s)")
    copy = package.get("release_copy", {})
    copy_path = root / copy.get("path", "")
    if not copy_path.exists() or sha256(copy_path) != copy.get("sha256"):
        raise ValueError("release copy changed or missing")
    return {
        "schema_version": "3.0",
        "video_id": video_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "prepare-only",
        "route": package.get("route"),
        "release_package_path": str(package_path.resolve()),
        "release_package_sha256": package_hash,
        "final_approval_path": str(approval_path.resolve()),
        "final_approval_sha256": sha256(approval_path),
        "upload_artifacts": uploads,
        "release_copy_path": str(copy_path.resolve()),
        "release_copy_sha256": copy["sha256"],
        "music_policy": package.get("music_policy", "none"),
        "publish_clicked": False,
        "next_action": "Use the browser to upload/fill only, write prepare_receipt.json, and stop before Publish.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and build a prepare-only browser job")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        job = build_prepare_job(root, args.video_id)
        output = args.output or root / "content" / args.video_id / "approvals" / "prepare_job.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
