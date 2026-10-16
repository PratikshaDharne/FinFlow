"""Write rejected-record, data-quality, reconciliation and run-summary reports."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def write_reports(ctx, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    rejected = [v.rejected for v in ctx.validations.values() if not v.rejected.empty]
    rej_cols = ["load_id", "entity", "source_file", "source_row_number", "record_key",
                "rule_codes", "messages", "raw_record"]
    if rejected:
        rej = pd.concat(rejected, ignore_index=True)
        rej.insert(0, "load_id", ctx.load_id)
        rej.insert(2, "source_file", rej["entity"].map(lambda e: f"{e}.csv"))
        rej = rej[rej_cols]
    else:
        rej = pd.DataFrame(columns=rej_cols)
    rej.to_csv(out_dir / "rejected_records.csv", index=False)

    dq = pd.DataFrame(
        [vars(s) for v in ctx.validations.values() for s in v.rule_stats],
        columns=["entity", "rule_code", "severity", "failed_rows", "checked_rows"],
    )
    dq.to_csv(out_dir / "dq_summary.csv", index=False)

    ent = pd.DataFrame([vars(o) for o in ctx.outcomes.values()])
    ent.to_csv(out_dir / "entity_summary.csv", index=False)

    recon = pd.DataFrame([c.as_record() for c in ctx.recon],
                         columns=["entity", "check_name", "source_value", "target_value", "difference", "status"])
    recon.to_csv(out_dir / "reconciliation.csv", index=False)

    summary = ctx.summary()
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "run_report.md").write_text(_markdown(summary, ent, recon, dq), encoding="utf-8")
    return out_dir


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    header = "| " + " | ".join(map(str, df.columns)) + " |\n"
    sep = "|" + "|".join("---" for _ in df.columns) + "|\n"
    body = "".join("| " + " | ".join(str(v) for v in row) + " |\n" for row in df.itertuples(index=False))
    return header + sep + body


def _markdown(summary: dict, ent: pd.DataFrame, recon: pd.DataFrame, dq: pd.DataFrame) -> str:
    failed = recon[recon["status"] == "FAIL"] if not recon.empty else recon
    cols = ["entity", "source_rows", "rejected_rows", "skipped_watermark", "staged_rows",
            "inserted", "updated", "unchanged", "skipped_duplicate_file"]
    ent_view = ent[[c for c in cols if c in ent.columns]] if not ent.empty else ent
    dq_view = dq.sort_values("failed_rows", ascending=False).head(25) if not dq.empty else dq
    return (
        f"# FinFlow run report\n\n- **Load ID:** `{summary['load_id']}`\n- **Status:** {summary['status']}"
        f"{' (dry run - nothing committed)' if summary['dry_run'] else ''}\n"
        f"- **Started / finished (UTC):** {summary['started_at']} / {summary['finished_at']}\n"
        f"- **Azure staging:** {summary['azure_status']} | **Snowflake:** {summary['snowflake_status']}\n"
        f"- **Reconciliation:** {summary['recon_passed']} passed, {summary['recon_failed']} failed\n"
        + (f"- **Error:** {summary['error']}\n" if summary.get("error") else "")
        + f"\n## Row disposition per entity\n\n{_table(ent_view)}\n"
        f"## Failed reconciliation checks\n\n{_table(failed)}\n"
        f"## Top data-quality rule failures\n\n{_table(dq_view)}\n"
    )
