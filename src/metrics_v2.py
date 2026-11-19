from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime
import os
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
CHECKPOINTS = {"first_visible", "2h", "24h", "72h", "delayed"}
WINDOW_STATUSES = {"on_time", "delayed", "manual", "unavailable"}
CONTENT_TYPES = {"IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO", "NARRATED_EXPLAINER"}
COUNT_FIELDS = (
    "plays", "likes", "comments", "collects", "shares", "new_followers",
)
RATE_FIELDS = (
    "swipe_away_rate", "caption_expand_rate", "completion_rate",
    "retention_2s", "retention_5s",
)
OPTIONAL_NUMBER_FIELDS = (
    "avg_images_viewed", "avg_watch_s", *RATE_FIELDS,
)
SNAPSHOT_FIELDS = [
    "snapshot_id", "video_id", "content_type", "identity_status", "checkpoint", "snapshot_type", "window_status", "captured_at",
    "published_at", "work_url", *COUNT_FIELDS, "avg_images_viewed",
    "swipe_away_rate", "caption_expand_rate", "avg_watch_s", "completion_rate",
    "retention_2s", "retention_5s", "like_rate", "comment_rate",
    "collect_rate", "share_rate", "follow_rate", "field_availability",
    "source_evidence_path", "source_evidence_sha256", "notes",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _cell(row.get(field)) for field in SNAPSHOT_FIELDS})


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _number(value: Any, field: str, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric or empty")
    try:
        parsed = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric or empty") from exc
    if not math.isfinite(float(parsed)) or parsed < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    if field in RATE_FIELDS and parsed > 1:
        raise ValueError(f"{field} must use a 0..1 ratio, not a percentage")
    return parsed


def _iso(value: Any, field: str, required: bool = False) -> str:
    if value in (None, ""):
        if required:
            raise ValueError(f"{field} is required")
        return ""
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return text


def normalize_snapshot(video_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("metrics"), dict):
        raw = {**raw, **raw["metrics"]}
    content_value = str(raw.get("content_type", "")).strip().upper()
    if content_value == "IMAGE_CAROUSEL":
        raw["content_type"] = content_value
    snapshot_type = str(raw.get("snapshot_type", ""))
    if not raw.get("checkpoint"):
        raw["checkpoint"] = "first_visible" if snapshot_type in {"first_visible_delayed_2h", "first_observed_visible"} else "delayed"
    if not raw.get("window_status"):
        raw["window_status"] = "delayed" if raw["checkpoint"] == "first_visible" else "manual"
    if str(raw.get("identity_status", "")).startswith("MATCHED"):
        raw["identity_status"] = "MATCHED"
    if not raw.get("field_availability") and raw.get("unavailable_fields"):
        raw["field_availability"] = "unavailable=" + ",".join(str(item) for item in raw["unavailable_fields"])
    content_type = str(raw.get("content_type", "")).strip().upper()
    checkpoint = str(raw.get("checkpoint", "")).strip()
    window_status = str(raw.get("window_status", "manual")).strip()
    identity_status = str(raw.get("identity_status", "PENDING")).strip().upper()
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"unsupported content_type: {content_type}")
    if checkpoint not in CHECKPOINTS:
        raise ValueError(f"unsupported checkpoint: {checkpoint}")
    if window_status not in WINDOW_STATUSES:
        raise ValueError(f"unsupported window_status: {window_status}")
    if identity_status not in {"MATCHED", "PENDING", "MISMATCH"}:
        raise ValueError(f"unsupported identity_status: {identity_status}")
    if identity_status == "MISMATCH":
        raise ValueError("MISMATCH identity cannot be recorded against this video_id")

    row: dict[str, Any] = {
        "video_id": video_id,
        "content_type": content_type,
        "identity_status": identity_status,
        "checkpoint": checkpoint,
        "snapshot_type": checkpoint,
        "window_status": window_status,
        "captured_at": _iso(raw.get("captured_at"), "captured_at", required=True),
        "published_at": _iso(raw.get("published_at"), "published_at"),
        "work_url": str(raw.get("work_url") or ""),
        "field_availability": str(raw.get("field_availability") or ""),
        "source_evidence_path": str(raw.get("source_evidence_path") or ""),
        "source_evidence_sha256": "",
        "notes": str(raw.get("notes") or ""),
    }
    for field in COUNT_FIELDS:
        row[field] = _number(raw.get(field), field, integer=True)
    for field in OPTIONAL_NUMBER_FIELDS:
        row[field] = _number(raw.get(field), field)

    plays = row["plays"]
    for source, target in (
        ("likes", "like_rate"), ("comments", "comment_rate"),
        ("collects", "collect_rate"), ("shares", "share_rate"),
        ("new_followers", "follow_rate"),
    ):
        value = row[source]
        row[target] = round(value / plays, 6) if plays not in (None, 0) and value is not None else None
    return row


def append_snapshot(root: Path, video_id: str, raw: dict[str, Any]) -> Path:
    content = root / "content" / video_id
    if not content.exists():
        raise ValueError(f"unknown video_id directory: {video_id}")
    path = content / "metrics" / "post_snapshots.csv"
    jsonl_path = content / "metrics" / "post_snapshots.jsonl"
    rows = _read_csv(path)
    row = normalize_snapshot(video_id, raw)
    evidence_value = row["source_evidence_path"]
    if not evidence_value:
        raise ValueError("source_evidence_path is required")
    evidence = Path(evidence_value)
    evidence = evidence if evidence.is_absolute() else root / evidence
    if not evidence.exists():
        raise ValueError(f"source evidence missing: {evidence}")
    digest = __import__("hashlib").sha256(evidence.read_bytes()).hexdigest()
    row["source_evidence_sha256"] = digest
    identity_payload = f"{video_id}|{row['captured_at']}|{digest}".encode("utf-8")
    row["snapshot_id"] = "sha256:" + __import__("hashlib").sha256(identity_payload).hexdigest()
    if any(existing.get("snapshot_id") == row["snapshot_id"] for existing in rows):
        raise ValueError(f"duplicate snapshot: {row['snapshot_id']}")
    rows.append(row)
    _write_csv(path, rows)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return path


def summarize(root: Path, video_id: str) -> dict[str, Any]:
    path = root / "content" / video_id / "metrics" / "post_snapshots.csv"
    rows = _read_csv(path)
    if not rows:
        raise ValueError("no snapshots available")
    latest = max(rows, key=lambda row: row.get("captured_at", ""))
    return {
        "video_id": video_id,
        "snapshot_count": len(rows),
        "latest_checkpoint": latest.get("checkpoint", ""),
        "latest_captured_at": latest.get("captured_at", ""),
        "latest": {key: latest.get(key, "") for key in SNAPSHOT_FIELDS if key not in {"video_id"}},
        "decision_status": "READY_FOR_72H_REVIEW" if any(row.get("checkpoint") == "72h" for row in rows) else "WAITING_FOR_72H",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append-only Douyin post metrics")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--video-id", required=True)
    record.add_argument("--snapshot-json", type=Path, required=True)
    report = sub.add_parser("summary")
    report.add_argument("--video-id", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    try:
        if args.command == "record":
            raw = json.loads(args.snapshot_json.read_text(encoding="utf-8"))
            raw.setdefault("source_evidence_path", str(args.snapshot_json.resolve()))
            print(append_snapshot(root, args.video_id, raw))
        else:
            print(json.dumps(summarize(root, args.video_id), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
