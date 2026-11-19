param(
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$projectRoot = if ($env:DOUYIN_PROJECT_ROOT) { [IO.Path]::GetFullPath($env:DOUYIN_PROJECT_ROOT) } else { (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
$python = $env:DOUYIN_PYTHON
if (-not $python) {
    $python = @((Join-Path $projectRoot '.venv\Scripts\python.exe'), (Join-Path $projectRoot 'envs\content\Scripts\python.exe')) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $python) { $python = (Get-Command python -ErrorAction SilentlyContinue).Source }

. (Join-Path $projectRoot 'config\project-env.ps1')

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python is missing: $python"
}

$env:DOUYIN_WORKBENCH_OFFLINE = if ($Offline) { '1' } else { '0' }
$serverArguments = @('-u', (Join-Path $projectRoot 'manage.py'), 'serve', '--port', "$Port")
if ($Offline) { $serverArguments += '--offline' }
& $python @serverArguments
exit $LASTEXITCODE
