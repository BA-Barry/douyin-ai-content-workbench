from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime
import os
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from metrics_v2 import append_snapshot
from workflow_trace import production_errors as route_production_errors


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
REGISTRY_FIELDS = [
    "video_id", "state", "owner", "title", "hypothesis", "brief_path",
    "manifest_path", "created_at", "updated_at", "blockers", "next_action",
    "content_type", "pillar", "baseline_video_id", "hypothesis_id",
    "published_at", "work_url",
]
STATES = [
    "IDEA", "RESEARCHING", "RESEARCHED", "BRIEF_DRAFT", "BRIEF_APPROVED",
    "PRODUCING", "QA_REVIEW", "READY_FOR_USER", "USER_APPROVED",
    "PREPARED_IN_DOUYIN", "PUBLISHED", "REVIEW_2H", "REVIEW_24H",
    "REVIEW_72H", "CLOSED",
]
TRANSITIONS = {
    "IDEA": {"RESEARCHING"},
    "RESEARCHING": {"RESEARCHED"},
    "RESEARCHED": {"BRIEF_DRAFT"},
    "BRIEF_DRAFT": {"BRIEF_APPROVED"},
    "BRIEF_APPROVED": {"PRODUCING"},
    "PRODUCING": {"QA_REVIEW"},
    "QA_REVIEW": {"PRODUCING", "READY_FOR_USER"},
    "READY_FOR_USER": {"PRODUCING", "USER_APPROVED"},
    "USER_APPROVED": {"PREPARED_IN_DOUYIN"},
    "PREPARED_IN_DOUYIN": {"PUBLISHED"},
    "PUBLISHED": {"REVIEW_2H"},
    "REVIEW_2H": {"REVIEW_24H"},
    "REVIEW_24H": {"REVIEW_72H"},
    "REVIEW_72H": {"CLOSED"},
    "CLOSED": set(),
}
REQUIRED_DEEP_FIELDS = {
    "url", "creator", "captured_at", "duration_seconds", "hook_pattern",
    "first_frame", "visual_pattern", "pace_notes", "proof_element",
    "caption_style", "audio_style", "cta_pattern", "comment_signal",
    "learning_hypothesis", "do_not_copy",
}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_registry(root: Path) -> list[dict[str, str]]:
    rows, fields = read_csv(root / "data" / "content_registry.csv")
    missing = set(REGISTRY_FIELDS) - set(fields)
    if missing:
        raise RuntimeError(f"registry missing fields: {', '.join(sorted(missing))}")
    return rows


def save_registry(root: Path, rows: list[dict[str, str]]) -> None:
    write_csv(root / "data" / "content_registry.csv", rows, REGISTRY_FIELDS)


def append_event(root: Path, event: dict) -> None:
    path = root / "data" / "workflow_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def latest_catalog(root: Path) -> Path:
    choices = sorted((root / "research").glob("douyin_sample_snapshot_expanded_*.csv"))
    if not choices:
        choices = sorted((root / "research").glob("douyin_sample_snapshot_*.csv"))
    return choices[-1] if choices else root / "research" / "missing_catalog.csv"


