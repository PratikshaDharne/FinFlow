# Security and governance

## Secrets
- All configuration comes from environment variables (`src/finflow/config.py`). **No credential appears in code, SQL, JSON or tests** (a test scans for hardcoded secrets).
- `.env` is git-ignored; `.env.example` contains names only. Rotate any secret that was ever pasted into a chat, ticket or commit.
- In Azure, use **Managed Identity** for storage and Key Vault; avoid account keys, SAS tokens and connection strings.
- Logs are passed through a redactor (URLs with credentials, `password=`, `token=`, `sig=`...). Database URLs are logged masked.

## Azure Key Vault (UNTESTED - no Azure access in the build environment)
1. Create the vault with RBAC authorization, soft-delete and purge protection:
   `az keyvault create -n <kv> -g <rg> -l <region> --enable-rbac-authorization true --enable-purge-protection true`
2. Store secrets (names use hyphens): `az keyvault secret set --vault-name <kv> --name MYSQL-PASSWORD --value "<from your password manager>"`,
   likewise `SNOWFLAKE-PASSWORD`, `BATCH-ACCESS-KEY`.
3. Grant the identity running the pipeline (ADF / Batch pool / your user for dev) **Key Vault Secrets User** on the vault only:
   `az role assignment create --assignee <principal-id> --role "Key Vault Secrets User" --scope <kv-resource-id>`
4. Set `KEY_VAULT_URL=https://<kv>.vault.azure.net/` for the pipeline. `get_secret()` reads the environment first, then Key Vault (`MYSQL_PASSWORD` -> `MYSQL-PASSWORD`) using `DefaultAzureCredential` (needs `pip install -r requirements-cloud.txt`).
5. For local dev, `az login` is enough; no secret needs to be on disk.
6. ADF linked services reference secrets through `AzureKeyVaultSecret` (see `azure/adf/linkedService/`).

## Least privilege
| Principal | Scope | Rights |
|---|---|---|
| `finflow_deploy` (MySQL) | `finflow.*` | DDL + DML; used by CI/DBA only |
| `finflow_etl` (MySQL) | `finflow.*` | SELECT/INSERT/UPDATE/DELETE only; run with `FINFLOW_AUTO_INIT_SCHEMA=false` |
| `finflow_reader` (MySQL) | `finflow.*` | SELECT; consider excluding `etl_rejected_records` |
| ADF managed identity | storage account | `Storage Blob Data Contributor` on `landing` (read) / `raw` (write) containers only; `Key Vault Secrets User` |
| Batch pool identity | `raw`, Key Vault | read raw, get secrets |
| `FINFLOW_ETL_ROLE` (Snowflake) | `FINFLOW_DB` | DML on STAGING/CURATED, no ownership, no ACCOUNTADMIN |
| Snowflake service user | - | key-pair auth, no interactive login |
| GitHub Actions | repo | `permissions: contents: read`; CI uses only throwaway service-container credentials |

## Data protection
- Synthetic data only: names are generic, emails use `example.com`. Treat real data as PII/financial data.
- `etl_rejected_records.raw_record` and `rejected_records.csv` mask PII columns (`FINFLOW_MASK_PII_IN_REPORTS=true`). The unmasked source stays in the raw layer; use `source_file` + `source_row_number` to find it.
- Raw files are immutable and checksummed (tamper evidence, replay). Apply Azure storage immutability/versioning and lifecycle rules in production.
- Encryption: Azure Storage, MySQL (enable TLS: add `?ssl_ca=...` to the URL in production) and Snowflake encrypt at rest; enforce TLS in transit.
- Network: private endpoints/firewall rules for storage, Key Vault, MySQL; no public access in production.

## Auditability
Every curated row carries `created_load_id`, `updated_load_id`, `source_file`, `row_hash`, `etl_created_at`, `etl_updated_at`;
`etl_load_audit`, `etl_file_registry`, `etl_dq_results`, `etl_reconciliation` and `etl_rejected_records` answer
"what was loaded, from which file, when, and what was rejected and why".
