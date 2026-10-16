<#
 Deploys the ADF JSON definitions with the Az PowerShell module.  UNTESTED - requires Azure access.
 Prereqs:  Install-Module Az -Scope CurrentUser ; Connect-AzAccount
 Edit the <placeholders> in azure/adf/**/*.json first (storage account, key vault, batch, snowflake).
 Usage:    .\azure\scripts\deploy_adf.ps1 -ResourceGroup rg-finflow -FactoryName adf-finflow
#>
param(
  [Parameter(Mandatory = $true)][string]$ResourceGroup,
  [Parameter(Mandatory = $true)][string]$FactoryName
)
$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot "..\adf"

# Order matters: Key Vault and storage first, then dependents.
$order = @("ls_keyvault", "ls_adls_gen2", "ls_adls_gen2_blob", "ls_azure_batch", "ls_snowflake")
foreach ($n in $order) {
  Set-AzDataFactoryV2LinkedService -ResourceGroupName $ResourceGroup -DataFactoryName $FactoryName `
    -Name $n -DefinitionFile (Join-Path $root "linkedService\$n.json") -Force
}
foreach ($n in @("ds_landing_binary", "ds_raw_binary")) {
  Set-AzDataFactoryV2Dataset -ResourceGroupName $ResourceGroup -DataFactoryName $FactoryName `
    -Name $n -DefinitionFile (Join-Path $root "dataset\$n.json") -Force
}
Set-AzDataFactoryV2Pipeline -ResourceGroupName $ResourceGroup -DataFactoryName $FactoryName `
  -Name "pl_finflow_daily" -DefinitionFile (Join-Path $root "pipeline\pl_finflow_daily.json") -Force
Set-AzDataFactoryV2Trigger -ResourceGroupName $ResourceGroup -DataFactoryName $FactoryName `
  -Name "tr_finflow_daily" -DefinitionFile (Join-Path $root "trigger\tr_finflow_daily.json") -Force

Write-Host "Definitions deployed. Start the trigger only after a successful manual debug run:"
Write-Host "  Start-AzDataFactoryV2Trigger -ResourceGroupName $ResourceGroup -DataFactoryName $FactoryName -Name tr_finflow_daily"
