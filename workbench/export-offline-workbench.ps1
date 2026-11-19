$ErrorActionPreference = 'Stop'
$projectRoot = 'G:\抖音视频'
$python = Join-Path $projectRoot 'envs\content\Scripts\python.exe'

. (Join-Path $projectRoot 'config\project-env.ps1')

if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到项目 Python 环境：$python"
}

& $python (Join-Path $projectRoot 'workbench\server.py') --export-offline
