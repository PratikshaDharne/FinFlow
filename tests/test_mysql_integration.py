"""Runs only when a real MySQL 8.0 is available: set FINFLOW_TEST_MYSQL_URL, e.g.
mysql+pymysql://finflow_deploy:<pw>@localhost:3306/finflow_test  (an empty scratch database!)."""
import os

import pytest

URL = os.environ.get("FINFLOW_TEST_MYSQL_URL")


@pytest.mark.skipif(not URL, reason="FINFLOW_TEST_MYSQL_URL not set (MySQL integration not exercised)")
def test_pipeline_on_mysql(settings, batch1, batch2):
    from sqlalchemy import create_engine, text

    from finflow import db
    from finflow.pipeline import run_pipeline

    engine = create_engine(URL)
    db.init_schema(engine, settings.sql_dir)
    r1 = run_pipeline(settings, batch1, engine=engine)
    r2 = run_pipeline(settings, batch2, engine=engine)
    assert r1.status == "SUCCESS" and r2.status == "SUCCESS"
    assert all(c.status == "PASS" for c in r1.recon + r2.recon)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar() > 0
