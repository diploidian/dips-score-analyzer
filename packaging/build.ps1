# Builds dist\dips-score-setup-<version>.exe: PyInstaller bundles the app, Inno Setup wraps it.
# Needs Python and Inno Setup 6 (winget install JRSoftware.InnoSetup). Run from anywhere.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value

# a private venv, so the build never touches the system Python's packages
$venv = Join-Path $PSScriptRoot ".venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) { python -m venv $venv }
& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade "PyQt6>=6.6" pyinstaller
if ($LASTEXITCODE) { throw "pip install failed" }

& "$venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name dips-score `
    --add-data "..srcdips_scoreIonts;dips_scoreIonts" `
    --paths src --distpath build\pyinstaller --workpath build\pyinstaller-work --specpath build `
    dips-score.pyw
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found: winget install JRSoftware.InnoSetup" }
& $iscc /Q "/DAppVersion=$version" packaging\dips-score.iss
if ($LASTEXITCODE) { throw "Inno Setup failed" }
Write-Host "Built dist\dips-score-setup-$version.exe"
