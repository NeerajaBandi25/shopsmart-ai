param(
    [ValidateSet("BackendOnly", "Live")]
    [string]$Mode = "BackendOnly",
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendRoot = Join-Path $repositoryRoot "backend"
$localEnvPath = Join-Path $backendRoot ".env"
$pythonPath = Join-Path $backendRoot ".venv\Scripts\python.exe"

function Get-LocalPortListenerPid([int]$Port) {
    foreach ($line in (& netstat.exe -ano -p tcp)) {
        if ($line -match "^\s*TCP\s+127\.0\.0\.1:$Port\s+\S+\s+LISTENING\s+(\d+)$") {
            return [int]$Matches[1]
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $localEnvPath -PathType Leaf)) {
    throw "Missing ignored local configuration: backend/.env"
}
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Backend virtual environment not found at backend/.venv."
}

$localConfig = @{}
foreach ($line in Get-Content -LiteralPath $localEnvPath) {
    if ($line -match '^\s*(?:#|$)') { continue }
    if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
        throw "Invalid local environment entry in backend/.env."
    }
    $name = $Matches[1]
    $value = $Matches[2].Trim()
    if ($value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
         ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    $localConfig[$name] = $value
}

foreach ($requiredName in @("DATABASE_URL", "SECRET_KEY", "AI_PROVIDER", "OPENROUTER_MODEL")) {
    if (-not $localConfig.ContainsKey($requiredName) -or
        [string]::IsNullOrWhiteSpace($localConfig[$requiredName])) {
        throw "Required local setting '$requiredName' is missing from backend/.env."
    }
}
if ($localConfig["DATABASE_URL"] -notmatch '^postgresql\+asyncpg://agentsuresh(?::[^@]*)?@(?:localhost|127\.0\.0\.1|\[::1\]):5432/shopsmart_portfolio(?:\?.*)?$') {
    throw "Portfolio mode requires the local shopsmart_portfolio database as agentsuresh."
}
if ($localConfig["AI_PROVIDER"] -ne "openrouter") {
    throw "This local workflow requires AI_PROVIDER=openrouter."
}
if ($Mode -eq "Live" -and [string]::IsNullOrWhiteSpace($localConfig["OPENROUTER_API_KEY"])) {
    Write-Output "OPENROUTER_KEY_NEEDS_ONE_LOCAL_INSERT"
    Write-Output "Populate OPENROUTER_API_KEY in backend/.env, then rerun with -Mode Live."
    exit 2
}

# Make this file authoritative over stale values inherited from a terminal.
foreach ($entry in $localConfig.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
}
foreach ($providerKey in @("OPENAI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY")) {
    [Environment]::SetEnvironmentVariable($providerKey, "", "Process")
}
if (-not $localConfig["REDIS_URL"]) {
    Write-Output "redis=optional_disabled; runtime uses documented local/degraded fallback"
}

Push-Location $backendRoot
try {
    & $pythonPath "-m" "scripts.verify_runtime_database"
    if ($LASTEXITCODE -ne 0) { throw "Runtime database identity check failed." }

    if (Get-LocalPortListenerPid -Port $Port) {
        throw "Port $Port is already in use; choose a free port before starting this configured instance."
    }

    if ($Foreground) {
        Write-Output "backend=starting_foreground port=$Port provider=$($localConfig['AI_PROVIDER']) model=$($localConfig['OPENROUTER_MODEL'])"
        & $pythonPath "-m" "uvicorn" "src.main:app" "--host" "127.0.0.1" "--port" "$Port"
        exit $LASTEXITCODE
    }

    $runtimeLog = Join-Path $repositoryRoot ".factory\runtime\backend-local.log"
    $runtimeErrorLog = Join-Path $repositoryRoot ".factory\runtime\backend-local-error.log"
    New-Item -ItemType Directory -Path (Split-Path $runtimeLog) -Force | Out-Null
    $process = Start-Process -FilePath $pythonPath `
        -ArgumentList @("-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $backendRoot `
        -RedirectStandardOutput $runtimeLog `
        -RedirectStandardError $runtimeErrorLog `
        -WindowStyle Hidden `
        -PassThru

    $healthy = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        if ($process.HasExited) { break }
        $listenerPid = Get-LocalPortListenerPid -Port $Port
        if (-not $listenerPid) { continue }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
            $readiness = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/readiness" -TimeoutSec 3
            if ($health.status -eq "ok" -and $readiness.status -eq "ready") {
                $healthy = $true
                break
            }
        } catch {
            # Continue waiting without emitting response or configuration details.
        }
    }
    if (-not $healthy) {
        throw "Backend did not become healthy. Review .factory/runtime/backend-local*.log; configuration values are not printed."
    }

    Write-Output "backend=running port=$Port"
    Write-Output "health=200 status=ok"
    Write-Output "readiness=ready"
    Write-Output "provider=$($localConfig['AI_PROVIDER']) model=$($localConfig['OPENROUTER_MODEL'])"
    if ([string]::IsNullOrWhiteSpace($localConfig["OPENROUTER_API_KEY"])) {
        Write-Output "OPENROUTER_KEY_NEEDS_ONE_LOCAL_INSERT"
        Write-Output "Populate OPENROUTER_API_KEY in backend/.env to enable live provider calls."
    }
    Write-Output "sweeper_log=.factory/runtime/backend-local.log"
} finally {
    Pop-Location
}
