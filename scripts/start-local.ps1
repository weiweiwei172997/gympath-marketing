[CmdletBinding()]
param(
    [string]$Python = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'backend\app.py') -PathType Leaf)) {
    throw 'Cannot find backend/app.py beside the scripts directory.'
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $LocalPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    $Python = if (Test-Path -LiteralPath $LocalPython -PathType Leaf) { $LocalPython } else { 'python' }
}

try {
    $PythonCommand = Get-Command -Name $Python -CommandType Application -ErrorAction Stop
}
catch {
    throw 'Python was not found. Install the requirements-trial.txt dependencies and pass -Python with your Python executable path.'
}

Write-Host 'GymPath local site: http://127.0.0.1:8081/'
Write-Host 'The server runs in this terminal. Press Ctrl+C to stop it.'

Push-Location -LiteralPath $ProjectRoot
try {
    & $PythonCommand.Source -m uvicorn backend.app:app --host 127.0.0.1 --port 8081 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-server-header
    $ServerExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $ServerExitCode
