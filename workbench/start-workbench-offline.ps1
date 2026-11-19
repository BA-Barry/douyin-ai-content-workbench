param([ValidateRange(1, 65535)][int]$Port = 8765)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'start-workbench.ps1') -Port $Port -Offline
exit $LASTEXITCODE
