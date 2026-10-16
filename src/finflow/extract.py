"""Extract step: discover source files, snapshot into the immutable raw layer, read as strings."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .errors import SchemaError, SourceFileError
from .logging_utils import get_logger
from .schemas import Entity
from .utils import sha256_file

log = get_logger("extract")


@dataclass
class SourceFile:
    entity: str
    original_path: Path
    raw_path: Path
    sha256: str
    size_bytes: int


def discover(source_dir: Path, entities: tuple[Entity, ...]) -> dict[str, Path]:
    if not source_dir.is_dir():
        raise SourceFileError(f"Source directory not found: {source_dir}")
    found: dict[str, Path] = {}
    missing: list[str] = []
    for spec in entities:
        path = source_dir / spec.file_name
        if path.is_file():
            found[spec.name] = path
        else:
            missing.append(spec.file_name)
    if missing:
        raise SourceFileError(f"Missing source files in {source_dir}: {', '.join(missing)}")
    return found


def snapshot_to_raw(files: dict[str, Path], raw_dir: Path, load_id: str) -> dict[str, SourceFile]:
    """Copy source files into raw/<load_id>/ (never modified afterwards) and verify checksums."""
    target_dir = raw_dir / load_id
    target_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, SourceFile] = {}
    for entity, path in files.items():
        digest = sha256_file(path)
        dest = target_dir / path.name
        shutil.copy2(path, dest)
        if sha256_file(dest) != digest:
            raise SourceFileError(f"Checksum mismatch after copying {path} to raw layer")
        out[entity] = SourceFile(entity, path, dest, digest, dest.stat().st_size)
        log.info("snapshotted to raw", extra={"entity": entity, "sha256": digest[:12]})
    return out


def read_source(path: Path, spec: Entity) -> tuple[pd.DataFrame, list[str]]:
    """Read a CSV as strings and enforce the file-level schema.

    Returns (frame with business columns + _row_number, unexpected_columns).
    Missing required columns -> SchemaError (whole load fails, nothing is committed).
    """
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as exc:
        raise SchemaError(f"{path.name}: unreadable or malformed CSV ({exc})") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    if df.columns.duplicated().any():
        raise SchemaError(f"{path.name}: duplicate column names in header")
    missing = [c for c in spec.column_names if c not in df.columns]
    if missing:
        raise SchemaError(f"{path.name}: missing required column(s): {', '.join(missing)}")
    extra = [c for c in df.columns if c not in spec.column_names]
    if extra:
        log.warning("unexpected columns ignored", extra={"entity": spec.name, "columns": extra})
    df = df[spec.column_names].copy()
    df["_row_number"] = range(2, len(df) + 2)  # 1-based file line, header is line 1
    return df, extra
