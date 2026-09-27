$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.11 or newer, select Add Python to PATH, and reopen PowerShell.'
}
python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
if (-not (Test-Path '.venv')) { python -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Could not install dependencies.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Could not install Static.' }
& '.\.venv\Scripts\python.exe' -m static_ai @args
