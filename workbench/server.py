"""Local-only control room for the Douyin content workflow.

This service is intentionally dependency-free.  It reads the project's existing
files and exposes local endpoints. Explicitly approved Flova generation may
upload its approved references; it never publishes or stores credentials.
Any workflow state mutation remains in the audited project commands.
"""

from __future__ import annotations

import csv
import html
import json
import math
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(r"G:\抖音视频")
CONTENT = ROOT / "content"
WORKBENCH_DIR = Path(__file__).resolve().parent
if str(WORKBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_DIR))
SRC_DIR = WORKBENCH_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import task_runner
import codex_dispatcher
import media_library
import draft_store
import flova_runtime


STATIC = WORKBENCH_DIR / "static"
SKILLS = Path(r"C:\Users\86135\.codex\skills")
TOPIC_POOL = ROOT / "research" / "SCENERY_TOPIC_POOL.csv"
TOOLCHAIN = ROOT / "workflow" / "TOOLCHAIN_STATUS.md"
ACCOUNT_PROFILES = ROOT / "data" / "account_profiles.json"
ACCOUNT_MAP = ROOT / "data" / "account_content_map.csv"
DOMAIN_CATALOG = ROOT / "research" / "TOPIC_DOMAIN_CATALOG.csv"
LLM_TOPIC_BANK = ROOT / "research" / "account_reset" / "llm_course_map" / "topic_bank_100.csv"
TREND_LATEST = ROOT / "research" / "trend_monitor" / "latest.json"
VIDEO_PROVIDER_MATRIX = ROOT / "research" / "tooling_refresh" / "video_provider" / "provider_matrix.json"
SHORTLIST = ROOT / "data" / "workbench_shortlist.json"
OFFLINE_DIR = ROOT / "workbench" / "offline"
TRASH = ROOT / "trash"
OFFLINE_MODE = False
ENGINE_PROCESSES: dict[str, subprocess.Popen] = {}
ENGINE_LOG_HANDLES: dict[str, object] = {}
STATE_COLORS = {
    "PUBLISHED": "published",
    "PREPARED_IN_DOUYIN": "prepared",
    "READY_FOR_USER": "review",
    "USER_APPROVED": "review",
    "QA_REVIEW": "working",
    "PRODUCING": "working",
    "BRIEF_APPROVED": "working",
    "BRIEF_DRAFT": "working",
    "RESEARCHED": "idea",
    "RESEARCHING": "idea",
    "IDEA": "idea",
}

WORKFLOW_STAGES = [
    {"id": "E0", "phase": "定位与选题", "title": "账号定位", "owner": "主控", "purpose": "冻结受众、账号承诺、栏目配比、禁区与复核节点。", "evidence": "workflow/ACCOUNT_POSITIONING_CARD.md", "pass": "定位卡字段完整且当前实验不越界", "rollback": "重写定位或拆分账号", "mode": "manual", "manual": "账号定位发生重大变化时，由你决定是否调整"},
    {"id": "E1", "phase": "定位与选题", "title": "增量研究", "owner": "选题 / 脚本", "purpose": "补充平台样本、受众信号和事实证据。", "evidence": "content/<id>/research/research_delta.md", "pass": "事实、推断、假设分开，事实有来源", "rollback": "补证据或降级为待验证假设", "mode": "auto", "manual": ""},
    {"id": "E2", "phase": "定位与选题", "title": "选题池", "owner": "主控", "purpose": "比较首图钩子、扩展性、受众收益、成本与风险。", "evidence": "research/SCENERY_TOPIC_POOL.csv", "pass": "首图可描述、系列可展开、指标与基线明确", "rollback": "改题、换路线或暂缓", "mode": "assisted", "manual": "你可否决推荐；系统不自动创建发布任务"},
    {"id": "E3", "phase": "定位与选题", "title": "单变量假设卡", "owner": "主控", "purpose": "一条内容只验证一个主变量，其余保持不变。", "evidence": "content/<id>/hypothesis_card.md", "pass": "变量、保持项、反证条件与最小样本完整", "rollback": "标为探索或退回选题池", "mode": "assisted", "manual": "观点、争议性表达或账号方向偏移时由你审核"},
    {"id": "E4", "phase": "策划", "title": "Brief 与最终立项", "owner": "主控 + 你", "purpose": "明确首屏、观众收益、结构、风险、AI 披露和声音 / 音乐策略。", "evidence": "brief.md + approvals/brief_approval.json", "pass": "你明确批准当前 brief", "rollback": "退回最早受影响阶段", "mode": "manual", "manual": "必须由你批准；意见改变后重新批准"},
    {"id": "E5", "phase": "策划", "title": "路线计划与镜头表", "owner": "制作", "purpose": "把 brief 拆为逐图或逐镜的唯一任务和验收句。", "evidence": "production/route_plan.json + shot_list.csv", "pass": "每张 / 镜只有一个主任务并有失败回退", "rollback": "修镜头表；内容原子变化则回 E4", "mode": "auto", "manual": ""},
    {"id": "P1", "phase": "制作", "title": "生成合同与素材授权", "owner": "制作 + 你", "purpose": "登记 prompt、provider、版本、权利、费用和素材来源。", "evidence": "production/material_manifest.csv", "pass": "来源、权利、哈希与授权记录完整", "rollback": "更换素材或补齐授权", "mode": "conditional", "manual": "付费 API、上传私人素材、声音克隆、本人录音、购买音乐前必须即时确认"},
    {"id": "P2", "phase": "制作", "title": "路线化制作", "owner": "制作", "purpose": "按图文、氛围视频或讲解视频合同生成最终素材。", "evidence": "production/production_manifest.json", "pass": "最终产物、顺序、版本和哈希完整", "rollback": "只替换失败单图 / 单镜并记录关系", "mode": "auto", "manual": ""},
    {"id": "Q1", "phase": "质量审核", "title": "机器 QA", "owner": "制作工具", "purpose": "检查尺寸、编码、时长、黑帧、音轨、字幕安全区和哈希。", "evidence": "qa/technical_report.json", "pass": "路线技术硬门全部通过", "rollback": "返回 P2 修复对应产物", "mode": "auto", "manual": ""},
    {"id": "Q2", "phase": "质量审核", "title": "独立内容 QA", "owner": "独立质检", "purpose": "检查审美、AI 痕迹、可读性、版权、节奏和观众收益。", "evidence": "qa/qa_result.json", "pass": "PASS / PASS_WITH_MINOR，开放 BLOCKER 与 MAJOR 均为 0", "rollback": "退回 E4、E5 或 P2", "mode": "assisted", "manual": "机器不能批准审美；你需查看最终画面 / 视频 / 声音"},
    {"id": "R1", "phase": "发布准备", "title": "锁定发布包", "owner": "主控", "purpose": "把成品顺序、标题、文案、音乐策略和 QA 绑定同一哈希。", "evidence": "approvals/release_package.json", "pass": "发布包校验通过且与当前 manifest 一致", "rollback": "重新打包并作废旧批准", "mode": "auto", "manual": ""},
    {"id": "A1", "phase": "发布准备", "title": "最终验收", "owner": "你", "purpose": "在上传前确认最终内容与发布包。", "evidence": "approvals/final_approval.json", "pass": "你的批准绑定当前 package hash", "rollback": "任何内容变化都回 R1 并重新批准", "mode": "manual", "manual": "必须查看最终成品、标题、文案和音乐策略后明确批准"},
    {"id": "R2", "phase": "发布准备", "title": "Prepare-only 上传", "owner": "主控 + 你", "purpose": "上传素材并填写信息，停在发布按钮前。", "evidence": "approvals/prepare_receipt.json", "pass": "publish_clicked=false 且页面内容核对无误", "rollback": "修正上传素材或填写项", "mode": "manual", "manual": "登录、验证码、权限提示由你处理；上传前再次确认"},
    {"id": "R3", "phase": "正式发布", "title": "手动发布与回执", "owner": "你 + 主控", "purpose": "由你点击发布，主控登记实际标题、音乐、时间与包哈希。", "evidence": "approvals/publish_receipt.json", "pass": "published=true 且作品身份可追溯", "rollback": "身份不明则不进入指标判断", "mode": "manual", "manual": "点击发布必须由你完成，或动作前再次明确授权"},
    {"id": "M1", "phase": "数据与复盘", "title": "FIRST_VISIBLE", "owner": "主控", "purpose": "第一次确认作品身份与可见指标。", "evidence": "metrics/post_snapshots.csv", "pass": "标题与发布时间匹配，字段只追加", "rollback": "等待可见或标注身份不确定", "mode": "auto", "manual": "页面不可访问、身份冲突时请你协助登录或确认作品"},
    {"id": "M2", "phase": "数据与复盘", "title": "H24 检查", "owner": "主控", "purpose": "在发布后 22–28 小时记录平台可见数据。", "evidence": "metrics/post_snapshots.csv", "pass": "窗口、身份和空值规则合规", "rollback": "超时标 LATE，不插值", "mode": "auto", "manual": ""},
    {"id": "M3", "phase": "数据与复盘", "title": "H72 复盘", "owner": "主控", "purpose": "只回答本条假设并给出 KEEP / STOP / INCONCLUSIVE。", "evidence": "metrics/post_snapshots.csv + postmortem_72h.json", "pass": "68–84 小时快照与基线证据足够", "rollback": "证据不足保持 INCONCLUSIVE", "mode": "assisted", "manual": "重大账号策略调整由你决定"},
    {"id": "N1", "phase": "数据与复盘", "title": "下一条单变量", "owner": "主控", "purpose": "根据复盘只修改一个主变量，生成下一题建议。", "evidence": "下一条 hypothesis_card.md", "pass": "主变量和保持项可追溯", "rollback": "返回 E2 重新选题", "mode": "assisted", "manual": "你确认最终选题与观点边界"},
]

