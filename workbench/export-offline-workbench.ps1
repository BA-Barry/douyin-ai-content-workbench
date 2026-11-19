$ErrorActionPreference = 'Stop'
$projectRoot = if ($env:DOUYIN_PROJECT_ROOT) { [IO.Path]::GetFullPath($env:DOUYIN_PROJECT_ROOT) } else { (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
$python = $env:DOUYIN_PYTHON
if (-not $python) {
    $python = @((Join-Path $projectRoot '.venv/Scripts/python.exe'), (Join-Path $projectRoot 'envs/content/Scripts/python.exe')) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $python) { $python = (Get-Command python -ErrorAction Stop).Source }

. (Join-Path $projectRoot 'config\project-env.ps1')

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python is missing: $python"
}

& $python (Join-Path $projectRoot 'manage.py') init
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python (Join-Path $projectRoot 'workbench\server.py') --export-offline
