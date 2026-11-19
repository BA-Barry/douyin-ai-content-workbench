# 抖音内容工作流项目规则

项目根目录由当前代码位置或 `DOUYIN_PROJECT_ROOT` 决定，不固定盘符或用户名。首次使用先执行 `python manage.py init`。任何任务开始前先阅读：

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

- 默认环境为 `.venv/`，兼容已有 `envs/`；模型、缓存、第三方源码默认位于 `models/`、`cache/`、`projects/`，也可按文档显式配置模型和缓存目录。
- 单条视频临时渲染放 `content/<video_id>/production/` 或 `workspace/`；不得意外写入另一份项目副本。
- 下载依赖或模型前确认目标位置与体积。Windows 可加载 `config/project-env.ps1`，其他系统使用对应缓存环境变量。
- 允许复用系统 PATH 中已有 Python、FFmpeg 和官方 CLI。工具的认证存储按官方方式管理，工作台不读取、复制或提交其凭证。
- 凭证、环境、模型、缓存、素材与真实运营数据不进入公开 Git 历史。

## 完成标准

- 任何阶段都必须有可核验文件，不接受只在聊天中声称完成。
- 所有状态变化通过 `src/workflow_control.py transition` 执行。
- 运行 `src/workflow_control.py audit` 失败时，不得进入下一阶段。
- 研究事实、推断和待验证假设必须分开；不得把精选页点赞量当成完播率或因果证据。
