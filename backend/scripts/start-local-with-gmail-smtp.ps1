$ErrorActionPreference = 'Stop'

if (-not $env:DATABASE_URL -or -not $env:SECRET_KEY) {
    throw 'Start this script from the same PowerShell session used for the local backend, so DATABASE_URL and SECRET_KEY are inherited.'
}

$pythonPath = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Backend virtual environment was not found at backend\.venv. Create it and install backend dependencies first.'
}

$emailAddress = Read-Host 'Gmail address to send order emails from'
$securePassword = Read-Host 'Gmail app password (input hidden; not your Google login password)' -AsSecureString
$retryRequestId = Read-Host 'Failed email request ID to retry (Enter to skip)'
$variableNames = @(
    'APP_ENV',
    'EMAIL_PROVIDER',
    'EMAIL_FROM_ADDRESS',
    'EMAIL_WORKER_ENABLED',
    'SMTP_HOST',
    'SMTP_PORT',
    'SMTP_USERNAME',
    'SMTP_PASSWORD',
    'SMTP_USE_SSL',
    'EMAIL_REQUEUE_REQUEST_ID'
)
$previousValues = @{}
foreach ($name in $variableNames) {
    $previousValues[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$passwordPointer = [IntPtr]::Zero
$plainPassword = $null
try {
    if ($emailAddress -notmatch '^[^\s@]+@gmail\.com$') {
        throw 'Enter the Gmail address that owns the app password.'
    }
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $plainPassword = $plainPassword -replace '\s', ''
    if ([string]::IsNullOrWhiteSpace($plainPassword)) {
        throw 'A Gmail app password is required.'
    }

    $env:APP_ENV = 'local'
    $env:EMAIL_PROVIDER = 'smtp'
    $env:EMAIL_FROM_ADDRESS = $emailAddress
    $env:EMAIL_WORKER_ENABLED = 'true'
    $env:SMTP_HOST = 'smtp.gmail.com'
    $env:SMTP_PORT = '587'
    $env:SMTP_USERNAME = $emailAddress
    $env:SMTP_PASSWORD = $plainPassword
    $env:SMTP_USE_SSL = 'false'
    $env:EMAIL_REQUEUE_REQUEST_ID = $retryRequestId

    Set-Location (Join-Path $PSScriptRoot '..')
    & $pythonPath -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
    if ($LASTEXITCODE -ne 0) {
        throw "Backend exited with code $LASTEXITCODE. Check its startup output above."
    }
}
finally {
    foreach ($name in $variableNames) {
        [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process')
    }
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
    $securePassword.Dispose()
}
