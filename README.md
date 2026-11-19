# 抖音视频半自动工作流

长期根目录：`G:\抖音视频`

这是一个本地优先的抖音图片与视频内容工作台。它把账号定位、选题、素材、Skill 编排、图片/视频制作、质检、发布准备和指标复盘组织在同一套可追溯流程中。网页负责提交和查看任务，Codex 或已接入的视频服务负责实际执行。

## GitHub 仓库边界

公开仓库保存可复现的源码、工作流规范、自有项目 Skills、测试、配置清单和脱敏示例。以下内容只保存在本机，不上传 GitHub：

- 登录凭证、Cookie、外部服务状态与账号映射；
- Python/Node 环境、模型权重、缓存、浏览器运行时和下载工具；
- 原始课程视频、生成图片、成片、声音和其他媒体文件；
- 真实内容项目、评论样本、审批记录、指标快照和运行任务；
- 第三方参考仓库和第三方 Skills。它们应按对应许可证单独安装，不复制进本仓库。

克隆公开仓库并初始化空白本地数据：

```powershell
git clone https://github.com/BA-Barry/douyin-ai-content-workbench.git
Set-Location '.\douyin-ai-content-workbench'
New-Item -ItemType Directory -Force '.\data' | Out-Null
Copy-Item '.\examples\data\content_registry.example.csv' '.\data\content_registry.csv'
Copy-Item '.\examples\data\account_profiles.example.json' '.\data\account_profiles.json'
Copy-Item '.\examples\data\account_content_map.example.csv' '.\data\account_content_map.csv'
Copy-Item '.\examples\data\media_library.example.json' '.\data\media_library.json'
```

克隆后先创建项目专用环境，并确保所有依赖、模型和缓存均位于项目所在磁盘。Windows 下运行：

```powershell
. '.\config\project-env.ps1'
```

安装基础 Python 依赖后，可启动本地工作台：

```powershell
python -m pip install -r '.\config\requirements-content.txt'
python '.\workbench\server.py'
```

默认访问地址为 `http://127.0.0.1:8765/`。外部视频平台仍需各自登录、额度确认和人工授权；仓库本身不包含任何凭证。

公开仓库初始化后，源码和前端测试可以直接运行；生产工作流 `audit` 会保持 `BLOCKED`，直到本地补齐研究样本、账号定位、内容项目和审批证据。这是发布安全门的预期行为，不应通过伪造样本或降低门槛绕过。

## 目录

- `src`：自有制作和发布审批代码；
- `envs`：在 G 盘重建的 Python 环境，禁止从其他盘符直接搬虚拟环境；
- `models`：项目使用的模型权重与模型专用缓存；
- `cache`：pip、uv、npm、Hugging Face、ModelScope、Torch、Playwright/Puppeteer 等可重建缓存；
- `projects`：参考 GitHub 项目及本地安全改造；
- `research`：参考视频样本和学习结论；
- `workspace`：每次运行的中间文件；
- `outputs`：成片、口播稿和发布任务；
- `assets`：后续获得授权的字体、音乐、图片和视频素材；
- `config`：锁定依赖和项目配置。
- `content`：每条视频独立的研究、brief、制作、质检、审批与指标；
- `data`：主控登记表、指标日志和状态事件；
- `workflow`：主控规则、交接协议、角色提示词和模板；
- `.codex/agents`：R1–R7 研究、脚本、视觉、合成、声音、剪辑与质检的项目级 Agent 定义。

所有可能下载依赖或模型的命令开始前先执行：

```powershell
. 'G:\抖音视频\config\project-env.ps1'
```

若工具仍要把项目环境、模型或缓存写入 C 盘，应停止执行并在工具审计中标记为不兼容。

## 主控方式

当前 Codex 任务是唯一主控。研究、制作、质检可以委派，但子任务不能修改内容登记表、批准内容或执行发布。完整规则见：

- `workflow/MASTER_WORKFLOW.md`
- `workflow/TASK_HANDOFF_PROTOCOL.md`
- `AGENTS.md`

查看当前状态和质量门：

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\workflow_control.py' status
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\workflow_control.py' audit
```

新建一条内容：

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\workflow_control.py' init --video-id demo-001 --title '标题' --hypothesis '本条只验证的一个假设'
```

只有主控可以转换状态：

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\workflow_control.py' transition --video-id demo-001 --to RESEARCHING --actor master --reason '选题确认'
```

如需用户自己新开 Codex 任务，直接复制 `workflow/prompts/` 下的研究、制作或质检提示词。

## 生成第二版视频

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\workflow_v2.py' --root 'G:\抖音视频'
```

使用本人录音时，将六段音频命名为 `01.wav` 至 `06.wav`：

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\workflow_v2.py' --root 'G:\抖音视频' --voice-dir 'G:\抖音视频\assets\my_voice\meeting_notes'
```

## 检查发布状态

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\publish_gate.py' validate --manifest 'G:\抖音视频\outputs\publish_job_v2.json'
```

研究门必须同时满足目录层与深看层：

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' 'G:\抖音视频\src\publish_gate.py' reference-review `
  --manifest 'G:\抖音视频\outputs\publish_job_v2.json' `
  --research 'G:\抖音视频\research\reference_videos.csv' `
  --catalog 'G:\抖音视频\research\douyin_sample_snapshot_expanded_2026-08-17.csv'
```

发布器只有 `--prepare-only` 可以由自动流程调用。它会上传并填写页面，但代码不会点击“发布”。最终发布仍需在抖音页面人工确认。
