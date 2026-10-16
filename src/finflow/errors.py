"""Exception hierarchy. Each maps to a CLI exit code (see cli.py)."""


class FinFlowError(Exception):
    exit_code = 1


class ConfigError(FinFlowError):
    exit_code = 10


class SourceFileError(FinFlowError):
    """Source file missing, unreadable or malformed."""

    exit_code = 11


class SchemaError(FinFlowError):
    """File-level schema violation (e.g. a required column is missing)."""

    exit_code = 12


class DataQualityError(FinFlowError):
    """Reject rate exceeded the configured circuit-breaker threshold."""

    exit_code = 13


class ReconciliationError(FinFlowError):
    """Source-to-target row counts or financial totals do not agree."""

    exit_code = 14


class CloudIntegrationError(FinFlowError):
    """Azure / Snowflake step failed (the local load may already be committed)."""

    exit_code = 15
