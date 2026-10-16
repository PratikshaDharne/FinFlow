"""Command line interface:  finflow <command>   (or: python -m finflow.cli <command>)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Settings
from .errors import FinFlowError
from .logging_utils import configure_logging, get_logger

log = get_logger("cli")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finflow", description="FinFlow financial data pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate-data", help="create synthetic source CSVs (batch_01, batch_02)")
    g.add_argument("--out", type=Path, default=None, help="output folder (default data/source)")
    g.add_argument("--seed", type=int, default=42)

    sub.add_parser("init-db", help="create schemas/tables (idempotent)")

    r = sub.add_parser("run", help="run the ETL pipeline for one source folder")
    r.add_argument("--source", type=Path, required=True, help="folder with the four CSV files")
    r.add_argument("--force", action="store_true", help="reprocess files even if already loaded")
    r.add_argument("--dry-run", action="store_true", help="do everything, then roll back")
    r.add_argument("--full-refresh", action="store_true", help="ignore the incremental watermark")
    r.add_argument("--azure", action="store_true", help="upload raw files to Azure Blob (untested)")
    r.add_argument("--snowflake", action="store_true", help="sync changed rows to Snowflake (untested)")

    sub.add_parser("status", help="show the most recent loads")
    s = sub.add_parser("sync-snowflake", help="re-send a committed load to Snowflake (untested)")
    s.add_argument("--load-id", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        configure_logging(settings.logs_dir, settings.log_level)
        return _dispatch(args, settings)
    except FinFlowError as exc:
        log.error("command failed", extra={"error": str(exc), "exit_code": exc.exit_code})
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


def _dispatch(args: argparse.Namespace, settings: Settings) -> int:
    from . import db
    from .generate_data import generate

    if args.command == "generate-data":
        out = args.out or settings.data_dir / "source"
        paths = generate(out, seed=args.seed)
        print("Generated:", *[str(p) for p in paths], sep="\n  ")
        return 0
    if args.command == "init-db":
        db.init_schema(db.make_engine(settings), settings.sql_dir)
        print(f"Schema ready ({settings.safe_database_url()})")
        return 0
    if args.command == "run":
        from .pipeline import run_pipeline

        ctx = run_pipeline(settings, args.source, force=args.force, dry_run=args.dry_run,
                           full_refresh=args.full_refresh, upload_azure=args.azure or None,
                           load_snowflake=args.snowflake or None)
        print(f"Load {ctx.load_id}: {ctx.status}")
        for o in ctx.outcomes.values():
            print(f"  {o.entity:<13} source={o.source_rows:<5} rejected={o.rejected_rows:<4} "
                  f"skipped_by_watermark={o.skipped_watermark:<4} inserted={o.inserted:<5} "
                  f"updated={o.updated:<4} unchanged={o.unchanged:<4}"
                  f"{' (file already loaded)' if o.skipped_duplicate_file else ''}")
        print(f"  reconciliation: {sum(c.status == 'PASS' for c in ctx.recon)} passed, "
              f"{sum(c.status == 'FAIL' for c in ctx.recon)} failed")
        print(f"  reports: {ctx.reports_dir}")
        return 0
    if args.command == "status":
        from sqlalchemy import text

        with db.make_engine(settings).connect() as conn:
            rows = conn.execute(text(
                "SELECT load_id, status, started_at, finished_at, azure_status, snowflake_status "
                "FROM etl_load_audit ORDER BY started_at DESC LIMIT 10")).fetchall()
        for row in rows:
            print(" | ".join(str(c) for c in row))
        return 0
    if args.command == "sync-snowflake":
        from .pipeline import sync_snowflake_for_latest

        print("Synced load", sync_snowflake_for_latest(settings, args.load_id))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
