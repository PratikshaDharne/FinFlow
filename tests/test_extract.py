import shutil

import pytest

from finflow.errors import SchemaError, SourceFileError
from finflow.extract import discover, read_source, snapshot_to_raw
from finflow.schemas import CUSTOMERS, ENTITIES


def test_discover_missing_file(tmp_path):
    with pytest.raises(SourceFileError):
        discover(tmp_path, ENTITIES)


def test_snapshot_copies_and_checksums(batch1, tmp_path):
    files = discover(batch1, ENTITIES)
    out = snapshot_to_raw(files, tmp_path / "raw", "L1")
    assert out["customers"].raw_path.exists() and len(out["customers"].sha256) == 64


def test_missing_required_column_is_schema_error(tmp_path):
    (tmp_path / "customers.csv").write_text("customer_id,first_name\nC000001,Ann\n")
    with pytest.raises(SchemaError, match="missing required column"):
        read_source(tmp_path / "customers.csv", CUSTOMERS)


def test_extra_columns_dropped_with_warning(batch2):
    df, extra = read_source(batch2 / "customers.csv", CUSTOMERS)
    assert extra == ["legacy_flag"] and "legacy_flag" not in df.columns and "_row_number" in df.columns


def test_malformed_csv(tmp_path):
    (tmp_path / "customers.csv").write_text("")
    with pytest.raises(SchemaError):
        read_source(tmp_path / "customers.csv", CUSTOMERS)
    shutil.rmtree(tmp_path, ignore_errors=True)
