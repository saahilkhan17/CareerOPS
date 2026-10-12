"""Naive-UTC clock helper.

All timestamps are naive UTC: consistent on SQLite (tests) and on PG
`timestamptz` columns whose server timezone is UTC (compose default).
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
