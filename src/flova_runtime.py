"""Flova CLI adapter. One aggregated CLI invocation owns each remote operation.

No credentials or signed URLs are retained. Local job records are handles and
delivery evidence, not a second copy of Flova's creative project state.
"""
from __future__ import annotations

import csv
import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, build_opener
from project_runtime import configured_path, find_tool

ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
ACTIVE_STATES = {"QUEUED", "RUNNING", "WAITING_USER", "RECOVERABLE"}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_message(value):
    return re.sub(r"https?://\S+", "[远端链接已隐藏]", str(value or ""))[:2000]


def _public_url(value):
    parsed = urlparse(str(value or ""))
    if parsed.scheme == "https" and parsed.hostname in {"flova.ai", "www.flova.ai", "flova.tv", "www.flova.tv"} and not parsed.username:
        return str(value)
    return ""


def _identifier(value):
    value = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", value):
        raise ValueError("平台返回无效任务标识")
    return value


def _inside(path, base):
    path, base = Path(path).resolve(), Path(base).resolve()
    if path != base and base not in path.parents:
        raise ValueError("路径必须保留在项目目录内")
    return path


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def cli(args, *, root=ROOT, cwd=None, on_event=None):
    """Allow-listed callers construct args; returned retry command strings are never executed."""
    exe = find_tool("flova", root)
    if not exe:
        raise FileNotFoundError("Flova CLI 未安装")
    # Authentication storage is managed by the official CLI; do not inspect it.
    env = dict(os.environ)
    cache = configured_path("DOUYIN_CACHE_DIR", root / "cache") / "flova-runtime"
    cache.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(cache), TMP=str(cache), XDG_CACHE_HOME=str(cache))
    process = subprocess.Popen([str(exe), *args], cwd=cwd or root, env=env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if on_event:
        on_event({"type": "process_started", "pid": process.pid})
    errors = []

    def consume_stderr():
        for line in process.stderr:
            text = line.strip()
            event = None
            match = re.search(r"\b(stream_chat_id|task_id)=([A-Za-z0-9_-]+)", text)
            if match:
                event = {"type": "handle", match.group(1): match.group(2)}
            if "flova_event=" in text:
                try:
                    event = json.loads(text.split("flova_event=", 1)[1])
                except json.JSONDecodeError:
                    pass
            if event and on_event:
                on_event(event)
            elif text:
                errors.append(_safe_message(text))
                del errors[:-30]
        process.stderr.close()

    output_parts = []
    def consume_stdout():
        output_parts.append(process.stdout.read())
        process.stdout.close()
    reader = threading.Thread(target=consume_stderr, daemon=True)
    stdout_reader = threading.Thread(target=consume_stdout, daemon=True)
    reader.start()
    stdout_reader.start()
    try:
        process.wait(timeout=960 if args and args[0] in {"run", "export", "upload"} else 60)
    except subprocess.TimeoutExpired:
        # Only terminate this invocation; a remote task may still be running.
        process.kill()
        process.wait()
    reader.join()
    stdout_reader.join()
    output = "".join(output_parts)
    if on_event:
        on_event({"type": "process_exited"})
    try:
        envelope = json.loads(output)
    except json.JSONDecodeError:
        envelope = {"code": "interrupted", "message": "CLI 未返回有效结果；必须恢复原任务，不能重发。", "data": {}, "error": {"retryable": True}}
    if not isinstance(envelope, dict):
        raise ValueError("Flova CLI 返回无效结果")
    return envelope


def account_status(root=ROOT):
    result = {"available": bool(find_tool("flova", root)), "authenticated": False,
              "credits_balance": None, "subscription_info": None, "message": "", "checked_at": now_iso()}
    if not result["available"]:
        result["message"] = "Flova CLI 未安装"
        return result
    try:
        auth = cli(["auth", "status"], root=root)
        result["authenticated"] = auth.get("code") == 0 and auth.get("data", {}).get("token_stored") is True
        if not result["authenticated"]:
            result["message"] = "需要登录 Flova；工作台不读取或保存凭证"
            return result
        response = cli(["account", "user"], root=root)
        if response.get("code") != 0:
            result["message"] = _safe_message(response.get("message"))
            return result
        data = response.get("data") or {}
        balance = data.get("credits_balance")
        if isinstance(balance, (str, int, float)) and not isinstance(balance, bool):
            try:
                balance = float(balance)
                if math.isfinite(balance):
                    result["credits_balance"] = balance
            except ValueError:
                pass
        info = data.get("subscription_info")
        if isinstance(info, dict):
            result["subscription_info"] = {key: _safe_message(info[key]) for key in ("plan", "name", "status", "expires_at") if key in info}
        result["message"] = "积分不足，未启动生成" if result["credits_balance"] == 0 else "已读取账号；生成前仍需确认本任务的模型与包含额度上限"
    except (OSError, ValueError, subprocess.SubprocessError):
        result["message"] = "无法读取 Flova 账号状态；未提交生成"
    return result


def confirmation(root, video_id):
    """Validate the existing card against the current source, not merely its filename."""
    from video_task_compiler import compile_package
    from codex_dispatcher import _approval_gate
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", video_id):
        raise ValueError("invalid video id")
    base = _inside(root / "content" / video_id, root / "content")
    with (root / "data/content_registry.csv").open(encoding="utf-8-sig", newline="") as handle:
        row = next((r for r in csv.DictReader(handle) if r.get("video_id") == video_id), None)
    if not row or row.get("content_type") != "ATMOSPHERE_VIDEO":
        raise ValueError("首轮仅支持氛围视频项目，图片与旁白路线不能调用此动作")
    if row.get("state") in {"PUBLISHED", "USER_APPROVED", "PREPARED_IN_DOUYIN", "CLOSED", "REVIEW_2H", "REVIEW_24H", "REVIEW_72H"}:
        raise ValueError("不能对已发布或已锁定发布的项目启动生成")
    approved, reason, _ = _approval_gate(video_id, root)
    if not approved:
        raise ValueError(reason)
    source = base / "production/prompt_package.json"
    task = _json(base / "production/video_task_package.json")
    fresh = compile_package(source)
    if fresh.get("provider_target") != "FLOVA" or fresh.get("status") != "WAITING_GENERATION_APPROVAL":
        raise ValueError("需要有效的 Flova 视频任务确认卡")
    for key in ("source_prompt_package_sha256", "generation_spec", "references", "shots", "negative_constraints", "continuity_locks", "private_skill"):
        if task.get(key) != fresh.get(key):
            raise ValueError("任务确认卡已过期，请重新生成并确认")
    if task.get("status") != "WAITING_GENERATION_APPROVAL" or task.get("blockers"):
        raise ValueError("任务确认卡存在阻塞")
    return task


def validate_approval(parameters, task):
    if not task.get("private_skill", {}).get("skill_id"):
        raise ValueError("请先设置自己的 DOUYIN_FLOVA_SKILL_ID 并重新生成任务确认卡")
    if parameters.get("generation_ack") is not True or parameters.get("budget_mode") != "INCLUDED_ONLY":
        raise ValueError("必须明确批准本任务，且仅使用免费或订阅内额度")
    limit = parameters.get("max_credits")
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0:
        raise ValueError("必须填写本任务允许消耗的包含积分上限")
    if parameters.get("model") != task.get("generation_spec", {}).get("model_proposal"):
        raise ValueError("批准的模型必须与当前确认卡一致")
    if task.get("references") and parameters.get("reference_upload_ack") is not True:
        raise ValueError("引用素材上传必须单独确认")


def _matches_attempt(data, attempted_at):
    """An unknown export handle must be demonstrably from this creation attempt."""
    try:
        attempt = datetime.fromisoformat(str(attempted_at).replace("Z", "+00:00"))
        created = datetime.fromisoformat(str(data.get("created_at", "")).replace("Z", "+00:00"))
        attempt = attempt if attempt.tzinfo else attempt.replace(tzinfo=timezone.utc)
        created = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        return (created - attempt).total_seconds() >= -1
    except (ValueError, TypeError):
        return False


def _pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _download_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("导出地址不是有效 HTTPS 地址")
    for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("不允许下载本地或私网导出地址")
    return url


def download_video(url, target):
    class SafeRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _download_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    temp = target.with_suffix(".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with build_opener(SafeRedirect()).open(_download_url(url), timeout=60) as response, temp.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 1024 ** 3:
                raise ValueError("导出超过本轮 1 GiB 下载上限")
            handle.write(chunk)
    if not size:
        raise ValueError("导出视频为空文件")
    temp.replace(target)


def probe_video(path, root=ROOT):
    from pipeline_tools.qa_probe import probe_media
    ffmpeg = find_tool("ffmpeg", root)
    ffprobe = find_tool("ffprobe", root)
    if not ffmpeg or not ffprobe:
        raise ValueError("本地媒体检测工具不可用")
    result = probe_media(path, ffmpeg=str(ffmpeg), ffprobe=str(ffprobe))
    if result.get("status") != "PASS" or not result.get("media", {}).get("video") or not (result.get("media", {}).get("duration_s") or 0) > 0:
        raise ValueError("导出文件未通过视频媒体检测")
    return result


def validate_delivery_spec(probe, spec):
    """Technical delivery must match the approved duration and frame geometry."""
    media = probe.get("media") or {}
    video = media.get("video") or {}
    try:
        target = float(spec.get("total_duration_seconds", spec.get("duration_seconds")))
        duration = float(media.get("duration_s"))
        width, height = float(video.get("width")), float(video.get("height"))
        ratio_width, ratio_height = [float(part) for part in str(spec.get("aspect_ratio")).split(":")]
    except (TypeError, ValueError):
        raise ValueError("无法把成片规格与任务确认卡进行比较")
    if any(not math.isfinite(value) or value <= 0 for value in (target, duration, width, height, ratio_width, ratio_height)):
        raise ValueError("成片或确认卡包含无效时长/尺寸")
    tolerance = max(0.5, target * 0.05)
    if abs(duration - target) > tolerance:
        raise ValueError(f"成片时长 {duration:g} 秒与批准 {target:g} 秒不符（允许误差 {tolerance:g} 秒）")
    target_ratio = ratio_width / ratio_height
    if abs(width / height - target_ratio) / target_ratio > 0.02:
        raise ValueError(f"成片尺寸 {width:g}×{height:g} 与批准宽高比 {spec.get('aspect_ratio')} 不符（允许相对误差 2%）")


def normalize_pending_actions(pending):
    """Project decision fields without changing a running job's lifecycle state."""
    return [{"action_id": p.get("action_id"), "type": p.get("type"), "blocking": p.get("blocking"),
        "message": _safe_message(p.get("message")), "description": _safe_message(p.get("description")),
        "resume_message_id": p.get("resume_message_id"),
        "action_url": _public_url(p.get("action_url")), "payload": sanitize_payload(p.get("payload") or {}),
        "options": [{"id": o.get("id"), "effect": o.get("effect"),
                     "label": _safe_message(o.get("label") or o.get("title") or o.get("id")),
                     "description": _safe_message(o.get("description") or o.get("consequence"))}
                    for o in p.get("options", []) if isinstance(o, dict)]}
        for p in pending if isinstance(p, dict)]


def execute(job, *, root=ROOT, persist, recover=False, resolution=None):
    """Update one existing job. Recovery never sends the original creative message again."""
    provider = job.setdefault("provider", {"name": "FLOVA"})
    runtime = job.setdefault("runtime", {})
    job.setdefault("media", [])
    job["evidence_mode"] = "REAL"
    base = _inside(root / "content" / job["video_id"] / "production" / "flova" / job["job_id"], root / "content" / job["video_id"] / "production")
    base.mkdir(parents=True, exist_ok=True)

    def state(status, message, next_action=""):
        job["status"] = status
        job["progress"] = {"message": message, "percentage": None}
        job["next_action"] = next_action
        job["updated_at"] = now_iso()
        persist(job)

    def event(item):
        kind = item.get("type")
        if kind == "process_started":
            runtime["cli_pid"] = item["pid"]
        elif kind == "process_exited":
            runtime["cli_pid"] = None
        elif kind == "handle":
            if item.get("stream_chat_id"):
                provider["stream_chat_id"] = item["stream_chat_id"]
            if item.get("task_id") and runtime.get("stage") == "export":
                provider["export_task_id"] = item["task_id"]
        elif kind == "resource_progress":
            counts = {key: value for key, value in (item.get("summary") or {}).items() if key in {"discovered", "queued", "processing", "succeeded", "failed", "unknown"} and isinstance(value, int)}
            job["progress"] = {"message": "Flova 正在生成素材", "percentage": None, "resources": counts}
        elif kind == "resource_ready":
            try:
                source = _inside(item.get("local_path", ""), root)
                if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}:
                    return
                if str(source) not in runtime.setdefault("preview_paths", []):
                    # Server delivery URL is local, not a signed provider URL.
                    dest = base / (f"preview-{len(runtime['preview_paths']) + 1}" + source.suffix.lower())
                    shutil.copyfile(source, dest)
                    runtime["preview_paths"].append(str(source))
                    job["media"].append({"kind": "video" if dest.suffix in {".mp4", ".webm"} else "image", "name": dest.name,
                                         "url": "/asset/" + quote(job["video_id"]) + "/" + quote(dest.relative_to(root / "content" / job["video_id"] / "production").as_posix(), safe="/")})
            except (OSError, ValueError):
                job["preview_warning"] = "收到素材预览事件，但本地文件不可安全展示"
        persist(job)

    def call(args):
        reply = cli(args, root=root, cwd=base, on_event=event)
        data = reply.get("data") or {}
        for name in ("project_id", "stream_chat_id"):
            if data.get(name):
                if name == "project_id" and provider.get(name) and provider[name] != str(data[name]):
                    raise ValueError("平台返回的项目与当前任务不一致")
                provider[name] = _identifier(data[name])
        if data.get("project_url"):
            provider["project_url"] = _public_url(data["project_url"])
        if runtime.get("stage") == "export" and data.get("task_id"):
            if provider.get("export_task_id") and provider["export_task_id"] != str(data["task_id"]):
                raise ValueError("平台返回的导出任务与当前记录不一致")
            provider["export_task_id"] = _identifier(data["task_id"])
        job["last_provider_result"] = {"code": reply.get("code"), "message": _safe_message(reply.get("message")),
                                       "request_id": str(reply.get("request_id") or ""), "status": data.get("status"), "terminal": data.get("terminal")}
        persist(job)
        return reply

    def result_or_stop(reply, *, terminal=True):
        data = reply.get("data") or {}
        pending = data.get("pending_actions") or []
        job["pending_actions"] = normalize_pending_actions(pending)
        if any(p.get("blocking") for p in job["pending_actions"]):
            state("WAITING_USER", "Flova 需要你确认下一步", "选择当前待确认操作；未自动批准")
            return False
        if reply.get("code") in {"insufficient_credits", "membership_required"}:
            state("BLOCKED", "Flova 额度不足或需要会员；未自动购买", "在 Flova 处理账号权益后检查本任务")
            return False
        if reply.get("code") != 0:
            recoverable = (reply.get("error") or {}).get("retryable") or reply.get("code") in {"interrupted", "agent_busy", "run_result_not_ready", "export_timeout"}
            state("RECOVERABLE" if recoverable else "FAILED", _safe_message(reply.get("message")), "恢复原任务；不要重复生成" if recoverable else "检查平台结果并修正原因")
            return False
        if terminal and (data.get("terminal") is not True or data.get("status") not in {"success", "completed"}):
            state("FAILED" if data.get("status") in {"failed", "error", "cancelled"} else "RECOVERABLE", "平台任务尚未成功结束", "恢复原任务查看结果")
            return False
        return True

    try:
        if recover and _pid_alive(runtime.get("cli_pid")):
            state("RECOVERABLE", "原 Flova CLI 进程仍在运行，未创建第二个轮询进程", "等待原进程结束后恢复")
            return
        if not recover and not resolution:
            task = confirmation(root, job["video_id"])
            if task != job.get("confirmation"):
                raise ValueError("确认卡已变化，请重新创建任务并确认")
            validate_approval(job["parameters"], task)
            account = account_status(root)
            job["account_check"] = account
            balance = account.get("credits_balance")
            if not account.get("authenticated") or balance is None or balance <= 0:
                state("BLOCKED", account.get("message") or "无法确认免费或订阅内额度", "检查 Flova 账号；未创建外部项目")
                return
            if job["parameters"]["max_credits"] > balance:
                raise ValueError("批准上限高于当前可用积分，请调整或检查账号")
            runtime["stage"] = "create"
            runtime["create_attempted_at"] = now_iso()
            persist(job)
            reply = call(["project", "create", "--name", f"Workbench {job['video_id']}", "--description", "Approved local workbench video task"])
            if not result_or_stop(reply, terminal=False):
                return
            if not provider.get("project_id"):
                state("RECOVERABLE", "项目创建结果不完整，禁止重复创建", "在 Flova 核对项目后人工恢复")
                return
            files = []
            try:
                for index, reference in enumerate(task.get("references", [])):
                    path = Path(reference["path_or_label"])
                    path = _inside(path if path.is_absolute() else root / path, root)
                    allowed_roots = [(root / "assets/library").resolve(), (root / "content" / job["video_id"] / "production").resolve()]
                    if not any(allowed in path.parents for allowed in allowed_roots):
                        raise ValueError("只能上传素材库或本项目制作目录中的已批准素材")
                    if not path.is_file() or reference.get("rights_status") not in {"user_owned", "licensed"}:
                        raise ValueError("引用素材不存在或权利不符合")
                    reply = call(["upload", str(path)])
                    if not result_or_stop(reply, terminal=False):
                        return
                    temporary = base / f"upload-{index}.temporary.json"
                    _write(temporary, reply)
                    files.append(temporary)
                runtime["stage"] = "run"
                runtime["run_attempted_at"] = now_iso()
                persist(job)
                spec = task["generation_spec"]
                prompt = (f"制作完整视频且准备最终导出。仅使用 {job['parameters']['model']}；{spec['aspect_ratio']}；"
                          f"{spec['total_duration_seconds']} 秒；{spec['resolution']}。已批准仅免费或订阅内额度，"
                          f"本任务最多 {job['parameters']['max_credits']} 积分；禁止充值、升级、额外收费或自动切换模型。"
                          "若模型、成本、素材或步骤超出此范围，必须暂停并提出确认操作，不得执行。\n"
                          + "\n\n".join(s["flova_prompt"] for s in task["shots"])
                          + "\n不可接受：" + "；".join(task.get("negative_constraints", [])))
                if task.get("references"):
                    prompt += "\n上传文件按以下顺序作为经批准的参考素材：" + "；".join(f"{Path(r['path_or_label']).name}: {r.get('role')} {r.get('retention', '')}" for r in task["references"])
                args = ["run", provider["project_id"], "--content", prompt, "--skill-id", task["private_skill"]["skill_id"], "--timeout", "900"]
                for path in files:
                    args.extend(["--file-from", str(path)])
                reply = call(args)
            finally:
                for path in files:
                    path.unlink(missing_ok=True)
        elif resolution:
            project_id = provider.get("project_id")
            if not project_id:
                raise ValueError("缺少现有 Flova 项目 ID")
            selected = next((p for p in job.get("pending_actions", []) if p.get("action_id") == resolution.get("action_id")), None)
            if not selected:
                raise ValueError("待确认操作已改变，请刷新后重新选择")
            selected_option = next((o for o in selected.get("options", []) if o.get("id") == resolution.get("option_id")), None)
            if not selected_option:
                raise ValueError("必须选择当前操作提供的准确选项")
            if selected_option.get("effect") in {"none", "open_url"}:
                # These are local user decisions, not a backend continuation.
                state("WAITING_USER", "未发送恢复命令", "请自行打开平台处理" if selected_option["effect"] == "open_url" else "保留当前任务，未继续执行")
                return
            refreshed = call(["chat", "pending-actions", project_id])
            if refreshed.get("code") != 0:
                result_or_stop(refreshed, terminal=False)
                return
            raw = refreshed.get("data") or {}
            current_actions = raw.get("pending_actions", []) if isinstance(raw, dict) else []
            # Refreshing for comparison must stay RUNNING. Persisting WAITING_USER
            # here would let a second HTTP resolve start another resume worker.
            job["pending_actions"] = normalize_pending_actions(current_actions)
            current = next((p for p in job.get("pending_actions", []) if p.get("action_id") == resolution.get("action_id")), None)
            if selected != current:
                state("WAITING_USER", "Flova 确认内容已改变，请重新选择", "查看最新选项")
                return
            option = next((o for o in current.get("options", []) if o.get("id") == resolution.get("option_id")), None)
            if not option:
                raise ValueError("必须选择当前操作提供的准确选项")
            if option.get("effect") != "resume":
                state("WAITING_USER", "未发送恢复命令", "请自行打开平台处理" if option.get("effect") == "open_url" else "保留当前任务，未继续执行")
                return
            if not current.get("resume_message_id"):
                raise ValueError("平台未提供恢复消息 ID")
            validate_approval(job["parameters"], job["confirmation"])
            account = account_status(root)
            job["account_check"] = account
            balance = account.get("credits_balance")
            max_credits = job["parameters"]["max_credits"]
            cost = None
            for key in ("credits", "required_credits", "estimated_credits"):
                value = current.get("payload", {}).get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    cost = value
                    break
            if (not account.get("authenticated") or balance is None or balance <= 0
                    or max_credits > balance or (cost is not None and (cost > max_credits or cost > balance))):
                job["blocker_code"] = "CREDITS_APPROVAL_REQUIRED"
                state("WAITING_USER", "当前额度或本任务预算不足，未恢复生成", "核对免费/订阅内余额及已批准积分上限后重新选择；未充值或升级")
                return
            job.pop("blocker_code", None)
            runtime["stage"] = "run"
            state("RUNNING", "按你的选择恢复原 Flova 任务")
            reply = call(["run", "resume", _identifier(project_id), "--message-id", _identifier(current["resume_message_id"]), "--action-id", _identifier(current["action_id"]), "--option", _identifier(option["id"]), "--timeout", "900"])
        elif runtime.get("stage") != "export":
            project_id = provider.get("project_id")
            if not project_id:
                state("RECOVERABLE", "缺少外部项目句柄，未重新创建", "在 Flova 核对项目，不能自动重发")
                return
            args = ["run", "status", project_id, "--stream-chat-id", provider["stream_chat_id"]] if provider.get("stream_chat_id") else ["run", "current", project_id]
            reply = call(args)
            if (reply.get("data") or {}).get("terminal") is not True:
                result_or_stop(reply)
                return
            if not provider.get("stream_chat_id"):
                state("RECOVERABLE", "无法找到准确的运行句柄", "人工核对原任务，禁止重发")
                return
            reply = call(["run", "result", project_id, "--stream-chat-id", provider["stream_chat_id"]])
        else:
            reply = None

        if runtime.get("stage") != "export":
            if not result_or_stop(reply):
                return
            runtime["creative_succeeded"] = True
            persist(job)
            readiness = call(["export", "readiness", provider["project_id"]])
            if not result_or_stop(readiness, terminal=False):
                return
            if readiness.get("data", {}).get("can_export") is not True:
                state("RECOVERABLE", "创作已结束，但时间线尚不能导出", "在 Flova 完成时间线后恢复；不重复生成")
                return
            runtime["stage"] = "export"
            runtime["export_attempted_at"] = now_iso()
            persist(job)
            state("RUNNING", "Flova 正在导出最终视频")
            exported = call(["export", "video", provider["project_id"], "--timeout", "900"])
        else:
            if not runtime.get("creative_succeeded"):
                raise ValueError("缺少原创作成功记录，不能绕过直接导出")
            known_task = provider.get("export_task_id")
            args = ["export", "status", provider["project_id"], "--task-id", known_task] if known_task else ["export", "current", provider["project_id"]]
            exported = call(args)
            if not known_task and not _matches_attempt(exported.get("data") or {}, runtime.get("export_attempted_at")):
                provider.pop("export_task_id", None)
                state("RECOVERABLE", "返回的导出任务无法与本次尝试匹配，未重复导出", "人工核对 Flova 导出任务及创建时间")
                return
            if not provider.get("export_task_id"):
                state("RECOVERABLE", "无法找到原导出任务，未重复导出", "核对 Flova 中的导出任务")
                return
        if not result_or_stop(exported):
            return
        url = exported.get("data", {}).get("export_url")
        if not url:
            state("RECOVERABLE", "导出未返回可下载的最终视频", "恢复原导出任务获取结果")
            return
        state("RUNNING", "下载并检测最终视频")
        target = base / "final.mp4"
        download_video(url, target)
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("下载结果为空；不能标记成功")
        probe = probe_video(target, root)
        _write(base / "media_probe.json", probe)
        relative = target.relative_to(root / "content" / job["video_id"] / "production").as_posix()
        media_item = {"kind": "video", "name": target.name, "url": f"/asset/{quote(job['video_id'])}/{quote(relative, safe='/')}"}
        if not any(item.get("url") == media_item["url"] for item in job["media"]):
            job["media"].append(media_item)
        job["artifacts"] = [str(target.relative_to(root).as_posix()), str((base / "media_probe.json").relative_to(root).as_posix())]
        try:
            validate_delivery_spec(probe, job.get("confirmation", {}).get("generation_spec", {}))
        except ValueError as exc:
            job["returncode"] = 2
            job["blocker_code"] = "DELIVERY_SPEC_MISMATCH"
            state("BLOCKED", str(exc), "已保留成片与检测报告供检查；未标记成功，不自动重新生成")
            return
        job["returncode"] = 0
        state("SUCCEEDED", "最终视频已下载且通过媒体检测", "预览并由你验收；未上传或发布")
    except Exception as exc:
        uncertain = runtime.get("stage") in {"create", "run", "export"}
        job["stderr"] = _safe_message(exc)
        state("RECOVERABLE" if uncertain else "BLOCKED", _safe_message(exc), "恢复原任务，不重新提交" if uncertain else "修正前置条件后创建任务")
    finally:
        if job.get("status") != "RUNNING":
            job["completed_at"] = now_iso()
            persist(job)


def sanitize_payload(value):
    if isinstance(value, dict):
        return {str(k): sanitize_payload(v) for k, v in value.items()
                if not any(word in str(k).lower() for word in ("token", "credential", "secret", "url", "cookie"))}
    if isinstance(value, list):
        return [sanitize_payload(v) for v in value[:100]]
    return _safe_message(value) if isinstance(value, str) else value