STATE_COMPLETED_STAGE = {
    "IDEA": 0,
    "RESEARCHING": 1,
    "RESEARCHED": 2,
    "BRIEF_DRAFT": 3,
    "BRIEF_APPROVED": 4,
    "PRODUCING": 5,
    "QA_REVIEW": 7,
    "READY_FOR_USER": 9,
    "USER_APPROVED": 11,
    "PREPARED_IN_DOUYIN": 12,
    "PUBLISHED": 13,
    "REVIEW_2H": 14,
    "REVIEW_24H": 15,
    "REVIEW_72H": 16,
    "CLOSED": 17,
}

TOPIC_LIBRARY = {
    "成年不可能世界": {
        "治愈": [
            ("夜班结束后，城市会出现六个回家入口", "公交站背后通向雾中湖岸的窄门", "现实压力锚点"),
            ("如果每次疲惫都能抵达一处安静出口", "写字楼电梯门外是无人的雪原木屋", "出口场景"),
        ],
        "震撼": [
            ("同一条路，穿过六种不可能的地貌", "城市公路越过边界后悬在巨型峡谷上", "连续世界"),
            ("六座城市，把天空当作了地面", "克制灰蓝天空下的倒悬建筑群", "尺度反转"),
        ],
        "浪漫": [("如果晚风能把思念送到六个世界", "海边电话亭的线缆延伸进星河", "生活痕迹")],
        "安静": [("凌晨两点，世界留下六间亮着灯的房子", "空旷山谷里一扇温暖的窗", "孤独陪伴")],
        "怀旧": [("旧车站停靠着六个再也回不去的夏天", "褪色站台旁停着通往云层的列车", "怀旧载体")],
    },
    "现实治愈": {
        "治愈": [
            ("清晨五点，城市还没有开始催你", "空无一人的坡道刚被第一束晨光照亮", "清晨时段"),
            ("雨停后的六个普通瞬间", "便利店门口水洼映着暖色灯光", "雨后生活痕迹"),
        ],
        "安静": [("把周末留给六条没有目的地的路", "薄雾里没有车的乡间公路", "低刺激慢生活")],
        "怀旧": [("那些像旧相册一样的夏日下午", "暖褪色胶片质感的临海小镇街角", "胶片记忆")],
        "浪漫": [("适合两个人慢慢走完的六处黄昏", "海边长椅留下两杯未喝完的饮料", "成对生活痕迹")],
        "震撼": [("现实里真的存在的六种辽阔", "低饱和云海与巨大山脊形成尺度对比", "真实尺度")],
    },
    "节点特辑": {
        "浪漫": [("把节日写进六张可以保存的风景", "无人的窗台上放着两封信和晚霞", "节点情绪")],
        "治愈": [("这个假期，给自己六个不赶时间的地方", "晨光中的空车站与一只行李箱", "假期放松")],
    },
    "人物日常": {
        "治愈": [("把普通的一天拼成十二个值得留下的瞬间", "人物背影、咖啡与窗边光组成生活页", "人物代入")],
        "怀旧": [("像旧杂志一样记录一个没有安排的周末", "胶片人像与生活物件的克制拼贴", "编辑感")],
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def shortlist_data(include_all: bool = False) -> dict:
    payload = load_json(SHORTLIST) or {"schema_version": 1, "updated_at": "", "items": []}
    items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
    active_id = active_account().get("account_id", "scenery-main")
    if not include_all and active_id != "open-topic-sandbox":
        items = [item for item in items if item.get("account_id", "scenery-main") == active_id]
    return {"schema_version": 1, "updated_at": payload.get("updated_at", ""), "items": items}


def save_shortlist_item(payload: dict) -> dict:
    candidate_id = str(payload.get("candidateId", "")).strip()
    if not candidate_id or len(candidate_id) > 180 or not re.fullmatch(r"[A-Za-z0-9._:-]+", candidate_id):
        raise ValueError("invalid candidate id")
    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("candidate title is required")
    data = load_json(SHORTLIST) or {"schema_version": 1, "items": []}
    items = data.setdefault("items", [])
    account_id = active_account().get("account_id", "scenery-main")
    item = {
        "candidate_id": candidate_id,
        "account_id": account_id,
        "title": title[:240],
        "source": str(payload.get("source", ""))[:120],
        "domain": str(payload.get("domain", ""))[:120],
        "format": str(payload.get("format", ""))[:120],
        "score": payload.get("score", 0),
        "hook": str(payload.get("hook", ""))[:600],
        "audience_need": str(payload.get("audienceNeed", ""))[:600],
        "evidence": str(payload.get("evidence", ""))[:1000],
        "risk": str(payload.get("risk", ""))[:240],
        "saved_at": now_iso(),
        "status": "SAVED",
    }
    items[:] = [existing for existing in items if not (
        existing.get("candidate_id") == candidate_id and existing.get("account_id", "scenery-main") == account_id
    )]
    items.insert(0, item)
    if len(items) > 300:
        del items[300:]
    data["schema_version"] = 1
    data["updated_at"] = now_iso()
    save_json(SHORTLIST, data)
    return item


def remove_shortlist_item(payload: dict) -> dict:
    candidate_id = str(payload.get("candidateId", "")).strip()
    if not candidate_id:
        raise ValueError("candidate id is required")
    data = load_json(SHORTLIST) or {"schema_version": 1, "items": []}
    account_id = active_account().get("account_id", "scenery-main")
    before = len(data.get("items", []))
    data["items"] = [item for item in data.get("items", []) if not (
        item.get("candidate_id") == candidate_id and item.get("account_id", "scenery-main") == account_id
    )]
    if len(data["items"]) == before:
        raise FileNotFoundError(candidate_id)
    data["updated_at"] = now_iso()
    save_json(SHORTLIST, data)
    return {"removed": True, "candidateId": candidate_id}


def _file_evidence(path: Path, label: str = "") -> dict:
    return {"label": label or path.name, "path": str(path.relative_to(ROOT)), "exists": path.exists()}


def stage_evidence(video_id: str, stage_id: str) -> list[dict]:
    base = CONTENT / video_id
    metrics_path = base / "metrics" / "post_snapshots.csv"
    metrics = read_csv(metrics_path)
    mapping: dict[str, list[dict]] = {
        "E0": [_file_evidence(ROOT / "workflow" / "ACCOUNT_POSITIONING_CARD.md", "账号定位卡")],
        "E1": [_file_evidence(base / "research" / "research_delta.md", "增量研究")],
        "E2": [_file_evidence(TOPIC_POOL, "正式选题池")],
        "E3": [_file_evidence(base / "hypothesis_card.md", "单变量假设卡")],
        "E4": [_file_evidence(base / "brief.md", "Brief"), _file_evidence(base / "approvals" / "brief_approval.json", "Brief 批准")],
        "E5": [_file_evidence(base / "production" / "route_plan.json", "路线计划"), _file_evidence(base / "production" / "shot_list.csv", "镜头表")],
        "P1": [_file_evidence(base / "production" / "material_manifest.csv", "素材与权利台账")],
        "P2": [_file_evidence(base / "production" / "production_manifest.json", "制作清单")],
        "Q1": [_file_evidence(base / "qa" / "technical_report.json", "机器 QA")],
        "Q2": [_file_evidence(base / "qa" / "qa_result.json", "独立 QA")],
        "R1": [_file_evidence(base / "approvals" / "release_package.json", "发布包")],
        "A1": [_file_evidence(base / "approvals" / "final_approval.json", "最终批准")],
        "R2": [_file_evidence(base / "approvals" / "prepare_receipt.json", "Prepare-only 回执")],
        "R3": [_file_evidence(base / "approvals" / "publish_receipt.json", "发布回执")],
        "M1": [{"label": "FIRST_VISIBLE 快照", "path": str(metrics_path.relative_to(ROOT)), "exists": any(row.get("checkpoint") == "first_visible" for row in metrics)}],
        "M2": [{"label": "H24 快照", "path": str(metrics_path.relative_to(ROOT)), "exists": any(row.get("checkpoint") == "24h" for row in metrics)}],
        "M3": [
            {"label": "H72 快照", "path": str(metrics_path.relative_to(ROOT)), "exists": any(row.get("checkpoint") == "72h" for row in metrics)},
            _file_evidence(base / "metrics" / "postmortem_72h.json", "72 小时复盘"),
        ],
        "N1": [_file_evidence(base / "metrics" / "next_hypothesis.json", "下一条单变量交接")],
    }
    return mapping.get(stage_id, [])


def project_stage_progress(row: dict[str, str]) -> dict:
    completed_index = STATE_COMPLETED_STAGE.get(row.get("state", "IDEA"), 0)
    evidence_by_stage = {stage["id"]: stage_evidence(row["video_id"], stage["id"]) for stage in WORKFLOW_STAGES}
    exact = {
        stage_id: bool(items) and all(item.get("exists") for item in items)
        for stage_id, items in evidence_by_stage.items()
    }
    current_index = next(
        (index for index, stage in enumerate(WORKFLOW_STAGES) if index > completed_index and not exact[stage["id"]]),
        None,
    )
    stages = []
    for index, stage in enumerate(WORKFLOW_STAGES):
        stage_id = stage["id"]
        if exact[stage_id]:
            status = "complete"
        elif index <= completed_index:
            status = "evidence_gap"
        elif index == current_index:
            status = "waiting_user" if stage.get("mode") == "manual" else "ready"
        else:
            status = "pending"
        stages.append({
            **stage,
            "status": status,
            "evidenceItems": evidence_by_stage[stage_id],
            "missing": [item["label"] for item in evidence_by_stage[stage_id] if not item.get("exists")],
        })
    verified = sum(1 for stage in stages if stage["status"] == "complete")
    gaps = sum(1 for stage in stages if stage["status"] == "evidence_gap")
    current = next((stage for stage in stages if stage["status"] in {"ready", "waiting_user"}), None)
    return {
        "verified": verified,
        "evidenceGaps": gaps,
        "total": len(stages),
        "verifiedPercent": round(verified / len(stages) * 100) if stages else 0,
        "current": current,
        "stages": stages,
    }


def offline_status() -> dict:
    trend = load_json(TREND_LATEST)
    local_modules = [
        {"id": "registry", "label": "项目状态与账号档案", "path": "data/content_registry.csv", "ready": (ROOT / "data" / "content_registry.csv").exists() and ACCOUNT_PROFILES.exists(), "mode": "完全离线"},
        {"id": "topics", "label": "选题池与课程题库", "path": "research/", "ready": TOPIC_POOL.exists() and DOMAIN_CATALOG.exists(), "mode": "完全离线"},
        {"id": "workflow", "label": "流程门、审计与项目创建", "path": "src/workflow_control.py", "ready": (ROOT / "src" / "workflow_control.py").exists(), "mode": "完全离线"},
        {"id": "assets", "label": "素材、成品与 QA 证据", "path": "content/", "ready": CONTENT.exists(), "mode": "完全离线"},
        {"id": "skills", "label": "本地 Skill 索引", "path": str(SKILLS), "ready": SKILLS.exists(), "mode": "完全离线"},
        {"id": "render", "label": "FFmpeg / Remotion 本地渲染入口", "path": "tools/ + projects/tooling_refresh/", "ready": (ROOT / "tools").exists() and (ROOT / "projects" / "tooling_refresh").exists(), "mode": "素材齐备后离线"},
    ]
    cached_modules = [
        {"id": "trends-cache", "label": "最近一次趋势快照", "ready": bool(trend), "freshness": trend.get("captured_at", ""), "note": "离线可读，断网时不会刷新"},
        {"id": "metrics-cache", "label": "历史作品指标快照", "ready": bool(all_metrics()), "freshness": max((item.get("captured_at", "") for item in all_metrics()), default=""), "note": "离线可复盘，断网时不会新增"},
    ]
    online_modules = [
        {"id": "trend-live", "label": "抖音热榜、搜索联想和创作灵感", "reason": "需要访问抖音公开页面或已登录创作者中心", "guard": "只读采集；失败时保留缓存"},
        {"id": "platform-metrics", "label": "FIRST_VISIBLE / H24 / H72 新快照", "reason": "需要创作者中心可见数据", "guard": "身份匹配后只追加，不可见字段留空"},
        {"id": "prepare-upload", "label": "Prepare-only 上传", "reason": "需要平台登录、网络与用户即时确认", "guard": "停在发布按钮前"},
        {"id": "publish", "label": "正式发布与平台音乐", "reason": "必须连接抖音并由用户确认或手动完成", "guard": "工作台永不自动越过发布门"},
    ]
    return {
        "runtimeMode": "offline" if OFFLINE_MODE else "local",
        "generatedAt": now_iso(),
        "offlineReady": all(item["ready"] for item in local_modules),
        "localModules": local_modules,
        "cachedModules": cached_modules,
        "onlineModules": online_modules,
        "snapshotPath": str(OFFLINE_DIR / "workbench_offline.html"),
        "snapshotExists": (OFFLINE_DIR / "workbench_offline.html").exists(),
        "policy": "默认本地优先；只有趋势刷新、平台指标、上传与发布需要联网。",
    }


def _snapshot_project_rows(items: list[dict]) -> str:
    rows = []
    for item in items:
        progress = item.get("stageProgress") or {}
        current = progress.get("current") or {}
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(item.get('title', ''))}</strong><small>{html.escape(item.get('id', ''))}</small></td>"
            f"<td>{html.escape(item.get('state', ''))}</td>"
            f"<td>{progress.get('verified', 0)}/{progress.get('total', 0)}</td>"
            f"<td>{html.escape(current.get('id', '—'))} {html.escape(current.get('title', ''))}</td>"
            f"<td>{html.escape(item.get('nextAction', '') or '—')}</td>"
            "</tr>"
        )
    return "".join(rows)


