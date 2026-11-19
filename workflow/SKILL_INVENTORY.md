# 视频工作流 Skill / Plugin 清单

更新时间：2026-08-24  
用途：记录安装来源、锁定版本、允许用途和禁止动作。主控在给执行任务分配能力前必须读取本文件。

## 已安装

| 名称 | 类型 | 来源 | 锁定版本 | 许可/状态 | 允许用途 | 硬限制 |
|---|---|---|---|---|---|---|
| HyperFrames by HeyGen | Codex Plugin | `hyperframes@openai-curated-remote` | Plugin `0.1.2`；CLI 实测 `0.8.1` | **已安装但暂停生产使用** | 仅作为 HTML/GSAP 信息动画设计参考 | CLI 会硬编码写 `%USERPROFILE%\.hyperframes`，无法满足 G 盘硬约束；解除前不得运行生产命令 |
| Remotion | Codex Plugin | `remotion@openai-curated-remote` | Plugin `1.0.7`；项目运行时 `4.0.506` | 已安装、已启用；1080×1920/30 FPS 实测通过 | React 时间轴、主合成、字幕、音频同步、证据组件、重复渲染 | 项目本地依赖；运行环境和缓存必须在 G 盘；许可证适用于个人、非营利及不超过 3 人的营利组织，团队规模变化时复核 |
| seedance2-skill | Codex Skill | `dexhunter/seedance2-skill` | `e06c7c63a766d623004a2807881c30685ce517af` | MIT | 生成 Seedance 分镜提示词、镜头语言、时段拆分 | 只生成提示词；不上传素材；不调用付费接口；不得模仿受保护角色/声音/片段 |
| seedance2-prompt-zh | Codex Skill | 同上 `zh/` | 同上 | MIT | 中文 Seedance 提示词与镜头方案 | 同上 |
| h3-prompt-writing | Official MiniMax H3 Codex Skill | `MiniMax-AI/MiniMax-H3/skills/h3-prompt-writing` | `d21241f0a4b3acbb34c97dae47fa417b7065e438` + 本地 frontmatter 兼容补丁 | MiniMax H3 Community License | 为 H3 的 T2VA/I2VA/FL2VA/L2VA/Ref2VA 编译官方字段、声音和参考保留语法 | 本地只删除校验器不接受的 `compatibility` 元数据键；提示词正文未改；提交前复核实时模型限制、费用与上传权限；不得自动调用 H3 |
| cinematic-director-frame | Third-party Codex Skill | `zhu930824/cinematic-director-frame` | `b2634d02ed53b1700d6ec0b34ae889d4d85b896c` | **LICENSE_NOT_FOUND；仅本地研究/提示词参考** | 把电影语言翻译为七轴 Director DNA、构图、单焦段、光线、色彩、材质与镜头卡 | 在本项目默认 prompt-only；抖音默认改为9:16；不得复制可识别电影画面、演员或导演身份；许可证澄清前不再分发其代码 |
| douyin-prompt-director | Project Codex Skill | 本项目原创 `G:\抖音视频\skills\douyin-prompt-director` | `1.0 / 2026-08-24` | 内部项目资产 | 生成统一 `prompt_package.md/json`，先锁定导演语言，再只为 IMAGEGEN、Seedance 或 H3 中一个目标编译 | 不生成、不提交、不付费、不上传、不发布；提示词包必须人工批准后才能进入生成 |
| generative-media-storyboard | Codex Skill | `SamurAIGPT/Generative-Media-Skills` | `3b62f7870496a10ebab42221e5e3226ad0ef8a9e` | MIT | 把已批准脚本拆成故事板和关键帧提示 | 只做方案；预算批准前不得调用 muapi、不得上传素材、不得索取 API Key |
| generative-media-one-shot | Codex Skill | 同上 | 同上 | MIT | 设计短 B-roll 的一镜到底提示方案 | 只做方案；预算批准前不得调用 muapi、不得上传素材、不得索取 API Key |
| video-use | Codex Skill | `browser-use/video-use` | `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` | MIT | EDL、按词边界剪辑、音频边界淡化、字幕时间轴、FFmpeg 合成、成片自检 | 禁用 ElevenLabs 上传和密钥落盘；转录优先本地；执行剪辑前必须有已批准策略；不得触碰发布页面 |
| visual-style | Codex Skill | `calesthio/OpenMontage/.agents/skills/visual-style` | `95e1c3d0ab93482159818560f6a8c8e866b9139f` | AGPL-3.0 | 为AI造境系列建立可复用的色彩、构图、材质、光线和运动规则 | 不直接复制第三方品牌资产；风格文件不能替代人工审美与相似性检查 |
| flux-best-practices | Codex Skill | `calesthio/OpenMontage/.agents/skills/flux-best-practices` | `95e1c3d0ab93482159818560f6a8c8e866b9139f` | AGPL-3.0 | 明确使用FLUX供应端时编写模型适配提示词 | 当前4GB显存不下载FLUX权重；不得暗示提示词Skill本身会生成图片；付费供应端仍需批准 |
| baoyu-image-gen | Codex Skill | `JimLiu/baoyu-skills/skills/baoyu-image-gen` | `6b7a2e417500561a5ecdd0b168332f4142584617` | MIT | 批量生成任务与多供应商接口；CLI help已实测 | 默认不运行付费API；不索取或保存密钥；Codex原生imagegen优先；live生成未通过前不得进入生产 |
| ai-scenery-studio | Project Codex Skill | 本项目原创 `G:\抖音视频\skills\ai-scenery-studio` | `1.0 / 2026-08-18` | 内部项目资产；Skill结构校验PASS | 规划3–6张AI造境对照批次，生成可追溯prompt、job合同、manifest并路由权利/技术/人工QA | 不生成许可不明权重、不静默切换付费API、不发布；模型/供应端未通过时批次保持BLOCKED |
| Flova | 官方 CLI + Codex Skill | `https://cli.flova.ai/flovaCLI-setup.md` | CLI `v0.0.10`；commit `4258717` | 安装、OAuth、只读状态 PASS | 视频项目创建、运行进度、资源、导出和下载的受控试点 | 首次及后续每次生成前确认模型/时长/分辨率/预计积分；不得自动充值、订阅或跨越发布门；官方 CLI 状态实际落 G 盘且主控不得读取凭据内容 |

