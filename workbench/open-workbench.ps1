param(
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [switch]$NoBrowser,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
# Keep this file ASCII: Windows PowerShell 5.1 otherwise reads UTF-8 as ANSI.
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot 'envs\content\Scripts\python.exe'
$server = Join-Path $projectRoot 'workbench\server.py'
$runtime = Join-Path $projectRoot 'workspace\workbench\runtime'
$url = "http://127.0.0.1:$Port/"
$healthUrl = "${url}api/health"
$expectedMode = if ($Offline) { 'offline' } else { 'local' }

function Get-WorkbenchHealth {
    try {
        return Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    }
    catch {
        return $null
    }
}

function Assert-WorkbenchIdentity($Health) {
    $sameRoot = $false
    if ($Health.root -is [string] -and $Health.root) {
        try {
            $sameRoot = [string]::Equals(
                [IO.Path]::GetFullPath($Health.root).TrimEnd('\'),
                [IO.Path]::GetFullPath($projectRoot).TrimEnd('\'),
                [StringComparison]::OrdinalIgnoreCase
            )
        }
        catch { $sameRoot = $false }
    }
    if ($Health.status -ne 'ok' -or -not $sameRoot) {
        throw "Port $Port is serving another application or project. Nothing was stopped. Close that service yourself or use -Port <unused-port>."
    }
    if ($Health.mode -ne $expectedMode) {
        throw "This workbench is already running in '$($Health.mode)' mode on port $Port; requested '$expectedMode'. Nothing was stopped. Use another -Port or close the existing service first."
    }
}

function Test-LocalPortInUse {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connection = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($connection)
        return $true
    }
    catch { return $false }
    finally { $client.Close() }
}

$health = Get-WorkbenchHealth
if ($null -ne $health) {
    Assert-WorkbenchIdentity $health
}
else {
    if (Test-LocalPortInUse) {
        throw "Port $Port is occupied, but this project's health endpoint is unavailable. Nothing was stopped. Use -Port <unused-port> or inspect the existing service."
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "Project Python is missing: $python"
    }
    if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
        throw "Workbench server is missing: $server"
    }
    . (Join-Path $projectRoot 'config\project-env.ps1')
    $env:DOUYIN_WORKBENCH_OFFLINE = if ($Offline) { '1' } else { '0' }
    $env:PYTHONUNBUFFERED = '1'
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    $runLabel = "workbench-$Port-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff')"
    $stdout = Join-Path $runtime "$runLabel.stdout.log"
    $stderr = Join-Path $runtime "$runLabel.stderr.log"
    # Start-Process joins ArgumentList with spaces, so quote the script path.
    $serverArguments = @('-u', ('"' + $server + '"'), '--port', "$Port")
    if ($Offline) { $serverArguments += '--offline' }
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList $serverArguments `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $pidName = if ($Port -eq 8765) { 'server.pid' } else { "server-$Port.pid" }
    Set-Content -LiteralPath (Join-Path $runtime $pidName) -Value $process.Id -Encoding ascii

    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        Start-Sleep -Milliseconds 500
        $health = Get-WorkbenchHealth
        if ($null -ne $health) {
            Assert-WorkbenchIdentity $health
            $ready = $true
            break
        }
        if ($process.HasExited) {
            break
        }
    }

    if (-not $ready) {
        $errorText = Get-Content -Raw $stderr -ErrorAction SilentlyContinue
        throw "Workbench did not become ready. Logs: $stdout ; $stderr`n$errorText"
    }
    Write-Output "Logs: $stdout ; $stderr"
}

Write-Output "Workbench ready: $url ($expectedMode)"
if (-not $NoBrowser) { Start-Process -FilePath $url }
