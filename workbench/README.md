# 抖音内容工作台

本机网页入口：`http://127.0.0.1:8765/`

日常使用可直接双击 `workbench\打开工作台.cmd`。它会先检查本地健康接口；若服务未运行，则使用 G 盘项目环境在后台启动，确认可用后打开网页。它不会创建开机启动项或 Windows 计划任务。

只启动、不打开浏览器：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\workbench\open-workbench.ps1 -NoBrowser`。启动器会核对已有服务的项目目录和运行模式；端口被其他服务占用时会提示原因。每次启动日志保存在 `workspace/workbench/runtime/`。

制作中心现支持：已保存参数回填；按账号、项目和任务暂存本标签页的未提交输入；项目独立执行记录；断线后的“重试连接”。未提交输入不会自动写盘，刷新或关闭页面前应执行保存。当前任务可直接从下拉框切换，详细工具说明默认折叠；手机端从“菜单”进入导航。

本轮改动与验证见 [2026-09-25 使用稳定性改进](HARDENING_20260925.md)。

启动：在 PowerShell 运行：

```powershell
& 'G:\抖音视频\workbench\start-workbench.ps1'
```

工作台直接读取 `data/content_registry.csv` 与每条内容的 `production/`、`qa/`、`approvals/`、`metrics/` 文件；它不复制状态，也不保存账号凭证。

当前页面：

- 总览：账号承诺、项目统计、下一候选与人工待办；
- 选题情报中心：合并 30 个内容领域、125+ 候选题、抖音趋势快照、风景正式选题池和 100 条 LLM 课程知识题；
- 内容项目：查看素材、QA、发布包与指标证据；
- 制作中心：在同一页面新建图片或视频作品、继续已有项目、保存制作要求、查看自动 Skill 编排、执行任务与检查产物；项目建立后路线锁定；
- 流程总控：先显示图片 / 视频制作路线边界与人工确认总表，再逐项列出 E0–N1 共 18 个阶段、通过条件、失败回退和人工介入；
- 发布与数据：最终验收清单、发布队列与只读指标快照；
- Skill 管理：按视觉风格、视频制作、声音字幕、设计工具和其他分类检索本地 Skill，并显示许可、运行要求与可恢复删除入口。
- 离线与队列：显示本地能力、缓存、联网边界、收藏选题、制作阶段和独立离线快照。

账号切换使用 `data/account_profiles.json` 与 `data/account_content_map.csv`。它只切换本地运营档案、账号定位和项目视图，不保存或切换抖音 Cookie；平台账号仍由用户在创作者中心手动登录。

“抖音流量与热点监控”已暂停，工作台只读取 `research/trend_monitor/latest.json` 中的历史快照，不再定时抓取热点。当前唯一活动心跳是图片制作调度器；它每 15 分钟只查看 READY 队列，队列为空就静默结束。

项目和非系统 Skill 的删除采用可恢复回收站：`trash/projects/` 与 `trash/skills/`。确认在工作台内完成，不依赖浏览器原生弹窗；输入完整 ID / 名称后按钮才会启用，并显示具体错误。删除本地项目不会删除抖音平台作品。

当前媒体边界：图片由 Codex 端生成；视频默认由私有 Flova Skill `抖音导演提示词编译器` 接收统一导演包，并在 Flova 内按任务选择 Seedance/H3 等模式；Codex 负责 brief、分镜、确认卡、素材接收，Remotion / video-use / FFmpeg 负责后期。详见 `workflow/MEDIA_PRODUCTION_WORKFLOW_V1.md`。

制作表单不再要求用户选择单个 Skill。保存内容要求后，`workbench/skill_router.py` 会根据项目路线、brief 和关键词选择所有相关能力，并写入 `production/workbench_request.json`、`production/skill_plan.json` 与 `production/dispatch_receipt.json`。图片和视频路线都会先经过 `douyin-prompt-director`，形成统一的 `production/prompt_package.md/json`；视频未点名服务商时默认走私有 Flova Skill，明确点名即梦/Seedance 或 H3 时保留对应直达编译器。工作台动作“生成视频任务确认卡”调用 `src/video_task_compiler.py`，生成 provider-agnostic 的 prepare-only `production/video_task_package.json`。强电影镜头可按需附加 `cinematic-director-frame` prompt-only。`src/codex_dispatcher.py` 使用计划哈希和租约保证同一计划只被领取一次；图片路线在 Brief 批准后进入 READY，视频、费用、声音和上传保持人工门。

项目卡片的“自动 Skill 编排”区同时显示 `provider_target`、`prompt_compiler`、私有 Flova Skill 名称和提示词包是否存在，便于确认实际将走 IMAGEGEN、FLOVA、Seedance 直达还是 MiniMax H3 直达。Skill 回收站支持普通目录和 G 盘源代码的 Codex Junction：移入 Junction Skill 时只移除 C 盘发现链接，G 盘源文件保持不变，恢复时重新建立链接。

“制作中心”使用 `src/workflow_control.py init` 建立图片或视频项目，创建时固定账号归属，并展示从选题、素材、制作、QA 到发布准备的操作入口。

制作中心使用 `workbench/task_runner.py`。白名单动作包括全项目审计、项目证据追踪、制作要求与 Skill 计划保存、视频任务确认卡、媒体技术检测、发布包构建/校验、prepare-only 任务生成、social-auto-upload 命令预览和指标摘要；Pixelle 仅保留一个不可创建的历史动作。任务历史写入 `data/workbench_jobs.json`，任务产物写入 `workspace/workbench/jobs/<job_id>/`；执行器不接受任意 shell 命令。

Pixelle-Video 的历史工程仍保留在 `envs/pixelle_video`，用于读取既有实验，不再显示为主创作页的视频生成动作。Flova 官方 CLI v0.0.10、官方 Skill、OAuth 和只读状态已通过受控验收；Seedance 官方 API 作为后续单镜头直接后端，即梦网页作为人工交接备用。决策证据见 `workflow/VIDEO_PROVIDER_DECISION_V1.md`；首次 Flova 生成仍需单独确认预计积分或费用，也不会把 Pixelle 或本地推拉动效静默当作替代路线。

`social-auto-upload` 当前只用于生成图文/视频命令预览。它的上游上传命令具备立即发布能力，因此工作台固定输出 `executable=false`，不会执行登录、Cookie 校验、上传或发布。

选题助手只生成候选草案，不会自动写入 registry 或创建内容项目。正式立项仍需假设卡和用户批准。

候选题现在可以先收藏到 `data/workbench_shortlist.json`。收藏只进入本地队列，不等于批准、立项或开始制作。

每个项目详情会按 E0–N1 检查 18 个阶段的真实文件，区分证据齐全、历史证据缺口、当前可推进、等待人工确认和尚未到达。registry 状态仍是唯一状态源；就绪度不会擅自转换状态。

离线使用：

```powershell
# 强制离线模式：隐藏平台入口，只使用本地数据和缓存
& 'G:\抖音视频\workbench\start-workbench-offline.ps1'

# 不启动服务器，导出单个只读 HTML
& 'G:\抖音视频\workbench\export-offline-workbench.ps1'
```

离线快照输出到 `G:\抖音视频\workbench\offline\workbench_offline.html`。它不请求网络、不含凭证；趋势与平台指标只能显示最近一次本地缓存。

GitHub 调研与采纳依据：`research/workbench/REFERENCE_ADOPTION_V3_20260823.md`。架构与边界：`workbench/ARCHITECTURE_V2.md`。

工作台 v4 的视觉系统位于 `workbench/workbench.visual-style.md`；Taste Skill 与 Impeccable 的来源、许可证、适用边界和本次改造记录位于 `research/workbench/DESIGN_SKILL_ADOPTION_V4_20260823.md`。默认创作页采用 Operate 模式，将项目上下文、六阶段进度、任务参数、执行状态和 9:16 预览合并为一条操作路径。

安全边界：页面能运行项目审计、展示素材与跳转到创作者中心。上传、对外发布、互动及任何需确认的动作不由它自动执行。
