import sqlite3

import pytest

from finflow import db
from finflow.errors import DataQualityError, SchemaError
from finflow.pipeline import run_pipeline


def _count(settings, table):
    with sqlite3.connect(settings.sqlite_path) as c:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_full_and_incremental_load(settings, batch1, batch2):
    r1 = run_pipeline(settings, batch1)
    assert r1.status == "SUCCESS" and all(c.status == "PASS" for c in r1.recon)
    base = {t: _count(settings, t) for t in ("customers", "accounts", "transactions", "payments")}
    assert all(v > 0 for v in base.values())
    for o in r1.outcomes.values():  # row disposition identity
        assert o.source_rows == o.rejected_rows + o.skipped_watermark + o.staged_rows
        assert o.inserted == o.staged_rows

    r2 = run_pipeline(settings, batch2)
    assert r2.status == "SUCCESS" and all(c.status == "PASS" for c in r2.recon)
    assert r2.outcomes["customers"].updated > 0 and r2.outcomes["transactions"].inserted > 0
    assert r2.outcomes["transactions"].skipped_watermark > 0
    assert _count(settings, "transactions") == base["transactions"] + r2.outcomes["transactions"].inserted
    assert _count(settings, "etl_rejected_records") > 0


def test_rerun_is_noop_and_forced_rerun_changes_nothing(settings, batch1):
    run_pipeline(settings, batch1)
    before = _count(settings, "transactions")
    again = run_pipeline(settings, batch1)
    assert again.status == "SKIPPED" and _count(settings, "transactions") == before
    forced = run_pipeline(settings, batch1, force=True)
    assert forced.status == "SUCCESS"
    assert all(o.inserted == 0 and o.updated == 0 for o in forced.outcomes.values())
    assert _count(settings, "transactions") == before


def test_dry_run_commits_nothing(settings, batch1):
    ctx = run_pipeline(settings, batch1, dry_run=True)
    assert ctx.status == "DRY_RUN" and _count(settings, "customers") == 0
    assert _count(settings, "etl_file_registry") == 0


def test_reports_are_written(settings, batch1):
    ctx = run_pipeline(settings, batch1)
    for name in ("rejected_records.csv", "dq_summary.csv", "reconciliation.csv", "run_summary.json", "run_report.md"):
        assert (ctx.reports_dir / name).exists()


def test_reject_threshold_aborts_and_rolls_back(settings, batch1, monkeypatch):
    monkeypatch.setenv("FINFLOW_DQ_MAX_REJECT_PCT", "0.5")
    from finflow.config import Settings

    strict = Settings.from_env(load_dotenv_file=False)
    with pytest.raises(DataQualityError):
        run_pipeline(strict, batch1)
    assert _count(strict, "customers") == 0
    with sqlite3.connect(strict.sqlite_path) as c:
        assert c.execute("SELECT status FROM etl_load_audit").fetchone()[0] == "FAILED"


def test_schema_violation_fails_load(settings, tmp_path, batch1):
    import shutil

    bad = tmp_path / "bad"
    shutil.copytree(batch1, bad)
    (bad / "accounts.csv").write_text("account_id,customer_id\nA0000001,C000001\n")
    with pytest.raises(SchemaError):
        run_pipeline(settings, bad)
    assert _count(settings, "customers") == 0


def test_failure_mid_transaction_rolls_back(settings, batch1, monkeypatch):
    calls = {"n": 0}
    original = db.merge_to_curated

    def exploding(conn, spec, load_id, now):
        calls["n"] += 1
        if spec.name == "transactions":
            raise RuntimeError("simulated crash after customers+accounts were merged")
        original(conn, spec, load_id, now)

    monkeypatch.setattr(db, "merge_to_curated", exploding)
    with pytest.raises(RuntimeError):
        run_pipeline(settings, batch1)
    assert calls["n"] == 3
    assert _count(settings, "customers") == 0 and _count(settings, "accounts") == 0  # atomic rollback
    assert _count(settings, "etl_file_registry") == 0  # so a rerun is allowed


def test_reconciliation_failure_rolls_back(settings, batch1, monkeypatch):
    from finflow import pipeline

    real = pipeline.reconcile_entity

    def corrupt(*a, **k):
        checks = real(*a, **k)
        checks[0].target_value += 1  # pretend a row went missing
        return checks

    monkeypatch.setattr(pipeline, "reconcile_entity", corrupt)
    from finflow.errors import ReconciliationError

    with pytest.raises(ReconciliationError):
        run_pipeline(settings, batch1)
    assert _count(settings, "customers") == 0
    assert _count(settings, "etl_reconciliation") > 0  # failure evidence kept for diagnosis


def test_curated_has_no_orphans_or_dupes(settings, batch1, batch2):
    run_pipeline(settings, batch1)
    run_pipeline(settings, batch2)
    with sqlite3.connect(settings.sqlite_path) as c:
        assert c.execute("SELECT COUNT(*) FROM transactions t LEFT JOIN accounts a USING (account_id) "
                         "WHERE a.account_id IS NULL").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM (SELECT customer_id FROM customers GROUP BY 1 HAVING COUNT(*)>1)"
                         ).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM transactions WHERE amount <= 0").fetchone()[0] == 0
