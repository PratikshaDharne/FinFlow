from datetime import datetime

import pandas as pd

from finflow.quality import References, validate_entity
from finflow.schemas import ACCOUNTS, CUSTOMERS, TRANSACTIONS

NOW = datetime(2026, 1, 1)


def _frame(rows, spec):
    df = pd.DataFrame(rows, columns=spec.column_names).astype(object)
    df["_row_number"] = range(2, len(df) + 2)
    return df


def _cust(**over):
    base = dict(customer_id="C000001", first_name="Ann", last_name="Lee", email="ann@example.com",
                phone="+14155550123", date_of_birth="1990-05-17", country="US", segment="RETAIL",
                kyc_status="VERIFIED", created_at="2025-01-01 10:00:00", updated_at="2025-01-02 10:00:00")
    base.update(over)
    return [base[c] for c in CUSTOMERS.column_names]


def _codes(result):
    return set(";".join(result.rejected["rule_codes"]).split(";")) if len(result.rejected) else set()


def test_valid_row_passes_and_is_standardised():
    df = _frame([_cust(email="  ANN@Example.COM ", country="us", phone="+1 (415) 555-0123")], CUSTOMERS)
    res = validate_entity(df, CUSTOMERS, References(), NOW)
    assert len(res.valid) == 1 and res.rejected_rows == 0
    row = res.valid.iloc[0]
    assert row["email"] == "ann@example.com" and row["country"] == "US" and row["phone"] == "+14155550123"


def test_missing_required_and_invalid_formats():
    rows = [_cust(customer_id="C000002", email=""), _cust(customer_id="C000003", email="bad@@x"),
            _cust(customer_id="C000004", date_of_birth="31/02/1990"),
            _cust(customer_id="C000005", date_of_birth="1990-02-30"),
            _cust(customer_id="C000006", date_of_birth="2099-01-01"),
            _cust(customer_id="C000007", segment="VIP"), _cust(customer_id="BAD")]
    res = validate_entity(_frame(rows, CUSTOMERS), CUSTOMERS, References(), NOW)
    assert len(res.valid) == 0
    codes = _codes(res)
    assert {"MISSING_VALUE:email", "INVALID_FORMAT:email", "INVALID_DATE:date_of_birth",
            "DATE_OUT_OF_RANGE:date_of_birth", "INVALID_ENUM:segment", "INVALID_FORMAT:customer_id"} <= codes


def test_updated_before_created():
    res = validate_entity(_frame([_cust(updated_at="2024-01-01 00:00:00")], CUSTOMERS), CUSTOMERS,
                          References(), NOW)
    assert "UPDATED_BEFORE_CREATED:updated_at" in _codes(res)


def test_duplicate_exact_and_key_supersede():
    a = _cust()
    b = _cust(first_name="Bea", updated_at="2025-02-01 00:00:00")
    res = validate_entity(_frame([a, a, b], CUSTOMERS), CUSTOMERS, References(), NOW)
    assert len(res.valid) == 1 and res.valid.iloc[0]["first_name"] == "Bea"  # latest wins
    assert _codes(res) == {"DUPLICATE_ROW:customer_id", "DUPLICATE_KEY:customer_id"} or len(res.rejected) == 2


def test_pii_masked_in_reject_record():
    res = validate_entity(_frame([_cust(segment="VIP")], CUSTOMERS), CUSTOMERS, References(), NOW)
    raw = res.rejected.iloc[0]["raw_record"]
    assert "ann@example.com" not in raw and "a***" in raw
    unmasked = validate_entity(_frame([_cust(segment="VIP")], CUSTOMERS), CUSTOMERS, References(), NOW,
                               mask_pii=False)
    assert "ann@example.com" in unmasked.rejected.iloc[0]["raw_record"]


def _acct(**over):
    base = dict(account_id="A0000001", customer_id="C000001", account_type="CHECKING", currency="USD",
                opened_date="2024-01-01", status="ACTIVE", credit_limit="", updated_at="2025-01-01 00:00:00")
    base.update(over)
    return [base[c] for c in ACCOUNTS.column_names]


def test_foreign_key_and_negative_limit():
    refs = References(keys={"customers": {"C000001"}})
    rows = [_acct(), _acct(account_id="A0000002", customer_id="C999999"),
            _acct(account_id="A0000003", credit_limit="-5")]
    res = validate_entity(_frame(rows, ACCOUNTS), ACCOUNTS, refs, NOW)
    assert list(res.valid["account_id"]) == ["A0000001"]
    assert {"FK_VIOLATION:customer_id", "NEGATIVE_VALUE:credit_limit"} <= _codes(res)


def _txn(**over):
    base = dict(transaction_id="T000000001", account_id="A0000001", transaction_ts="2025-03-01 12:00:00",
                amount="10.50", currency="USD", txn_type="DEBIT", channel="POS", merchant_category="",
                status="POSTED", updated_at="2025-03-01 12:05:00")
    base.update(over)
    return [base[c] for c in TRANSACTIONS.column_names]


def test_amount_rules_and_currency_mismatch():
    refs = References(keys={"accounts": {"A0000001"}}, account_currency={"A0000001": "USD"})
    rows = [_txn(), _txn(transaction_id="T000000002", amount="-1"), _txn(transaction_id="T000000003", amount="0"),
            _txn(transaction_id="T000000004", amount="N/A"), _txn(transaction_id="T000000005", amount="1.234"),
            _txn(transaction_id="T000000006", currency="EUR"),
            _txn(transaction_id="T000000007", transaction_ts="2025-13-45 10:00:00")]
    res = validate_entity(_frame(rows, TRANSACTIONS), TRANSACTIONS, refs, NOW)
    assert list(res.valid["transaction_id"]) == ["T000000001"]
    codes = _codes(res)
    assert {"NON_POSITIVE_AMOUNT:amount", "INVALID_NUMBER:amount", "CURRENCY_MISMATCH:currency",
            "INVALID_TIMESTAMP:transaction_ts"} <= codes
    assert res.valid.iloc[0]["amount"] == "10.50"


def test_row_counts_add_up():
    refs = References(keys={"accounts": {"A0000001"}}, account_currency={"A0000001": "USD"})
    rows = [_txn(), _txn(transaction_id="T000000002", amount="x"), _txn()]
    res = validate_entity(_frame(rows, TRANSACTIONS), TRANSACTIONS, refs, NOW)
    assert res.source_rows == len(res.valid) + res.rejected_rows == 3