def research_audit(root: Path) -> tuple[dict[str, int | str], list[str]]:
    catalog_path = latest_catalog(root)
    catalog, catalog_fields = read_csv(catalog_path)
    deep_path = root / "research" / "reference_videos.csv"
    deep, deep_fields = read_csv(deep_path)
    contrasts, _ = read_csv(root / "research" / "contrast_pairs.csv")

    errors: list[str] = []
    catalog_ids = [row.get("id", "").strip() for row in catalog if row.get("id", "").strip()]
    groups = {row.get("sample_group", "").strip() for row in catalog if row.get("sample_group", "").strip()}
    catalog_creators = {row.get("creator", "").strip() for row in catalog if row.get("creator", "").strip()}
    low_heat = 0
    for row in catalog:
        try:
            if float(row.get("likes", "")) < 5000:
                low_heat += 1
        except ValueError:
            pass

    if len(catalog) < 60:
        errors.append(f"目录样本不足：{len(catalog)}/60")
    if len(groups) < 6:
        errors.append(f"品类不足：{len(groups)}/6")
    if len(catalog_creators) < 20:
        errors.append(f"目录创作者不足：{len(catalog_creators)}/20")
    if len(catalog_ids) != len(set(catalog_ids)):
        errors.append("目录样本存在重复ID")
    if {"sample_group", "id", "likes", "title", "creator"} - set(catalog_fields):
        errors.append("目录样本缺少必要字段")

    missing_deep_fields = REQUIRED_DEEP_FIELDS - set(deep_fields)
    if missing_deep_fields:
        errors.append(f"深看CSV缺字段：{', '.join(sorted(missing_deep_fields))}")
    deep_urls = [row.get("url", "").strip() for row in deep if row.get("url", "").strip()]
    deep_creators = {row.get("creator", "").strip() for row in deep if row.get("creator", "").strip()}
    usable_comment_signals = 0
    for row in deep:
        signal = row.get("comment_signal", "").strip().lower()
        if signal and not any(marker in signal for marker in ("超时", "未读取", "unavailable")):
            usable_comment_signals += 1
    if len(deep) < 12:
        errors.append(f"深看样本不足：{len(deep)}/12")
    if len(deep_creators) < 4:
        errors.append(f"深看创作者不足：{len(deep_creators)}/4")
    if usable_comment_signals < 8:
        errors.append(f"有效评论需求信号不足：{usable_comment_signals}/8")
    if len(deep_urls) != len(set(deep_urls)):
        errors.append("深看样本存在重复URL")
    for index, row in enumerate(deep, start=2):
        for field in REQUIRED_DEEP_FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"深看第{index}行缺少 {field}")
    if low_heat < 2:
        errors.append(f"低热度对照不足：{low_heat}/2")
    if len(contrasts) < 3:
        errors.append(f"高低热度对照组不足：{len(contrasts)}/3")

    stats: dict[str, int | str] = {
        "catalog_file": str(catalog_path),
        "catalog_count": len(catalog),
        "category_count": len(groups),
        "catalog_creator_count": len(catalog_creators),
        "deep_count": len(deep),
        "deep_creator_count": len(deep_creators),
        "usable_comment_signal_count": usable_comment_signals,
        "low_heat_count": low_heat,
        "contrast_pair_count": len(contrasts),
    }
    return stats, errors


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_dir(root: Path, video_id: str) -> Path:
    return root / "content" / video_id


def approval_path(root: Path, video_id: str, phase: str) -> Path:
    return content_dir(root, video_id) / "approvals" / f"{phase}_approval.json"


def has_user_approval(root: Path, video_id: str, phase: str) -> bool:
    path = approval_path(root, video_id, phase)
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("approved") is True and data.get("approved_by") == "user"


def production_audit(root: Path, video_id: str) -> list[str]:
    return route_production_errors(root, video_id)


def latest_qa_report(root: Path, video_id: str) -> Path | None:
    reports = sorted((content_dir(root, video_id) / "qa").glob("qa_report_*.md"))
    return reports[-1] if reports else None


def metrics_has_checkpoint(root: Path, video_id: str, checkpoint: str) -> bool:
    content_rows, _ = read_csv(content_dir(root, video_id) / "metrics" / "post_snapshots.csv")
    if any(row.get("checkpoint") == checkpoint for row in content_rows):
        return True
    rows, _ = read_csv(root / "data" / "metrics_log.csv")
    return any(row.get("video_id") == video_id and row.get("checkpoint") == checkpoint for row in rows)


