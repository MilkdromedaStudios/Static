$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Find-SupportedPython {
    $options = @(
        @{ Command = 'py'; Args = @('-3.12') },
        @{ Command = 'py'; Args = @('-3') },
        @{ Command = 'python'; Args = @() }
    )
    foreach ($option in $options) {
        if (-not (Get-Command $option.Command -ErrorAction SilentlyContinue)) { continue }
        $versionArgs = @($option.Args) + @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)')
        try { & $option.Command @versionArgs 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0) { return $option }
    }
    return $null
}

$python = Find-SupportedPython
if (-not $python) {
    Write-Host 'Static needs Python 3.11 or newer.'
    $answer = Read-Host 'Install Python 3.12 with Windows Package Manager (WinGet)? [y/N]'
    if ($answer -notin @('y', 'Y', 'yes', 'YES')) {
        throw 'Install Python from https://www.python.org/downloads/ and rerun start.ps1.'
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'WinGet is unavailable. Install Python from https://www.python.org/downloads/ and rerun start.ps1.'
    }
    & winget install --id Python.Python.3.12 --exact --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python installation did not finish. Use https://www.python.org/downloads/ and retry.' }
    # WinGet may update the user PATH without updating the current shell.
    $env:PATH = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $python = Find-SupportedPython
    if (-not $python) {
        throw 'Python was installed, but this terminal cannot find it yet. Open a new PowerShell window and rerun start.ps1.'
    }
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    $venvArgs = @($python.Args) + @('-m', 'venv', '.venv')
    & $python.Command @venvArgs
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $venvPython -m pip install --disable-pip-version-check -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Could not install Static dependencies.' }
& $venvPython -m pip install --disable-pip-version-check --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Could not install Static.' }
& $venvPython -m static_ai @args
exit $LASTEXITCODE
