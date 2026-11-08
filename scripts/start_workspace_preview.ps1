param(
    [switch]$EnableLiveFromEnv = $true,
    [switch]$EnableBillingLive = $true,
    [switch]$EnableRetryFromEnv = $true,
    [ValidateRange(1, 10000)][int]$MaxRuns = 40,
    [ValidateRange(1, 100)][int]$MaxModelCalls = 48,
    [ValidateRange(1, 200000)][int]$MaxOutputTokens = 196608
)

$ErrorActionPreference = 'Stop'
if ($EnableRetryFromEnv -and -not $EnableLiveFromEnv) {
    throw 'Live recovery also requires -EnableLiveFromEnv.'
}
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv/Scripts/python.exe'
$state = Join-Path $env:LOCALAPPDATA 'TrustBound/workspace-preview-v2'
New-Item -ItemType Directory -Path $state -Force | Out-Null
$env:TRUSTBOUND_WORKSPACE_DB = Join-Path $state 'workspace-history.sqlite3'
$env:TRUSTBOUND_QUOTA_DB = Join-Path $state 'quota.sqlite3'
$env:TRUSTBOUND_ENABLE_WORKSPACE = '1'
$env:TRUSTBOUND_WORKSPACE_LOCAL_DOCKER = '1'
$env:TRUSTBOUND_WORKSPACE_LOCAL_PREVIEW = '1'
$env:TRUSTBOUND_PUBLIC_DEMO = '0'
$env:TRUSTBOUND_LOAD_DOTENV = '1'
$env:TRUSTBOUND_ENABLE_LIVE = [string][int]$EnableBillingLive.IsPresent
if ($EnableRetryFromEnv) {
    $env:TRUSTBOUND_ENABLE_RECOVERY_LIVE = '1'
} else {
    $env:TRUSTBOUND_ENABLE_RECOVERY_LIVE = '0'
}
$env:TRUSTBOUND_MAX_RUNS = [string]$MaxRuns
$env:TRUSTBOUND_MIN_RUN_SECONDS = '0'
$env:TRUSTBOUND_MAX_MODEL_CALLS = [string]$MaxModelCalls
$env:TRUSTBOUND_MAX_OUTPUT_TOKENS = [string]$MaxOutputTokens
Remove-Item Env:TRUSTBOUND_RUNNER_SOCKET -ErrorAction SilentlyContinue
if ($EnableLiveFromEnv) {
    $env:TRUSTBOUND_ENABLE_WORKSPACE_LIVE = '1'
} else {
    $env:TRUSTBOUND_ENABLE_WORKSPACE_LIVE = '0'
}
Push-Location $root
try {
    if (-not (Test-Path -LiteralPath $env:TRUSTBOUND_QUOTA_DB)) {
        & $python -B -m trustbound.admission init $env:TRUSTBOUND_QUOTA_DB
        if ($LASTEXITCODE -ne 0) { throw 'Preview quota initialization failed.' }
    }
    & $python -B -m uvicorn trustbound.api:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw 'Preview API failed.' }
} finally {
    Pop-Location
}