def build_offline_snapshot_html() -> str:
    account = active_account()
    items = projects()
    for item in items:
        registry_row = next((row for row in read_csv(ROOT / "data" / "content_registry.csv") if row.get("video_id") == item["id"]), {})
        item["stageProgress"] = project_stage_progress(registry_row) if registry_row else {}
    shortlist = shortlist_data().get("items", [])
    status = offline_status()
    dashboard_data = dashboard()
    local_cards = "".join(
        f"<article class='cap {'ok' if module['ready'] else 'bad'}'><b>{html.escape(module['label'])}</b><span>{html.escape(module['mode'])}</span><small>{html.escape(module['path'])}</small></article>"
        for module in status["localModules"]
    )
    online_cards = "".join(
        f"<article class='online'><b>{html.escape(module['label'])}</b><p>{html.escape(module['reason'])}</p><small>{html.escape(module['guard'])}</small></article>"
        for module in status["onlineModules"]
    )
    shortlist_rows = "".join(
        f"<li><div><b>{html.escape(item.get('title', ''))}</b><span>{html.escape(item.get('domain', ''))} · {html.escape(item.get('source', ''))}</span></div><strong>{html.escape(str(item.get('score', '—')))}</strong></li>"
        for item in shortlist
    ) or "<li class='empty'>尚未收藏候选题。</li>"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>抖音内容工作台 · 离线快照</title><style>
