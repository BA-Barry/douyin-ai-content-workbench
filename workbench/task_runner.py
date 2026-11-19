"""Persistent, allow-listed job runner for the local Douyin workbench.

The workbench must be able to perform useful work without becoming an arbitrary
shell or a publish bot. Every action is explicit and project-scoped. Flova
generation may upload only specifically approved reference files; no action
logs in to a platform or clicks Publish.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WORKBENCH_DIR = Path(__file__).resolve().parent
if str(WORKBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_DIR))
SRC_DIR = WORKBENCH_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skill_router import build_skill_plan
from codex_dispatcher import enqueue_plan
import media_library
import flova_runtime
from project_runtime import project_python


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
PYTHON = project_python(ROOT)
JOB_STORE = ROOT / "data" / "workbench_jobs.json"
JOB_OUTPUT = ROOT / "workspace" / "workbench" / "jobs"
_LOCK = threading.RLock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="douyin-workbench")
OFFLINE_MODE = False


ACTIONS: dict[str, dict[str, Any]] = {
    "WORKFLOW_AUDIT": {
        "label": "运行全项目审计",
        "category": "治理",
        "description": "执行 workflow_control audit，检查唯一状态源与项目结构。",
        "requires_project": False,
        "writes_project": False,
        "external_action": False,
        "fields": [],
    },
    "PROJECT_TRACE": {
        "label": "生成项目证据追踪",
        "category": "治理",
        "description": "按路线检查研究、制作、质检、发布与指标证据，报告写入工作台任务目录。",
        "requires_project": True,
        "writes_project": False,
        "external_action": False,
        "fields": [],
    },
    "SAVE_PRODUCTION_REQUEST": {
        "label": "保存要求并自动编排 Skills",
        "category": "制作",
        "description": "按项目路线和内容要求自动选择相关 Skills，同时保存可审计的制作请求与执行计划。",
        "requires_project": True,
        "writes_project": True,
        "external_action": False,
        "fields": [
            {"name": "prompt", "label": "主题、视觉方向与不可接受项", "type": "textarea", "required": True},
            {"name": "image_count", "label": "图片 / 镜头数", "type": "number", "default": 6},
            {"name": "duration_seconds", "label": "目标时长（秒）", "type": "number", "default": 20},
            {"name": "asset_ids", "label": "绑定素材", "type": "asset_picker", "required": False},
            {"name": "asset_strategy", "label": "素材策略", "type": "select", "default": "AUTO", "options": ["AUTO", "NONE", "USE_EXISTING", "GENERATE_KEYFRAMES", "GENERATE_ELEMENTS", "EXTRACT_FROM_REFERENCE", "MIXED"]},
            {"name": "video_mode", "label": "视频生成模式", "type": "select", "default": "AUTO", "options": ["AUTO", "TEXT_TO_VIDEO", "FIRST_FRAME_TO_VIDEO", "FIRST_LAST_FRAME", "MULTIMODAL_TO_VIDEO", "VIDEO_EDIT"]},
            {"name": "video_provider", "label": "视频服务商 / 提示词路线", "type": "select", "default": "AUTO", "options": ["AUTO", "FLOVA", "JIMENG", "MINIMAX_H3"]},
            {"name": "voice_mode", "label": "声音策略", "type": "select", "options": ["none", "sample-first", "user-voice"]},
            {"name": "music_mode", "label": "音乐策略", "type": "select", "options": ["platform_manual", "local_cleared", "none"]},
        ],
    },
    "COMPILE_VIDEO_TASK_PACKAGE": {
        "label": "生成视频任务确认卡",
        "category": "制作",
        "description": "按当前计划目标生成 Flova、Seedance 或 MiniMax H3 的任务确认卡；不创建项目、不上传素材、不消耗积分。",
        "requires_project": True,
        "writes_project": True,
        "external_action": False,
        "fields": [],
    },
    "GENERATE_FLOVA_VIDEO": {
        "label": "提交已确认的 Flova 视频任务",
        "category": "制作",
        "description": "仅当前 Flova 路线可执行；确认模型与包含积分上限后提交，保留任务句柄并回收本地成片。当前零积分将阻断，不购买或升级。",
        "requires_project": True,
        "writes_project": True,
        "external_action": True,
        "fields": [
            {"name": "model", "label": "确认卡上的具体模型", "type": "text", "required": True},
            {"name": "budget_mode", "label": "预算来源", "type": "select", "default": "INCLUDED_ONLY", "options": ["INCLUDED_ONLY"]},
            {"name": "max_credits", "label": "本任务可消耗的免费或订阅内积分上限", "type": "number", "required": True, "default": 0},
            {"name": "reference_upload_ack", "label": "如有引用素材，我批准本确认卡列明素材上传至 Flova", "type": "checkbox", "required": False},
            {"name": "generation_ack", "label": "我批准当前确认卡的模型、时长、清晰度与包含积分上限；不允许额外付费", "type": "checkbox", "required": True},
        ],
    },
    "PROBE_MEDIA": {
        "label": "运行媒体技术检测",
        "category": "质检",
        "description": "用 ffprobe / ffmpeg 检查编码、尺寸、时长、黑帧、冻结、静音与响度。",
        "requires_project": True,
        "writes_project": False,
        "external_action": False,
        "fields": [{"name": "media_path", "label": "项目内媒体路径", "type": "text", "required": True}],
    },
    "PIXELLE_VIDEO_GENERATE": {
        "label": "用 Pixelle 生成视频",
        "category": "制作",
        "description": "历史实验动作；当前视频生成路线已冻结为即梦 / Seedance，因此禁止新建任务。",
        "enabled": False,
        "disabled_reason": "当前视频生成入口为即梦 / Seedance；Pixelle 只保留历史工程读取，不再允许提交新任务。",
        "requires_project": True,
        "writes_project": True,
        "external_action": True,
        "fields": [
            {"name": "text", "label": "主题或完整文案", "type": "textarea", "required": True},
            {"name": "mode", "label": "文案模式", "type": "select", "options": ["fixed", "generate"]},
            {"name": "title", "label": "视频标题", "type": "text", "required": False},
            {"name": "n_scenes", "label": "分镜数", "type": "number", "default": 5},
            {"name": "frame_template", "label": "竖屏模板", "type": "text", "default": "1080x1920/image_default.html", "required": True},
            {"name": "tts_workflow", "label": "TTS 工作流", "type": "text", "default": "selfhost/tts_edge.json", "required": False},
            {"name": "media_workflow", "label": "图像 / 视频工作流", "type": "text", "default": "selfhost/image_flux.json", "required": False},
            {"name": "prompt_prefix", "label": "视觉提示词前缀", "type": "textarea", "required": False},
            {"name": "provider_ack", "label": "我确认当前 Pixelle 的模型/接口配置及可能产生的费用", "type": "checkbox", "required": True},
        ],
    },
    "BUILD_RELEASE_PACKAGE": {
        "label": "构建哈希锁定发布包",
        "category": "发布准备",
        "description": "校验必要证据并锁定最终素材、顺序、文案和哈希。",
        "requires_project": True,
        "writes_project": True,
        "external_action": False,
        "fields": [{"name": "release_copy", "label": "项目内发布文案路径", "type": "text", "required": True}],
    },
    "VALIDATE_RELEASE_PACKAGE": {
        "label": "校验当前发布包",
        "category": "发布准备",
        "description": "验证发布包哈希及其绑定文件是否仍未变化。",
        "requires_project": True,
        "writes_project": False,
        "external_action": False,
        "fields": [],
    },
    "BUILD_PREPARE_JOB": {
        "label": "生成 Prepare-only 任务",
        "category": "发布准备",
        "description": "在最终用户批准已绑定当前发布包后，生成上传前任务；不会打开平台或上传。",
        "requires_project": True,
        "writes_project": True,
        "external_action": False,
        "fields": [],
    },
    "BUILD_UPLOAD_PLAN": {
        "label": "生成抖音上传命令预览",
        "category": "发布准备",
        "description": "参考 social-auto-upload 生成不可执行的图文/视频命令预览，保持最终发布确认门。",
        "requires_project": True,
        "writes_project": False,
        "external_action": False,
        "fields": [],
    },
    "METRICS_SUMMARY": {
        "label": "汇总作品指标",
        "category": "数据",
        "description": "读取只追加指标快照并生成当前作品摘要。",
        "requires_project": True,
        "writes_project": False,
        "external_action": False,
        "fields": [],
    },
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_video_id(value: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError("invalid video id")
    if not (ROOT / "content" / value).is_dir():
        raise ValueError("project does not exist")
    return value


def _project_path(video_id: str, value: str, *, must_exist: bool = True) -> Path:
    base = (ROOT / "content" / _safe_video_id(video_id)).resolve()
    candidate = Path(str(value or "").strip())
    candidate = candidate if candidate.is_absolute() else ROOT / candidate
    candidate = candidate.resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("path must stay inside the selected project")
    if must_exist and not candidate.is_file():
        raise ValueError(f"file does not exist: {candidate}")
    return candidate


def _load_store() -> dict[str, Any]:
    if not JOB_STORE.exists():
        return {"schema_version": 1, "updated_at": "", "jobs": []}
    try:
        data = json.loads(JOB_STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        return {"schema_version": 1, "updated_at": "", "jobs": []}
    return data


def _save_store(data: dict[str, Any]) -> None:
    JOB_STORE.parent.mkdir(parents=True, exist_ok=True)
    data["schema_version"] = 1
    data["updated_at"] = now_iso()
    data["jobs"] = data.get("jobs", [])[:500]
    temporary = JOB_STORE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(JOB_STORE)


def action_catalog() -> list[dict[str, Any]]:
    return [{"id": action_id, **definition} for action_id, definition in ACTIONS.items()]


def list_jobs(video_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
    with _LOCK:
        jobs = list(_load_store().get("jobs", []))
    if video_id:
        jobs = [job for job in jobs if job.get("video_id") == video_id]
    return jobs[: max(1, min(int(limit), 500))]


def get_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        job = next((item for item in _load_store().get("jobs", []) if item.get("job_id") == job_id), None)
    if not job:
        raise FileNotFoundError(job_id)
    return job


def _replace_job(job: dict[str, Any]) -> None:
    with _LOCK:
        data = _load_store()
        jobs = data.setdefault("jobs", [])
        jobs[:] = [item for item in jobs if item.get("job_id") != job["job_id"]]
        jobs.insert(0, job)
        _save_store(data)


def _validate_parameters(action_id: str, video_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    definition = ACTIONS[action_id]
    if definition["requires_project"]:
        video_id = _safe_video_id(video_id)
    elif video_id:
        video_id = _safe_video_id(video_id)
    cleaned: dict[str, Any] = {}
    for field in definition.get("fields", []):
        name = field["name"]
        value = parameters.get(name, field.get("default", ""))
        if field.get("type") == "checkbox":
            value = value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}
            if field.get("required") and value is not True:
                raise ValueError(f"{field['label']} is required")
            cleaned[name] = value
            continue
        if field.get("type") == "asset_picker":
            if isinstance(value, list):
                cleaned[name] = [str(item).strip() for item in value if str(item).strip()][:100]
            else:
                cleaned[name] = [item.strip() for item in str(value or "").split(",") if item.strip()][:100]
            continue
        if field.get("required") and (value is None or str(value).strip() == ""):
            raise ValueError(f"{field['label']} is required")
        if field.get("type") == "number":
            value = max(0, min(float(value or 0), 10000))
            if value.is_integer():
                value = int(value)
        elif isinstance(value, str):
            value = value.strip()[:8000]
        cleaned[name] = value
    if action_id == "PROBE_MEDIA":
        cleaned["media_path"] = str(_project_path(video_id, cleaned["media_path"]))
    if action_id == "BUILD_RELEASE_PACKAGE":
        cleaned["release_copy"] = str(_project_path(video_id, cleaned["release_copy"]))
    return cleaned


def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    action_id = str(payload.get("actionId", "")).strip().upper()
    if action_id not in ACTIONS:
        raise ValueError("unknown or disallowed action")
    if ACTIONS[action_id].get("enabled") is False:
        raise ValueError(str(ACTIONS[action_id].get("disabled_reason") or "action is disabled"))
    video_id = str(payload.get("videoId", "")).strip()
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    parameters = _validate_parameters(action_id, video_id, parameters)
    confirmation = None
    if action_id == "GENERATE_FLOVA_VIDEO":
        if OFFLINE_MODE:
            raise ValueError("离线模式不允许调用 Flova")
        confirmation = flova_runtime.confirmation(ROOT, video_id)
        flova_runtime.validate_approval(parameters, confirmation)
    job_id = f"wb-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "action_id": action_id,
        "action_label": ACTIONS[action_id]["label"],
        "video_id": video_id,
        "status": "QUEUED",
        "created_at": now_iso(),
        "started_at": "",
        "completed_at": "",
        "parameters": parameters,
        "progress": {"current": 0, "total": 1, "percentage": 0, "message": "等待执行"},
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "artifacts": [],
        "external_action": bool(ACTIONS[action_id].get("external_action")),
        "publish_clicked": False,
    }
    if confirmation is not None:
        job.update({"confirmation": confirmation, "provider": {"name": "FLOVA"},
                    "pending_actions": [], "media": [], "evidence_mode": "REAL",
                    "next_action": "启动当前已批准任务；平台账户将再次核验"})
    with _LOCK:
        if action_id == "GENERATE_FLOVA_VIDEO":
            prior = next((item for item in _load_store().get("jobs", [])
                          if item.get("action_id") == action_id and item.get("video_id") == video_id
                          and item.get("status") in flova_runtime.ACTIVE_STATES), None)
            if prior:
                return prior
        _replace_job(job)
        return job


def _run_command(command: list[str], timeout: int = 180) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _execute_action(job: dict[str, Any]) -> tuple[int, str, str, list[str]]:
    action_id = job["action_id"]
    video_id = job.get("video_id", "")
    parameters = job.get("parameters", {})
    output_dir = JOB_OUTPUT / job["job_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[str] = []

    if action_id == "WORKFLOW_AUDIT":
        return (*_run_command([str(PYTHON), str(ROOT / "src" / "workflow_control.py"), "audit"]), artifacts)

    if action_id == "PROJECT_TRACE":
        report = output_dir / "trace_report.json"
        command = [str(PYTHON), str(ROOT / "src" / "workflow_trace.py"), "--video-id", video_id, "--output", str(report)]
        code, stdout, stderr = _run_command(command)
        if report.exists():
            artifacts.append(report.relative_to(ROOT).as_posix())
        return code, stdout, stderr, artifacts

    if action_id == "PIXELLE_VIDEO_GENERATE":
        if parameters.get("provider_ack") is not True:
            return 2, "", "Pixelle provider/cost acknowledgement is required", artifacts
        request_payload = {
            "text": parameters["text"],
            "mode": parameters.get("mode") or "fixed",
            "title": parameters.get("title") or None,
            "n_scenes": int(parameters.get("n_scenes") or 5),
            "frame_template": parameters["frame_template"],
            "tts_workflow": parameters.get("tts_workflow") or None,
            "media_workflow": parameters.get("media_workflow") or None,
            "prompt_prefix": parameters.get("prompt_prefix") or None,
            "video_fps": 30,
            "bgm_path": None,
            "bgm_volume": 0.0,
        }
        try:
            request = Request(
                "http://127.0.0.1:8502/api/video/generate/async",
                data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                submitted = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
            return 2, "", f"Pixelle API is unavailable or rejected the request: {detail}", artifacts
        pixelle_task_id = submitted.get("task_id")
        if not pixelle_task_id:
            return 2, json.dumps(submitted, ensure_ascii=False), "Pixelle did not return a task_id", artifacts
        task_result: dict[str, Any] = {}
        for _ in range(1200):
            try:
                with urlopen(f"http://127.0.0.1:8502/api/tasks/{pixelle_task_id}", timeout=10) as response:
                    task_result = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, TimeoutError) as exc:
                return 2, "", f"Pixelle task polling failed: {exc}", artifacts
            status = str(task_result.get("status", "")).lower()
            if status in {"completed", "failed", "cancelled"}:
                break
            time.sleep(1)
        status = str(task_result.get("status", "")).lower()
        if status != "completed":
            return 2, json.dumps(task_result, ensure_ascii=False, indent=2), task_result.get("error") or "Pixelle task did not complete", artifacts
        video_url = (task_result.get("result") or {}).get("video_url")
        if not video_url:
            return 2, json.dumps(task_result, ensure_ascii=False, indent=2), "Pixelle completed without a video URL", artifacts
        output = ROOT / "content" / video_id / "production" / "pixelle" / "final.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urlopen(video_url, timeout=120) as response:
                output.write_bytes(response.read())
        except (HTTPError, URLError, TimeoutError) as exc:
            return 2, json.dumps(task_result, ensure_ascii=False, indent=2), f"failed to copy Pixelle result into project: {exc}", artifacts
        artifacts.append(output.relative_to(ROOT).as_posix())
        receipt = output_dir / "pixelle_result.json"
        _write_json(receipt, {"request": request_payload, "pixelle_task": task_result, "project_output": str(output)})
        artifacts.append(receipt.relative_to(ROOT).as_posix())
        return 0, json.dumps(task_result, ensure_ascii=False, indent=2), "", artifacts

    if action_id == "SAVE_PRODUCTION_REQUEST":
        output = ROOT / "content" / video_id / "production" / "workbench_request.json"
        plan_output = ROOT / "content" / video_id / "production" / "skill_plan.json"
        dispatch_output = ROOT / "content" / video_id / "production" / "dispatch_receipt.json"
        media_library.configure(ROOT)
        binding = media_library.bind_assets(video_id, parameters.get("asset_ids", []))
        registry_path = ROOT / "data" / "content_registry.csv"
        route = str(parameters.get("content_route") or "IMAGE_CAROUSEL")
        if registry_path.is_file():
            with registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
                route = next((row.get("content_type", "") for row in csv.DictReader(handle) if row.get("video_id") == video_id), route)
        asset_decision = media_library.decide_asset_strategy(
            video_id,
            route,
            str(parameters.get("prompt") or ""),
            str(parameters.get("asset_strategy") or "AUTO"),
            str(parameters.get("video_mode") or "AUTO"),
            binding.get("asset_ids", []),
        )
        asset_strategy_output = ROOT / "content" / video_id / "production" / "asset_strategy.json"
        _write_json(asset_strategy_output, asset_decision)
        skill_plan = build_skill_plan(ROOT, video_id, {**parameters, "_asset_decision": asset_decision})
        _write_json(plan_output, skill_plan)
        dispatch = enqueue_plan(
            video_id,
            plan_output,
            root=ROOT,
            store=ROOT / "data" / "codex_dispatch_queue.json",
        )
        request = {
            "schema_version": "1.0",
            "video_id": video_id,
            "created_at": now_iso(),
            "source": "local_workbench",
            "route_parameters": parameters,
            "asset_strategy": asset_decision,
            "status": {
                "READY": "QUEUED_FOR_CODEX",
                "WAITING_APPROVAL": "WAITING_APPROVAL",
            }.get(dispatch["state"], "BLOCKED"),
            "skill_plan_path": plan_output.relative_to(ROOT).as_posix(),
            "dispatch_id": dispatch["dispatch_id"],
            "dispatch_state": dispatch["state"],
            "external_action": False,
            "notice": "The workbench planned and queued the relevant Skills. A Codex task may claim eligible image work; paid services, private uploads, voice, platform upload and publishing remain gated.",
        }
        _write_json(output, request)
        _write_json(dispatch_output, dispatch)
        artifacts.extend([
            output.relative_to(ROOT).as_posix(),
            plan_output.relative_to(ROOT).as_posix(),
            dispatch_output.relative_to(ROOT).as_posix(),
            asset_strategy_output.relative_to(ROOT).as_posix(),
            (ROOT / "content" / video_id / "production" / "assets" / "asset_bindings.json").relative_to(ROOT).as_posix(),
        ])
        code = 0 if skill_plan["status"] == "READY_FOR_CODEX" else 2
        stderr = "" if code == 0 else f"required Skills are missing: {', '.join(skill_plan['missing_required_skills'])}"
        return code, json.dumps({"request": request, "skill_plan": skill_plan, "dispatch": dispatch}, ensure_ascii=False, indent=2), stderr, artifacts

    if action_id == "COMPILE_VIDEO_TASK_PACKAGE":
        prompt_package = ROOT / "content" / video_id / "production" / "prompt_package.json"
        output = ROOT / "content" / video_id / "production" / "video_task_package.json"
        if not prompt_package.is_file():
            return 2, "", "approved production/prompt_package.json does not exist", artifacts
        command = [
            str(PYTHON),
            str(SRC_DIR / "video_task_compiler.py"),
            "--input", str(prompt_package),
            "--output", str(output),
        ]
        code, stdout, stderr = _run_command(command)
        if output.is_file():
            artifacts.append(output.relative_to(ROOT).as_posix())
        return code, stdout, stderr, artifacts

    if action_id == "PROBE_MEDIA":
        report = output_dir / "media_probe.json"
        command = [str(PYTHON), str(ROOT / "src" / "pipeline_tools" / "qa_probe.py"), parameters["media_path"], "--output", str(report)]
        code, stdout, stderr = _run_command(command, timeout=300)
        if report.exists():
            artifacts.append(report.relative_to(ROOT).as_posix())
        return code, stdout, stderr, artifacts

    if action_id == "BUILD_RELEASE_PACKAGE":
        command = [str(PYTHON), str(ROOT / "src" / "release_package.py"), "build", "--video-id", video_id, "--release-copy", parameters["release_copy"]]
        code, stdout, stderr = _run_command(command)
        package = ROOT / "content" / video_id / "approvals" / "release_package.json"
        if package.exists():
            artifacts.append(package.relative_to(ROOT).as_posix())
        return code, stdout, stderr, artifacts

    if action_id == "VALIDATE_RELEASE_PACKAGE":
        package = ROOT / "content" / video_id / "approvals" / "release_package.json"
        if not package.is_file():
            return 2, "", "release package does not exist", artifacts
        return (*_run_command([str(PYTHON), str(ROOT / "src" / "release_package.py"), "validate", "--package", str(package)]), artifacts)

    if action_id == "BUILD_PREPARE_JOB":
        output = ROOT / "content" / video_id / "approvals" / "prepare_job.json"
        command = [str(PYTHON), str(ROOT / "src" / "prepare_only.py"), "--video-id", video_id, "--output", str(output)]
        code, stdout, stderr = _run_command(command)
        if output.exists():
            artifacts.append(output.relative_to(ROOT).as_posix())
        return code, stdout, stderr, artifacts

    if action_id == "BUILD_UPLOAD_PLAN":
        prepare_path = ROOT / "content" / video_id / "approvals" / "prepare_job.json"
        if not prepare_path.is_file():
            return 2, "", "prepare_job.json is required before creating an upload plan", artifacts
        prepare = json.loads(prepare_path.read_text(encoding="utf-8"))
        route = prepare.get("route")
        uploads = [item.get("absolute_path") for item in prepare.get("upload_artifacts", []) if item.get("absolute_path")]
        if route == "IMAGE_CAROUSEL":
            command_preview = ["sau", "douyin", "upload-note", "--account", "<selected-account>", "--images", *uploads, "--title", "<approved-title>", "--note", "<approved-copy>", "--headed"]
        else:
            command_preview = ["sau", "douyin", "upload-video", "--account", "<selected-account>", "--file", uploads[0] if uploads else "<video-path>", "--title", "<approved-title>", "--desc", "<approved-copy>", "--headed"]
        plan = {
            "schema_version": "1.0",
            "video_id": video_id,
            "created_at": now_iso(),
            "adapter": "dreammis/social-auto-upload",
            "route": route,
            "command_preview": command_preview,
            "executable": False,
            "requires_fresh_user_confirmation": True,
            "publish_capable_upstream": True,
            "publish_clicked": False,
            "reason": "Upstream upload commands can publish immediately; the workbench only records a preview.",
        }
        output = output_dir / "social_upload_plan.json"
        _write_json(output, plan)
        artifacts.append(output.relative_to(ROOT).as_posix())
        return 0, json.dumps(plan, ensure_ascii=False, indent=2), "", artifacts

    if action_id == "METRICS_SUMMARY":
        command = [str(PYTHON), str(ROOT / "src" / "metrics_v2.py"), "summary", "--video-id", video_id]
        return (*_run_command(command), artifacts)

    return 2, "", "action has no implementation", artifacts


def _execute_job(job_id: str) -> None:
    job = get_job(job_id)
    if job.get("action_id") == "GENERATE_FLOVA_VIDEO":
        flova_runtime.execute(job, root=ROOT, persist=_replace_job)
        return
    try:
        code, stdout, stderr, artifacts = _execute_action(job)
        job["returncode"] = code
        job["stdout"] = stdout[-40000:]
        job["stderr"] = stderr[-20000:]
        job["artifacts"] = artifacts
        job["status"] = "SUCCEEDED" if code == 0 else "BLOCKED"
        job["progress"] = {
            "current": 1,
            "total": 1,
            "percentage": 100,
            "message": "完成" if code == 0 else "前置条件未通过或检查失败",
        }
    except subprocess.TimeoutExpired as exc:
        job["status"] = "FAILED"
        job["stderr"] = f"task timed out: {exc}"
        job["progress"]["message"] = "执行超时"
    except Exception as exc:  # pragma: no cover - defensive job boundary
        job["status"] = "FAILED"
        job["stderr"] = f"{type(exc).__name__}: {exc}"
        job["progress"]["message"] = "执行失败"
    finally:
        job["completed_at"] = now_iso()
        _replace_job(job)


def submit_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        job = get_job(job_id)
        if job.get("action_id") == "GENERATE_FLOVA_VIDEO" and OFFLINE_MODE:
            raise ValueError("离线模式不允许调用 Flova")
        if job.get("status") == "RUNNING":
            return job
        if job.get("status") != "QUEUED":
            raise ValueError("only queued jobs can be started")
        job["status"] = "RUNNING"
        job["started_at"] = now_iso()
        job["progress"] = {"percentage": None, "message": "正在执行"}
        _replace_job(job)
        _EXECUTOR.submit(_execute_job, job_id)
        return job


def recover_interrupted_jobs() -> int:
    """On server restart, expose interrupted jobs; never silently send a new run."""
    with _LOCK:
        count = 0
        data = _load_store()
        for job in data.get("jobs", []):
            if job.get("status") == "RUNNING":
                video = job.get("action_id") == "GENERATE_FLOVA_VIDEO"
                job["status"] = "RECOVERABLE" if video else "FAILED"
                job["progress"] = {"percentage": None, "message": "工作台上次运行中断，未自动重发"}
                job["next_action"] = "恢复原 Flova 任务" if video else "核对已有产物后重试"
                count += 1
        if count:
            _save_store(data)
        return count


def recover_job(job_id: str) -> dict[str, Any]:
    return _continue_video_job(job_id)


def resolve_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("action_id"), str) or not isinstance(payload.get("option_id"), str):
        raise ValueError("action_id and option_id are required")
    return _continue_video_job(job_id, {"action_id": payload["action_id"], "option_id": payload["option_id"]})


def _continue_video_job(job_id: str, resolution=None) -> dict[str, Any]:
    with _LOCK:
        if OFFLINE_MODE:
            raise ValueError("离线模式不允许恢复外部任务")
        job = get_job(job_id)
        if job.get("action_id") != "GENERATE_FLOVA_VIDEO":
            raise ValueError("this job does not support Flova recovery")
        if job.get("status") == "RUNNING":
            return job
        allowed = {"WAITING_USER"} if resolution else {"RECOVERABLE", "WAITING_USER"}
        if job.get("status") not in allowed:
            raise ValueError("current job state does not allow recovery")
        if resolution:
            action = next((p for p in job.get("pending_actions", []) if p.get("action_id") == resolution["action_id"]), None)
            if not action or not any(o.get("id") == resolution["option_id"] for o in action.get("options", [])):
                raise ValueError("stale or invalid pending action option")
        job["status"] = "RUNNING"
        job["completed_at"] = ""
        job["progress"] = {"percentage": None, "message": "正在恢复原任务"}
        _replace_job(job)
        _EXECUTOR.submit(flova_runtime.execute, job, root=ROOT, persist=_replace_job, recover=True, resolution=resolution)
        return job


def cancel_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job.get("status") != "QUEUED":
        raise ValueError("only queued jobs can be cancelled")
    job["status"] = "CANCELLED"
    job["completed_at"] = now_iso()
    job["progress"] = {"current": 0, "total": 1, "percentage": 0, "message": "已取消"}
    _replace_job(job)
    return job


def resolve_job_artifact(job_id: str, name: str) -> Path:
    if not re.fullmatch(r"wb-[A-Za-z0-9-]+", job_id) or name != Path(name).name:
        raise ValueError("invalid job artifact path")
    base = (JOB_OUTPUT / job_id).resolve()
    candidate = (base / name).resolve()
    if candidate.parent != base or not candidate.is_file():
        raise FileNotFoundError(name)
    return candidate
