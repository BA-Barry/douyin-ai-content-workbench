# 架构与数据

## 组件分工

| 组件 | 入口 | 职责 |
| --- | --- | --- |
| 启动管理 | manage.py | 初始化本地数据、选择解释器、配置缓存、启动服务、诊断 |
| 网页 | workbench/static/ | 表单、草稿、项目、素材、任务日志、预览与确认 |
| HTTP 服务 | workbench/server.py | 只监听回环接口，处理本地请求与文件 |
| 草稿存储 | workbench/draft_store.py | 账号/项目/动作隔离、版本检查、保存冲突 |
| 素材库 | workbench/media_library.py | 导入、绑定、用途与外部上传许可 |
| 路由器 | workbench/skill_router.py | 按类型、明确服务商与意图规则编排 Skill |
| 网页任务 | workbench/task_runner.py | 执行允许的动作、记录结果，限制任意命令 |
| Codex 队列 | src/codex_dispatcher.py | 原子领取图片计划、回传产物与失败原因 |
| 视频适配 | src/video_task_compiler.py、src/flova_runtime.py | 任务卡、外部句柄、状态恢复和有效视频回收 |
| 状态/发布/指标 | src/workflow_control.py 等 | 阶段转换、发布包、快照与复盘 |

路由器采用规则，不是在网页中嵌入一个持续思考的大模型代理。它生成计划；Codex 读取 Skill 并执行理解与创作。当前没有在仓库中打包一个全天在线的 Codex worker。

## 一次操作的生命周期

前端提交数据到本地接口，后端校验参数后写入当前项目。任务执行器把动作和结果写到本地 job 记录；前端只查询本地任务。Flova 的一个后端 CLI 运行解析进度事件和终态结果，不另建前端外部轮询器。

图片计划进入单独队列，Codex 领取后制作和登记产物。完成回传后，工作台从产物路径提供预览。缺失真实文件时不能显示为制作成功。

草稿自动保存与正式提交分开。约 700 ms 防抖保存使用版本检查，多标签页冲突要求选择保留本页或载入远端版本；保存过程中继续输入不会被较早的响应覆盖。批准勾选不作为持久草稿。

## 状态不是一个枚举

| 状态来源 | 回答的问题 | 示例 |
| --- | --- | --- |
| content_registry.csv | 内容项目处于哪个运营阶段 | PRODUCING、READY_FOR_USER、PUBLISHED |
| workbench_jobs.json | 刚点击的具体动作执行怎样 | QUEUED、RUNNING、SUCCEEDED、BLOCKED、FAILED |
| codex_dispatch_queue.json | 图片计划有没有被领取和交付 | READY、LEASED、COMPLETED、FAILED |
| 外部视频任务 | 平台现在正在等待什么 | WAITING_USER、RECOVERABLE、额度不足、生成中 |

“生成确认卡”动作 SUCCEEDED 只表示卡片生成成功；图片队列 COMPLETED 也不等于用户验收或已发布。未知进度显示等待，不推断百分比。

## 本地目录

`data/` 保存账号档案、登记表、项目映射、队列、任务、草稿和素材索引。`content/<id>/` 保存 brief、production、qa、approvals、metrics 和 research。`assets/library/` 保存可被多个项目引用的实际素材。

`workspace/` 是任务中间结果，`cache/` 和 `models/` 可按环境变量更换位置。它们与真实账号和作品文件默认被 Git 排除。状态文件和作品文件应作为一组备份；只备份源码不能恢复运营记录。

素材和发布包中的既有哈希用于确认批准对应的具体版本。普通草稿使用版本检查，任务使用既有标识和领取机制；此次通用部署不新增另一套冻结文件或门禁。

## HTTP 接口速查

接口以实际代码为准，主要使用 `/api/health`、`/api/accounts`、`/api/projects`、`/api/assets`、`/api/actions`、`/api/jobs/create`、`/api/jobs/<id>`、`/api/dispatch`、`/api/skills` 和 `/api/video-providers`。

可以用 `/api/health` 确认当前 root 与端口是不是目标副本。创建/运行任务使用页面提供的白名单动作，不接受任意 shell。接口面向本地浏览器，尚不作为稳定的第三方公网 API。

## 路径选择

源码默认通过 `__file__` 找到项目根目录，允许 `DOUYIN_PROJECT_ROOT` 指定另一份完整副本。Python 子进程按显式配置、当前项目 `.venv`、旧 content 环境、当前 Python 顺序选择；Skill 默认只管理项目 `skills/`。

FFmpeg、ffprobe 与 Flova 支持显式路径和 PATH，兼容系统安装与项目内安装。基础功能不要求所有可选工具就绪；操作到某项能力时才检查相应条件。
