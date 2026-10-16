# Azure Data Factory definitions  (UNTESTED - never deployed)

These JSON files are ready-to-edit definitions. They were validated only as JSON (see `tests/test_sql_and_definitions.py`);
no Azure subscription was available, so **nothing here has been deployed or run**. Expect to adjust names, API shapes and
the Batch/Custom-activity packaging in your environment.

| Folder | Content |
|---|---|
| `linkedService/` | ADLS Gen2 (Managed Identity), Key Vault, Blob endpoint, Azure Batch, Snowflake (password from Key Vault) |
| `dataset/` | Parameterised Binary datasets for `landing` and `raw` file systems |
| `pipeline/pl_finflow_daily.json` | `Validation` (wait for file) -> `Copy` landing->raw (retry 3) -> `Custom` run ETL (retry 2) -> `Script` Snowflake check -> on failure `WebActivity` alert + `Fail` |
| `trigger/tr_finflow_daily.json` | Tumbling-window, daily 02:00 UTC, `maxConcurrency: 1`, retry policy 2 x 5 min |
| `../monitoring/adf_failed_runs_alert.json` | ARM template: metric alert on `PipelineFailedRuns` |
| `../scripts/deploy_adf.ps1` | Az PowerShell deployment script |

## Prerequisites
1. Storage account (hierarchical namespace ON) with file systems `landing` and `raw`; ADF system-assigned identity has `Storage Blob Data Contributor`.
2. Key Vault with secrets `BATCH-ACCESS-KEY`, `SNOWFLAKE-PASSWORD`, `MYSQL-PASSWORD`; ADF identity has `Key Vault Secrets User`.
3. An Azure Batch pool with Python 3.11 and `pip install .` of this repo (or run the same command from a container job/Databricks/Container Apps job - the `Custom` activity is one of several valid choices).
4. A Logic App / Teams webhook URL for alerts (pass as pipeline parameter; keep it out of git).

## Deploy
```powershell
Connect-AzAccount
.\azure\scripts\deploy_adf.ps1 -ResourceGroup rg-finflow -FactoryName adf-finflow
```
Alternatively connect the factory to this GitHub repo in ADF Studio (Manage -> Git configuration) and author from these files.
Run `pl_finflow_daily` once with **Debug** before starting the trigger.

## Retries and failure handling
| Layer | Mechanism |
|---|---|
| File arrival | `Validation` activity polls every 60 s up to 1 h |
| Copy | activity retry 3 x 60 s |
| ETL | activity retry 2 x 300 s - safe because loads are atomic and rerun-safe |
| Window | tumbling-window retry 2 x 300 s, `maxConcurrency 1` |
| Alerting | `Notify_Failure` webhook, then `Fail_Pipeline`; Azure Monitor metric alert on failed runs |

## Monitoring
- ADF Studio -> Monitor (pipeline/trigger runs). Enable diagnostic settings to Log Analytics and query:
  `ADFPipelineRun | where Status == "Failed" | project TimeGenerated, PipelineName, RunId, FailureType`
- Application-level evidence: `etl_load_audit`, `etl_reconciliation` (MySQL) and JSON logs.
