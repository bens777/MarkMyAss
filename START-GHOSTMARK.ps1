$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Fail($msg) {
    Write-Host ""
    Write-Host $msg -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Fail "Python 3.11+ is required but was not found.`nDownload it from https://www.python.org/downloads/ and run this script again."
}

$versionOk = & python -c "import sys; print(1 if sys.version_info >= (3, 11) else 0)"
if ($versionOk -ne "1") {
    Fail "GhostMark needs Python 3.11 or newer.`nDownload it from https://www.python.org/downloads/ and run this script again."
}

if (-not (Test-Path ".venv")) {
    Write-Host "Setting up GhostMark for the first time. This can take a minute..."
    python -m venv .venv
    if (-not $?) { Fail "Could not create a Python virtual environment." }
}

& ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& ".venv\Scripts\python.exe" -m pip install --quiet -e "."
if (-not $?) { Fail "GhostMark could not install its dependencies. See the messages above for details." }

Write-Host ""
Write-Host "Starting GhostMark at http://127.0.0.1:8765"
Write-Host "Your files never leave this computer."
Write-Host ""
& ".venv\Scripts\ghostmark.exe" ui
