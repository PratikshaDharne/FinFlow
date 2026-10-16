from __future__ import annotations

from pathlib import Path

import pytest

from finflow.config import Settings

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source"


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """Isolated settings: temp SQLite DB, temp raw/report/log dirs, no .env, no cloud."""
    for var in ("MYSQL_PASSWORD", "KEY_VAULT_URL", "FINFLOW_AZURE_ENABLED", "FINFLOW_SNOWFLAKE_ENABLED",
                "FINFLOW_DB_BACKEND", "FINFLOW_DQ_MAX_REJECT_PCT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FINFLOW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FINFLOW_SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("FINFLOW_LOGS_DIR", str(tmp_path / "logs"))
    return Settings.from_env(load_dotenv_file=False)


@pytest.fixture
def batch1() -> Path:
    return SOURCE / "batch_01"


@pytest.fixture
def batch2() -> Path:
    return SOURCE / "batch_02"
