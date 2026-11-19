# 图片与视频生产工作流 v2

更新时间：2026-08-23  
状态：当前执行合同；不替代 `MASTER_WORKFLOW.md` 的状态机和批准门。

## 0. 统一底座，双轨制作

图片和视频共用账号、选题、素材库、项目登记、发布和复盘，但使用不同制作步骤。

- 图片：主题 / 可选素材 → 自动视觉 Skill 与完整逐图提示词 → Codex 图片生成 → 整批审核 → 高清导出。
- 视频：主题 / 可选素材 → 分镜 → 素材策略判断 → 条件性图片锚点 → 视频任务确认卡 → 服务商生成 → 后期与 QA。
- 视频的图片锚点是项目内子任务，不会把视频项目改变成图片项目。
- 图片成品衍生视频时，创建新的关联视频项目。

素材库文件固定在 `assets/library/`，全局索引为 `data/media_library.json`。每个项目只通过 `production/assets/asset_bindings.json` 使用素材，并以 `production/asset_strategy.json` 记录自动判断理由。

## 1. 固定工具边界

| 路线 | 生成入口 | Codex 负责 | 后处理 | 当前状态 |
|---|---|---|---|---|
| 图片轮播 | Codex 图片生成 | 选题、风格 Skill、提示词、批次生成、版本与 QA 协调 | 高清导出、尺寸与压缩 QA | 生产可用 |
| 氛围视频 | 私有 Flova Skill（内部按任务选择 Seedance/H3）；即梦直达为备用 | brief、导演提示词包、Flova 确认卡、素材接收 | Remotion / video-use / FFmpeg 合成与 QA | 受控试点 |
| 旁白讲解 | 私有 Flova Skill + 已批准声音方案 | 事实脚本、逐镜证据、字幕、Flova 确认卡 | Remotion / video-use / FFmpeg；ElevenLabs 仅在批准后调用 | 声音门阻断 |

Remotion、HyperFrames 示例和普通图片推拉只提供构图、动效或合成能力，不等于生成了真实视频镜头。

Skill 不再由用户逐个选择。工作台根据 registry 路线、brief 和制作要求写入 `production/skill_plan.json`；`douyin-media-orchestrator` 在 Codex 任务中执行该计划。所谓“调用所有 Skill”固定解释为调用所有相关能力，禁止把无关 Skill 或付费服务一并装入流水线。

## 2. 图片轮播

| 步骤 | 输入 | 输出证据 | 人工介入 | 失败回退 |
|---|---|---|---|---|
| 选题与单变量 | 趋势、账号栏目、上一条复盘 | `research_delta.md`、`hypothesis_card.md` | 观点或账号方向改变时审核 | 返回选题池 |
| Brief | 受众收益、首图、图数、风格、禁区 | `brief.md`、brief approval | 必须批准 | 修改 brief |
| 批次设计 | 已批准 brief、风格 Skill | `route_plan.json`、`shot_list.csv`、逐图提示词 | 无 | 只修失败图任务 |
| Codex 生成 | 逐图提示词和参考图 | 原始图、provider/version、prompt、hash | 私人参考图上传前确认 | 替换失败单图并留拒绝记录 |
| 审美与技术 QA | 完整批次 | contact sheet、技术报告、`qa_result.json` | 必须查看整批与首图 | 回生成或排版 |
| 高清导出 | 已批准原图 | 1080×1920 发布图、导出 manifest | 无 | 重做裁切/编码，不虚构细节 |
| 发布包 | 图序、标题、短文案、音乐策略 | `release_package.json` | 最终批准与手动发布 | 变更后重新打包 |

## 3. 氛围视频

| 步骤 | 输入 | 输出证据 | 人工介入 | 失败回退 |
|---|---|---|---|---|
| 选题与 Brief | 账号栏目、观众情绪、时长、主变量 | `brief.md`、批准记录 | 必须批准 | 返回选题或重写钩子 |
| 分镜与验收句 | brief、镜头数量、逐秒结构 | `shot_list.csv`、每镜失败条件 | 无 | 只改失败镜头 |
| 素材策略 | 分镜、素材绑定、人物/场景一致性要求 | `asset_strategy.json`、`asset_bindings.json` | 私人素材外传或新锚点审美确认 | 无必要图片前置时回到文生视频 |
| 条件性图片锚点 | `GENERATE_KEYFRAMES / GENERATE_ELEMENTS` 决策 | 首帧、尾帧、人物或场景锚点及 prompt/hash | 必须查看锚点 | 只替换失败锚点，不把静态图冒充视频 |
| 视频任务编译 | 分镜、关键帧、镜头运动、连续性要求 | `video_task_package.json`、逐镜 prompt、引用资产清单、生成确认卡 | 此步不创建项目、不上传、不扣积分 | 降低运动、拆短镜头或换受支持服务商/模式 |
| 视频生成 | 已批准确认卡 | 原始生成视频、provider/model/version、任务与文件 hash | 创建项目、私人素材上传、积分消耗前确认 | 未取回真实文件不得进入后期；不得静默换模型 |
| 本地后期 | 原始镜头、声音/音乐计划 | Remotion 或 video-use 工程、时间线、最终视频 | 声音与音乐策略需确认 | 回单镜或音轨，不用 PPT 动效补假镜头 |
| 视频 QA | 最终视频 | 编码、黑帧、冻结、响度、字幕安全区、内容 QA | 必须查看最终成片与声音 | 回后期或回生成镜头 |
| 发布包与发布 | QA 通过成片、封面、标题文案 | 锁定包、prepare-only 回执、发布回执 | 最终批准；用户点击发布 | 任一变化重新打包 |

## 4. 旁白与字幕

1. ElevenLabs Skill 的安装只提供操作规范，不代表服务免费或已接通。
2. 任何 API 调用前检查 API Key、套餐费用、声音权利与输出用途；不得在工作台保存明文凭证。
3. 先生成 8–15 秒声音短样，记录 voice/model/settings；用户批准自然度后才生成全片。
4. 字幕默认走 Remotion Captions 或 video-use；Captions AI 在没有官方 Skill/API 合同前不进入生产链。
5. 使用声音克隆时，必须确认声音主体授权；没有授权则改用有明确使用权的预设声音或本人录音。

## 5. 工作台仍缺的自动化接口

- 工作台已能本地编译私有 Flova 任务包；Flova 的创建项目、提交、任务轮询、失败重试和原文件下载仍需一次获批的真实生产验证。
- ElevenLabs 尚未配置凭证、预算上限、费用预估和短样审批表单。
- 工作台现在能展示流程边界和工具状态，但还不能在网页中直接触发 Codex 图片生成。
- 工作台已能自动选择 Skill 并生成计划，但还没有常驻 Codex dispatcher 去领取 `READY_FOR_CODEX` 计划；当前需要从 Codex 任务执行，或后续用项目定时任务轮询队列。
- 发布页仍是 prepare-only / 跳转边界，正式点击发布保持人工确认。

这些缺口必须以真实接口、任务日志和产物文件关闭，不能只把按钮做出来就标记完成。