def gate_errors(root: Path, video_id: str, target: str) -> list[str]:
    if target == "RESEARCHED":
        return research_audit(root)[1]
    if target == "BRIEF_APPROVED":
        errors = []
        brief = content_dir(root, video_id) / "brief.md"
        if not brief.exists() or len(brief.read_text(encoding="utf-8").strip()) < 400:
            errors.append("brief不存在或内容不完整")
        if not has_user_approval(root, video_id, "brief"):
            errors.append("缺少用户brief批准记录")
        return errors
    if target == "QA_REVIEW":
        return production_audit(root, video_id)
    if target == "READY_FOR_USER":
        qa_json = content_dir(root, video_id) / "qa" / "qa_result.json"
        route_plan = content_dir(root, video_id) / "production" / "route_plan.json"
        if route_plan.exists():
            if not qa_json.exists():
                return ["缺少机器可读独立质检结果 qa/qa_result.json"]
            data = json.loads(qa_json.read_text(encoding="utf-8"))
            errors = []
            conclusion = data.get("conclusion", data.get("overall_conclusion"))
            counts = data.get("counts", {})
            blocker_count = data.get("blocker_count", counts.get("blocker_open", 0))
            major_count = data.get("major_count", counts.get("major_open", 0))
            if conclusion not in {"PASS", "PASS_WITH_MINOR"}:
                errors.append("独立质检未通过")
            if int(blocker_count):
                errors.append("独立质检仍含BLOCKER")
            if int(major_count):
                errors.append("独立质检仍含未解决MAJOR")
            expected = data.get("production_manifest_sha256") or data.get("inputs", {}).get("production_manifest", {}).get("sha256")
            manifest = content_dir(root, video_id) / "production" / "production_manifest.json"
            if not expected or not manifest.exists() or expected.lower() != sha256(manifest).lower():
                errors.append("质检结果未绑定当前制作manifest")
            return errors
        report = latest_qa_report(root, video_id)
        if not report:
            return ["缺少独立质检报告"]
        text = report.read_text(encoding="utf-8")
        errors = []
        if "结论：PASS" not in text and "结论: PASS" not in text:
            errors.append("独立质检未判定PASS")
        if "BLOCKER" in text and "BLOCKER |" in text:
            errors.append("独立质检仍含BLOCKER")
        return errors
    if target == "USER_APPROVED":
        if not has_user_approval(root, video_id, "final"):
            return ["缺少用户最终成片批准记录"]
        package = content_dir(root, video_id) / "approvals" / "release_package.json"
        if package.exists():
            package_data = json.loads(package.read_text(encoding="utf-8"))
            approval_data = json.loads(approval_path(root, video_id, "final").read_text(encoding="utf-8"))
            if approval_data.get("release_package_sha256") != package_data.get("package_sha256"):
                return ["用户最终批准未绑定当前release package"]
        return []
    if target == "PREPARED_IN_DOUYIN":
        receipt = content_dir(root, video_id) / "approvals" / "prepare_receipt.json"
        return [] if receipt.exists() else ["缺少抖音发布页准备回执"]
    if target == "PUBLISHED":
        errors = []
        if not has_user_approval(root, video_id, "publish"):
            errors.append("缺少点击发布前的用户动作确认记录")
        receipt = content_dir(root, video_id) / "approvals" / "publish_receipt.json"
        if not receipt.exists():
            errors.append("缺少发布成功回执")
        else:
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if data.get("published") is not True:
                errors.append("发布回执未确认 published=true")
            if not data.get("reported_at"):
                errors.append("发布回执缺少 reported_at")
        return errors
    checkpoint_by_target = {
        "REVIEW_2H": "2h", "REVIEW_24H": "24h", "REVIEW_72H": "72h"
    }
    if target in checkpoint_by_target:
        checkpoint = checkpoint_by_target[target]
        return [] if metrics_has_checkpoint(root, video_id, checkpoint) else [f"缺少{checkpoint}指标记录"]
    if target == "CLOSED":
        postmortem = content_dir(root, video_id) / "metrics" / "postmortem_72h.md"
        return [] if postmortem.exists() else ["缺少72小时复盘"]
    return []


def command_status(args: argparse.Namespace) -> int:
    rows = load_registry(args.root)
    stats, errors = research_audit(args.root)
    print("video_id\tstate\tnext_action")
    for row in rows:
        print(f"{row['video_id']}\t{row['state']}\t{row['next_action']}")
    print("research=" + json.dumps(stats, ensure_ascii=False))
    print(f"research_gate={'PASS' if not errors else 'BLOCKED'}")
    for error in errors:
        print(f"BLOCKED: {error}")
    return 0


