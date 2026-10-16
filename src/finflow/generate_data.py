"""Deterministic synthetic data generator (no real personal data; all emails use example.com).

Produces two batches under <out>/:
  batch_01/  initial load (customers, accounts, transactions, payments)
  batch_02/  incremental load: new rows, updated rows, replays of old rows, plus an extra column
Both batches deliberately contain defects so every data-quality rule has something to catch.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FIRST = ["Aarav", "Maya", "Liam", "Olivia", "Noah", "Emma", "Sofia", "Arjun", "Priya", "Lucas",
         "Mia", "Ethan", "Zara", "Kabir", "Isla", "Omar", "Chloe", "Ravi", "Hannah", "Diego"]
LAST = ["Sharma", "Patel", "Smith", "Johnson", "Garcia", "Muller", "Dubois", "Tan", "Khan", "Rossi",
        "Brown", "Singh", "Nair", "Lopez", "Wilson", "Kumar", "Ali", "Chen", "Davies", "Iyer"]
COUNTRIES = ["US", "GB", "IN", "DE", "FR", "SG", "AE", "CA", "AU"]
CURRENCIES = ["USD", "EUR", "GBP", "INR"]
CATEGORIES = ["GROCERY", "FUEL", "TRAVEL", "DINING", "UTILITIES", "RETAIL", "HEALTH", "SALARY", ""]
TS = "%Y-%m-%d %H:%M:%S"

B1_START, B1_END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-06-30 23:59:59")
B2_START, B2_END = pd.Timestamp("2025-07-01"), pd.Timestamp("2025-07-31 23:59:59")


def _rand_ts(rng, start, end, n):
    span = int((end - start).total_seconds())
    return [start + pd.Timedelta(seconds=int(s)) for s in rng.integers(0, span, n)]


def _fmt(series):
    return [t.strftime(TS) for t in series]


def _customers(rng, first_id, n, start, end):
    rows = []
    for i in range(n):
        first, last = FIRST[rng.integers(len(FIRST))], LAST[rng.integers(len(LAST))]
        cid = first_id + i
        created = _rand_ts(rng, start, end - pd.Timedelta(days=1), 1)[0]
        rows.append({
            "customer_id": f"C{cid:06d}", "first_name": first, "last_name": last,
            "email": f"{first}.{last}{cid}@example.com".lower(),
            "phone": f"+{rng.integers(1, 99)}{rng.integers(10**8, 10**9 - 1)}",
            "date_of_birth": (pd.Timestamp("1950-01-01") + pd.Timedelta(days=int(rng.integers(0, 20000)))).strftime("%Y-%m-%d"),
            "country": COUNTRIES[rng.integers(len(COUNTRIES))],
            "segment": rng.choice(["RETAIL", "SME", "CORPORATE"], p=[0.7, 0.2, 0.1]),
            "kyc_status": rng.choice(["VERIFIED", "PENDING", "REJECTED"], p=[0.85, 0.12, 0.03]),
            "created_at": created.strftime(TS),
            "updated_at": min(created + pd.Timedelta(hours=int(rng.integers(0, 2000))), end).strftime(TS),
        })
    return pd.DataFrame(rows)


def _accounts(rng, first_id, n, customer_ids, start, end):
    rows = []
    for i in range(n):
        opened = _rand_ts(rng, start, end - pd.Timedelta(days=1), 1)[0]
        atype = rng.choice(["CHECKING", "SAVINGS", "CREDIT", "LOAN"], p=[0.4, 0.3, 0.2, 0.1])
        rows.append({
            "account_id": f"A{first_id + i:07d}", "customer_id": customer_ids[rng.integers(len(customer_ids))],
            "account_type": atype, "currency": rng.choice(CURRENCIES, p=[0.5, 0.2, 0.15, 0.15]),
            "opened_date": opened.strftime("%Y-%m-%d"), "status": rng.choice(["ACTIVE", "DORMANT", "CLOSED"], p=[0.85, 0.1, 0.05]),
            "credit_limit": f"{int(rng.integers(5, 50)) * 1000:.2f}" if atype == "CREDIT" else "",
            "updated_at": min(opened + pd.Timedelta(hours=int(rng.integers(1, 3000))), end).strftime(TS),
        })
    return pd.DataFrame(rows)


def _transactions(rng, first_id, n, accounts, start, end):
    rows = []
    for i in range(n):
        acc = accounts.iloc[rng.integers(len(accounts))]
        lo = max(start, pd.Timestamp(acc["opened_date"]))
        ts = _rand_ts(rng, lo, end, 1)[0] if lo < end else end
        amount = float(np.clip(rng.lognormal(4.2, 1.1), 0.5, 25000))
        rows.append({
            "transaction_id": f"T{first_id + i:09d}", "account_id": acc["account_id"],
            "transaction_ts": ts.strftime(TS), "amount": f"{amount:.2f}", "currency": acc["currency"],
            "txn_type": rng.choice(["CREDIT", "DEBIT"], p=[0.4, 0.6]),
            "channel": rng.choice(["ATM", "POS", "ONLINE", "BRANCH", "TRANSFER"]),
            "merchant_category": CATEGORIES[rng.integers(len(CATEGORIES))],
            "status": rng.choice(["POSTED", "PENDING", "REVERSED"], p=[0.92, 0.05, 0.03]),
            "updated_at": min(ts + pd.Timedelta(minutes=int(rng.integers(1, 600))), end).strftime(TS),
        })
    return pd.DataFrame(rows)


def _payments(rng, first_id, n, accounts, txns, start, end):
    by_acc = txns.groupby("account_id")["transaction_id"].apply(list).to_dict()
    rows = []
    for i in range(n):
        acc = accounts.iloc[rng.integers(len(accounts))]
        linked = by_acc.get(acc["account_id"], [])
        lo = max(start, pd.Timestamp(acc["opened_date"]))
        day = _rand_ts(rng, lo, end, 1)[0] if lo < end else end
        rows.append({
            "payment_id": f"P{first_id + i:08d}", "account_id": acc["account_id"],
            "transaction_id": linked[rng.integers(len(linked))] if linked and rng.random() < 0.6 else "",
            "payment_date": day.strftime("%Y-%m-%d"), "amount": f"{float(np.clip(rng.lognormal(5, 1), 1, 20000)):.2f}",
            "currency": acc["currency"], "method": rng.choice(["ACH", "WIRE", "CARD", "UPI", "CHEQUE"]),
            "status": rng.choice(["SETTLED", "FAILED", "PENDING"], p=[0.88, 0.05, 0.07]),
            "updated_at": min(day + pd.Timedelta(hours=int(rng.integers(1, 48))), end).strftime(TS),
        })
    return pd.DataFrame(rows)


def _pin_recent(df, ts_col_min, end, k=4):
    """Make the last k rows 'recent' so they fall inside the incremental look-back window."""
    df = df.copy()
    for j in range(1, k + 1):
        i = len(df) - j
        floor = pd.Timestamp(ts_col_min[i]) if ts_col_min is not None else B1_START
        df.loc[df.index[i], "updated_at"] = max(end - pd.Timedelta(hours=j), floor).strftime(TS)
    return df


def _bump(df, rng, idx_n, end, changes, start):
    """Return updated copies of random existing rows (new updated_at inside [start, end])."""
    pick = df.sample(n=min(idx_n, len(df)), random_state=int(rng.integers(1, 10**6))).copy()
    for col, fn in changes.items():
        pick[col] = [fn(v) for v in pick[col]]
    pick["updated_at"] = _fmt(_rand_ts(rng, start, end, len(pick)))
    return pick


def _inject(df, rng, defects):
    """defects: list of (count, fn(df,row_idx)->None) ; fn mutates df in place or appends rows."""
    df = df.copy().reset_index(drop=True)
    pool = list(rng.permutation(len(df)))
    extra = []
    for count, kind, col, value in defects:
        for _ in range(count):
            i = int(pool.pop())
            if kind == "set":
                df.at[i, col] = value
            elif kind == "dup_exact":
                extra.append(df.iloc[i].to_dict())
            elif kind == "dup_key":
                row = df.iloc[i].to_dict()
                row["updated_at"] = (pd.Timestamp(row["updated_at"]) + pd.Timedelta(hours=1)).strftime(TS)
                if col in row and row[col] != "":
                    row[col] = value
                extra.append(row)
    if extra:
        df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)
    return df


def _write(frames, folder):
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, df in frames.items():
        p = folder / f"{name}.csv"
        df.fillna("").to_csv(p, index=False)
        paths.append(p)
    return paths


def generate(out_dir: Path, seed: int = 42, scale: float = 1.0) -> list[Path]:
    rng = np.random.default_rng(seed)
    s = lambda n: max(5, int(n * scale))  # noqa: E731
    out_dir = Path(out_dir)

    # ------------------------------------------------------------- batch 1 (clean base)
    c1 = _customers(rng, 1, s(300), B1_START, B1_END)
    a1 = _accounts(rng, 1, s(450), list(c1.customer_id), B1_START, B1_END)
    t1 = _transactions(rng, 1, s(4000), a1, B1_START, B1_END)
    p1 = _payments(rng, 1, s(1200), a1, t1, B1_START, B1_END)
    c1 = _pin_recent(c1, c1["created_at"].tolist(), B1_END)
    a1 = _pin_recent(a1, a1["opened_date"].tolist(), B1_END)
    t1 = _pin_recent(t1, t1["transaction_ts"].tolist(), B1_END)
    p1 = _pin_recent(p1, p1["payment_date"].tolist(), B1_END)
    clean1 = {"customers": c1.copy(), "accounts": a1.copy(), "transactions": t1.copy(), "payments": p1.copy()}

    c1d = _inject(c1, rng, [
        (2, "set", "email", ""), (2, "set", "email", "not-an-email"), (2, "set", "date_of_birth", "31/02/1990"),
        (1, "set", "date_of_birth", "2099-01-01"), (1, "set", "segment", "VIP"), (1, "set", "customer_id", ""),
        (1, "set", "country", "XX"), (2, "dup_exact", "", ""), (2, "dup_key", "first_name", "Changed"),
    ])
    a1d = _inject(a1, rng, [
        (3, "set", "customer_id", "C999999"), (1, "set", "currency", "XYZ"), (1, "set", "credit_limit", "-500.00"),
        (2, "set", "opened_date", "not-a-date"), (1, "set", "account_id", ""), (2, "dup_exact", "", ""),
        (2, "dup_key", "status", "CLOSED"),
    ])
    t1d = _inject(t1, rng, [
        (5, "set", "account_id", "A9999999"), (3, "set", "amount", "-45.10"), (3, "set", "amount", "N/A"),
        (2, "set", "amount", "0.00"), (1, "set", "amount", "12.345"), (2, "set", "transaction_ts", "2099-01-01 10:00:00"),
        (2, "set", "txn_type", "WITHDRAW"), (3, "set", "currency", "JPY"), (2, "set", "transaction_ts", "2025-13-45 10:00:00"),
        (2, "set", "account_id", ""), (4, "dup_exact", "", ""), (2, "dup_key", "amount", "99.99"),
    ])
    p1d = _inject(p1, rng, [
        (3, "set", "account_id", "A9999999"), (2, "set", "method", "BARTER"), (2, "set", "amount", "-10.00"),
        (2, "set", "transaction_id", "T999999999"), (2, "set", "payment_date", ""), (2, "dup_exact", "", ""),
    ])
    paths = _write({"customers": c1d, "accounts": a1d, "transactions": t1d, "payments": p1d}, out_dir / "batch_01")

    # ------------------------------------------------------------- batch 2 (incremental)
    c2_new = _customers(rng, len(c1) + 1, s(60), B2_START, B2_END)
    c2_upd = _bump(clean1["customers"], rng, s(40), B2_END, {
        "email": lambda v: v.replace("@example.com", ".work@example.com"),
        "kyc_status": lambda v: "VERIFIED"}, B2_START)
    all_c = list(clean1["customers"].customer_id) + list(c2_new.customer_id)
    a2_new = _accounts(rng, len(a1) + 1, s(90), all_c, B2_START, B2_END)
    a2_upd = _bump(clean1["accounts"], rng, s(25), B2_END, {"status": lambda v: "DORMANT"}, B2_START)
    all_a = pd.concat([clean1["accounts"], a2_new], ignore_index=True)
    t2_new = _transactions(rng, len(t1) + 1, s(1200), all_a, B2_START, B2_END)
    t2_upd = _bump(clean1["transactions"], rng, s(30), B2_END, {"status": lambda v: "POSTED"}, B2_START)
    p2_new = _payments(rng, len(p1) + 1, s(300), all_a, pd.concat([clean1["transactions"], t2_new]), B2_START, B2_END)
    p2_upd = _bump(clean1["payments"], rng, s(20), B2_END, {"status": lambda v: "SETTLED"}, B2_START)

    def replay(df):  # unchanged rows re-sent by the source: last 4 (inside look-back) + 15 old ones
        return pd.concat([df.tail(4), df.head(15)])

    def build(replayed, upd, new):
        return pd.concat([replayed, upd, new], ignore_index=True)

    c2 = build(replay(clean1["customers"]), c2_upd, c2_new)
    a2 = build(replay(clean1["accounts"]), a2_upd, a2_new)
    t2 = build(replay(clean1["transactions"]), t2_upd, t2_new)
    p2 = build(replay(clean1["payments"]), p2_upd, p2_new)

    c2 = _inject(c2, rng, [(1, "set", "email", "broken@@example"), (1, "set", "date_of_birth", "1990-02-30")])
    c2["legacy_flag"] = "Y"  # schema drift: unexpected extra column -> warning, column ignored
    a2 = _inject(a2, rng, [(2, "set", "customer_id", "C999998")])
    t2 = _inject(t2, rng, [(3, "set", "account_id", "A9999998"), (2, "set", "amount", "abc"),
                           (2, "set", "txn_type", "SWAP"), (2, "dup_exact", "", "")])
    p2 = _inject(p2, rng, [(2, "set", "method", "BARTER"), (1, "set", "transaction_id", "T999999998")])
    paths += _write({"customers": c2, "accounts": a2, "transactions": t2, "payments": p2}, out_dir / "batch_02")
    return paths
