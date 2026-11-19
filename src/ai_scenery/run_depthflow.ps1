param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DepthFlowArgs
)

$projectRoot = if ($env:DOUYIN_PROJECT_ROOT) { [IO.Path]::GetFullPath($env:DOUYIN_PROJECT_ROOT) } else { (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path }
$cacheRoot = if ($env:DOUYIN_CACHE_DIR) { $env:DOUYIN_CACHE_DIR } else { Join-Path $projectRoot 'cache' }
$runtimeRoot = Join-Path $cacheRoot 'ai_scenery_motion'
$pythonEnv = Join-Path $projectRoot 'envs\ai_scenery_motion'
$depthflow = $env:DOUYIN_DEPTHFLOW_EXE
if (-not $depthflow) { $depthflow = Join-Path $pythonEnv 'Scripts\depthflow.exe' }
if (-not (Test-Path -LiteralPath $depthflow)) { $depthflow = (Get-Command depthflow -ErrorAction SilentlyContinue).Source }
$ffmpeg = $env:PROJECT_FFMPEG_EXE
if (-not $ffmpeg) { $ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source }
$ffprobe = $env:PROJECT_FFPROBE_EXE
if (-not $ffprobe) { $ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source }

$required = @(
    $depthflow,
    $ffmpeg,
    $ffprobe
)
foreach ($path in $required) {
    if (-not $path -or -not (Test-Path -LiteralPath $path)) {
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
$ffmpegBin = Split-Path -Parent $ffmpeg
$ffprobeBin = Split-Path -Parent $ffprobe
$env:PATH = "$ffmpegBin;$ffprobeBin;$env:PATH"

& $depthflow @DepthFlowArgs
exit $LASTEXITCODE
