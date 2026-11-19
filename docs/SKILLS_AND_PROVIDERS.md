# Skills 与生成服务配置

## 仓库提供什么

公开仓库目前包含四个自有 Skill：

- `ai-scenery-studio`：风景主题、提示词、系列约束与验收方法。
- `douyin-prompt-director`：统一图片/视频导演提示词包及供应端编译规范。
- `douyin-media-orchestrator`：制作路线和能力编排、执行留痕。
- `douyin-wallpaper-export`：竖屏图片导出、预览与技术验收。

本机曾安装的所有外部 Skill 不等于本仓库全部分发。缺失项会在制作计划中显示，不会假装存在。`imagegen` 是运行 Codex 会话提供的内置能力，仍需该会话确实能生成图片；路由器列出它不构成可用性证明。

## 让工作台发现 Skill

默认索引 `<项目>/skills/<skill-name>/SKILL.md`。可按各自上游说明安装第三方 Skill 到项目目录，或用 `DOUYIN_SKILLS_DIR` 指定专门目录。必要时把这份项目 Skill 安装到自己的 Codex Skill 发现位置，重新载入会话后由 Codex 读取执行。

工作台显示 Skill 与 Codex 能调用 Skill 是两个检查：网页看入口文件，Codex 还需要真实加载其说明和依赖。当前没有一键把所有外部 Skill 自动安装并完成凭证配置的功能。

页面的删除操作会把所配置目录中的 Skill 移到本地回收目录。因此默认使用项目目录；若明确配置为全局 Codex Skills 目录，网页的移除与恢复会影响该目录，操作前应核对范围。

## 按任务组合能力

| 内容 | 典型组合 |
| --- | --- |
| 静态图片系列 | douyin-media-orchestrator → 一个主视觉风格 → douyin-prompt-director → imagegen → douyin-wallpaper-export |
| 单镜头氛围视频 | 导演提示词 → hyperframes-motion-language → 一个服务商编译器 → 视频生成 → video-use/FFmpeg 检查 |
| 多镜头视频 | 上述能力 + 所需 Remotion 规则、合成、媒体、预览与渲染 |
| 讲解视频 | 上述能力 + 来源与事实脚本、声音短样、douyin-caption-pipeline/Remotion Captions |
| 产品或固定人物 | 按需增加 cinematic-director-frame 与 imagegen 锚点子任务 |

这些是路由器支持的技能名称，安装状态以本机显示为准。基础风景图片组合的四个自有 Skill 已随仓库分发；其他风格、字幕、视频与声音能力按需另外配置，不能用空壳文件绕过生产依赖检查。

主视觉按意图规则选择，明确的即梦、Flova 或 H3 选择优先于旧 brief 的默认文字。未指定服务商的视频默认规划 Flova；切换服务商后重新编译任务卡与核对费用，不拼接各模型不同语法。

## Flova

先按官方 CLI 说明安装并登录。CLI 可以在 PATH 中，或通过环境变量指定：

```powershell
$env:DOUYIN_FLOVA_CLI = 'D:\tools\flova\flova.exe'
$env:DOUYIN_FLOVA_SKILL_ID = '<你自己的可访问 Skill ID>'
python manage.py serve
```

项目不附带维护者私有 Skill 的访问权。你可根据本仓库导演规范创建自己的 Flova Skill，再把 ID 配置到当前进程；本轮只把配置入口通用化，不会在你的外部账号自动创建 Skill。

账户状态读取不保存凭证。任务执行前需批准当前模型、包含额度上限与引用素材上传。`max_credits` 是本地授权上限，尚未证明是平台强制扣费硬上限。平台提示余额不足或待选择时，工作台显示真实阻塞和选项。

CLI 生命周期已用模拟平台响应测试；真实模型生成、扣费、导出仍需针对自己的账号完成一次明确获批的小样。`doctor` 仅探测可执行文件，不调用账号接口或提交生成。

## 即梦 / Seedance 与 MiniMax H3

目前支持统一导演包、目标提示词与任务确认卡。独立平台的自动提交与下载后端尚未接通；可以通过平台网页执行，并把真实视频交回当前项目。即梦可以独立使用，不强制经 Flova。

配置自己的模型、时长、分辨率后，以当次页面或官方接口的积分报价确认。维护者历史账号的积分余额或某次报价不适用于其他用户。

## 音频、字幕与后期

Remotion 用于时间线、合成、字幕、预览和渲染，依赖 Node 与具体工程。HyperFrames motion Skill 提供节奏与运动方法，不等于安装 HyperFrames 渲染器。ElevenLabs 系列 Skill 需要服务配置、额度和自然度样段。Captions AI 尚没有本项目验证通过的独立官方接入。

这些服务都按需使用。纯风景可以无旁白，音乐可在平台选择。必要时先用极短样段检查语音自然度，再做整条视频。
