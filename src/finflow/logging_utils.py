"""Structured (JSON-lines) logging with automatic secret redaction and load_id context."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

load_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("load_id", default="-")

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
_URL_CREDS = re.compile(r"(://[^:/@\s]+):([^@\s]+)@")
_KV_SECRET = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|accountkey|sharedaccesssignature|sig)\s*[=:]\s*[^\s;,'\"]+"
)


def redact(text: str) -> str:
    """Remove credentials from URLs and key=value pairs."""
    text = _URL_CREDS.sub(r"\1:***@", text)
    return _KV_SECRET.sub(lambda m: f"{m.group(1)}=***", text)


def set_load_id(load_id: str) -> None:
    load_id_var.set(load_id)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "load_id": load_id_var.get(),
            "msg": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = redact(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(logs_dir: Path | None = None, level: str = "INFO") -> None:
    """Idempotent: reconfigures the 'finflow' logger tree."""
    import time

    root = logging.getLogger("finflow")
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    formatter = JsonFormatter()
    formatter.converter = time.gmtime
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    root.addHandler(stream)
    if logs_dir is not None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            logs_dir / "finflow.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"finflow.{name}")
