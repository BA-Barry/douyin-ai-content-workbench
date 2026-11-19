# Agent 与工具链重构结论

日期：2026-08-18  
最终审计：`PASS`  
范围：Agent 分工、GitHub/Skill 候选审计、G 盘环境、视觉/声音/剪辑/QA/指标工具、数据契约。

## 总结

三份候选矩阵共审计 59 个项目或工具，另单独审计 TzFilm Douyin Tool，总计 60 个。结论不是继续堆 Skill，而是把工作流收敛为：轻量研究环境 → 证据优先镜头表 → Remotion 单一主合成 → 本地 FFmpeg 技术收口 → 独立 QA → 主控登记发布与指标。

项目级 Agent 已拆为 8 个定义文件，覆盖 R1–R7；发布与指标仍归主控，不向执行 Agent 下放账号动作。

## 角色与准入结果

| 角色 | 默认工具 | 当前状态 | 关键限制 |
|---|---|---|---|
| R1 趋势/受众研究 | DuckDB、scikit-learn、Trafilatura | G 盘环境已安装、导入与 smoke 通过 | 聚类只作人审辅助；Trafilatura 仅处理允许访问的静态公开页 |
| R2 脚本/故事板 | 现有 storyboard、Seedance 提示词 Skill | 已有能力足够，不新增全局 Skill | 必须用来源台账和证据优先镜头表；生成式 B-roll 需另行批准费用/上传 |
| R3 证据视觉 | Remotion 组件 | 1080×1920/30 FPS smoke 通过 | HyperFrames 因硬编码写 C 盘而暂停生产使用 |
| R4 主合成 | Remotion 4.0.506 | 确认为唯一主时间轴 | 项目本地依赖；团队规模超过许可证条件时复核 |
| R5 剪辑收口 | video-use 的本地 EDL/timeline + FFmpeg/ffprobe | 本地技术 smoke 通过 | ElevenLabs helper 永久禁用，不上传音视频 |
| R6 声音 | MeloTTS 预训练中文音色候选 | 代码已固定；模型未下载、自然度未验证 | 先建 G 盘最小中文环境并做逐句 A/B；不使用克隆链 |
| R7 独立 QA | ffmpeg/ffprobe 只读探测 | 解码、静音、黑帧、冻结、EBU R128 smoke 通过 | QA 不得直接修片或批准发布 |
| R8 发布/指标 | 主控 + 冻结的指标模板 | 数据契约已建立 | 发布、回复、点赞、关注、私信仍需动作时确认 |

## TzFilm Douyin Tool

结论：`PIN_REFERENCE`，不安装为 Skill、不运行账号自动化。

- 原仓库：`TradingAi666/TzFilm-Douyin-Tool`，MIT；固定脱敏 commit `a0c12c3fc47f48797b306a2ed144ec9c0f30e8e6`。
- 有价值的部分：创作者后台指标字段、SQLite 历史快照/checkpoint 分表、同期倍率中位数思路。
- 不能直接采用：核心抓取依赖 macOS AppleScript/launchd，当前是 Windows；路径硬编码到 `~/.hermes` 和 `/tmp`；评论模块保存 Playwright 登录 profile 并能实际发送回复；还包含飞书/Telegram 外发。
- 数据风险：`schema.sql` 落后于运行代码；标题匹配可能串记录；所谓 confidence 是手工规则，不是校准后的统计置信度。
- 安全验证仅做离线 schema/语法检查；没有安装依赖、下载浏览器、登录、访问抖音、生成 profile、回复或外发。
- 推荐改法：保留代码作参考，后续自写 Windows 本地 XLSX 导入器，只处理用户从创作者中心手动导出的表格，并映射到项目 `PostSnapshots` 契约。

完整审计：`research/tooling_refresh/research_script/tzfilm_douyin_tool_review.md`。

## G 盘落地状态

- 环境与缓存入口：`config/project-env.ps1`；HF、ModelScope、Torch、npm、pip、Playwright、Puppeteer 等运行缓存全部重定向到 G 盘。
- 研究环境：`envs/tooling_refresh_research_script`，锁定 DuckDB 1.5.5、scikit-learn 1.9.0、Trafilatura 2.2.0。
- FFmpeg：`tools/ffmpeg/current/ffmpeg-master-latest-win64-gpl`，包含 ffmpeg 和 ffprobe；实测版本 `N-126188-g426841da9d-20260817`。
- 参考仓库：全部位于 `projects/`；MeloTTS 与 TzFilm 已固定 commit。
- 模型：本轮没有下载任何模型权重。MeloTTS、FunASR、faster-whisper 仍待真实测试脚本确定后再按体积和路径下载。
- 一份误建的重复研究环境已可恢复地移到 `envs/_quarantine/research_script_duplicate_20260818`；一份重复 TzFilm 克隆移到 `projects/_quarantine/tzfilm_duplicate_root_20260818`，未直接删除。

## 已冻结的数据契约

`workflow/DATA_CONTRACTS.md` 定义了六类正式 CSV：研究原始信号、来源台账、证据优先镜头表、素材与权利清单、发布后指标快照、自有作品评论信号。字段说明工作簿为 `workflow_data_contracts_2026-08-18.xlsx`。

## 当前还缺什么

工作流的结构和路由已经完整，但还没有达到“第一条视频可稳定生产”的工程完成状态。下一阶段应按顺序完成：

1. 做一个 15–30 秒真实工程样片：真实录屏/证据 → 逐句旁白 → 字幕对齐 → 5 类证据组件 → Remotion → FFmpeg QA。它只验证管线，不代表正式选题。
2. 建立 G 盘最小声音链：MeloTTS 逐句 A/B；FunASR 中文回环；若时间戳不足，再加 faster-whisper base/small。未通过自然度门前不能进入正式视频。
3. 补四个本地接口：转写适配器、`qa_probe`、素材 manifest validator、手动导出 XLSX 的指标导入器。
4. 建立 `DESIGN.md`：字体许可、最多五色、移动安全区、字幕层级、证据标签、录屏规范和禁止的 AI/PPT 套路。
5. 完成真实工程样片和声音 A/B 后，才选择第一条正式选题并写新 brief。旧 registry 项 `office-meeting-notes-v2` 仍是历史状态，不能误当新账号的首条内容。

因此，当前最准确的判断是：**Agent 分工、存储规则、工具准入和数据契约已经完成；真正的下一瓶颈是声音自然度与真实证据型工程样片，而不是继续找更多 Skill。**

## 验证记录

- 8 份 Agent TOML：解析 `PASS`；
- 研究环境版本导入：`PASS`；
- FFmpeg/ffprobe 与 4 秒音视频样本：`PASS`；
- 3 项单元测试：`PASS`；
- 6 份 CSV 契约表头：`PASS`；
- `workflow_control.py audit`：`PASS`。

本轮未上传、未发布、未评论、未点赞、未关注、未私信，也未获取或保存浏览器 Cookie、验证码或密码。
