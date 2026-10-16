"""Small shared helpers."""

from __future__ import annotations

import functools
import hashlib
import logging
import math
import secrets
import time
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

T = TypeVar("T")

# Indirection so tests can disable real sleeping.
_sleep = time.sleep

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def fmt_ts(value: datetime) -> str:
    return value.strftime(TS_FORMAT)


def new_load_id() -> str:
    """Sortable, unique load identifier, e.g. 20260101T020000Z-3fa9c2d1."""
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def chunked(items: list[T], size: int) -> Iterator[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def to_records(df: pd.DataFrame, columns: Iterable[str]) -> list[dict[str, Any]]:
    """DataFrame -> list of dicts with NaN/NA converted to None (DB-API friendly)."""
    cols = list(columns)
    out: list[dict[str, Any]] = []
    for row in df[cols].astype(object).itertuples(index=False, name=None):
        out.append({c: (None if is_missing(v) else v) for c, v in zip(cols, row, strict=True)})
    return out


def retry(
    attempts: int = 3,
    base_delay: float = 1.0,
    factor: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    logger: logging.Logger | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Exponential-backoff retry decorator for transient failures."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt >= attempts:
                        raise
                    if logger:
                        logger.warning(
                            "transient failure, will retry",
                            extra={
                                "function": fn.__name__,
                                "attempt": attempt,
                                "max_attempts": attempts,
                                "retry_in_s": delay,
                                "error": str(exc)[:300],
                            },
                        )
                    _sleep(delay)
                    delay *= factor
            raise AssertionError("unreachable")  # pragma: no cover

        return wrapper

    return decorator
