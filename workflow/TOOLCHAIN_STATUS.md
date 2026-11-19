# 工具链状态 v4

更新时间：2026-08-24

| 能力 | 状态 | 生产用途 | 说明 |
|---|---|---|---|
| Codex imagegen / baoyu-image-gen | PRODUCTION PASS | 图片生成默认 | 图片生成固定由 Codex 端完成；批次产物与缓存落 项目目录 |
| 内置 imagegen | 历史 HTTP 404 | 诊断备用 | 不作为静默回退 |
| 本地 SD1.4 | 工程 PASS / 审美 FAIL | 禁止默认生产 | 4GB GPU 可跑，但输出不达标 |
| 确定性裁切/归一化 | PASS | 图片默认 | 1080×1920；不生成新细节 |
| visual_asset_qa + 人工审美 | PASS / 人工必需 | 所有图片 | 机器不能批准审美 |
| 抖音图片轮播 | 真实发布 3 条 | 当前默认 | prepare-only 已验证 |
| DepthFlow 1.0.0 | 工程 PASS | 氛围视频试片 | 1080×1920 低幅景深已跑通 |
| Remotion 4.0.506 + 官方 Skills | ENGINEERING PASS | 视频后期合成 | 官方 12 个 Skill 已安装；它不是视频生成模型，仍需独立防 PPT 感 QA |
| 项目目录 FFmpeg/ffprobe | PASS | 视频/音频默认 | 由 `config/project-env.ps1` 注入 |
| qa_probe | PASS AS PROBE | 视频必需 | 顶层 PASS 只代表探针成功 |
| material manifest validator | PASS | 所有路线必需 | 权利、哈希、AI来源门 |
| MeloTTS zero-BERT | 工程 PASS / 生产 FAIL | 仅诊断 | 自然度未通过用户门 |
| transcript_adapter | fixture PASS | 辅助 | 真实 ASR 尚需样本验证 |
| 平台曲库音乐 | 手动部分通过 | 发布阶段 | 实际选择写回执；不推断外部授权 |
| Flova 官方 CLI + 私有导演 Skill | INSTALL / AUTH / PRIVATE SKILL / DRY-RUN PASS | 视频默认执行入口 | v0.0.10 与官方 Skill 已安装；私有 `抖音导演提示词编译器` 已创建，工作台确认卡编译通过；未执行真实生成、充值或订阅，生成费用仍需逐次批准 |
| Seedance / BytePlus ModelArk API | API CONTRACT PASS / COST GATE | 后续单镜头直接后端 | 官方创建/查询/列表/取消任务接口已核验；需要 API Key、计费账户与区域测试 |
| 即梦网页 | MANUAL HANDOFF | 视频人工备用 | 公开创作入口可用；未发现公开开发者 API，保持任务包交接，不自动调用私有接口 |
| ElevenLabs 官方 Skills | INSTALLED / CALL BLOCKED | 配音、转写、声音处理候选 | 需要联网、API Key、可能付费；未获费用与声音批准，不调用 |
| hyperframes-motion-language | SKILL PASS / RENDER REFERENCE | 动效与镜头语言合同 | 从 HeyGen 官方示例提炼项目自有 Skill；不复制上游代码或资产，实际后期仍由 Remotion / video-use 执行 |
| douyin-caption-pipeline | SKILL PASS / PROVIDER GATED | 字幕自动编排 | 组合 Remotion Captions、真实时间戳来源与 video-use；ElevenLabs 转写仍受费用/上传门限制 |
| douyin-media-orchestrator | SKILL PASS / DISPATCH PASS | 自动组合相关 Skills | 工作台生成 `skill_plan.json` 并进入幂等队列；Codex 任务使用租约领取，视频费用门不会自动跨越 |
| Captions AI | UNVERIFIED / REPLACED | 不直接进入工具链 | 未找到可验证的官方 GitHub Skill；由 douyin-caption-pipeline + Remotion Captions / video-use 替代 |
| Real-ESRGAN | 未运行 | 非默认 | 无权重/运行验证 |

路线结论：`IMAGE_CAROUSEL=PRODUCTION_PASS（Codex 生成）`；`ATMOSPHERE_VIDEO=FLOVA_CONTROLLED_PILOT（私有 Skill + 本地后期，真实生成待批准验证）`；`NARRATED_EXPLAINER=VOICE_GATE_BLOCKED`。

详细证据矩阵：`research/workflow_v3/production/TOOLCHAIN_EVIDENCE_MATRIX.csv`。
