from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar


DEFAULT_BUSY_TIMEOUT_MS = 5000
DEFAULT_RETRY = 3

T = TypeVar("T")


class RetryableBusyError(RuntimeError):
    def __init__(self, message: str = "Database is busy."):
        super().__init__(message)


def connect(
    db_path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    resolved_path = Path(db_path)
    resolved_timeout_ms = max(0, int(busy_timeout_ms))
    conn = sqlite3.connect(resolved_path, timeout=resolved_timeout_ms / 1000)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA recursive_triggers = ON;")
    conn.execute(f"PRAGMA busy_timeout = {resolved_timeout_ms};")
    return conn


def execute_with_retry(fn: Callable[[], T], *, retry: int = DEFAULT_RETRY) -> T:
    attempts = max(0, int(retry)) + 1
    last_error: RetryableBusyError | None = None

    for attempt in range(attempts):
        try:
            return fn()
        except RetryableBusyError as exc:
            last_error = exc
        except sqlite3.OperationalError as exc:
            if not _is_retryable_busy_error(exc):
                raise
            last_error = RetryableBusyError(str(exc))

        if attempt == attempts - 1:
            raise last_error or RetryableBusyError()

    raise RetryableBusyError()


def _is_retryable_busy_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message
