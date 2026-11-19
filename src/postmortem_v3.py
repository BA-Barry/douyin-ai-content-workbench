from __future__ import annotations

import argparse
import csv
import json
import sys
import os
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def choose(rows: list[dict[str, str]], names: set[str]) -> dict[str, str] | None:
    candidates = [row for row in rows if (row.get("checkpoint") or row.get("snapshot_type")) in names]
    return max(candidates, key=lambda row: row.get("captured_at", "")) if candidates else None


def build_postmortem(root: Path, video_id: str, baseline_video_id: str, hypothesis_id: str, next_single_variable: str) -> dict[str, Any]:
    rows = read_rows(root / "content" / video_id / "metrics" / "post_snapshots.csv")
    baseline_rows = read_rows(root / "content" / baseline_video_id / "metrics" / "post_snapshots.csv") if baseline_video_id else []
    first = choose(rows, {"first_visible", "FIRST_VISIBLE"})
    h24 = choose(rows, {"24h", "H24"})
    h72 = choose(rows, {"72h", "H72"})
    baseline_h72 = choose(baseline_rows, {"72h", "H72"})
    latest = max(rows, key=lambda row: row.get("captured_at", "")) if rows else None
    facts: list[str] = []
    if latest:
        facts.append(f"latest snapshot={latest.get('captured_at')} plays={latest.get('plays') or 'unavailable'}")
    decision = "INCONCLUSIVE"
    reason = "H72 snapshot is not available"
    if h72:
        plays = number(h72.get("plays"))
        if plays is None or plays < 300:
            reason = "H72 plays are unavailable or below the 300-play minimum"
        elif not baseline_h72:
            reason = "baseline H72 snapshot is unavailable"
        else:
            reason = "H72 and baseline are available; master must evaluate the frozen hypothesis without inferring platform causality"
    return {
        "schema_version": "3.0", "video_id": video_id,
        "content_route": "IMAGE_CAROUSEL", "hypothesis_id": hypothesis_id,
        "baseline_video_id": baseline_video_id,
        "snapshot_refs": {
            "first_visible": first.get("snapshot_id") if first else None,
            "h24": h24.get("snapshot_id") if h24 else None,
            "h72": h72.get("snapshot_id") if h72 else None,
            "baseline_h72": baseline_h72.get("snapshot_id") if baseline_h72 else None,
        },
        "facts": facts, "inferences": [], "hypothesis_decision": decision,
        "decision_reason": reason, "retain": [], "stop": [],
        "next_single_variable": next_single_variable,
        "held_constants_next": [], "remaining_unknowns": [],
        "status": "READY_FOR_MASTER_DECISION" if h72 and baseline_h72 else "WAITING_FOR_EVIDENCE",
    }


def validate_postmortem(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("video_id", "content_route", "hypothesis_id", "snapshot_refs", "facts", "inferences", "hypothesis_decision", "next_single_variable"):
        if field not in report:
            errors.append(f"missing {field}")
    if report.get("hypothesis_decision") not in {"KEEP", "STOP", "INCONCLUSIVE"}:
        errors.append("invalid hypothesis_decision")
    if report.get("hypothesis_decision") in {"KEEP", "STOP"} and not report.get("snapshot_refs", {}).get("h72"):
        errors.append("KEEP/STOP requires H72 evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a fail-closed H72 postmortem draft")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--baseline-video-id", default="")
    parser.add_argument("--hypothesis-id", required=True)
    parser.add_argument("--next-single-variable", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_postmortem(args.root.resolve(), args.video_id, args.baseline_video_id, args.hypothesis_id, args.next_single_variable)
    errors = validate_postmortem(report)
    if errors:
        print(json.dumps({"status": "BLOCKED", "errors": errors}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
