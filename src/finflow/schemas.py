"""Single source of truth for entity schemas, validation rules and source-to-target mapping.

Quality rules, staging/merge SQL builders, Snowflake SQL generation and the data
dictionary all derive from the definitions below.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

COUNTRIES = ("US", "GB", "IN", "DE", "FR", "SG", "AE", "CA", "AU")
CURRENCIES = ("USD", "EUR", "GBP", "INR")

AUDIT_COLUMNS = (
    "row_hash",
    "source_file",
    "created_load_id",
    "updated_load_id",
    "etl_created_at",
    "etl_updated_at",
)
STAGING_EXTRA_COLUMNS = ("load_id", "row_hash", "source_file", "source_row_number", "staged_at")


@dataclass(frozen=True)
class Col:
    name: str
    kind: str = "str"  # str | enum | date | datetime | decimal
    required: bool = True
    max_len: int | None = None
    pattern: str | None = None
    enum: tuple[str, ...] = ()
    case: str | None = None  # upper | lower
    strip_chars: str = ""
    min_value: Decimal | None = None
    min_inclusive: bool = True
    max_value: Decimal | None = None
    min_date: str | None = None
    pii: bool = False
    description: str = ""

    @property
    def snowflake_type(self) -> str:
        if self.kind == "date":
            return "DATE"
        if self.kind == "datetime":
            return "TIMESTAMP_NTZ"
        if self.kind == "decimal":
            return "NUMBER(18,2)"
        length = self.max_len or max((len(v) for v in self.enum), default=255)
        return f"VARCHAR({length})"


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_entity: str
    ref_column: str


@dataclass(frozen=True)
class Entity:
    name: str
    pk: str
    columns: tuple[Col, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    amount_column: str | None = None
    currency_column: str | None = None
    direction_column: str | None = None  # CREDIT/DEBIT column for net-flow reconciliation
    description: str = ""

    @property
    def table(self) -> str:
        return self.name

    @property
    def stg_table(self) -> str:
        return f"stg_{self.name}"

    @property
    def file_name(self) -> str:
        return f"{self.name}.csv"

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def col(self, name: str) -> Col:
        return next(c for c in self.columns if c.name == name)


_ID = lambda p, n: rf"^{p}\d{{{n}}}$"  # noqa: E731

CUSTOMERS = Entity(
    name="customers",
    pk="customer_id",
    description="Bank customers (KYC master data).",
    columns=(
        Col("customer_id", max_len=10, pattern=_ID("C", 6), description="Business key, C + 6 digits"),
        Col("first_name", max_len=50, pii=True),
        Col("last_name", max_len=50, pii=True),
        Col("email", max_len=120, pattern=r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$",
            case="lower", pii=True),
        Col("phone", required=False, max_len=20, pattern=r"^\+?\d{7,15}$", strip_chars=" -()", pii=True),
        Col("date_of_birth", kind="date", min_date="1900-01-01", pii=True),
        Col("country", kind="enum", enum=("US", "GB", "IN", "DE", "FR", "SG", "AE", "CA", "AU"),
            case="upper"),
        Col("segment", kind="enum", enum=("RETAIL", "SME", "CORPORATE"), case="upper"),
        Col("kyc_status", kind="enum", enum=("VERIFIED", "PENDING", "REJECTED"), case="upper"),
        Col("created_at", kind="datetime", min_date="2000-01-01"),
        Col("updated_at", kind="datetime", min_date="2000-01-01"),
    ),
)

ACCOUNTS = Entity(
    name="accounts",
    pk="account_id",
    description="Customer accounts.",
    foreign_keys=(ForeignKey("customer_id", "customers", "customer_id"),),
    currency_column="currency",
    columns=(
        Col("account_id", max_len=10, pattern=_ID("A", 7)),
        Col("customer_id", max_len=10, pattern=_ID("C", 6)),
        Col("account_type", kind="enum", enum=("CHECKING", "SAVINGS", "CREDIT", "LOAN"), case="upper"),
        Col("currency", kind="enum", enum=CURRENCIES, case="upper"),
        Col("opened_date", kind="date", min_date="1990-01-01"),
        Col("status", kind="enum", enum=("ACTIVE", "DORMANT", "CLOSED"), case="upper"),
        Col("credit_limit", kind="decimal", required=False, min_value=Decimal("0"),
            max_value=Decimal("1000000000")),
        Col("updated_at", kind="datetime", min_date="2000-01-01"),
    ),
)

TRANSACTIONS = Entity(
    name="transactions",
    pk="transaction_id",
    description="Account transactions (amounts are positive; txn_type gives direction).",
    foreign_keys=(ForeignKey("account_id", "accounts", "account_id"),),
    amount_column="amount",
    currency_column="currency",
    direction_column="txn_type",
    columns=(
        Col("transaction_id", max_len=12, pattern=_ID("T", 9)),
        Col("account_id", max_len=10, pattern=_ID("A", 7)),
        Col("transaction_ts", kind="datetime", min_date="2000-01-01"),
        Col("amount", kind="decimal", min_value=Decimal("0"), min_inclusive=False,
            max_value=Decimal("1000000000")),
        Col("currency", kind="enum", enum=CURRENCIES, case="upper"),
        Col("txn_type", kind="enum", enum=("CREDIT", "DEBIT"), case="upper"),
        Col("channel", kind="enum", enum=("ATM", "POS", "ONLINE", "BRANCH", "TRANSFER"), case="upper"),
        Col("merchant_category", required=False, max_len=40, case="upper"),
        Col("status", kind="enum", enum=("POSTED", "PENDING", "REVERSED"), case="upper"),
        Col("updated_at", kind="datetime", min_date="2000-01-01"),
    ),
)

PAYMENTS = Entity(
    name="payments",
    pk="payment_id",
    description="Payments made against accounts, optionally linked to a transaction.",
    foreign_keys=(
        ForeignKey("account_id", "accounts", "account_id"),
        ForeignKey("transaction_id", "transactions", "transaction_id"),
    ),
    amount_column="amount",
    currency_column="currency",
    columns=(
        Col("payment_id", max_len=12, pattern=_ID("P", 8)),
        Col("account_id", max_len=10, pattern=_ID("A", 7)),
        Col("transaction_id", required=False, max_len=12, pattern=_ID("T", 9)),
        Col("payment_date", kind="date", min_date="2000-01-01"),
        Col("amount", kind="decimal", min_value=Decimal("0"), min_inclusive=False,
            max_value=Decimal("1000000000")),
        Col("currency", kind="enum", enum=CURRENCIES, case="upper"),
        Col("method", kind="enum", enum=("ACH", "WIRE", "CARD", "UPI", "CHEQUE"), case="upper"),
        Col("status", kind="enum", enum=("SETTLED", "FAILED", "PENDING"), case="upper"),
        Col("updated_at", kind="datetime", min_date="2000-01-01"),
    ),
)

# Dependency order: parents before children.
ENTITIES: tuple[Entity, ...] = (CUSTOMERS, ACCOUNTS, TRANSACTIONS, PAYMENTS)
ENTITY_BY_NAME = {e.name: e for e in ENTITIES}
WATERMARK_COLUMN = "updated_at"