:root{{--ink:#161916;--muted:#697068;--paper:#f5f1e8;--card:#fffdf8;--line:#ded8cc;--green:#345c48;--amber:#a66c21;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1180px;margin:auto;padding:42px 24px 64px}}header{{display:flex;justify-content:space-between;gap:24px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:24px}}h1{{font-size:34px;margin:4px 0}}h2{{font-size:22px;margin:0 0 16px}}p,small{{color:var(--muted)}}.stamp{{text-align:right}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}.kpi,.panel,.cap,.online{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}}.kpi b{{display:block;font-size:28px}}.grid{{display:grid;grid-template-columns:1.15fr .85fr;gap:18px;margin:18px 0}}.panel{{overflow:hidden}}.caps{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.cap b,.online b{{display:block}}.cap span{{color:var(--green);font-weight:700}}.cap.bad span{{color:#9d3e31}}.cap small{{display:block;margin-top:8px;word-break:break-all}}.online{{margin:8px 0;border-left:4px solid var(--amber)}}ul{{list-style:none;padding:0;margin:0}}li{{display:flex;justify-content:space-between;gap:16px;padding:12px 0;border-bottom:1px solid var(--line)}}li span{{display:block;color:var(--muted);font-size:13px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;padding:12px 10px;border-bottom:1px solid var(--line);vertical-align:top}}td small{{display:block}}.note{{padding:14px 16px;border-radius:12px;background:#e8eee8;color:var(--green);margin:18px 0}}@media(max-width:800px){{.kpis,.caps,.grid{{grid-template-columns:1fr 1fr}}header{{display:block}}.stamp{{text-align:left}}}}@media(max-width:560px){{.kpis,.caps,.grid{{grid-template-columns:1fr}}main{{padding:24px 14px}}table{{display:block;overflow:auto}}}}
</style></head><body><main>
<header><div><small>DOUYIN CONTENT OS · OFFLINE SNAPSHOT</small><h1>{html.escape(account.get('display_name', '本地工作台'))}</h1><p>{html.escape(account.get('positioning', ''))}</p></div><div class="stamp"><b>生成于</b><p>{html.escape(status['generatedAt'])}</p><small>此文件不连接网络，不包含账号凭证。</small></div></header>
<section class="kpis"><article class="kpi"><span>内容项目</span><b>{dashboard_data['counts']['total']}</b></article><article class="kpi"><span>已发布</span><b>{dashboard_data['counts']['published']}</b></article><article class="kpi"><span>待推进</span><b>{dashboard_data['counts']['active']}</b></article><article class="kpi"><span>收藏候选</span><b>{len(shortlist)}</b></article></section>
<div class="note">{html.escape(status['policy'])} 离线快照是只读副本；正式状态仍以 data/content_registry.csv 为准。</div>
<section class="panel"><h2>本地能力</h2><div class="caps">{local_cards}</div></section>
<div class="grid"><section class="panel"><h2>收藏候选</h2><ul>{shortlist_rows}</ul></section><section class="panel"><h2>仍需联网的环节</h2>{online_cards}</section></div>
<section class="panel"><h2>项目与阶段就绪度</h2><table><thead><tr><th>项目</th><th>状态</th><th>证据</th><th>当前门</th><th>下一步</th></tr></thead><tbody>{_snapshot_project_rows(items)}</tbody></table></section>
</main></body></html>"""


def export_offline_snapshot(target: Path | None = None) -> Path:
    target = target or (OFFLINE_DIR / "workbench_offline.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(build_offline_snapshot_html(), encoding="utf-8")
    temporary.replace(target)
    return target


def account_data() -> dict:
    data = load_json(ACCOUNT_PROFILES)
    profiles = data.get("profiles", [])
    active = data.get("active_account_id")
    if not any(profile.get("account_id") == active for profile in profiles) and profiles:
        active = profiles[0].get("account_id")
    return {"activeAccountId": active, "profiles": profiles}


def active_account() -> dict:
    data = account_data()
    return next((profile for profile in data["profiles"] if profile.get("account_id") == data["activeAccountId"]), {})


def select_account(account_id: str) -> dict:
    data = load_json(ACCOUNT_PROFILES)
    if not any(profile.get("account_id") == account_id for profile in data.get("profiles", [])):
        raise ValueError("unknown account profile")
    data["active_account_id"] = account_id
    save_json(ACCOUNT_PROFILES, data)
    return account_data()


def create_account(payload: dict) -> dict:
    account_id = re.sub(r"[^a-z0-9-]", "-", str(payload.get("accountId", "")).strip().lower()).strip("-")
    display_name = str(payload.get("displayName", "")).strip()
    positioning = str(payload.get("positioning", "")).strip()
    if len(account_id) < 3 or not display_name or not positioning:
        raise ValueError("accountId, displayName and positioning are required")
    data = load_json(ACCOUNT_PROFILES)
    if any(profile.get("account_id") == account_id for profile in data.get("profiles", [])):
        raise ValueError("account profile already exists")
    profile = {
        "account_id": account_id,
        "display_name": display_name,
        "status": "PLANNED",
        "platform_account_label": "尚未绑定平台账号",
        "positioning": positioning,
        "audience": str(payload.get("audience", "")).strip() or "待补充",
        "allowed_domains": list(payload.get("allowedDomains") or ["ALL"]),
        "preferred_formats": list(payload.get("preferredFormats") or ["IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO"]),
        "notes": "由工作台创建；平台登录仍需用户在创作者中心手动完成。",
    }
    data.setdefault("profiles", []).append(profile)
    data["active_account_id"] = account_id
    save_json(ACCOUNT_PROFILES, data)
    return account_data()


def account_mapping() -> dict[str, str]:
    return {row.get("video_id", ""): row.get("account_id", "") for row in read_csv(ACCOUNT_MAP)}


def map_project(video_id: str, account_id: str) -> None:
    rows = read_csv(ACCOUNT_MAP)
    rows = [row for row in rows if row.get("video_id") != video_id]
    rows.append({"video_id": video_id, "account_id": account_id})
    write_csv(ACCOUNT_MAP, rows, ["video_id", "account_id"])


def safe_video_id(value: str) -> str:
    if not value or value != Path(value).name or ".." in value or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError("invalid video id")
    return value


def image_files(video_id: str) -> list[str]:
    folder = CONTENT / video_id / "production" / "publish_images"
    if not folder.exists():
        return []
    return [item.name for item in sorted(folder.iterdir()) if item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]


def latest_metrics(video_id: str) -> dict[str, str]:
    rows = read_csv(CONTENT / video_id / "metrics" / "post_snapshots.csv")
    return max(rows, key=lambda item: item.get("captured_at", ""), default={})


def all_metrics() -> list[dict[str, str]]:
    result = []
    active_id = active_account().get("account_id")
    mapping = account_mapping()
    title_by_id = {row["video_id"]: row.get("title", row["video_id"]) for row in read_csv(ROOT / "data" / "content_registry.csv")}
    for video_id, title in title_by_id.items():
        if active_id != "open-topic-sandbox" and mapping.get(video_id, "scenery-main") != active_id:
            continue
        for row in read_csv(CONTENT / video_id / "metrics" / "post_snapshots.csv"):
            result.append({"videoId": video_id, "title": title, **row})
    return sorted(result, key=lambda item: item.get("captured_at", ""), reverse=True)


def score_topic(row: dict[str, str]) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    if row.get("gate_status") == "READY":
        score += 22
        reasons.append("已通过选题预审")
    elif row.get("gate_status") == "SELECTED":
        score += 10
        reasons.append("已被选用，适合作为基线而非重复发布")
    if row.get("first_frame_visual"):
        score += 20
        reasons.append("首图钩子可直接视觉化")
    if row.get("six_panel_expandability"):
        score += 18
        reasons.append("具备连续多图扩展结构")
    if row.get("nearest_baseline_video_id"):
        score += 12
        reasons.append("存在可比较的历史基线")
    if row.get("rights_risk", "").upper() == "LOW":
        score += 10
        reasons.append("版权与品牌风险较低")
    if row.get("freshness") in {"EVERGREEN", "TIMELY"}:
        score += 8
    try:
        hours = float(row.get("production_hours_est") or 99)
    except ValueError:
        hours = 99
    if hours <= 6:
        score += 10
        reasons.append("预计可在单周投入内完成")
    elif hours <= 8:
        score += 6
    return min(score, 100), reasons


def topics() -> dict:
    profile = active_account()
    rows = []
    for row in read_csv(TOPIC_POOL):
        score, reasons = score_topic(row)
        rows.append({**row, "score": score, "scoreReasons": reasons})
    ready = [item for item in rows if item.get("gate_status") == "READY"]
    recommended = max(ready, key=lambda item: item["score"], default=None)
    return {
        "accountPromise": profile.get("positioning", ""),
        "audience": profile.get("audience", ""),
        "scoreModel": ["首图钩子 20", "系列扩展 18", "选题门 22", "历史基线 12", "权利风险 10", "时效 8", "制作成本 10"],
        "recommended": recommended,
        "items": sorted(rows, key=lambda item: item["score"], reverse=True),
    }


def topic_intelligence() -> dict:
    profile = active_account()
    allowed = set(profile.get("allowed_domains") or [])
    allow_all = "ALL" in allowed
    domains = []
    for row in read_csv(DOMAIN_CATALOG):
        fit = allow_all or row.get("domain") in allowed or row.get("subdomain") in allowed
        domains.append({**row, "accountFit": fit})

    candidates = []
    for row in read_csv(TOPIC_POOL):
        score, reasons = score_topic(row)
        candidates.append({
            "id": "scenery-" + row.get("topic_id", ""), "title": row.get("working_title", ""),
            "domain": "视觉壁纸", "subdomain": row.get("pillar", ""), "source": "正式风景选题池",
            "sourceType": "evergreen_pool", "format": "图片轮播 / 氛围视频", "hook": row.get("first_frame_visual", ""),
            "audienceNeed": row.get("audience_job", ""), "freshness": row.get("freshness", ""),
            "risk": row.get("rights_risk", ""), "score": score, "scoreReasons": reasons,
            "accountFit": allow_all or "视觉壁纸" in allowed or row.get("pillar") in allowed,
            "evidence": row.get("source_signal_ids", ""), "status": row.get("gate_status", ""),
        })
    for row in read_csv(LLM_TOPIC_BANK):
        priority_score = {"P1": 82, "P2": 72, "P3": 62}.get(row.get("priority", ""), 55)
        candidates.append({
            "id": "llm-" + row.get("topic_id", ""), "title": row.get("title", ""),
            "domain": "AI 与大模型", "subdomain": row.get("module_name", ""), "source": "LLM 课程知识题库",
            "sourceType": "evergreen_pool", "format": row.get("content_type", ""), "hook": row.get("zero_based_hook", ""),
            "audienceNeed": "零基础理解、实测验证与减少误解", "freshness": "EVERGREEN" if row.get("evergreen_flag") == "是" else "HOTSPOT_LINKED",
            "risk": row.get("copyright_risk", ""), "score": priority_score,
            "scoreReasons": ["已有课程知识映射", "要求自建画面与独立证据", f"优先级 {row.get('priority', '')}"],
            "accountFit": allow_all or "AI 与大模型" in allowed, "evidence": row.get("evidence_standard", ""),
            "status": "KNOWLEDGE_BANK", "triggers": row.get("hotspot_triggers", ""),
        })
    trend = load_json(TREND_LATEST)
    for item in trend.get("items", []):
        matched = item.get("matched_accounts", [])
        candidates.append({
            "id": "trend-" + item.get("trend_id", ""), "title": item.get("title", ""),
            "domain": item.get("category", "热点"), "subdomain": item.get("source_type", ""), "source": "抖音热点雷达",
            "sourceType": "live_trend", "format": item.get("content_form", ""), "hook": item.get("rank_or_signal", ""),
            "audienceNeed": item.get("inference", ""), "freshness": item.get("fresh_until", "") or "LIVE",
            "risk": item.get("rights_risk", ""), "score": item.get("fit_score", 0),
            "scoreReasons": [item.get("facts", ""), item.get("to_verify", "")],
            "accountFit": allow_all or profile.get("account_id") in matched, "evidence": item.get("source_url", ""),
            "status": "TREND_SIGNAL", "doNotCopy": item.get("do_not_copy", ""),
        })
    candidates.sort(key=lambda item: (item.get("accountFit", False), item.get("score", 0)), reverse=True)
    return {
        "account": profile,
        "domains": domains,
        "candidates": candidates,
        "trend": {"capturedAt": trend.get("captured_at", ""), "status": "PAUSED", "summary": "热点监控已关闭；以下候选只包含历史快照与常青题库。", "schedule": []},
        "counts": {"domains": len(domains), "candidates": len(candidates), "trendSignals": sum(1 for item in candidates if item["sourceType"] == "live_trend"), "accountFit": sum(1 for item in candidates if item["accountFit"])},
    }


def trend_status() -> dict:
    trend = load_json(TREND_LATEST)
    snapshots = sorted((TREND_LATEST.parent / "snapshots").glob("trend_*.json"), reverse=True) if TREND_LATEST.parent.exists() else []
    return {**trend, "snapshotCount": len(snapshots), "automation": {"name": "抖音流量与热点监控", "schedule": "已暂停", "mode": "PAUSED", "status": "PAUSED"}}


def topic_suggestions(payload: dict) -> dict:
    pillar = str(payload.get("pillar") or "现实治愈")
    mood = str(payload.get("mood") or "治愈")
    content_format = str(payload.get("format") or "图片轮播")
    pool = TOPIC_LIBRARY.get(pillar, TOPIC_LIBRARY["现实治愈"])
    candidates = pool.get(mood) or next(iter(pool.values()))
    cards = []
    for index, (working_title, first_frame, variable) in enumerate(candidates[:3], start=1):
        cards.append({
            "rank": index,
            "title": working_title,
            "pillar": pillar,
            "mood": mood,
            "format": content_format,
            "audienceJob": "让成年人获得可保存、可代入、低理解成本的短暂停留。",
            "firstFrame": first_frame,
            "seriesPlan": "用同一视觉规则扩展为 6–12 张 / 镜，保持色调、比例和情绪一致。",
            "hypothesis": f"在账号承诺和画面质量保持不变时，{variable}会提高收藏或多图停留。",
            "singleVariable": variable,
            "heldConstants": "9:16；成年人语气；无品牌；原创素材；低 AI 痕迹；平台音乐；只改一个主变量",
            "primaryMetric": "每千播放收藏 / 平均浏览张数",
            "risk": "LOW" if pillar != "人物日常" else "MEDIUM：需检查人脸一致性与肖像原创性",
            "recommendedSkill": "ai-scenery-studio" if pillar in {"成年不可能世界", "现实治愈"} else "retro-scrapbook-collage",
        })
    return {"input": {"pillar": pillar, "mood": mood, "format": content_format}, "cards": cards, "notice": "这是候选草案，不会自动写入 registry；立项前仍需 E3 假设卡与 E4 用户批准。"}


def toolchain_status() -> dict:
    text = TOOLCHAIN.read_text(encoding="utf-8", errors="replace") if TOOLCHAIN.exists() else ""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line or "能力" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 4:
            rows.append({"capability": cells[0], "status": cells[1], "use": cells[2], "note": cells[3]})
    route_match = re.search(r"路线结论：(.+?)。", text)
    updated_match = re.search(r"更新时间：(\d{4}-\d{2}-\d{2})", text)
    return {"updatedAt": updated_match.group(1) if updated_match else "未记录", "routes": route_match.group(1) if route_match else "", "items": rows}


def integration_status() -> dict:
    """Report source/runtime readiness without reading or storing credentials."""
    integrations = [
        {
            "id": "moneyprinterturbo",
            "name": "MoneyPrinterTurbo",
            "role": "参数化视频生成与任务交互参考",
            "license": "MIT",
            "source": ROOT / "projects" / "MoneyPrinterTurbo",
            "runtime": ROOT / "envs" / "moneyprinterturbo",
            "entry": "webui/Main.py",
            "adoption": "UI structure + task lifecycle + preview",
        },
        {
            "id": "pixelle-video",
            "name": "Pixelle-Video",
            "role": "模块化视频流水线与历史任务引擎",
            "license": "Apache-2.0",
            "source": ROOT / "projects" / "Pixelle-Video",
            "runtime": ROOT / "envs" / "pixelle_video",
            "entry": "web/app.py",
            "adoption": "pipeline registry + three-column generation workspace + history",
        },
        {
            "id": "social-auto-upload",
            "name": "social-auto-upload",
            "role": "抖音平台命令适配与多账号抽象",
            "license": "MIT",
            "source": ROOT / "projects" / "social-auto-upload",
            "runtime": ROOT / "envs" / "publisher",
            "entry": "sau_cli.py",
            "adoption": "command plan only; login/upload/publish remain gated",
        },
    ]
    payload = []
    for item in integrations:
        source_ready = item["source"].is_dir()
        runtime_ready = (item["runtime"] / "Scripts" / "python.exe").is_file()
        entry_ready = (item["source"] / item["entry"]).is_file()
        status = "READY" if source_ready and runtime_ready and entry_ready else ("SOURCE_READY" if source_ready and entry_ready else "MISSING")
        process = ENGINE_PROCESSES.get(item["id"])
        process_running = bool(process and process.poll() is None)
        healthy = False
        api_healthy = False
        if item["id"] == "pixelle-video":
            try:
                with socket.create_connection(("127.0.0.1", 8501), timeout=0.1):
                    healthy = True
            except OSError:
                pass
            try:
                with socket.create_connection(("127.0.0.1", 8502), timeout=0.1):
                    api_healthy = True
            except OSError:
                pass
        running = process_running or healthy
        payload.append({
            **{key: value for key, value in item.items() if key not in {"source", "runtime"}},
            "sourcePath": str(item["source"]),
            "runtimePath": str(item["runtime"]),
            "sourceReady": source_ready,
            "runtimeReady": runtime_ready,
            "entryReady": entry_ready,
            "status": status,
            "canLaunch": status == "READY" and item["id"] != "social-auto-upload",
            "running": running,
            "healthy": healthy,
            "apiHealthy": api_healthy,
            "url": "http://127.0.0.1:8501" if item["id"] == "pixelle-video" else "",
            "apiUrl": "http://127.0.0.1:8502" if item["id"] == "pixelle-video" else "",
            "logPath": str(ROOT / "workspace" / "workbench" / "engines" / f"{item['id']}.log"),
            "safety": "不会从工作台读取或保存 API Key、Cookie、验证码。" if item["id"] != "social-auto-upload" else "上游命令可直接发布；当前只启用命令预览。",
        })
    return {
        "items": payload,
        "policy": "生成引擎可本地启动；平台适配器默认只生成计划，上传和发布需要即时确认。",
        "updatedAt": now_iso(),
    }


def start_integration(engine_id: str) -> dict:
    if OFFLINE_MODE:
        raise ValueError("offline mode does not start generation engines")
    if engine_id != "pixelle-video":
        raise ValueError("this integration is not launch-enabled")
    source = ROOT / "projects" / "Pixelle-Video"
    python = ROOT / "envs" / "pixelle_video" / "Scripts" / "python.exe"
    app = source / "web" / "app.py"
    api_app = source / "api" / "app.py"
    if not python.is_file() or not app.is_file() or not api_app.is_file():
        raise ValueError("Pixelle-Video source or runtime is missing")
    log_dir = ROOT / "workspace" / "workbench" / "engines"
    log_dir.mkdir(parents=True, exist_ok=True)
    ui_command = [
        str(python), "-m", "streamlit", "run", str(app),
        "--server.address=127.0.0.1", "--server.port=8501",
        "--server.headless=true", "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal", "--logger.level=warning",
    ]
    api_command = [str(python), str(api_app), "--host", "127.0.0.1", "--port", "8502"]
    engine_env = os.environ.copy()
    engine_env["PIXELLE_VIDEO_ROOT"] = str(source)
    engine_env["PIXELLE_OUTPUT_DIR"] = str(ROOT / "workspace" / "pixelle-video" / "output")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def spawn(key: str, command: list[str], log_name: str) -> subprocess.Popen:
        current = ENGINE_PROCESSES.get(key)
        if current and current.poll() is None:
            return current
        previous = ENGINE_LOG_HANDLES.pop(key, None)
        if previous:
            previous.close()
        handle = (log_dir / log_name).open("a", encoding="utf-8")
        process = subprocess.Popen(
            command, cwd=source, env=engine_env, stdin=subprocess.DEVNULL,
            stdout=handle, stderr=subprocess.STDOUT, creationflags=creationflags,
        )
        ENGINE_PROCESSES[key] = process
        ENGINE_LOG_HANDLES[key] = handle
        return process

    ui_process = spawn(engine_id, ui_command, f"{engine_id}.log")
    api_process = spawn(f"{engine_id}-api", api_command, f"{engine_id}-api.log")
    for process, port, label in ((ui_process, 8501, "UI"), (api_process, 8502, "API")):
        for _ in range(60):
            if process.poll() is not None:
                raise ValueError(f"Pixelle-Video {label} exited during startup; see {log_dir}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                    break
            except OSError:
                time.sleep(0.2)
    return next(item for item in integration_status()["items"] if item["id"] == engine_id)


def stop_integration(engine_id: str) -> dict:
    if engine_id != "pixelle-video":
        raise ValueError("this integration is not launch-enabled")
    for key in (engine_id, f"{engine_id}-api"):
        process = ENGINE_PROCESSES.get(key)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        handle = ENGINE_LOG_HANDLES.pop(key, None)
        if handle:
            handle.close()
        ENGINE_PROCESSES.pop(key, None)
    return next(item for item in integration_status()["items"] if item["id"] == engine_id)


def workflow_model() -> dict:
    manual = [stage for stage in WORKFLOW_STAGES if stage["manual"]]
    return {
        "stages": WORKFLOW_STAGES,
        "counts": {"total": len(WORKFLOW_STAGES), "manual": len(manual), "automated": sum(1 for stage in WORKFLOW_STAGES if stage["mode"] == "auto")},
        "manualSummary": [
            "定位重大变化与最终选题边界",
            "Brief 最终批准",
            "付费、私人素材上传、声音克隆、本人录音与音乐购买",
            "最终成品、声音、标题文案和音乐策略验收",
            "登录、验证码、权限提示与 prepare-only 上传确认",
            "点击正式发布",
            "数据身份冲突和重大策略调整",
        ],
    }


def production_request_summary(video_id: str, asset_binding: dict) -> dict:
    """Expose editable, non-secret form values, using current asset bindings."""
    try:
        request = load_json(CONTENT / video_id / "production" / "workbench_request.json")
    except UnicodeDecodeError:
        request = {}
    if not isinstance(request, dict):
        request = {}
    raw_parameters = request.get("route_parameters")
    if not isinstance(raw_parameters, dict):
        raw_parameters = {}
    parameters = {}
    for field in task_runner.ACTIONS["SAVE_PRODUCTION_REQUEST"]["fields"]:
        name = field["name"]
        if name == "asset_ids" or name not in raw_parameters:
            continue
        value = raw_parameters[name]
        if field["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                continue
            try:
                number = float(value)
            except (ValueError, OverflowError):
                continue
            if not math.isfinite(number) or not 0 <= number <= 10000:
                continue
            value = int(number) if number.is_integer() else number
        elif field["type"] == "checkbox":
            if not isinstance(value, bool):
                continue
        elif not isinstance(value, str):
            continue
        elif field["type"] == "select" and value not in field.get("options", []):
            continue
        else:
            value = value[:8000]
        parameters[name] = value
    raw_asset_ids = asset_binding.get("asset_ids", []) if isinstance(asset_binding, dict) else []
    asset_ids = list(dict.fromkeys(item for item in raw_asset_ids if isinstance(item, str) and item.strip())) if isinstance(raw_asset_ids, list) else []
    parameters["asset_ids"] = asset_ids
    saved_at = request.get("created_at", "")
    if not isinstance(saved_at, str):
        saved_at = ""
    return {"parameters": parameters, "savedAt": saved_at, "assetIds": asset_ids}


def project_summary(row: dict[str, str]) -> dict:
    video_id = row["video_id"]
    qa = load_json(CONTENT / video_id / "qa" / "qa_result.json")
    images = image_files(video_id)
    metrics = latest_metrics(video_id)
    mapping = account_mapping()
    progress = project_stage_progress(row)
    skill_plan = load_json(CONTENT / video_id / "production" / "skill_plan.json")
    provider_skill = skill_plan.get("provider_skill") if isinstance(skill_plan.get("provider_skill"), dict) else {}
    prompt_package = CONTENT / video_id / "production" / "prompt_package.json"
    asset_binding = media_library.bindings(video_id)
    asset_strategy = load_json(CONTENT / video_id / "production" / "asset_strategy.json")
    video_task = load_json(CONTENT / video_id / "production" / "video_task_package.json")
    video_spec = video_task.get("generation_spec") or {}
    dispatch_items = codex_dispatcher.list_items(
        video_id=video_id,
        store=ROOT / "data" / "codex_dispatch_queue.json",
    )
    dispatch = dispatch_items[0] if dispatch_items else {}
    return {
        "id": video_id,
        "title": row.get("title", "未命名内容"),
        "state": row.get("state", ""),
        "stateTone": STATE_COLORS.get(row.get("state", ""), "idea"),
        "type": row.get("content_type", ""),
        "pillar": row.get("pillar", ""),
        "hypothesis": row.get("hypothesis", ""),
        "nextAction": row.get("next_action", ""),
        "updatedAt": row.get("updated_at", ""),
        "publishedAt": row.get("published_at", ""),
        "cover": f"/asset/{video_id}/publish_images/{images[0]}" if images else "",
        "imageCount": len(images),
        "assetCount": len(asset_binding.get("asset_ids", [])),
        "assetStrategy": asset_strategy,
        "productionRequest": production_request_summary(video_id, asset_binding),
        "videoTask": {
            "ready": bool(video_task),
            "provider": video_task.get("provider_target", ""),
            "status": video_task.get("status", ""),
            "model": video_spec.get("model_proposal", ""),
            "aspectRatio": video_spec.get("aspect_ratio", ""),
            "duration": video_spec.get("total_duration_seconds"),
            "resolution": video_spec.get("resolution", ""),
        },
        "qaStatus": qa.get("verdict", qa.get("result", qa.get("conclusion", "未质检"))),
        "plays": metrics.get("plays", ""),
        "collects": metrics.get("collects", ""),
        "shares": metrics.get("shares", ""),
        "checkpoint": metrics.get("checkpoint", ""),
        "accountId": mapping.get(video_id, "scenery-main"),
        "skillPlan": {
            "status": skill_plan.get("status", "NOT_PLANNED"),
            "executor": skill_plan.get("executor", ""),
            "selectedVisualSkill": skill_plan.get("selected_visual_skill", ""),
            "selectionReason": skill_plan.get("selection_reason", ""),
            "providerTarget": skill_plan.get("provider_target", ""),
            "providerMode": skill_plan.get("provider_mode", ""),
            "promptCompiler": skill_plan.get("prompt_compiler", ""),
            "providerSkillId": provider_skill.get("id", ""),
            "providerSkillName": provider_skill.get("name", ""),
            "providerSkillUrl": provider_skill.get("url", ""),
            "providerSkillVisibility": provider_skill.get("visibility", ""),
            "providerSelectionReason": skill_plan.get("provider_selection_reason", ""),
            "promptPackageReady": prompt_package.is_file(),
            "skills": [step.get("skill", "") for step in skill_plan.get("steps", []) if step.get("skill")],
            "stepCount": len(skill_plan.get("steps", [])),
            "missing": skill_plan.get("missing_required_skills", []),
        },
        "dispatch": {
            "id": dispatch.get("dispatch_id", ""),
            "state": dispatch.get("state", "NOT_QUEUED"),
            "reason": dispatch.get("reason", ""),
            "attempts": dispatch.get("attempts", 0),
            "updatedAt": dispatch.get("updated_at", ""),
            "workerId": dispatch.get("worker_id", ""),
            "artifacts": dispatch.get("artifacts", []),
        },
        "stageProgress": {key: progress[key] for key in ("verified", "evidenceGaps", "total", "verifiedPercent", "current")},
    }


def projects(include_all: bool = False) -> list[dict]:
    items = [project_summary(row) for row in read_csv(ROOT / "data" / "content_registry.csv")]
    if include_all or active_account().get("account_id") == "open-topic-sandbox":
        return items
    active_id = active_account().get("account_id")
    return [item for item in items if item.get("accountId") == active_id]


def detail(video_id: str) -> dict:
    safe_video_id(video_id)
    row = next((item for item in read_csv(ROOT / "data" / "content_registry.csv") if item["video_id"] == video_id), None)
    if not row:
        raise FileNotFoundError(video_id)
    base = CONTENT / video_id
    summary = project_summary(row)
    files = {
        "brief": base / "brief.md",
        "routePlan": base / "production" / "route_plan.json",
        "skillPlan": base / "production" / "skill_plan.json",
        "promptPackageMd": base / "production" / "prompt_package.md",
        "promptPackageJson": base / "production" / "prompt_package.json",
        "assetBindings": base / "production" / "assets" / "asset_bindings.json",
        "assetStrategy": base / "production" / "asset_strategy.json",
        "manifest": base / "production" / "production_manifest.json",
        "qa": base / "qa" / "qa_result.json",
        "release": base / "approvals" / "release_package.json",
        "prepare": base / "approvals" / "prepare_receipt.json",
        "publish": base / "approvals" / "publish_receipt.json",
    }
    summary["artifacts"] = {key: {"path": str(path.relative_to(ROOT)), "exists": path.exists()} for key, path in files.items()}
    summary["images"] = [f"/asset/{video_id}/publish_images/{name}" for name in image_files(video_id)]
    summary["boundAssets"] = media_library.bindings(video_id)
    summary["metrics"] = latest_metrics(video_id)
    summary["qa"] = load_json(files["qa"])
    summary["release"] = load_json(files["release"])
    summary["stageProgress"] = project_stage_progress(row)
    return summary


def dashboard() -> dict:
    items = projects()
    intelligence = topic_intelligence()
    states: dict[str, int] = {}
    for item in items:
        states[item["state"]] = states.get(item["state"], 0) + 1
    published = [item for item in items if item["state"] == "PUBLISHED"]
    actions = [item for item in items if item["state"] not in {"PUBLISHED", "IDEA"}]
    shortlist = shortlist_data().get("items", [])
    offline = offline_status()
    return {
        "projectRoot": str(ROOT),
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "counts": {"total": len(items), "published": len(published), "active": len(actions), "skills": len(skill_catalog()), "shortlist": len(shortlist)},
        "states": states,
        "recent": sorted(items, key=lambda item: item["updatedAt"], reverse=True)[:8],
        "attention": sorted(actions, key=lambda item: item["updatedAt"], reverse=True)[:6],
        "safety": "发布按钮不在工作台内；工作台只做准备、校验与跳转，正式发布由你手动完成。",
        "workflow": {"total": len(WORKFLOW_STAGES), "manual": sum(1 for stage in WORKFLOW_STAGES if stage["manual"])},
        "topicRecommendation": next((item for item in intelligence["candidates"] if item.get("accountFit")), None),
        "account": active_account(),
        "trend": trend_status(),
        "offline": {"ready": offline["offlineReady"], "runtimeMode": offline["runtimeMode"], "snapshotPath": offline["snapshotPath"]},
    }


def video_provider_status() -> dict:
    data = load_json(VIDEO_PROVIDER_MATRIX)
    if not data:
        return {"decision": "UNRESEARCHED", "decision_summary": "尚未形成服务商决策。", "providers": []}
    return data


def skill_category(name: str, description: str) -> str:
    explicit = {
        "douyin-media-orchestrator": "视频制作",
        "douyin-prompt-director": "视频制作",
        "douyin-caption-pipeline": "声音字幕",
        "h3-prompt-writing": "视频制作",
        "cinematic-director-frame": "视觉风格",
    }
    if name in explicit:
        return explicit[name]
    value = f"{name} {description}".lower()
    if any(token in value for token in ("voice", "speech", "music", "sound", "dubbing", "audio", "字幕", "配音")):
        return "声音字幕"
    if any(token in value for token in ("remotion", "video", "seedance", "manim", "hyperframe", "视频")):
        return "视频制作"
    if any(token in value for token in ("wallpaper", "scenery", "collage", "image-gen", "imagegen", "flux", "postcard", "scrapbook", "风景", "壁纸", "拼贴")):
        return "视觉风格"
    if any(token in value for token in ("design", "frontend", "visual-style", "impeccable", "界面")):
        return "设计工具"
    return "其他"


def skill_catalog() -> list[dict[str, str]]:
    catalog = []
    if not SKILLS.exists():
        return catalog
    for folder in sorted(SKILLS.iterdir()):
        skill = folder / "SKILL.md"
        if not folder.is_dir() or folder.name.startswith(".") or not skill.exists():
            continue
        text = skill.read_text(encoding="utf-8", errors="replace")
        description = ""
        license_name = ""
        compatibility = ""
        for line in text.splitlines():
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("license:"):
                license_name = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("compatibility:"):
                compatibility = line.split(":", 1)[1].strip().strip('"')
            if line.strip() == "---" and description:
                break
        catalog.append({
            "name": folder.name,
            "description": description,
            "path": str(skill),
            "category": skill_category(folder.name, description),
            "license": license_name,
            "compatibility": compatibility,
        })
    return catalog


def run_audit() -> dict[str, str | int]:
    command = [str(ROOT / "envs" / "content" / "Scripts" / "python.exe"), str(ROOT / "src" / "workflow_control.py"), "audit"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    return {"returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def create_project(payload: dict) -> dict:
    video_id = safe_video_id(str(payload.get("videoId", "")).strip())
    title = str(payload.get("title", "")).strip()
    hypothesis = str(payload.get("hypothesis", "")).strip()
    content_type = str(payload.get("contentType", "")).strip()
    pillar = str(payload.get("pillar", "")).strip()
    if not title or not hypothesis or not pillar:
        raise ValueError("title, hypothesis and pillar are required")
    if content_type not in {"IMAGE_CAROUSEL", "ATMOSPHERE_VIDEO", "NARRATED_EXPLAINER"}:
        raise ValueError("invalid content type")
    accounts = account_data()
    account_id = payload.get("accountId", accounts.get("activeAccountId"))
    if not isinstance(account_id, str) or not any(profile.get("account_id") == account_id for profile in accounts["profiles"]):
        raise ValueError("unknown account profile")
    if any(row.get("video_id") == video_id for row in read_csv(ROOT / "data" / "content_registry.csv")):
        raise ValueError("project already exists")
    command = [
        str(ROOT / "envs" / "content" / "Scripts" / "python.exe"), str(ROOT / "src" / "workflow_control.py"), "init",
        "--video-id", video_id, "--title", title, "--hypothesis", hypothesis, "--content-type", content_type, "--pillar", pillar,
        "--hypothesis-id", str(payload.get("hypothesisId") or f"WB-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    ]
    baseline = str(payload.get("baselineVideoId", "")).strip()
    if baseline:
        command.extend(["--baseline-video-id", baseline])
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "project initialization failed")
    # Initialization can outlive a profile switch in this or another browser tab.
    map_project(video_id, account_id)
    return detail(video_id)


def trash_project(video_id: str, payload: dict) -> dict:
    safe_video_id(video_id)
    if payload.get("confirm") != video_id:
        raise ValueError("confirmation does not match project id")
    registry_path = ROOT / "data" / "content_registry.csv"
    rows = read_csv(registry_path)
    row = next((item for item in rows if item.get("video_id") == video_id), None)
    if not row:
        raise FileNotFoundError(video_id)
    if row.get("state") == "PUBLISHED" and payload.get("publishedAcknowledged") is not True:
        raise ValueError("published project requires explicit acknowledgement")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = TRASH / "projects" / f"{stamp}__{video_id}"
    archive.mkdir(parents=True, exist_ok=False)
    source = CONTENT / video_id
    if source.exists():
        shutil.move(str(source), str(archive / "content"))
    mapping_rows = read_csv(ACCOUNT_MAP)
    account_id = next((item.get("account_id", "") for item in mapping_rows if item.get("video_id") == video_id), "")
    save_json(archive / "trash_manifest.json", {
        "kind": "project", "trash_id": archive.name, "video_id": video_id, "trashed_at": datetime.now().astimezone().isoformat(),
        "registry_row": row, "account_id": account_id, "recoverable": True,
    })
    write_csv(registry_path, [item for item in rows if item.get("video_id") != video_id], list(rows[0].keys()))
    write_csv(ACCOUNT_MAP, [item for item in mapping_rows if item.get("video_id") != video_id], ["video_id", "account_id"])
    return {"trashed": True, "trashId": archive.name, "recoverable": True}


def trash_skill(name: str, payload: dict) -> dict:
    if not name or name != Path(name).name or name.startswith(".") or payload.get("confirm") != name:
        raise ValueError("invalid skill confirmation")
    source = SKILLS / name
    if source.parent.resolve() != SKILLS.resolve() or not source.exists() or not (source / "SKILL.md").is_file():
        raise FileNotFoundError(name)
    is_directory_link = source.is_symlink() or bool(getattr(source, "is_junction", lambda: False)())
    link_target = str(source.resolve()) if is_directory_link else ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = TRASH / "skills" / f"{stamp}__{name}"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if is_directory_link:
        archive.mkdir(parents=False, exist_ok=False)
        source.rmdir()
    else:
        shutil.move(str(source), str(archive))
    save_json(archive / "trash_manifest.json", {
        "kind": "skill", "trash_id": archive.name, "skill_name": name, "trashed_at": datetime.now().astimezone().isoformat(),
        "original_path": str(source), "storage_mode": "junction" if is_directory_link else "directory",
        "link_target": link_target, "recoverable": True,
    })
    return {"trashed": True, "trashId": archive.name, "recoverable": True}


def trash_catalog() -> list[dict]:
    items = []
    for kind in ("projects", "skills"):
        folder = TRASH / kind
        if not folder.exists():
            continue
        for child in sorted(folder.iterdir(), reverse=True):
            manifest = load_json(child / "trash_manifest.json")
            if manifest:
                items.append(manifest)
    return items


def restore_trash(payload: dict) -> dict:
    kind = str(payload.get("kind", ""))
    trash_id = str(payload.get("trashId", ""))
    if kind not in {"project", "skill"} or trash_id != Path(trash_id).name or payload.get("confirm") != trash_id:
        raise ValueError("invalid restore request")
    archive = TRASH / ("projects" if kind == "project" else "skills") / trash_id
    manifest = load_json(archive / "trash_manifest.json")
    if not manifest:
        raise FileNotFoundError(trash_id)
    if kind == "project":
        video_id = manifest["video_id"]
        target = CONTENT / video_id
        if target.exists() or any(row.get("video_id") == video_id for row in read_csv(ROOT / "data" / "content_registry.csv")):
            raise ValueError("project destination already exists")
        if (archive / "content").exists():
            shutil.move(str(archive / "content"), str(target))
        rows = read_csv(ROOT / "data" / "content_registry.csv")
        rows.append(manifest["registry_row"])
        write_csv(ROOT / "data" / "content_registry.csv", rows, list(manifest["registry_row"].keys()))
        map_project(video_id, manifest.get("account_id") or "scenery-main")
    else:
        name = manifest["skill_name"]
        target = SKILLS / name
        if os.path.lexists(target):
            raise ValueError("skill destination already exists")
        if manifest.get("storage_mode") == "junction":
            link_target = Path(str(manifest.get("link_target", "")))
            if not link_target.is_dir() or not (link_target / "SKILL.md").is_file():
                raise ValueError("skill junction target is unavailable")
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(target), str(link_target)],
                text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=15,
            )
            if result.returncode or not target.exists():
                raise ValueError(result.stderr.strip() or result.stdout.strip() or "failed to restore skill junction")
            shutil.rmtree(archive)
        else:
            (archive / "trash_manifest.json").unlink()
            shutil.move(str(archive), str(target))
        return {"restored": True, "kind": kind, "name": name}
    shutil.rmtree(archive)
    return {"restored": True, "kind": kind}


CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


class ClientDisconnected(ConnectionError):
    """A known disconnect originating from this request's client stream."""


class ClientStream:
    """Mark client I/O failures without hiding downstream service failures."""

    def __init__(self, stream) -> None:
        self.stream = stream

    def _call(self, method: str, *args):
        try:
            return getattr(self.stream, method)(*args)
        except CLIENT_DISCONNECT_ERRORS as exc:
            raise ClientDisconnected(str(exc)) from exc

    def read(self, size: int = -1):
        return self._call("read", size)

    def readline(self, size: int = -1):
        return self._call("readline", size)

    def write(self, data):
        return self._call("write", data)

    def flush(self):
        return self._call("flush")


class WorkbenchHandler(SimpleHTTPRequestHandler):
    server_version = "DouyinWorkbench/0.2"

    def log_message(self, format: str, *args) -> None:
        return

    def handle_one_request(self) -> None:
        # Reloading/closing a tab may disconnect during parsing, writing or flush.
        # Only transport disconnects are expected; other failures stay observable.
        input_stream, output_stream = self.rfile, self.wfile
        self.rfile, self.wfile = ClientStream(input_stream), ClientStream(output_stream)
        try:
            super().handle_one_request()
        except ClientDisconnected:
            self.close_connection = True
        finally:
            self.rfile, self.wfile = input_stream, output_stream

    def send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_security_headers(self, offline_snapshot: bool = False) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if offline_snapshot:
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src data:; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        else:
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def send_file(self, path: Path, offline_snapshot: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers(offline_snapshot=offline_snapshot)
        self.end_headers()
        self.wfile.write(data)

    def read_body(self) -> dict:
        length = min(int(self.headers.get("Content-Length", "0") or 0), 128_000)
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def valid_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and parsed.netloc == self.headers.get("Host", "")

    def do_GET(self) -> None:
        parsed_request = urlparse(self.path)
        path = parsed_request.path
        query = parse_qs(parsed_request.query)
        try:
            if path == "/api/dashboard":
                return self.send_json(dashboard())
            if path == "/api/projects":
                return self.send_json(projects())
            if path == "/api/assets":
                include_trashed = (query.get("includeTrash") or [""])[0].lower() == "true"
                project_id = (query.get("projectId") or [""])[0]
                return self.send_json({"items": media_library.catalog(project_id=project_id, include_trashed=include_trashed)})
            if path.startswith("/api/projects/") and path.endswith("/assets"):
                video_id = unquote(path.removeprefix("/api/projects/").removesuffix("/assets").strip("/"))
                return self.send_json(media_library.bindings(video_id))
            if path.startswith("/api/projects/"):
                return self.send_json(detail(unquote(path.rsplit("/", 1)[-1])))
            if path == "/api/skills":
                return self.send_json(skill_catalog())
            if path == "/api/topics":
                return self.send_json(topics())
            if path == "/api/topic-intelligence":
                return self.send_json(topic_intelligence())
            if path == "/api/trends":
                return self.send_json(trend_status())
            if path == "/api/offline":
                return self.send_json(offline_status())
            if path == "/api/shortlist":
                return self.send_json(shortlist_data())
            if path == "/api/accounts":
                return self.send_json(account_data())
            if path == "/api/drafts":
                return self.send_json(draft_store.load_draft(*[(query.get(name) or [""])[0] for name in ("account_id", "video_id", "action")]))
            if path == "/api/providers/flova/status":
                if OFFLINE_MODE:
                    return self.send_json({"available": False, "authenticated": False, "credits_balance": None,
                                           "subscription_info": None, "message": "离线模式未访问 Flova", "checked_at": now_iso()})
                return self.send_json(flova_runtime.account_status(ROOT))
            if path == "/api/trash":
                return self.send_json(trash_catalog())
            if path == "/api/workflow":
                return self.send_json(workflow_model())
            if path == "/api/metrics":
                return self.send_json(all_metrics())
            if path == "/api/toolchain":
                return self.send_json(toolchain_status())
            if path == "/api/integrations":
                return self.send_json(integration_status())
            if path == "/api/video-providers":
                return self.send_json(video_provider_status())
            if path == "/api/actions":
                return self.send_json({"items": task_runner.action_catalog(), "publishBoundary": "Flova generation requires explicit task approval; no job publishes to Douyin."})
            if path == "/api/jobs":
                return self.send_json({"items": task_runner.list_jobs((query.get("videoId") or [""])[0], (query.get("limit") or [100])[0])})
            if path == "/api/dispatch":
                return self.send_json({"items": codex_dispatcher.list_items(
                    state=(query.get("state") or [""])[0],
                    video_id=(query.get("videoId") or [""])[0],
                    store=ROOT / "data" / "codex_dispatch_queue.json",
                )})
            if path.startswith("/api/jobs/"):
                job_id = unquote(path.removeprefix("/api/jobs/").strip("/"))
                return self.send_json(task_runner.get_job(job_id))
            if path == "/api/health":
                return self.send_json({"status": "ok", "root": str(ROOT), "mode": "offline" if OFFLINE_MODE else "local"})
            if path.startswith("/job-asset/"):
                parts = [unquote(part) for part in path.split("/")[2:]]
                if len(parts) != 2:
                    raise ValueError("invalid job artifact path")
                return self.send_file(task_runner.resolve_job_artifact(parts[0], parts[1]))
            if path.startswith("/library-asset/"):
                asset_id = unquote(path.removeprefix("/library-asset/").strip("/"))
                return self.send_file(media_library.resolve_asset(asset_id))
            if path == "/offline/workbench_offline.html":
                return self.send_file(OFFLINE_DIR / "workbench_offline.html", offline_snapshot=True)
            if path.startswith("/asset/"):
                parts = [unquote(part) for part in path.split("/")[2:]]
                if len(parts) < 2:
                    raise ValueError("invalid asset path")
                video_id = safe_video_id(parts[0])
                candidate = (CONTENT / video_id / "production" / Path(*parts[1:])).resolve()
                allowed = (CONTENT / video_id / "production").resolve()
                if allowed not in candidate.parents:
                    raise ValueError("invalid asset path")
                return self.send_file(candidate)
            requested = "index.html" if path in {"", "/"} else path.lstrip("/")
            candidate = (STATIC / requested).resolve()
            if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
                raise ValueError("invalid static path")
            return self.send_file(candidate)
        except ClientDisconnected:
            raise
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            if path.startswith("/api/"):
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            else:
                self.send_error(HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - local diagnostics
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed_request = urlparse(self.path)
        path = parsed_request.path
        if not self.valid_origin():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if path == "/api/assets/import":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw_metadata = unquote(self.headers.get("X-Asset-Metadata", ""))
                metadata = json.loads(raw_metadata) if raw_metadata else {}
                return self.send_json(media_library.import_stream(self.rfile, length, metadata), HTTPStatus.CREATED)
            except (ValueError, json.JSONDecodeError) as exc:
                return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except ClientDisconnected:
                raise
            except Exception as exc:
                return self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        allowed = {"/api/audit", "/api/topics/suggest", "/api/accounts/select", "/api/accounts/create", "/api/projects/create", "/api/trash/restore", "/api/shortlist/save", "/api/shortlist/remove", "/api/offline/export", "/api/jobs/create", "/api/assets/register-path", "/api/drafts/save"}
        is_job_action = path.startswith("/api/jobs/") and any(path.endswith(suffix) for suffix in ("/run", "/cancel", "/recover", "/resolve"))
        is_engine_action = path.startswith("/api/integrations/") and (path.endswith("/start") or path.endswith("/stop"))
        is_asset_action = path.startswith("/api/assets/") and (path.endswith("/trash") or path.endswith("/restore"))
        is_asset_binding = path.startswith("/api/projects/") and path.endswith("/assets/bind")
        if path not in allowed and not is_job_action and not is_engine_action and not is_asset_action and not is_asset_binding and not (path.startswith("/api/projects/") and path.endswith("/trash")) and not (path.startswith("/api/skills/") and path.endswith("/trash")):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            if path == "/api/audit":
                return self.send_json(run_audit())
            payload = self.read_body()
            if path == "/api/drafts/save":
                return self.send_json(draft_store.save_draft(payload))
            if path == "/api/topics/suggest":
                return self.send_json(topic_suggestions(payload))
            if path == "/api/shortlist/save":
                return self.send_json(save_shortlist_item(payload), HTTPStatus.CREATED)
            if path == "/api/shortlist/remove":
                return self.send_json(remove_shortlist_item(payload))
            if path == "/api/offline/export":
                target = export_offline_snapshot()
                return self.send_json({"exported": True, "path": str(target), "url": "/offline/workbench_offline.html", "generatedAt": now_iso()})
            if path == "/api/accounts/select":
                return self.send_json(select_account(str(payload.get("accountId", ""))))
            if path == "/api/accounts/create":
                return self.send_json(create_account(payload), HTTPStatus.CREATED)
            if path == "/api/projects/create":
                return self.send_json(create_project(payload), HTTPStatus.CREATED)
            if path == "/api/assets/register-path":
                return self.send_json(media_library.import_existing(str(payload.get("path", "")), payload), HTTPStatus.CREATED)
            if is_asset_binding:
                video_id = unquote(path.removeprefix("/api/projects/").removesuffix("/assets/bind").strip("/"))
                asset_ids = payload.get("assetIds") if isinstance(payload.get("assetIds"), list) else []
                return self.send_json(media_library.bind_assets(video_id, asset_ids))
            if is_asset_action:
                suffix = "/trash" if path.endswith("/trash") else "/restore"
                asset_id = unquote(path.removeprefix("/api/assets/").removesuffix(suffix).strip("/"))
                expected = "TRASHED" if suffix == "/trash" else "ACTIVE"
                if payload.get("confirm") != asset_id:
                    raise ValueError("confirmation does not match asset id")
                return self.send_json(media_library.set_status(asset_id, expected))
            if path == "/api/jobs/create":
                if OFFLINE_MODE and str(payload.get("actionId", "")).upper() == "GENERATE_FLOVA_VIDEO":
                    raise ValueError("离线模式不允许创建外部生成任务")
                return self.send_json(task_runner.create_job(payload), HTTPStatus.CREATED)
            if is_job_action:
                suffix = next(value for value in ("/run", "/cancel", "/recover", "/resolve") if path.endswith(value))
                job_id = unquote(path.removeprefix("/api/jobs/").removesuffix(suffix).strip("/"))
                if OFFLINE_MODE and task_runner.get_job(job_id).get("action_id") == "GENERATE_FLOVA_VIDEO" and suffix != "/cancel":
                    raise ValueError("离线模式不允许执行外部生成任务")
                if suffix == "/resolve":
                    result = task_runner.resolve_job(job_id, payload)
                else:
                    result = {"/run": task_runner.submit_job, "/cancel": task_runner.cancel_job, "/recover": task_runner.recover_job}[suffix](job_id)
                return self.send_json(result, HTTPStatus.OK if suffix == "/cancel" else HTTPStatus.ACCEPTED)
            if is_engine_action:
                suffix = "/start" if path.endswith("/start") else "/stop"
                engine_id = unquote(path.removeprefix("/api/integrations/").removesuffix(suffix).strip("/"))
                result = start_integration(engine_id) if suffix == "/start" else stop_integration(engine_id)
                return self.send_json(result, HTTPStatus.ACCEPTED if suffix == "/start" else HTTPStatus.OK)
            if path == "/api/trash/restore":
                return self.send_json(restore_trash(payload))
            if path.startswith("/api/projects/"):
                video_id = unquote(path.removeprefix("/api/projects/").removesuffix("/trash").strip("/"))
                return self.send_json(trash_project(video_id, payload))
            if path.startswith("/api/skills/"):
                name = unquote(path.removeprefix("/api/skills/").removesuffix("/trash").strip("/"))
                return self.send_json(trash_skill(name, payload))
        except ClientDisconnected:
            raise
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except draft_store.DraftConflict as exc:
            self.send_json({"error": str(exc), "code": "DRAFT_CONFLICT", "current": exc.current}, HTTPStatus.CONFLICT)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    global OFFLINE_MODE
    import argparse

    parser = argparse.ArgumentParser(description="Run the local Douyin workflow workbench")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--offline", action="store_true", help="run with all external platform actions visibly disabled")
    parser.add_argument("--export-offline", action="store_true", help="write a self-contained read-only HTML snapshot and exit")
    args = parser.parse_args()
    OFFLINE_MODE = bool(args.offline or os.environ.get("DOUYIN_WORKBENCH_OFFLINE") == "1")
    task_runner.OFFLINE_MODE = OFFLINE_MODE
    if args.export_offline:
        print(export_offline_snapshot())
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), WorkbenchHandler)
    task_runner.recover_interrupted_jobs()
    mode = "offline" if OFFLINE_MODE else "local"
    print(f"Douyin Workflow Workbench ({mode}): http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for engine_id in list(ENGINE_PROCESSES):
            try:
                stop_integration(engine_id)
            except Exception:
                pass
        server.server_close()


if __name__ == "__main__":
    main()