新AI造境 Skill 实体目录：`G:\抖音视频\skills\`；`C:\Users\86135\.codex\skills\` 中仅建立同名 Junction 供 Codex 发现。根据安装器规则，新安装 Skill 从下一轮任务起进入正式可发现状态。

## 已审计但未激活

`SamurAIGPT/Generative-Media-Skills` 的 `social-media-video`、`workflow`、`cinema-director` 等完整流程会安装或调用 `muapi` CLI、读取 API Key、上传素材并执行外部生成。当前账号尚未批准生成预算和外部素材上传，因此不作为全局 Skill 激活。可把其镜头语法作为内部参考，但不得运行附带脚本。

`remotion-dev/skills` 为 Remotion 官方组织仓库，但 GitHub API 未返回可识别许可证。本项目已安装官方 Remotion 插件，因此不额外复制该仓库文件。

`MiniMax-AI/MiniMax-H3` 还包含 8 个官方风格工作流：3D 动画短片、纸艺定格科普、品牌宣传、音乐字幕、双人游戏开场、纸张拼贴科普、手绘实拍融合和极简产品广告。这些流程依赖 MiniMax Hub 的 canvas 节点及 `hub_generate_*` 能力，不能直接移植为通用 Codex Skill。本项目只提取其“brief → 方案门 → 资产/角色卡 → 分镜表 → 静帧门 → 生成 → 组装 → QA”方法，不安装或调用其 Hub 执行层。

## G 盘本地运行时与锁定参考

| 名称 | 路径/版本 | 结论 | 用途与限制 |
|---|---|---|---|
| FFmpeg + ffprobe | `tools/ffmpeg/current/ffmpeg-master-latest-win64-gpl`；`N-126188-g426841da9d-20260817` | 已安装并实测 | 解码、合成、黑帧/冻结/静音、EBU R128、成片探测；由 `config/project-env.ps1` 注入进程 PATH |
| 研究轻量环境 | `envs/tooling_refresh_research_script` | 已安装并实测 | `duckdb==1.5.5`、`scikit-learn==1.9.0`、`trafilatura==2.2.0`；仅处理公开或项目既有数据，不把聚类结果当事实结论 |
| MeloTTS | `projects/tooling_refresh/audio_edit_qa/MeloTTS`，commit `209145371cff8fc3bd60d7be902ea69cbdb7965a` | 仅锁定代码，模型未下载 | 首条视频的预训练中文音色候选；必须先建立 G 盘最小中文运行时并做句级 A/B，不能使用克隆链路 |
| TzFilm Douyin Tool | `projects/tooling_refresh/research_script/tzfilm-douyin-tool`，commit `a0c12c3fc47f48797b306a2ed144ec9c0f30e8e6` | `PIN_REFERENCE` | 参考 Excel 解析、SQLite 快照和同期对比；核心采集仅支持 macOS AppleScript，自动回复模块永久禁用，不能读取/保存 Cookie 或代表用户互动 |
| DepthFlow | `projects/ai_scenery_tooling/DepthFlow`，commit `843d840a99b426c6affecffc9c8d03eab0d01ed5` + 本地G盘缓存补丁 | `ISOLATED_RUNTIME / RENDER_PASS` | 把通过权利门的静图与深度图生成低幅度无缝景深循环；环境 `envs/ai_scenery_motion`，缓存 `cache/ai_scenery_motion`；代码AGPL-3.0 |
| OpenMontage | `projects/ai_scenery_tooling/OpenMontage-reference`，commit `95e1c3d0ab93482159818560f6a8c8e866b9139f` | `PIN_REFERENCE` | 仅稀疏保留visual-style/FLUX/ComfyUI等Skill参考；完整系统权限面和外部API过大，不运行 |
| Real-ESRGAN | `projects/ai_scenery_tooling/Real-ESRGAN`，commit `a4abfb2979a7bbff3f69f58f58ae324608821e27` | `PIN_REFERENCE` | 只有真实生成图分辨率不足且人工检查认为超分不会破坏细节时才建立运行时；当前未安装权重/运行环境 |

## 通用安全门

1. Skill/Plugin 只提供制作能力，不拥有选题、事实批准、预算、账号登录或发布权。
2. 任何外部 API、上传、购买、订阅或可能产生费用的调用，必须在动作发生前由用户批准。
3. 不读取、复制或在项目业务文件中写入浏览器 Cookie、验证码、密码、第三方令牌或 API Key；经用户批准的官方 CLI 可在其 G 盘专用状态目录管理自身登录状态，主控只读取 `auth status` 等非敏感结果。
4. 不克隆第三方声音、肖像或角色；用户本人声音克隆也要先记录明确授权。
5. 执行任务只能写自己的目录；主控负责 brief、registry、approvals 和 metrics。
6. 所有生成素材进入 QA 前必须记录模型、版本、提示词、来源、许可和 AI 标识要求。
