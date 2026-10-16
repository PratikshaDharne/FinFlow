"""Azure Blob / ADLS Gen2 raw-layer staging.  UNTESTED: no Azure access in the build environment.

Auth order: connection string (local dev only) -> DefaultAzureCredential (Managed Identity,
`az login`, env-based service principal). No keys are stored in code.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .config import Settings, get_secret
from .errors import CloudIntegrationError, ConfigError
from .extract import SourceFile
from .logging_utils import get_logger
from .utils import retry

log = get_logger("azure")


def _client(settings: Settings):
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise ConfigError("Azure enabled but azure-storage-blob missing: pip install -r requirements-cloud.txt") from exc
    conn_str = get_secret("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)
    if not settings.azure_account_url:
        raise ConfigError("Set AZURE_STORAGE_ACCOUNT_URL (and sign in / use Managed Identity)")
    from azure.identity import DefaultAzureCredential

    return BlobServiceClient(settings.azure_account_url, credential=DefaultAzureCredential())


def blob_path(entity: str, load_id: str, file_name: str, when: datetime | None = None) -> str:
    when = when or datetime.now(UTC)
    return f"{entity}/ingest_date={when:%Y-%m-%d}/load_id={load_id}/{file_name}"


def upload_raw(settings: Settings, files: dict[str, SourceFile], load_id: str) -> list[str]:
    """Upload immutable raw copies. Existing blobs are never overwritten (overwrite=False)."""
    client = _client(settings)
    container = client.get_container_client(settings.azure_raw_container)

    @retry(attempts=3, base_delay=2.0, logger=log)
    def _upload(entity: str, sf: SourceFile) -> str:
        name = blob_path(entity, load_id, sf.raw_path.name)
        with sf.raw_path.open("rb") as fh:
            container.upload_blob(name=name, data=fh, overwrite=False, metadata={"sha256": sf.sha256})
        return name

    uploaded = []
    try:
        for entity, sf in files.items():
            uploaded.append(_upload(entity, sf))
            log.info("uploaded raw file", extra={"entity": entity, "blob": uploaded[-1]})
    except Exception as exc:
        raise CloudIntegrationError(f"Azure upload failed: {exc}") from exc
    return uploaded