def command_audit(args: argparse.Namespace) -> int:
    errors: list[str] = []
    rows = load_registry(args.root)
    ids = [row["video_id"] for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("content_registry存在重复video_id")
    for row in rows:
        if row["state"] not in STATES:
            errors.append(f"{row['video_id']}状态非法：{row['state']}")
        if not resolve(args.root, row["brief_path"]).exists():
            errors.append(f"{row['video_id']} brief缺失")
        if row.get("manifest_path") and not resolve(args.root, row["manifest_path"]).exists():
            errors.append(f"{row['video_id']} manifest缺失")
    _, research_errors = research_audit(args.root)
    errors.extend(research_errors)
    for error in errors:
        print(f"ERROR: {error}")
    print(f"audit={'PASS' if not errors else 'BLOCKED'}")
    return 0 if not errors else 2


def command_transition(args: argparse.Namespace) -> int:
    if args.actor != "master":
        raise RuntimeError("only actor=master may change workflow state")
    rows = load_registry(args.root)
    matches = [row for row in rows if row["video_id"] == args.video_id]
    if not matches:
        raise RuntimeError(f"unknown video_id: {args.video_id}")
    row = matches[0]
    current = row["state"]
    if args.to not in TRANSITIONS.get(current, set()):
        raise RuntimeError(f"illegal transition: {current} -> {args.to}")
    errors = gate_errors(args.root, args.video_id, args.to)
    if errors:
        for error in errors:
            print(f"BLOCKED: {error}")
        return 2
    changed_at = now()
    row["state"] = args.to
    row["updated_at"] = changed_at
    row["blockers"] = ""
    row["next_action"] = args.next_action or "由主控按MASTER_WORKFLOW执行下一阶段"
    manifest = content_dir(args.root, args.video_id) / "production" / "production_manifest.json"
    if manifest.exists():
        row["manifest_path"] = manifest.relative_to(args.root).as_posix()
    save_registry(args.root, rows)
    append_event(args.root, {
        "event": "state_transition", "video_id": args.video_id,
        "from": current, "to": args.to, "actor": args.actor,
        "reason": args.reason, "at": changed_at,
    })
    print(f"state={args.to}")
    return 0


def command_record_approval(args: argparse.Namespace) -> int:
    if args.actor != "master" or args.approved_by != "user":
        raise RuntimeError("approval may only be recorded by master after an explicit user decision")
    path = approval_path(args.root, args.video_id, args.phase)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "video_id": args.video_id, "phase": args.phase, "approved": True,
        "approved_by": "user", "recorded_by": "master", "recorded_at": now(),
        "user_message_excerpt": args.user_message_excerpt,
    }
    if args.release_package_sha256:
        data["release_package_sha256"] = args.release_package_sha256
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    append_event(args.root, {"event": "approval_recorded", **data})
    print(f"approval={path}")
    return 0


def command_record_metrics(args: argparse.Namespace) -> int:
    row = {
        "content_type": args.content_type,
        "checkpoint": args.checkpoint,
        "window_status": args.window_status,
        "captured_at": args.captured_at or now(),
        "published_at": args.published_at,
        "work_url": args.work_url,
        "plays": args.plays,
        "likes": args.likes,
        "comments": args.comments,
        "collects": args.collects,
        "shares": args.shares,
        "new_followers": args.new_followers,
        "avg_images_viewed": args.avg_images_viewed,
        "swipe_away_rate": args.swipe_away_rate,
        "caption_expand_rate": args.caption_expand_rate,
        "avg_watch_s": args.avg_watch_s,
        "completion_rate": args.completion_rate,
        "retention_2s": args.retention_2s,
        "retention_5s": args.retention_5s,
        "field_availability": args.field_availability,
        "source_evidence_path": args.source_evidence_path,
        "notes": args.notes,
    }
    path = append_snapshot(args.root, args.video_id, row)
    print(f"metrics={path}")
    return 0


