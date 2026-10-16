<#
 Runs the whole local demo on SQLite: tests -> batch 1 -> batch 2 -> rerun (skipped) -> status.
     .\scripts\run_local.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run scripts\setup_windows.ps1 first." }

& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
& $py -m finflow run --source data/source/batch_01
& $py -m finflow run --source data/source/batch_02
Write-Host "`n--- rerunning batch_02: must be SKIPPED (duplicate-file prevention) ---"
& $py -m finflow run --source data/source/batch_02
& $py -m finflow status
