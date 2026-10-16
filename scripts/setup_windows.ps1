<#
 One-shot Windows setup (PowerShell 5.1+ / 7+).   Run from the project root:
     powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
 Creates .venv, installs dependencies + the package, creates .env from the template.
#>
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Prefer the py launcher (installed with python.org Python) so we get 3.11+.
$py = $null
foreach ($candidate in @("py -3.12", "py -3.11", "python")) {
  try {
    $v = Invoke-Expression "$candidate -c `"import sys;print('%d.%d' % sys.version_info[:2])`"" 2>$null
    if ($v -and ([version]$v -ge [version]"3.11")) { $py = $candidate; break }
  } catch { }
}
if (-not $py) { throw "Python 3.11+ not found. Install from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')." }
Write-Host "Using: $py"

Invoke-Expression "$py -m venv .venv"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip install -e .

if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env from .env.example (edit as needed)." }
Write-Host "`nDone. Activate with:  .\.venv\Scripts\Activate.ps1"
