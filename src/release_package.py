from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path("G:/抖音视频")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_sha256(package: dict[str, Any]) -> str:
    payload = {key: value for key, value in package.items() if key != "package_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _artifact_path(root: Path, value: Any) -> Path | None:
    if isinstance(value, (str, Path)):
        path = Path(value)
    elif isinstance(value, dict):
        candidate = value.get("absolute_path") or value.get("path") or value.get("local_path")
        if not isinstance(candidate, (str, Path)) or not str(candidate).strip():
            return None
        path = Path(candidate)
    else:
        return None
    return path if path.is_absolute() else root / path


def _manifest_artifact_paths(root: Path, manifest: dict[str, Any]) -> list[Path]:
    artifacts = manifest.get("artifacts", {})
    values: list[Any] = []
    for key in ("video", "cover", "captions", "narration", "contact_sheet"):
        value = artifacts.get(key)
        if value:
            values.append(value)
    images = artifacts.get("images") or []
    if isinstance(images, list):
        values.extend(images)
    unique: list[Path] = []
    seen: set[str] = set()
    for value in values:
        candidate = _artifact_path(root, value)
        if candidate is None:
            continue
        resolved = str(candidate.resolve()).lower()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(candidate)
    return unique


def build_release_package(root: Path, video_id: str, release_copy: Path) -> dict[str, Any]:
    base = root / "content" / video_id
    fixed = [
        base / "brief.md",
        base / "hypothesis_card.md",
        base / "production" / "route_plan.json",
        base / "production" / "shot_list.csv",
        base / "production" / "material_manifest.csv",
        base / "production" / "production_manifest.json",
        base / "qa" / "qa_result.json",
        release_copy,
    ]
    missing = [str(path) for path in fixed if not path.exists()]
    if missing:
        raise ValueError("required release inputs missing: " + ", ".join(missing))
    manifest = json.loads((base / "production" / "production_manifest.json").read_text(encoding="utf-8"))
    artifacts = _manifest_artifact_paths(root, manifest)
    missing_artifacts = [str(path) for path in artifacts if not path.exists()]
    if missing_artifacts:
        raise ValueError("release artifacts missing: " + ", ".join(missing_artifacts))
    files = []
    for path in [*fixed, *artifacts]:
        rel = _relative(root, path)
        if any(item["path"] == rel for item in files):
            continue
        files.append({"path": rel, "sha256": file_sha256(path), "bytes": path.stat().st_size})
    route_plan = json.loads((base / "production" / "route_plan.json").read_text(encoding="utf-8"))
    route = route_plan.get("route")
    ordered_values = manifest.get("artifacts", {}).get("images", []) if route == "IMAGE_CAROUSEL" else [manifest.get("artifacts", {}).get("video")]
    ordered_values = [value for value in ordered_values if value]
    final_artifacts = []
    for ordinal, value in enumerate(ordered_values, start=1):
        candidate = _artifact_path(root, value)
        if candidate is None:
            raise ValueError(f"release artifact {ordinal} has no usable path")
        final_artifacts.append({
            "ordinal": ordinal,
            "path": _relative(root, candidate),
            "sha256": file_sha256(candidate),
            "bytes": candidate.stat().st_size,
        })
    package: dict[str, Any] = {
        "schema_version": "3.0",
        "video_id": video_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "route": route,
        "files": files,
        "final_artifacts": final_artifacts,
        "release_copy": {"path": _relative(root, release_copy), "sha256": file_sha256(release_copy)},
        "music_policy": route_plan.get("music_mode", "none"),
        "publish_boundary": "prepare-only; final Publish click requires separate user confirmation",
    }
    package["package_sha256"] = package_sha256(package)
    return package


def validate_release_package(root: Path, package_path: Path) -> list[str]:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if package_sha256(package) != package.get("package_sha256"):
        errors.append("package_sha256 mismatch")
    for item in package.get("files", []):
        path = root / item.get("path", "")
        if not path.exists():
            errors.append(f"missing release file: {path}")
        elif file_sha256(path) != item.get("sha256"):
            errors.append(f"release file changed: {item.get('path')}")
    if not package.get("files"):
        errors.append("release package has no files")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or validate a hash-locked release package")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--video-id", required=True)
    build.add_argument("--release-copy", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "build":
            package = build_release_package(root, args.video_id, args.release_copy.resolve())
            output = root / "content" / args.video_id / "approvals" / "release_package.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
            print(output)
        else:
            errors = validate_release_package(root, args.package.resolve())
            for error in errors:
                print(f"ERROR: {error}")
            print("release_package=" + ("PASS" if not errors else "BLOCKED"))
            return 0 if not errors else 2
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
