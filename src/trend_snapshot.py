"""Validate and append read-only Douyin trend snapshots for the workbench."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
import os
from pathlib import Path


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
TREND_DIR = ROOT / "research" / "trend_monitor"
SNAPSHOTS = TREND_DIR / "snapshots"
LATEST = TREND_DIR / "latest.json"
REQUIRED = {
    "trend_id", "source_type", "source_url", "rank_or_signal", "title", "category",
    "content_form", "facts", "inference", "to_verify", "matched_accounts", "fit_score",
    "fresh_until", "rights_risk", "do_not_copy",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(payload: dict) -> list[str]:
    errors: list[str] = []
    if payload.get("collection_status") not in {"PASS", "PARTIAL", "FAILED"}:
        errors.append("collection_status must be PASS, PARTIAL, or FAILED")
    if not payload.get("captured_at"):
        errors.append("captured_at is required")
    items = payload.get("items")
    if not isinstance(items, list):
        errors.append("items must be an array")
        return errors
    for index, item in enumerate(items):
        missing = sorted(REQUIRED - set(item))
        if missing:
            errors.append(f"item {index} missing: {', '.join(missing)}")
        if not isinstance(item.get("matched_accounts", []), list):
            errors.append(f"item {index} matched_accounts must be an array")
        score = item.get("fit_score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            errors.append(f"item {index} fit_score must be 0..100")
    return errors


def append(payload: dict) -> Path:
    errors = validate(payload)
    if errors:
        raise ValueError("; ".join(errors))
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    stamp = datetime.fromisoformat(payload["captured_at"]).strftime("%Y%m%d_%H%M%S")
    target = SNAPSHOTS / f"trend_{stamp}_{digest}.json"
    if target.exists():
        raise ValueError(f"duplicate snapshot: {target.name}")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "append", "status"])
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(load(LATEST) if LATEST.exists() else {"collection_status": "EMPTY", "items": []}, ensure_ascii=False, indent=2))
        return 0
    if not args.input:
        parser.error("--input is required")
    payload = load(args.input)
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    if args.command == "append":
        print(append(payload))
    else:
        print("trend_snapshot=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
