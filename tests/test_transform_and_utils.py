import pandas as pd
import pytest

from finflow import utils
from finflow.logging_utils import redact
from finflow.transform import apply_watermark, row_hash, watermark_cutoff
from finflow.utils import retry


def test_row_hash_stable_and_sensitive():
    assert row_hash(["a", None, "1"]) == row_hash(["a", None, "1"])
    assert row_hash(["a", None, "1"]) != row_hash(["a", "", "2"])


def test_watermark_cutoff_applies_lookback():
    assert watermark_cutoff("2025-06-30 12:00:00", 24) == "2025-06-29 12:00:00"
    assert watermark_cutoff(None, 24) is None


def test_watermark_skips_old_known_keys_only():
    df = pd.DataFrame({"id": ["a", "b", "c"], "updated_at": ["2025-01-01 00:00:00"] * 2 + ["2025-07-01 00:00:00"]})
    kept, skipped = apply_watermark(df, "2025-06-01 00:00:00", "id", {"a"})
    assert sorted(kept["id"]) == ["b", "c"] and skipped == 1  # 'b' is old but unknown -> must be kept


def test_retry_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(utils, "_sleep", lambda s: None)
    calls = {"n": 0}

    @retry(attempts=3, base_delay=0, exceptions=(ValueError,))
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok" and calls["n"] == 3


def test_retry_gives_up(monkeypatch):
    monkeypatch.setattr(utils, "_sleep", lambda s: None)

    @retry(attempts=2, base_delay=0, exceptions=(ValueError,))
    def always():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        always()


def test_redaction():
    assert "s3cret" not in redact("mysql+pymysql://user:s3cret@host/db")
    assert "abc123" not in redact("connect password=abc123 now")
