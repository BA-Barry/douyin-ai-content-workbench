# 内容路线运行手册 v3

## 路由决定

| 问题 | 选择 |
|---|---|
| 主要价值来自 6 张静态构图、壁纸或世界选择 | `IMAGE_CAROUSEL` |
| 主要价值来自空间运动、雾光、水流或镜头氛围，无需讲解 | `ATMOSPHERE_VIDEO` |
| 主要价值来自论点、证据、原理和解释 | `NARRATED_EXPLAINER` |

每条只能选一个 route。失败时按预先声明回退，不静默换路线。

## IMAGE_CAROUSEL

- 输入：批准 brief、假设卡、六图 shot list、系列视觉规则、六个 prompt。
- 输出：6 张 1080×1920 图、封面、contact sheet、逐图 prompt/output hash、拒绝记录、material/production manifest。
- 机器门：尺寸、格式、非空、哈希、重复度、路径和权利。
- 人工门：首屏、构图、语义、人物/品牌/假字、AI 伪影、六图差异与顺序。
- 回退：单图失败只换该图；不足 6 张不降级发布；整体同质则回 prompt/shot list。
- 音乐：`platform_manual`，实际曲目写发布回执。

## ATMOSPHERE_VIDEO

- 输入：已过审源图、每镜 3–8 秒 motion plan、EDL、音乐策略。
- 输出：motion units、15–30 秒 1080×1920/30fps/H.264/yuv420p MP4、封面、qa_probe、manifest。
- 工具：DepthFlow → Remotion → FFmpeg/ffprobe。
- 人工门：首尾 seam、边缘空洞、深度穿帮、运动语义、模板/PPT 感。
- 回退：减小运动或删失败镜头；仍不成立则回图文。音乐权利不清时移除音轨，改平台手选。
- 当前状态：工程 PASS，正式内容闭环未验证。

## NARRATED_EXPLAINER

- 输入：批准事实脚本、source ledger、proof mapping、voice script、8–15 秒声音样本。
- 输出：15–60 秒成片、48kHz AAC、字幕、voice master、转写/ASR 报告、EDL、QA。
- 声音门：来源/许可/同意明确；手机外放和耳机试听；用户明确接受自然度。
- 声音合同使用 `workflow/templates/VOICE_GATE_TEMPLATE.json`，由 `src/voice_gate.py` 验证 8–15 秒、48kHz mono、权利/同意和绑定样本哈希的用户批准。
- 事实门：每个外部 claim 可追溯；前 2 秒收益、前 5 秒证据。
- 回退：合成声音失败改本人分句录音；不录音则改无旁白视频/图文。视觉像 PPT 时回 proof job 和镜头动作。
- 当前状态：生产 BLOCKED；MeloTTS zero-BERT 只作诊断基线。

## 音乐决策

1. `platform_manual`：默认，发布页手选；记录实际曲名/ID和页面证据。
2. `licensed_local`：必须有音乐文件、来源、许可范围和哈希。
3. `original_local`：必须有创作来源与工程/导出哈希。
4. `none`：允许，但应说明为什么无声成立。

“能搜索到”不等于可跨平台或商业授权；权利不清时不嵌入本地音轨。

音乐计划使用 `workflow/templates/MUSIC_PLAN_TEMPLATE.json`，由 `src/music_gate.py` 验证。`platform_manual` 禁止意外嵌入本地文件；实际平台曲目写入 publish receipt。

## 工具状态

唯一实时表：`workflow/TOOLCHAIN_STATUS.md`。详细审计证据在 `research/workflow_v3/production/`。
