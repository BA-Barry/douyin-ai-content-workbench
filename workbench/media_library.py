"""Local media library and project binding helpers for the workbench.

The library is a shared asset base, not a second workflow state machine.  Files
are copied into the project's ``assets/library`` and every project consumes
them through an auditable binding manifest inside its production directory.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import threading
import uuid
from datetime import datetime
import os
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
LIBRARY_ROOT = ROOT / "assets" / "library"
MANIFEST = ROOT / "data" / "media_library.json"
CONTENT_ROOT = ROOT / "content"
MAX_ASSET_BYTES = 512 * 1024 * 1024
ALLOWED_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif",
    ".mp4", ".mov", ".m4v", ".webm", ".mkv",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
}
ALLOWED_KINDS = {"image", "video", "audio"}
ALLOWED_SOURCE_TYPES = {"USER_UPLOAD", "PROJECT_FILE", "PUBLIC_REFERENCE", "GENERATED"}
ALLOWED_RIGHTS = {"OWNED", "LICENSED", "PUBLIC_REFERENCE_ONLY", "PENDING_REVIEW"}
ALLOWED_ROLES = {
    "STYLE_REFERENCE", "COMPOSITION_REFERENCE", "CHARACTER_IDENTITY",
    "SCENE_IDENTITY", "CAMERA_MOTION_REFERENCE", "FIRST_FRAME", "LAST_FRAME",
    "CONTENT_FACT_REFERENCE", "SOURCE_TRANSFORM", "AUDIO_REFERENCE",
}
ALLOWED_STRATEGIES = {"AUTO", "NONE", "USE_EXISTING", "GENERATE_KEYFRAMES", "GENERATE_ELEMENTS", "EXTRACT_FROM_REFERENCE", "MIXED"}
ALLOWED_VIDEO_MODES = {"AUTO", "TEXT_TO_VIDEO", "FIRST_FRAME_TO_VIDEO", "FIRST_LAST_FRAME", "MULTIMODAL_TO_VIDEO", "VIDEO_EDIT"}
_LOCK = threading.RLock()


def configure(root: Path) -> None:
    """Point the library at a test/project root without changing callers."""
    global ROOT, LIBRARY_ROOT, MANIFEST, CONTENT_ROOT
    ROOT = Path(root)
    LIBRARY_ROOT = ROOT / "assets" / "library"
    MANIFEST = ROOT / "data" / "media_library.json"
    CONTENT_ROOT = ROOT / "content"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load() -> dict[str, Any]:
    if not MANIFEST.is_file():
        return {"schema_version": "1.0", "updated_at": "", "items": []}
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload.get("items"), list):
        payload["items"] = []
    payload.setdefault("schema_version", "1.0")
    return payload


def _save(payload: dict[str, Any]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    payload["schema_version"] = "1.0"
    payload["updated_at"] = _now()
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(MANIFEST)


def _safe_project_id(value: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError("invalid project id")
    if not (CONTENT_ROOT / value).is_dir():
        raise ValueError("project does not exist")
    return value


def _safe_asset_id(value: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"asset-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}", value):
        raise ValueError("invalid asset id")
    return value


def _clean_name(value: str) -> str:
    name = Path(str(value or "asset")).name.strip().replace("\x00", "")
    if not name:
        name = "asset"
    stem = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "-", Path(name).stem).strip(".-")[:90] or "asset"
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("unsupported media file type")
    return f"{stem}{suffix}"


def _kind_for(filename: str, declared: str = "") -> str:
    declared = str(declared or "").strip().lower()
    if declared in ALLOWED_KINDS:
        return declared
    mime = mimetypes.guess_type(filename)[0] or ""
    kind = mime.split("/", 1)[0]
    if kind not in ALLOWED_KINDS:
        raise ValueError("unable to determine media type")
    return kind


def _normalize_metadata(metadata: dict[str, Any], filename: str) -> dict[str, Any]:
    source_type = str(metadata.get("source_type") or "USER_UPLOAD").strip().upper()
    rights_status = str(metadata.get("rights_status") or "PENDING_REVIEW").strip().upper()
    role = str(metadata.get("role") or "STYLE_REFERENCE").strip().upper()
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError("invalid source type")
    if rights_status not in ALLOWED_RIGHTS:
        raise ValueError("invalid rights status")
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid asset role")
    return {
        "name": str(metadata.get("name") or Path(filename).stem).strip()[:120] or Path(filename).stem,
        "kind": _kind_for(filename, str(metadata.get("kind") or "")),
        "source_type": source_type,
        "source_locator": str(metadata.get("source_locator") or "local_upload").strip()[:1000],
        "rights_status": rights_status,
        "role": role,
        "retain": str(metadata.get("retain") or "").strip()[:2000],
        "change": str(metadata.get("change") or "").strip()[:2000],
        "external_upload_allowed": bool(metadata.get("external_upload_allowed") is True),
        "notes": str(metadata.get("notes") or "").strip()[:2000],
    }


def import_stream(stream: BinaryIO, length: int, metadata: dict[str, Any]) -> dict[str, Any]:
    if length <= 0 or length > MAX_ASSET_BYTES:
        raise ValueError("asset must be between 1 byte and 512 MB")
    filename = _clean_name(str(metadata.get("filename") or metadata.get("name") or "asset"))
    normalized = _normalize_metadata(metadata, filename)
    asset_id = f"asset-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    folder = LIBRARY_ROOT / asset_id
    target = folder / filename
    folder.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    remaining = length
    try:
        with target.open("wb") as handle:
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("asset upload ended before declared length")
                handle.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
        item = {
            "id": asset_id,
            **normalized,
            "filename": filename,
            "stored_path": target.relative_to(ROOT).as_posix(),
            "size_bytes": length,
            "sha256": digest.hexdigest(),
            "project_ids": [],
            "status": "ACTIVE",
            "created_at": _now(),
            "updated_at": _now(),
        }
        with _LOCK:
            payload = _load()
            payload["items"].insert(0, item)
            _save(payload)
        return public_item(item)
    except Exception:
        if target.exists():
            target.unlink()
        if folder.exists():
            folder.rmdir()
        raise


def import_existing(path_value: str, metadata: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(path_value or "").strip())
    if not source.is_absolute() or not source.is_file():
        raise ValueError("existing media path does not exist")
    filename = _clean_name(source.name)
    payload = {**metadata, "filename": filename, "source_type": metadata.get("source_type") or "PROJECT_FILE", "source_locator": str(source)}
    with source.open("rb") as stream:
        return import_stream(stream, source.stat().st_size, payload)


def public_item(item: dict[str, Any]) -> dict[str, Any]:
    result = dict(item)
    result["preview_url"] = f"/library-asset/{item['id']}"
    return result


def catalog(*, project_id: str = "", include_trashed: bool = False) -> list[dict[str, Any]]:
    with _LOCK:
        items = list(_load().get("items", []))
    if project_id:
        _safe_project_id(project_id)
        items = [item for item in items if project_id in item.get("project_ids", [])]
    if not include_trashed:
        items = [item for item in items if item.get("status") != "TRASHED"]
    return [public_item(item) for item in items]


def resolve_asset(asset_id: str) -> Path:
    asset_id = _safe_asset_id(asset_id)
    with _LOCK:
        item = next((entry for entry in _load().get("items", []) if entry.get("id") == asset_id), None)
    if not item or item.get("status") == "TRASHED":
        raise FileNotFoundError(asset_id)
    candidate = (ROOT / str(item.get("stored_path") or "")).resolve()
    allowed = LIBRARY_ROOT.resolve()
    if allowed not in candidate.parents or not candidate.is_file():
        raise FileNotFoundError(asset_id)
    return candidate


def binding_path(project_id: str) -> Path:
    return CONTENT_ROOT / _safe_project_id(project_id) / "production" / "assets" / "asset_bindings.json"


def bindings(project_id: str) -> dict[str, Any]:
    path = binding_path(project_id)
    if not path.is_file():
        return {"schema_version": "1.0", "video_id": project_id, "asset_ids": [], "items": [], "updated_at": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload.setdefault("asset_ids", [])
    payload.setdefault("items", [])
    return payload


def bind_assets(project_id: str, asset_ids: list[str]) -> dict[str, Any]:
    project_id = _safe_project_id(project_id)
    normalized_ids = list(dict.fromkeys(_safe_asset_id(value) for value in asset_ids if value))
    with _LOCK:
        library = _load()
        by_id = {item.get("id"): item for item in library.get("items", []) if item.get("status") != "TRASHED"}
        missing = [asset_id for asset_id in normalized_ids if asset_id not in by_id]
        if missing:
            raise ValueError(f"unknown active assets: {', '.join(missing)}")
        for item in library.get("items", []):
            projects = list(item.get("project_ids", []))
            if item.get("id") in normalized_ids and project_id not in projects:
                projects.append(project_id)
            elif item.get("id") not in normalized_ids and project_id in projects:
                projects.remove(project_id)
            item["project_ids"] = projects
            item["updated_at"] = _now()
        _save(library)
        selected = [by_id[asset_id] for asset_id in normalized_ids]
    payload = {
        "schema_version": "1.0",
        "video_id": project_id,
        "asset_ids": normalized_ids,
        "items": [
            {
                "asset_id": item["id"], "name": item.get("name", ""), "kind": item.get("kind", ""),
                "role": item.get("role", ""), "rights_status": item.get("rights_status", ""),
                "retain": item.get("retain", ""), "change": item.get("change", ""),
                "external_upload_allowed": bool(item.get("external_upload_allowed")),
                "sha256": item.get("sha256", ""), "stored_path": item.get("stored_path", ""),
            }
            for item in selected
        ],
        "updated_at": _now(),
    }
    path = binding_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return payload


def set_status(asset_id: str, status: str) -> dict[str, Any]:
    asset_id = _safe_asset_id(asset_id)
    status = str(status or "").strip().upper()
    if status not in {"ACTIVE", "TRASHED"}:
        raise ValueError("invalid asset status")
    with _LOCK:
        payload = _load()
        item = next((entry for entry in payload.get("items", []) if entry.get("id") == asset_id), None)
        if not item:
            raise FileNotFoundError(asset_id)
        item["status"] = status
        item["updated_at"] = _now()
        _save(payload)
    return public_item(item)


def decide_asset_strategy(
    project_id: str,
    route: str,
    prompt: str,
    requested_strategy: str = "AUTO",
    requested_video_mode: str = "AUTO",
    asset_ids: list[str] | None = None,
) -> dict[str, Any]:
    route = str(route or "").strip().upper()
    strategy = str(requested_strategy or "AUTO").strip().upper()
    video_mode = str(requested_video_mode or "AUTO").strip().upper()
    if strategy not in ALLOWED_STRATEGIES:
        raise ValueError("invalid asset strategy")
    if video_mode not in ALLOWED_VIDEO_MODES:
        raise ValueError("invalid video mode")
    current = bindings(project_id)
    selected_ids = asset_ids if asset_ids is not None else current.get("asset_ids", [])
    with _LOCK:
        active = {item.get("id"): item for item in _load().get("items", []) if item.get("status") != "TRASHED"}
    selected = [active[item_id] for item_id in selected_ids if item_id in active]
    roles = {item.get("role", "") for item in selected}
    kinds = {item.get("kind", "") for item in selected}
    normalized_prompt = str(prompt or "").lower()
    reasons: list[str] = []

    if route == "IMAGE_CAROUSEL":
        resolved = "USE_EXISTING" if selected else "NONE"
        if strategy != "AUTO":
            resolved = strategy
        mode = "IMAGE_REFERENCE" if selected else "TEXT_TO_IMAGE"
        reasons.append("图片路线直接生成完整逐图提示词；素材仅作为可选参考或原始变换输入")
    else:
        if strategy == "AUTO":
            if selected:
                resolved = "MIXED" if len(kinds) > 1 or "CAMERA_MOTION_REFERENCE" in roles else "USE_EXISTING"
                reasons.append("已绑定素材，优先复用并按角色约束，不重复生成相同锚点")
            elif any(signal in normalized_prompt for signal in ("同一人物", "人物一致", "角色一致", "首帧", "尾帧", "固定场景", "产品一致", "服装一致")):
                resolved = "GENERATE_KEYFRAMES"
                reasons.append("主题要求人物、场景或起止画面一致，先生成关键视觉锚点")
            else:
                resolved = "NONE"
                reasons.append("未绑定素材且没有一致性硬要求，避免无必要图片前置造成静态感")
        else:
            resolved = strategy
            reasons.append("采用工作台明确指定的素材策略")

        if video_mode == "AUTO":
            if "FIRST_FRAME" in roles and "LAST_FRAME" in roles:
                mode = "FIRST_LAST_FRAME"
            elif "FIRST_FRAME" in roles or resolved == "GENERATE_KEYFRAMES":
                mode = "FIRST_FRAME_TO_VIDEO"
            elif "video" in kinds or len(selected) > 1:
                mode = "MULTIMODAL_TO_VIDEO"
            else:
                mode = "TEXT_TO_VIDEO"
        else:
            mode = video_mode

    requires_image_subtask = route != "IMAGE_CAROUSEL" and resolved in {"GENERATE_KEYFRAMES", "GENERATE_ELEMENTS"}
    requires_external_upload_approval = any(not bool(item.get("external_upload_allowed")) for item in selected)
    decision = {
        "schema_version": "1.0",
        "video_id": project_id,
        "route": route,
        "asset_strategy": resolved,
        "generation_mode": mode,
        "bound_asset_ids": [item.get("id") for item in selected],
        "bound_roles": sorted(role for role in roles if role),
        "requires_image_subtask": requires_image_subtask,
        "requires_visual_approval": requires_image_subtask or bool(selected),
        "requires_external_upload_approval": requires_external_upload_approval,
        "reason": "；".join(reasons),
        "created_at": _now(),
    }
    return decision
