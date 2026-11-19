# 抖音内容工作流项目规则

本项目的唯一根目录是 `G:\抖音视频`。任何任务开始前先阅读：

1. `workflow/MASTER_WORKFLOW.md`
2. `workflow/TASK_HANDOFF_PROTOCOL.md`
3. `data/content_registry.csv`

## 主控原则

- 当前主任务是唯一运营主控，负责选题、草案、状态转换、发布准备、指标登记和复盘结论。
- 可以在用户直接要求并行代理工作时，把独立、边界清楚的研究、制作或质检任务委派给子代理。
- 研究、制作、质检必须使用不同目录；禁止两个代理同时编辑同一文件。
- 子代理不能改变 `data/content_registry.csv`、不能批准内容、不能发布、不能点赞、评论、关注或私信。
- 子代理只返回摘要和产物路径，主控必须检查证据后才能更新状态。

## 角色目录

- 趋势研究：`research/` 和 `content/<video_id>/research/`
- 草案：`content/<video_id>/brief.md`，仅主控写
- 制作：`content/<video_id>/production/`
- 质检：`content/<video_id>/qa/`
- 指标：`content/<video_id>/metrics/`，仅主控写
- 审批记录：`content/<video_id>/approvals/`，仅主控根据用户明确答复写

## 外部动作

- 浏览、读取、统计可以在任务范围内执行。
- 上传可以只做到 `prepare-only`，停在抖音发布按钮前。
- 点击发布、发表评论、点赞、关注、私信或任何代表用户对外表达的动作，必须在动作发生前取得用户确认。
- 不获取或转存浏览器密码、Cookie、验证码、令牌等敏感凭证。

## 存储与运行时硬约束

- 所有项目专用 Python/Node 环境、GitHub 项目、模型权重、模型缓存、包管理缓存、浏览器运行时和渲染缓存必须位于 `G:\抖音视频` 内。
- 固定目录：环境放 `envs/`，模型放 `models/`，包与工具缓存放 `cache/`，参考项目放 `projects/`，单条视频临时渲染放 `content/<video_id>/production/` 或 `workspace/`。
- 运行任何会下载依赖或模型的命令前，先加载 `config/project-env.ps1`，确认下载位置与预计体积；无法显式重定向到 G 盘的工具不得安装或运行。
- C 盘只允许保留 Codex 应用自身管理的 Skill/Plugin 元数据；Skill/Plugin 运行产生的模型、浏览器、依赖和缓存仍必须重定向到 G 盘。
- 禁止把新虚拟环境、Hugging Face/ModelScope/Torch 模型、npm/pip/uv 缓存或临时渲染文件写入用户目录或系统盘。

## 完成标准

- 任何阶段都必须有可核验文件，不接受只在聊天中声称完成。
- 所有状态变化通过 `src/workflow_control.py transition` 执行。
- 运行 `src/workflow_control.py audit` 失败时，不得进入下一阶段。
- 研究事实、推断和待验证假设必须分开；不得把精选页点赞量当成完播率或因果证据。
