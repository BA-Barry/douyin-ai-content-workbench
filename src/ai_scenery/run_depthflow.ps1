param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DepthFlowArgs
)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$runtimeRoot = Join-Path $projectRoot 'cache\ai_scenery_motion'
$pythonEnv = Join-Path $projectRoot 'envs\ai_scenery_motion'
$ffmpegBin = Join-Path $projectRoot 'tools\ffmpeg\current\ffmpeg-master-latest-win64-gpl\bin'

$required = @(
    (Join-Path $pythonEnv 'Scripts\depthflow.exe'),
    (Join-Path $ffmpegBin 'ffmpeg.exe'),
    (Join-Path $ffmpegBin 'ffprobe.exe')
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required runtime file is missing: $path"
    }
}

$tempDir = Join-Path $runtimeRoot 'temp'
$depthflowCache = Join-Path $runtimeRoot 'depthflow'
$hfCache = Join-Path $runtimeRoot 'hf'
$torchCache = Join-Path $runtimeRoot 'torch'
New-Item -ItemType Directory -Force -Path $tempDir, $depthflowCache, $hfCache, $torchCache | Out-Null

$env:DEPTHFLOW_CACHE_DIR = $depthflowCache
$env:HF_HOME = $hfCache
$env:TORCH_HOME = $torchCache
$env:TEMP = $tempDir
$env:TMP = $tempDir
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PATH = "$ffmpegBin;$env:PATH"

& (Join-Path $pythonEnv 'Scripts\depthflow.exe') @DepthFlowArgs
exit $LASTEXITCODE
