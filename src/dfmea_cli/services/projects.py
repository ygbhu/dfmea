from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy
from dfmea_cli.schema import bootstrap_schema


@dataclass(frozen=True, slots=True)
class ProjectInitResult:
    db_path: Path
    project_id: str
    name: str
    busy_timeout_ms: int
    retry: int


DEFAULT_PROJECT_DATA = {
    "canonical_revision": 0,
    "last_projection_build_at": None,
    "last_projection_revision": 0,
    "projection_dirty": False,
    "projection_schema_version": "1.0",
}


def initialize_project(
    *,
    db_path: str | Path,
    project_id: str,
    name: str,
    busy_timeout_ms: int,
    retry: int,
) -> ProjectInitResult:
    resolved_db_path = Path(db_path)
    db_existed_before = resolved_db_path.exists()
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        db_helpers.execute_with_retry(
            lambda: _initialize_project_once(
                db_path=resolved_db_path,
                project_id=project_id,
                name=name,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        _cleanup_failed_init(
            db_path=resolved_db_path,
            db_existed_before=db_existed_before,
        )
        raise _normalize_sqlite_init_error(
            db_path=resolved_db_path,
            exc=exc,
        ) from exc

    return ProjectInitResult(
        db_path=resolved_db_path,
        project_id=project_id,
        name=name,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _initialize_project_once(
    *,
    db_path: Path,
    project_id: str,
    name: str,
    busy_timeout_ms: int,
) -> None:
    _ensure_db_is_safe_for_init(db_path)
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        bootstrap_schema(conn)
        existing_project_count = conn.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]
        if existing_project_count != 0:
            raise CliError(
                code="INVALID_REFERENCE",
                message="Database already contains a DFMEA project.",
                target={"db": str(db_path), "project_count": existing_project_count},
                suggested_action="Use a new database path for dfmea init.",
            )

        timestamp = _utc_now()
        conn.execute(
            "INSERT INTO projects (id, name, data, created, updated) VALUES (?, ?, ?, ?, ?)",
            (
                project_id,
                name,
                json.dumps(DEFAULT_PROJECT_DATA, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if project_count != 1:
            raise CliError(
                code="INVALID_REFERENCE",
                message="Database must contain exactly one project in V1.",
                target={"db": str(db_path), "project_count": project_count},
                suggested_action="Recreate the database with a single project.",
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_sqlite_init_error(*, db_path: Path, exc: sqlite3.Error) -> CliError:
    message = str(exc).lower()
    if "unable to open database file" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message=f"Database '{db_path}' could not be opened.",
            target={"db": str(db_path)},
            suggested_action=(
                "Ensure the parent directory exists and the database path is writable."
            ),
        )

    return CliError(
        code="UNKNOWN",
        message=f"Failed to initialize database '{db_path}'.",
        target={"db": str(db_path)},
        suggested_action=(
            "Retry the command. If it persists, inspect filesystem permissions and SQLite state."
        ),
    )


def _cleanup_failed_init(*, db_path: Path, db_existed_before: bool) -> None:
    if db_existed_before or not db_path.exists() or not db_path.is_file():
        return

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        _remove_sqlite_artifacts(db_path)
        return

    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    except sqlite3.Error:
        _remove_sqlite_artifacts(db_path)
        return
    finally:
        conn.close()

    if not rows:
        _remove_sqlite_artifacts(db_path)


def _ensure_db_is_safe_for_init(db_path: Path) -> None:
    if not db_path.exists():
        return

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise _normalize_sqlite_init_error(db_path=db_path, exc=exc) from exc

    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    except sqlite3.Error as exc:
        raise _normalize_sqlite_init_error(db_path=db_path, exc=exc) from exc
    finally:
        conn.close()

    table_names = [row[0] for row in rows]
    if not table_names:
        return

    expected_tables = {"projects", "nodes", "fm_links", "derived_views"}
    unexpected_tables = [name for name in table_names if name not in expected_tables]
    if unexpected_tables:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Existing database is not a fresh DFMEA init target.",
            target={"db": str(db_path), "unexpected_tables": unexpected_tables},
            suggested_action="Use a new empty database path instead of reusing a legacy SQLite file.",
        )

    non_empty_tables: list[str] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise _normalize_sqlite_init_error(db_path=db_path, exc=exc) from exc

    try:
        for table_name in sorted(expected_tables.intersection(table_names)):
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            if row_count > 0:
                non_empty_tables.append(table_name)
    except sqlite3.Error as exc:
        raise _normalize_sqlite_init_error(db_path=db_path, exc=exc) from exc
    finally:
        conn.close()

    if non_empty_tables:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Existing database is not empty enough for fresh DFMEA init.",
            target={"db": str(db_path), "non_empty_tables": non_empty_tables},
            suggested_action="Use a new empty database path or clear all DFMEA tables before running init.",
        )


def _remove_sqlite_artifacts(db_path: Path) -> None:
    for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
