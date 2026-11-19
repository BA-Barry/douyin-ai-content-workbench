$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

$projectPaths = @{
    Envs = Join-Path $projectRoot 'envs'
    Models = Join-Path $projectRoot 'models'
    Cache = Join-Path $projectRoot 'cache'
    Workspace = Join-Path $projectRoot 'workspace'
    Projects = Join-Path $projectRoot 'projects'
    Tools = Join-Path $projectRoot 'tools'
}

foreach ($path in $projectPaths.Values) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

$env:HF_HOME = Join-Path $projectPaths.Models 'huggingface'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:HF_DATASETS_CACHE = Join-Path $env:HF_HOME 'datasets'
$env:TRANSFORMERS_CACHE = Join-Path $env:HF_HOME 'transformers'
$env:TORCH_HOME = Join-Path $projectPaths.Models 'torch'
$env:MODELSCOPE_CACHE = Join-Path $projectPaths.Models 'modelscope'

$env:XDG_CACHE_HOME = $projectPaths.Cache
$env:PIP_CACHE_DIR = Join-Path $projectPaths.Cache 'pip'
$env:UV_CACHE_DIR = Join-Path $projectPaths.Cache 'uv'
$env:NPM_CONFIG_CACHE = Join-Path $projectPaths.Cache 'npm'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $projectPaths.Cache 'playwright'
$env:PUPPETEER_CACHE_DIR = Join-Path $projectPaths.Cache 'puppeteer'
$env:MPLCONFIGDIR = Join-Path $projectPaths.Cache 'matplotlib'
$env:NUMBA_CACHE_DIR = Join-Path $projectPaths.Cache 'numba'
$env:TEMP = Join-Path $projectPaths.Cache 'temp'
$env:TMP = $env:TEMP

# baoyu-image-gen's codex-cli provider uses the existing Codex login and stores
# all project-generated cache/log intermediates on G:.  Per-task output/log
# paths are still supplied by the caller.
$env:BAOYU_CODEX_IMAGEGEN_CACHE_DIR = Join-Path $projectPaths.Cache 'baoyu-codex-imagegen\idempotency'
$env:BAOYU_CODEX_IMAGEGEN_TIMEOUT_MS = '300000'
$env:BAOYU_CODEX_IMAGEGEN_RETRIES = '1'

$managedPaths = @(
    $env:HF_HOME,
    $env:HF_HUB_CACHE,
    $env:HF_DATASETS_CACHE,
    $env:TRANSFORMERS_CACHE,
    $env:TORCH_HOME,
    $env:MODELSCOPE_CACHE,
    $env:PIP_CACHE_DIR,
    $env:UV_CACHE_DIR,
    $env:NPM_CONFIG_CACHE,
    $env:PLAYWRIGHT_BROWSERS_PATH,
    $env:PUPPETEER_CACHE_DIR,
    $env:MPLCONFIGDIR,
    $env:NUMBA_CACHE_DIR,
    $env:TEMP,
    $env:BAOYU_CODEX_IMAGEGEN_CACHE_DIR
)

foreach ($path in $managedPaths) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

$projectFfmpeg = Get-ChildItem -LiteralPath (Join-Path $projectPaths.Tools 'ffmpeg\current') -Recurse -Filter 'ffmpeg.exe' -File -ErrorAction SilentlyContinue | Select-Object -First 1
$projectFfprobe = Get-ChildItem -LiteralPath (Join-Path $projectPaths.Tools 'ffmpeg\current') -Recurse -Filter 'ffprobe.exe' -File -ErrorAction SilentlyContinue | Select-Object -First 1

if ($projectFfmpeg -and $projectFfprobe) {
    $projectFfmpegBin = $projectFfmpeg.Directory.FullName
    $env:PROJECT_FFMPEG_EXE = $projectFfmpeg.FullName
    $env:PROJECT_FFPROBE_EXE = $projectFfprobe.FullName
    $env:IMAGEIO_FFMPEG_EXE = $projectFfmpeg.FullName
    $env:FFMPEG_BINARY = $projectFfmpeg.FullName
    $env:FFPROBE_BINARY = $projectFfprobe.FullName
    if (-not (($env:PATH -split ';') -contains $projectFfmpegBin)) {
        $env:PATH = "$projectFfmpegBin;$env:PATH"
    }
}

# Make the GitHub baoyu-image-gen Skill callable from a fresh Codex task.
# Bun is already cached on G:.  The native Codex executable is an existing
# application runtime, not a project dependency or model.
$projectBun = Get-ChildItem -LiteralPath $env:NPM_CONFIG_CACHE -Recurse -Filter 'bun.exe' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if ($projectBun) {
    $env:PROJECT_BUN_EXE = $projectBun.FullName
    if (-not (($env:PATH -split ';') -contains $projectBun.Directory.FullName)) {
        $env:PATH = "$($projectBun.Directory.FullName);$env:PATH"
    }
}

$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
if ($codexCommand) {
    $codexInstallRoot = Join-Path (Split-Path -Parent $codexCommand.Source) 'node_modules\@openai\codex'
    if (Test-Path -LiteralPath $codexInstallRoot) {
        $nativeCodex = Get-ChildItem -LiteralPath $codexInstallRoot -Recurse -Filter 'codex.exe' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match 'vendor\\x86_64-pc-windows-msvc\\codex\\codex\.exe$' } |
            Select-Object -First 1
        if ($nativeCodex) {
            $env:PROJECT_CODEX_NATIVE_EXE = $nativeCodex.FullName
            if (-not (($env:PATH -split ';') -contains $nativeCodex.Directory.FullName)) {
                $env:PATH = "$($nativeCodex.Directory.FullName);$env:PATH"
            }
        }
    }
}

Write-Host "Project runtime paths configured under $projectRoot"
