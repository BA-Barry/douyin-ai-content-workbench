# 内容工作台 v3 架构

## 事实源

- 项目状态：`data/content_registry.csv`
- 账号档案：`data/account_profiles.json`、`data/account_content_map.csv`
- 选题收藏：`data/workbench_shortlist.json`
- 任务历史：`data/workbench_jobs.json`
- 素材库索引：`data/media_library.json`
- 素材文件：`assets/library/<asset_id>/`
- 项目素材绑定：`content/<video_id>/production/assets/asset_bindings.json`
- 项目素材策略：`content/<video_id>/production/asset_strategy.json`
- Skill 执行计划：`content/<video_id>/production/skill_plan.json`
- 趋势缓存：`research/trend_monitor/latest.json`
- 项目证据：`content/<video_id>/`
- Skill：`C:\Users\86135\.codex\skills`（只索引 Codex 管理的元数据；运行缓存仍在 G 盘）

工作台不建立第二套项目状态，不直接修改内容阶段；正式状态仍通过 `src/workflow_control.py` 转换。任务状态只描述一次本地命令的执行结果，不等于内容阶段状态。

工作台 UI 使用统一“制作中心”，新建时选择图片或视频；项目创建后 `content_type` 固定，任务步骤再按图片或视频路线动态呈现。两条底层生产线共用素材库和治理底座，但不混写制作产物。视频在选择供应端前先生成素材策略；条件性图片锚点是视频项目内的依赖，不是新的图片内容项目。

## 任务执行层

`workbench/task_runner.py` 是唯一任务执行入口：

- 只接受固定白名单动作；
- 项目路径参数必须位于当前 `content/<video_id>/`；
- 任务记录、日志、返回码和产物路径持久化；
- 支持排队、运行、成功、阻断、失败与取消状态；
- 不包含平台登录、上传、正式发布或任意 shell 动作。

`workbench/skill_router.py` 读取项目路线、brief 和制作要求，自动选择所有相关 Skills；它不会把所有已安装 Skill 无差别调用。统一的 `douyin-prompt-director` 先固定导演语言、分镜/逐图结构、连续性、声音与 QA，再为图片、Seedance 或 MiniMax H3 中唯一一个目标编译提示词；`cinematic-director-frame` 只在强镜头语言场景以 prompt-only 方式加入。网页只生成计划和日志，实际 instruction-only Skill 必须由 Codex 任务执行。

`MoneyPrinterTurbo` 提供参数化任务页范式，`Pixelle-Video` 提供 Pipeline/引擎范式，`social-auto-upload` 只提供平台载荷与命令预览范式。采用详情见 `research/workbench/REFERENCE_ADOPTION_V3_20260823.md`。

## 生成引擎层

Pixelle-Video 的运行时和历史实验仍保留，但新任务动作已禁用。图片生成固定由 Codex 端完成；视频镜头固定由即梦 / Seedance 完成。工作台当前生成 Seedance 任务包，尚未形成自动提交、轮询、失败重试和原文件下载闭环。Remotion、HyperFrames 镜头语言和 video-use 只负责后期，不冒充视频生成模型。

完整自治需要一个常驻或定时 Codex dispatcher：只领取 `READY_FOR_CODEX` 计划，在同一项目目录执行已安装 Skills，并把每步状态、产物和错误写回计划。调度器不能跨越费用、私人素材上传、声音权利、prepare-only 和发布确认门。

## 本地模式

普通启动：

```powershell
& 'G:\抖音视频\workbench\start-workbench.ps1'
```

可离线完成：账号档案切换、选题浏览与收藏、项目创建、证据检查、流程查看、素材预览、审计、本地制作规划、历史指标复盘、Skill 索引和离线快照导出。

## 强制离线模式

```powershell
& 'G:\抖音视频\workbench\start-workbench-offline.ps1'
```

该模式不增加新的执行能力，只把联网边界显式化并隐藏平台入口。趋势与指标仅显示本地缓存；不会伪装刷新成功。

## 无服务器离线快照

```powershell
& 'G:\抖音视频\workbench\export-offline-workbench.ps1'
```

输出：`G:\抖音视频\workbench\offline\workbench_offline.html`

这是单个只读 HTML 文件：无 `fetch`、无外部脚本、无远程字体、无图片请求、无账号凭证。它适合断网查看账号定位、收藏候选、项目阶段和联网边界；需要刷新时重新导出。

## 联网边界

- 抖音热榜、搜索联想、创作灵感与官方活动刷新；
- 创作者中心作品指标新增快照；
- Prepare-only 上传；
- 正式发布和平台音乐选择。

任何平台上传、发布、评论、点赞、关注或私信仍遵循 `MASTER_WORKFLOW.md` 的即时确认门。

## 安全与恢复

- 服务只绑定 `127.0.0.1`；
- 写入接口校验同源请求；
- 页面使用 CSP、禁止 iframe 嵌入并禁止 MIME 猜测；
- 项目和 Skill 删除继续进入 G 盘可恢复回收站；
- 离线快照完全只读，不提供修改或发布按钮。
