# 抖音项目工具链当前状态

更新时间：2026-08-18  
判定口径：`PASS` 只表示已用实际文件或自动化测试验证相应技术能力，不代表内容质量、平台权限或用户审批通过。

## 总结

整体工具链不能称为“全部测试无误”。当前状态是：

- 本地工程主链：`PASS`
- 正式内容生产链：`PARTIAL`
- 抖音发布与真实监控闭环：`NOT_TESTED_END_TO_END`
- 当前项目自动化测试：`18/18 PASS`
- `workflow_control.py audit`：`PASS`

## AI造境扩展（2026-08-18 晚）

- `visual-style`、`flux-best-practices`、`baoyu-image-gen` 三项Skill已安装；实体在 `.\skills`，Codex目录为Junction。
- DepthFlow 1.0.0 已建立项目目录隔离运行时并完成真实竖屏景深循环渲染；本地补丁增加 `DEPTHFLOW_CACHE_DIR`，上游首次产生的32KB 系统级目录缓存已迁移回项目目录。
- 新增 `generation_job_validator.py`、`render_parallax.py`、`visual_asset_qa.py` 和5项定向测试；定向测试 `5/5 PASS`，既有测试加载项目环境后仍为 `18/18 PASS`。
- Codex原生图片生成本轮返回 HTTP 404，未切换付费API，因此AI造境图像供应端仍为 `BLOCKED`；本地动效与QA链为 `PASS`，整体扩展为 `PARTIAL`。
- 完整说明：`workflow/AI_SCENERY_TOOLCHAIN.md`；测试：`workspace/ai_scenery_toolchain_20260818/TEST_RESULTS.md`。

## 分段状态

| 环节 | 状态 | 已验证 | 未验证或阻断 |
|---|---|---|---|
| 主控状态机与文件审计 | PASS_WITH_GAPS | 合法迁移、禁止跳状态、账号研究门、审计、审批文件和指标检查已有单元测试 | brief/final/publish 批准尚未绑定产物哈希；视频级研究门较浅；QA 仍依赖 Markdown 字符串 |
| 数据契约与交接 | PASS | 六类 CSV 模板、Agent 目录隔离、handoff、来源与素材台账均已实际使用 | production manifest 与 material manifest 尚未完全统一 |
| 研究环境 | PASS_WITH_LIMITS | 项目目录 DuckDB/scikit-learn/Trafilatura 环境可运行；真实评论与样本研究已经产出 | 抖音评论深采样仍不足；平台抓取限制下不能自动补齐；不能把B站排序冒充抖音事实 |
| 选题、来源和分镜 | PASS | 选题评分、15题候选池、SourceLedger、shot source mapping 已验证 | 尚未用正式新视频完整走过 v2 的视频级事实门和 brief 哈希锁 |
| Remotion视觉 | PASS | 1080×1920/30fps 完整渲染、8秒非PPT预演、安全区、字体、概率一致性和哈希已验证；用户认可本次预演方向 | 视觉方向通过不代表正式成片；真实录屏/产品界面流程尚未完整测试 |
| FFmpeg/ffprobe剪辑与技术QA | PASS | 项目目录 ffmpeg/ffprobe、音画合成、H.264/AAC、黑帧、冻结、静音、EBU R128、哈希只读检查均通过 | 机器探针不能判断内容价值、AI味或PPT感；需人工QA |
| 本地辅助CLI | PASS | `qa_probe`、manifest validator、snapshot importer、transcript adapter；本轮修复无音轨预演误报，完整测试18/18通过 | transcript adapter只通过fixture；真实ASR运行时和真实中文时间戳尚未接入 |
| 中文配音 | ENGINEERING_PASS / PRODUCTION_FAIL | MeloTTS权重、项目目录环境、逐句生成、响度、峰值、句间处理与A/B短样可运行 | zero-BERT自然度不合格；用户明确不接受本轮A/B；完整BERT链、其他许可清晰音色和真实ASR回环未通过 |
| HyperFrames | PAUSED | 曾完成3秒渲染smoke | CLI硬编码写用户目录，不满足项目目录约束，禁止生产运行 |
| Seedance/Generative Media | PROMPT_ONLY | Skill来源和提示词能力已审计 | 未调用外部生成、未测试费用/上传/成片质量；未经批准不得运行 |
| TzFilm Douyin Tool | PIN_REFERENCE | 代码、schema、Excel/SQLite思路已审计 | macOS AppleScript与Windows不兼容；自动回复、登录profile和外发永久禁用，不作为采集器运行 |
| 抖音prepare-only | NOT_TESTED_END_TO_END | 已定义权限边界和回执要求 | 尚未以用户批准的正式成片在创作者中心完成上传填表并可靠停在发布按钮前 |
| 正式发布 | NOT_TESTED | 状态门和确认规则已建立 | 从未执行点击发布；必须在动作发生前获得用户确认 |
| 2h/24h/72h指标监控 | PARTIAL | snapshot importer对CSV/XLSX fixture通过，重复数据会阻断 | 未用真实已发布作品校准导出表头；调度、登录失效、迟到窗口和真实字段可见性未闭环 |
| 收益化实验 | NOT_STARTED | 已完成版权、商业化顺序与实验边界研究 | 尚无足够自有发布数据，不启动带货、广告、投流或收益归因 |

## 当前可放心复用的最小栈

1. R1 研究台账与本地结构化分析。
2. R2 证据优先镜头表和来源映射。
3. Remotion 作为唯一主时间轴与证据视觉工具。
4. 项目目录 FFmpeg/ffprobe 做转码、合成和技术探测。
5. 素材 manifest validator、`qa_probe`、快照导入器与转写适配器。
6. 独立 QA 和用户审批门。

MeloTTS 只保留为工程基线，不进入正式配音。

## 尚需完成的生产级验证

1. 实现 v2 控制缺口：批准绑定哈希、机器可读 QA、统一 manifest、指标空值与只追加语义、视频级研究门。
2. 声音路线恢复时，先做新的 8–15 秒短样；未通过前不生成完整旁白。当前按用户要求暂停。
3. 有正式批准内容后，单独测试抖音 `prepare-only`，停在发布按钮前；不得顺带发布。
4. 第一条真实发布后，完成一次 2h/24h/72h 采集与导出字段校准，才算运营闭环通过。

## 存储

- 项目环境、模型、浏览器副本与运行缓存均使用 `.` 下路径。
- Codex 自身管理的 Skill/Plugin 元数据仍位于其应用目录，不能作为项目模型或运行缓存使用。
- 本轮 jieba 误写 系统级目录的单个临时缓存已迁移到 `.\cache\jieba\jieba.cache`，原路径确认不存在。
