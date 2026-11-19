"""Account-scoped durable editing drafts. Saving never invokes a job."""
from __future__ import annotations

import csv
import json
import math
import re
import threading
from datetime import datetime
import os
from pathlib import Path

ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
STORE = ROOT / "data" / "workbench_drafts.json"
_LOCK = threading.RLock()


class DraftConflict(ValueError):
    def __init__(self, current: dict):
        super().__init__("草稿已在另一页面更新，请选择保留当前输入或读取服务器版本。")
        self.current = current


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def _scope(account_id: str, video_id: str, action: str) -> str:
    from task_runner import ACTIONS
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", value) or value in {".", ".."}
           for value in (account_id, video_id, action)):
        raise ValueError("invalid draft scope")
    if action not in {"SAVE_PRODUCTION_REQUEST", "COMPILE_VIDEO_TASK_PACKAGE", "GENERATE_FLOVA_VIDEO"} or action not in ACTIONS:
        raise ValueError("only production editing drafts are supported")
    profiles = _read(ROOT / "data" / "account_profiles.json", {}).get("profiles", [])
    if not any(item.get("account_id") == account_id for item in profiles):
        raise ValueError("unknown account profile")
    with (ROOT / "data" / "content_registry.csv").open(encoding="utf-8-sig", newline="") as handle:
        if not any(row.get("video_id") == video_id for row in csv.DictReader(handle)):
            raise ValueError("project does not exist")
    mapping = ROOT / "data" / "account_content_map.csv"
    with mapping.open(encoding="utf-8-sig", newline="") as handle:
        owner = next((row.get("account_id") for row in csv.DictReader(handle) if row.get("video_id") == video_id), "scenery-main")
    if owner != account_id:
        raise ValueError("project does not belong to this account")
    return "|".join((account_id, video_id, action))


def _clean(action: str, values: dict) -> dict:
    from task_runner import ACTIONS
    if not isinstance(values, dict):
        raise ValueError("values must be an object")
    result = {}
    for field in ACTIONS[action].get("fields", []):
        name, kind = field["name"], field.get("type")
        if kind == "checkbox" or name not in values:
            continue
        value = values[name]
        if kind == "asset_picker":
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError("asset_ids must be a list of strings")
            result[name] = value[:100]
        elif isinstance(value, str):
            result[name] = value[:8000]
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result[name] = value
        elif value is None:
            result[name] = ""
        else:
            raise ValueError(f"invalid draft field: {name}")
    return result


def load_draft(account_id: str, video_id: str, action: str) -> dict:
    key = _scope(account_id, video_id, action)
    with _LOCK:
        item = _read(STORE, {}).get(key, {"values": {}, "version": 0, "updated_at": ""})
        return {**item, "values": _clean(action, item.get("values", {}))}


def save_draft(payload: dict) -> dict:
    account, video, action = (payload.get(name, "") for name in ("account_id", "video_id", "action"))
    key = _scope(account, video, action)
    values = _clean(action, payload.get("values"))
    version = payload.get("expected_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise ValueError("expected_version must be a non-negative integer")
    with _LOCK:
        data = _read(STORE, {})
        current = data.get(key, {"values": {}, "version": 0, "updated_at": ""})
        if version != current["version"]:
            raise DraftConflict(current)
        record = {"values": values, "version": version + 1,
                  "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        data[key] = record
        STORE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STORE.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(STORE)
        return record
