# 安装与部署

## 运行条件

基础工作台使用 Python 标准库，推荐 Python 3.11 或以上。它运行在本机，默认地址 `http://127.0.0.1:8765/`，没有数据库或云端后台需要部署。克隆目录需要可写权限；盘符与用户名不固定。

Windows 核心流程已验证。Python 主入口兼容 Windows、macOS、Linux 的目录与虚拟环境布局，但 macOS/Linux 尚待实际平台验收。PowerShell / CMD 启动器只面向 Windows；旧版 `workflow_v1.py` 和 `workflow_v2.py` 仍是含 Windows 字体依赖的历史演示。

## 基础启动

```sh
git clone https://github.com/BA-Barry/douyin-ai-content-workbench.git
cd douyin-ai-content-workbench
python manage.py init
python manage.py serve
```

系统使用 `python3` 时替换 Python 命令即可。打开浏览器访问本机地址。`serve` 会自动补齐缺失的基础数据；`init` 可以单独执行，重复执行保留所有已有数据。

`python manage.py serve --port 8877` 更换端口。`--offline` 禁用外部执行动作；它仍允许保存本地制作要求。前台运行用 Ctrl+C 停止。

## 独立虚拟环境

基础界面不强制创建环境，若要安装媒体依赖，建议使用项目 `.venv`：

```sh
python manage.py init --venv
```

Windows：

```powershell
. .\config\project-env.ps1
& .\.venv\Scripts\python.exe manage.py serve
```

macOS/Linux：

```sh
.venv/bin/python manage.py serve
```

后续 `python manage.py serve` 会优先选择当前项目 `.venv`，同时兼容早期 `envs/content` 环境。最后才使用启动命令的解释器。已经创建的虚拟环境不应跨机器复制；迁移后重新建立。

## 可选依赖

| 需要做什么 | 额外条件 | 未配置时表现 |
| --- | --- | --- |
| 管理账号、素材元数据、草稿和项目 | 无 | 基础功能可用 |
| 图片尺寸/颜色检测、历史图片脚本 | Pillow、NumPy 等 | 对应操作提示缺失依赖 |
| 视频探测、解码、时长/黑帧检查 | FFmpeg 与 ffprobe | 无法把视频标记为交付成功 |
| Codex 图片生成 | 能执行图片生成的 Codex 会话及相应 Skills | 制作队列等待或显示缺失 Skill |
| Flova 镜头生成 | 官方 CLI、登录、自己的私有 Skill、足够额度 | 无 CLI/未登录/缺少配置/额度不足 |
| Remotion 后期 | Node.js、Remotion 及对应项目依赖 | 无法运行后期工程 |
| 配音与音乐生成 | 对应第三方服务、配置与费用确认 | 只保留方案或样段任务 |

媒体 Python 依赖清单是 `config/requirements-content.txt`，属于可选安装。Windows 在 dot-source 环境后安装：

```powershell
& .\.venv\Scripts\python.exe -m pip install -r .\config\requirements-content.txt
```

macOS/Linux：

```sh
PIP_CACHE_DIR="$PWD/cache/pip" .venv/bin/python -m pip install -r config/requirements-content.txt
```

FFmpeg 可采用已有系统安装，也可以放在 `tools/ffmpeg/` 的任意子目录。需要同时有 FFmpeg 和 ffprobe。工作台按显式路径、项目工具目录、PATH 的顺序查找。通过 `python manage.py doctor` 查看结果；该命令不会下载依赖、调用模型或登录平台。

不要仅为了打开网页而安装全部媒体工具。先跑通基础使用，再按需要安装可选项。

## 配置覆盖

设置在启动进程环境中，修改后重新启动服务。工作台不会读取 `.env` 文件；不要把秘密写进版本控制。

PowerShell 示例：

```powershell
$env:DOUYIN_CACHE_DIR = 'D:\ai-cache\douyin'
$env:DOUYIN_MODELS_DIR = 'D:\ai-models'
$env:DOUYIN_SKILLS_DIR = 'D:\my-project-skills'
$env:PROJECT_FFMPEG_EXE = 'D:\tools\ffmpeg\bin\ffmpeg.exe'
$env:PROJECT_FFPROBE_EXE = 'D:\tools\ffmpeg\bin\ffprobe.exe'
python manage.py serve
```

macOS/Linux 示例：

```sh
export DOUYIN_CACHE_DIR="$PWD/cache"
export DOUYIN_MODELS_DIR="$PWD/models"
export DOUYIN_SKILLS_DIR="$PWD/skills"
python3 manage.py serve
```

`DOUYIN_PROJECT_ROOT` 指向一个完整、可写的项目副本，而不是独立素材盘。代码与状态按该副本组织；若只是想把大模型和缓存放到大容量磁盘，使用对应的 MODELS/CACHE 配置即可。`DOUYIN_PYTHON` 是执行子任务的解释器绝对路径。

`manage.py serve` 为服务与子进程设置 pip、npm、Hugging Face、Torch、Playwright、临时目录等缓存位置；它不会更改系统级设置。直接在 shell 安装依赖时，仍需在该 shell 设置缓存变量，或在 Windows 加载 `config/project-env.ps1`。

## Windows 便捷入口

- `workbench/打开工作台.cmd`：启动后台服务并打开网页，默认优先使用 `.venv`。
- `workbench/start-workbench.ps1`：前台运行；支持 `-Port` 与 `-Offline`。
- `workbench/export-offline-workbench.ps1`：导出当前本地数据的只读 HTML。

端口已有其他程序或另一份项目时，启动器会提示更换端口，不会终止其他程序。后台日志和 PID 位于 `workspace/workbench/runtime/`。停止后台服务前，先用日志、命令行与 PID 核对确实是本项目的进程。

## 迁移与更新

更新源码可以 `git pull`。本地 `data/`、`content/`、`assets/library/`、`research/` 不在公开仓库中，应自行备份。关闭生成任务和工作台后再复制数据，目标机器重新建立环境与第三方登录。

部分生成 manifest、审批和引用素材中会保存绝对路径。基础工作台已经支持任意路径部署，但移动已有生产项目后，需要核对旧引用并重新生成受影响的任务卡和发布包；目前没有一键重写全部历史路径的迁移器。

## 网络部署范围

当前服务以单用户本机使用为目标，未提供多用户身份认证、HTTPS、租户隔离和远程权限管理。保持默认回环监听。要做公网或团队部署，需要另外实现这些能力，不能仅把监听地址改成 `0.0.0.0`。
