param(
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot 'envs\content\Scripts\python.exe'

. (Join-Path $projectRoot 'config\project-env.ps1')

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python is missing: $python"
}

$env:DOUYIN_WORKBENCH_OFFLINE = if ($Offline) { '1' } else { '0' }
$serverArguments = @('-u', (Join-Path $projectRoot 'workbench\server.py'), '--port', "$Port")
if ($Offline) { $serverArguments += '--offline' }
& $python @serverArguments
exit $LASTEXITCODE
