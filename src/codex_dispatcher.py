"""Auditable, idempotent dispatch queue for Codex media work.

This module bridges a workbench-created ``skill_plan.json`` and a scheduled
Codex task.  It never calls a model, uploads media, or publishes content.  It
only decides whether a plan is eligible, leases one eligible item atomically,
and records completion evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
QUEUE_STORE = ROOT / "data" / "codex_dispatch_queue.json"
QUEUE_STATES = {"READY", "WAITING_APPROVAL", "LEASED", "COMPLETED", "FAILED", "CANCELLED"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_video_id(value: str, root: Path) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError("invalid video id")
    if not (root / "content" / value).is_dir():
        raise ValueError("project does not exist")
    return value


def _inside_project(path_value: str | Path, video_id: str, root: Path, *, must_exist: bool) -> Path:
    project = (root / "content" / _safe_video_id(video_id, root)).resolve()
    path = Path(path_value)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    if path != project and project not in path.parents:
        raise ValueError("path must stay inside the selected project")
    if must_exist and not path.is_file():
        raise ValueError(f"file does not exist: {path}")
    return path


def _empty_store() -> dict[str, Any]:
    return {"schema_version": "1.0", "updated_at": "", "items": []}


def _load(store: Path) -> dict[str, Any]:
    if not store.is_file():
        return _empty_store()
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return _empty_store()
    return data


def _save(store: Path, data: dict[str, Any]) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    data["schema_version"] = "1.0"
    data["updated_at"] = now_iso()
    data["items"] = list(data.get("items", []))[:1000]
    temporary = store.with_suffix(store.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(store)


@contextmanager
def _locked(store: Path) -> Iterator[None]:
    """Use a one-byte advisory lock so workbench and automation cannot race."""

    store.parent.mkdir(parents=True, exist_ok=True)
    lock_path = store.with_suffix(store.suffix + ".lock")
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _approval_gate(video_id: str, root: Path) -> tuple[bool, str, dict[str, Any]]:
    approval_path = root / "content" / video_id / "approvals" / "brief_approval.json"
    brief_path = root / "content" / video_id / "brief.md"
    if not approval_path.is_file():
        return False, "等待 Brief 明确批准", {"mode": "missing", "path": str(approval_path.relative_to(root))}
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "Brief 批准记录无法解析", {"mode": "invalid", "path": str(approval_path.relative_to(root))}
    if approval.get("approved") is not True:
        return False, "Brief 尚未批准", {"mode": "not_approved", "path": str(approval_path.relative_to(root))}

    expected_hash = ""
    expected_rel = f"content/{video_id}/brief.md"
    for artifact in approval.get("approved_artifacts", []):
        if str(artifact.get("path", "")).replace("\\", "/") == expected_rel:
            expected_hash = str(artifact.get("sha256", "")).lower()
            break
    evidence = {
        "path": str(approval_path.relative_to(root)).replace("\\", "/"),
        "approved_at": approval.get("recorded_at", ""),
        "approved_by": approval.get("approved_by", ""),
    }
    if expected_hash:
        if not brief_path.is_file():
            return False, "已批准的 Brief 文件缺失", {**evidence, "mode": "hash_locked", "expected_sha256": expected_hash}
        current_hash = _sha256(brief_path)
        evidence.update({"mode": "hash_locked", "expected_sha256": expected_hash, "current_sha256": current_hash})
        if current_hash != expected_hash:
            return False, "Brief 在批准后发生变化，需要重新确认", evidence
        return True, "Brief 哈希与批准记录一致", evidence
    evidence["mode"] = "legacy_approval"
    return True, "沿用历史批准记录（未绑定 Brief 哈希）", evidence


def _eligibility(plan: dict[str, Any], video_id: str, root: Path) -> tuple[str, str, dict[str, Any]]:
    if str(plan.get("status", "")) != "READY_FOR_CODEX":
        missing = "、".join(str(item) for item in plan.get("missing_required_skills", []) if item)
        return "WAITING_APPROVAL", f"Skill 计划未就绪{f'：{missing}' if missing else ''}", {"mode": "plan_blocked"}
    route = str(plan.get("route", "")).upper()
    if route == "ATMOSPHERE_VIDEO":
        provider = str(plan.get("provider_target", "")).upper()
        provider_label = {"FLOVA": "Flova", "SEEDANCE_2_0": "Seedance 2.0", "MINIMAX_H3": "MiniMax H3"}.get(provider, "Seedance / 即梦等视频服务商")
        return "WAITING_APPROVAL", f"等待确认 {provider_label} 的模型、费用与素材上传范围后再提交", {"mode": "provider_gate", "provider": provider or "UNKNOWN"}
    if route == "NARRATED_EXPLAINER":
        return "WAITING_APPROVAL", "等待确认视频服务商及配音费用、声音权利与上传范围", {"mode": "provider_and_voice_gate"}
    if route != "IMAGE_CAROUSEL":
        return "WAITING_APPROVAL", f"不支持自动执行的路线：{route or 'UNKNOWN'}", {"mode": "unsupported_route"}
    approved, reason, lineage = _approval_gate(video_id, root)
    return ("READY" if approved else "WAITING_APPROVAL"), reason, lineage


def _requeue_stale_items(data: dict[str, Any]) -> int:
    count = 0
    now = _utc_now()
    for item in data.get("items", []):
        if item.get("state") != "LEASED":
            continue
        expiry = _parse_iso(item.get("lease_expires_at", ""))
        if expiry and expiry.astimezone(timezone.utc) <= now:
            item.update({
                "state": "READY",
                "reason": "上一次执行租约超时，已自动回收",
                "worker_id": "",
                "lease_expires_at": "",
                "updated_at": now_iso(),
            })
            count += 1
    return count


def enqueue_plan(
    video_id: str,
    plan_path: str | Path,
    *,
    root: Path = ROOT,
    store: Path | None = None,
) -> dict[str, Any]:
    store = store or (root / "data" / "codex_dispatch_queue.json")
    video_id = _safe_video_id(video_id, root)
    plan_file = _inside_project(plan_path, video_id, root, must_exist=True)
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if str(plan.get("video_id", "")) != video_id:
        raise ValueError("plan video_id does not match selected project")
    plan_hash = _sha256(plan_file)
    state, reason, approval_lineage = _eligibility(plan, video_id, root)
    created = now_iso()
    with _locked(store):
        data = _load(store)
        _requeue_stale_items(data)
        existing = next((item for item in data["items"] if item.get("idempotency_key") == plan_hash), None)
        if existing:
            return dict(existing)
        for prior in data["items"]:
            if prior.get("video_id") == video_id and prior.get("state") in {"READY", "WAITING_APPROVAL", "LEASED", "FAILED"}:
                prior.update({"state": "CANCELLED", "reason": "已被更新的 Skill 计划取代", "updated_at": created, "worker_id": "", "lease_expires_at": ""})
        item = {
            "dispatch_id": f"dispatch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
            "idempotency_key": plan_hash,
            "video_id": video_id,
            "route": str(plan.get("route", "")),
            "plan_path": str(plan_file.relative_to(root)).replace("\\", "/"),
            "plan_sha256": plan_hash,
            "state": state,
            "reason": reason,
            "approval_lineage": approval_lineage,
            "created_at": created,
            "updated_at": created,
            "attempts": 0,
            "worker_id": "",
            "lease_expires_at": "",
            "artifacts": [],
            "errors": [],
        }
        data["items"].insert(0, item)
        _save(store, data)
        return dict(item)


def list_items(*, state: str = "", video_id: str = "", store: Path = QUEUE_STORE) -> list[dict[str, Any]]:
    normalized = state.strip().upper()
    if normalized and normalized not in QUEUE_STATES:
        raise ValueError("unknown queue state")
    with _locked(store):
        data = _load(store)
        if _requeue_stale_items(data):
            _save(store, data)
        items = list(data.get("items", []))
    if normalized:
        items = [item for item in items if item.get("state") == normalized]
    if video_id:
        items = [item for item in items if item.get("video_id") == video_id]
    return items


def claim(worker_id: str, *, lease_minutes: int = 45, store: Path = QUEUE_STORE) -> dict[str, Any] | None:
    worker_id = str(worker_id or "").strip()[:120]
    if not worker_id:
        raise ValueError("worker_id is required")
    lease_minutes = max(5, min(int(lease_minutes), 240))
    with _locked(store):
        data = _load(store)
        changed = bool(_requeue_stale_items(data))
        ready = sorted(
            (item for item in data.get("items", []) if item.get("state") == "READY"),
            key=lambda item: item.get("created_at", ""),
        )
        if not ready:
            if changed:
                _save(store, data)
            return None
        item = ready[0]
        item.update({
            "state": "LEASED",
            "reason": "已由 Codex 执行任务领取",
            "worker_id": worker_id,
            "lease_expires_at": (_utc_now() + timedelta(minutes=lease_minutes)).isoformat(timespec="seconds"),
            "attempts": int(item.get("attempts", 0)) + 1,
            "updated_at": now_iso(),
        })
        _save(store, data)
        return dict(item)


def _owned_item(data: dict[str, Any], dispatch_id: str, worker_id: str) -> dict[str, Any]:
    item = next((entry for entry in data.get("items", []) if entry.get("dispatch_id") == dispatch_id), None)
    if not item:
        raise FileNotFoundError(dispatch_id)
    if item.get("state") != "LEASED":
        raise ValueError("dispatch item is not leased")
    if item.get("worker_id") != worker_id:
        raise PermissionError("dispatch lease belongs to another worker")
    return item


def complete(
    dispatch_id: str,
    worker_id: str,
    artifacts: list[str],
    *,
    root: Path = ROOT,
    store: Path = QUEUE_STORE,
) -> dict[str, Any]:
    if not artifacts:
        raise ValueError("at least one completion artifact is required")
    with _locked(store):
        data = _load(store)
        item = _owned_item(data, dispatch_id, worker_id)
        plan_path = _inside_project(item["plan_path"], item["video_id"], root, must_exist=True)
        if _sha256(plan_path) != item.get("plan_sha256"):
            raise ValueError("skill plan changed after dispatch; enqueue the new plan")
        verified = [
            str(_inside_project(value, item["video_id"], root, must_exist=True).relative_to(root)).replace("\\", "/")
            for value in artifacts
        ]
        item.update({
            "state": "COMPLETED",
            "reason": "Codex 制作任务已完成并登记可核验产物",
            "artifacts": verified,
            "updated_at": now_iso(),
            "lease_expires_at": "",
        })
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["execution"] = {
            "dispatch_id": dispatch_id,
            "worker_id": worker_id,
            "completed_at": item["updated_at"],
            "artifacts": verified,
        }
        plan["execution_status"] = "CODEX_COMPLETED"
        temporary = plan_path.with_suffix(plan_path.suffix + ".tmp")
        temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(plan_path)
        _save(store, data)
        return dict(item)


def fail(dispatch_id: str, worker_id: str, reason: str, *, store: Path = QUEUE_STORE) -> dict[str, Any]:
    reason = str(reason or "").strip()[:2000]
    if not reason:
        raise ValueError("failure reason is required")
    with _locked(store):
        data = _load(store)
        item = _owned_item(data, dispatch_id, worker_id)
        errors = list(item.get("errors", []))
        errors.append({"at": now_iso(), "worker_id": worker_id, "reason": reason})
        item.update({
            "state": "FAILED",
            "reason": reason,
            "errors": errors[-10:],
            "updated_at": now_iso(),
            "lease_expires_at": "",
        })
        _save(store, data)
        return dict(item)


def retry(dispatch_id: str, *, store: Path = QUEUE_STORE) -> dict[str, Any]:
    with _locked(store):
        data = _load(store)
        item = next((entry for entry in data.get("items", []) if entry.get("dispatch_id") == dispatch_id), None)
        if not item:
            raise FileNotFoundError(dispatch_id)
        if item.get("state") != "FAILED":
            raise ValueError("only failed items can be retried")
        item.update({"state": "READY", "reason": "已人工允许重试", "worker_id": "", "lease_expires_at": "", "updated_at": now_iso()})
        _save(store, data)
        return dict(item)


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex media dispatch queue")
    sub = parser.add_subparsers(dest="command", required=True)
    enqueue_parser = sub.add_parser("enqueue")
    enqueue_parser.add_argument("--video-id", required=True)
    enqueue_parser.add_argument("--plan", required=True)
    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--worker-id", required=True)
    claim_parser.add_argument("--lease-minutes", type=int, default=45)
    list_parser = sub.add_parser("list")
    list_parser.add_argument("--state", default="")
    list_parser.add_argument("--video-id", default="")
    complete_parser = sub.add_parser("complete")
    complete_parser.add_argument("--dispatch-id", required=True)
    complete_parser.add_argument("--worker-id", required=True)
    complete_parser.add_argument("--artifact", action="append", default=[])
    fail_parser = sub.add_parser("fail")
    fail_parser.add_argument("--dispatch-id", required=True)
    fail_parser.add_argument("--worker-id", required=True)
    fail_parser.add_argument("--reason", required=True)
    retry_parser = sub.add_parser("retry")
    retry_parser.add_argument("--dispatch-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "enqueue":
        _print(enqueue_plan(args.video_id, args.plan))
    elif args.command == "claim":
        _print(claim(args.worker_id, lease_minutes=args.lease_minutes))
    elif args.command == "list":
        _print({"items": list_items(state=args.state, video_id=args.video_id)})
    elif args.command == "complete":
        _print(complete(args.dispatch_id, args.worker_id, args.artifact))
    elif args.command == "fail":
        _print(fail(args.dispatch_id, args.worker_id, args.reason))
    elif args.command == "retry":
        _print(retry(args.dispatch_id))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # CLI must surface a machine-readable failure.
        _print({"error": type(exc).__name__, "message": str(exc)})
        raise SystemExit(2)