def command_init(args: argparse.Namespace) -> int:
    rows = load_registry(args.root)
    if any(row["video_id"] == args.video_id for row in rows):
        raise RuntimeError(f"video_id already exists: {args.video_id}")
    folder = content_dir(args.root, args.video_id)
    for name in ("research", "production", "qa", "metrics", "approvals"):
        (folder / name).mkdir(parents=True, exist_ok=True)
    template = args.root / "workflow" / "templates" / "BRIEF_TEMPLATE.md"
    shutil.copyfile(template, folder / "brief.md")
    created = now()
    rows.append({
        "video_id": args.video_id, "state": "IDEA", "owner": "master",
        "title": args.title, "hypothesis": args.hypothesis,
        "brief_path": str((folder / "brief.md").relative_to(args.root)).replace("\\", "/"),
        "manifest_path": "", "created_at": created, "updated_at": created,
        "blockers": "", "next_action": "确认选题后进入RESEARCHING",
        "content_type": args.content_type, "pillar": args.pillar,
        "baseline_video_id": args.baseline_video_id or "",
        "hypothesis_id": args.hypothesis_id or "", "published_at": "", "work_url": "",
    })
    save_registry(args.root, rows)
    append_event(args.root, {"event": "content_initialized", "video_id": args.video_id, "at": created})
    print(f"content_dir={folder}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Douyin workflow control plane")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.set_defaults(func=command_status)
    audit = sub.add_parser("audit")
    audit.set_defaults(func=command_audit)

    transition = sub.add_parser("transition")
    transition.add_argument("--video-id", required=True)
    transition.add_argument("--to", choices=STATES, required=True)
    transition.add_argument("--actor", required=True)
    transition.add_argument("--reason", required=True)
    transition.add_argument("--next-action")
    transition.set_defaults(func=command_transition)

    approval = sub.add_parser("record-approval")
    approval.add_argument("--video-id", required=True)
    approval.add_argument("--phase", choices=["brief", "final", "publish"], required=True)
    approval.add_argument("--actor", required=True)
    approval.add_argument("--approved-by", required=True)
    approval.add_argument("--user-message-excerpt", required=True)
    approval.add_argument("--release-package-sha256")
    approval.set_defaults(func=command_record_approval)

    metrics = sub.add_parser("record-metrics")
    metrics.add_argument("--video-id", required=True)
    metrics.add_argument("--content-type", choices=["IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO", "NARRATED_EXPLAINER"], required=True)
    metrics.add_argument("--checkpoint", choices=["first_visible", "2h", "24h", "72h", "delayed"], required=True)
    metrics.add_argument("--window-status", choices=["on_time", "delayed", "manual", "unavailable"], default="manual")
    metrics.add_argument("--captured-at")
    metrics.add_argument("--published-at")
    metrics.add_argument("--work-url", default="")
    for name in ("plays", "likes", "comments", "collects", "shares", "new_followers"):
        metrics.add_argument(f"--{name.replace('_', '-')}", type=int)
    for name in ("avg_images_viewed", "swipe_away_rate", "caption_expand_rate", "avg_watch_s", "completion_rate", "retention_2s", "retention_5s"):
        metrics.add_argument(f"--{name.replace('_', '-')}", type=float)
    metrics.add_argument("--field-availability", default="")
    metrics.add_argument("--source-evidence-path", default="")
    metrics.add_argument("--notes", default="")
    metrics.set_defaults(func=command_record_metrics)

    init = sub.add_parser("init")
    init.add_argument("--video-id", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--hypothesis", required=True)
    init.add_argument("--content-type", choices=["IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO", "NARRATED_EXPLAINER"], required=True)
    init.add_argument("--pillar", required=True)
    init.add_argument("--baseline-video-id")
    init.add_argument("--hypothesis-id")
    init.set_defaults(func=command_init)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.root = args.root.resolve()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
