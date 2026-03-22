from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import dfmea_cli.db as db_helpers
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import (
    CliError,
    DbBusyError,
    InvalidOptionValueError,
    ProjectDbMismatchError,
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
    retry: int = DEFAULT_RETRY


@dataclass(frozen=True, slots=True)
class ResolvedProjectContext:
    db_path: Path
    project_id: str
    retry_policy: RetryPolicy


@dataclass(frozen=True, slots=True)
class ResolvedNode:
    rowid: int
    id: str | None
    type: str
    parent_id: int
    project_id: str
    name: str | None
    data: str


def resolve_project_context(
    *,
    db_path: str | Path,
    project_id: str | None,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    retry: int = DEFAULT_RETRY,
) -> ResolvedProjectContext:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    available_projects = _read_project_ids(
        resolved_db_path,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )

    if not available_projects:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Database does not contain any DFMEA projects.",
            target={"db": str(resolved_db_path)},
            suggested_action="Initialize the database before running DFMEA commands.",
        )

    if len(available_projects) != 1:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Database must contain exactly one project in V1.",
            target={
                "db": str(resolved_db_path),
                "project_count": len(available_projects),
            },
            suggested_action="Split the data so each database contains exactly one project.",
        )

    if project_id is None:
        resolved_project_id = available_projects[0]
    else:
        if available_projects[0] != project_id:
            raise ProjectDbMismatchError(
                db_project_id=available_projects[0],
                requested_project_id=project_id,
            )
        resolved_project_id = project_id

    return ResolvedProjectContext(
        db_path=resolved_db_path,
        project_id=resolved_project_id,
        retry_policy=retry_policy,
    )


def normalize_retry_policy(*, busy_timeout_ms: int, retry: int) -> RetryPolicy:
    if busy_timeout_ms < 0:
        raise InvalidOptionValueError(option="busy_timeout_ms", value=busy_timeout_ms)
    if retry < 0:
        raise InvalidOptionValueError(option="retry", value=retry)
    return RetryPolicy(busy_timeout_ms=busy_timeout_ms, retry=retry)


def resolve_node_reference(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    node_ref: str,
) -> ResolvedNode:
    row = _lookup_node_row(conn, project_id=project_id, node_ref=node_ref)
    if row is None:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{node_ref}' does not exist in project '{project_id}'.",
            target={"node": node_ref, "project_id": project_id},
            suggested_action="Provide an existing node id or rowid from the same project.",
        )

    return ResolvedNode(
        rowid=int(row["rowid"]),
        id=row["id"],
        type=row["type"],
        parent_id=int(row["parent_id"]),
        project_id=row["project_id"],
        name=row["name"],
        data=row["data"],
    )


def _read_project_ids(
    db_path: Path,
    *,
    busy_timeout_ms: int,
    retry: int,
) -> list[str]:
    if not db_path.exists() or not db_path.is_file():
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Database '{db_path}' does not exist or is not readable.",
            target={"db": str(db_path)},
            suggested_action="Check that the database path exists and is readable.",
        )

    try:
        return db_helpers.execute_with_retry(
            lambda: _read_project_ids_once(
                db_path=db_path,
                busy_timeout_ms=busy_timeout_ms,
            ),
            retry=retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_project_read_error(db_path=db_path, exc=exc) from exc


def _read_project_ids_once(*, db_path: Path, busy_timeout_ms: int) -> list[str]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        rows = conn.execute("SELECT id FROM projects ORDER BY id").fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def _normalize_project_read_error(*, db_path: Path, exc: sqlite3.Error) -> CliError:
    message = str(exc).lower()
    if "no such table" in message and "projects" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message="Database does not expose the expected projects table.",
            target={"db": str(db_path)},
            suggested_action="Create a valid DFMEA database before using this command.",
        )

    return CliError(
        code="INVALID_REFERENCE",
        message=f"Database '{db_path}' does not exist or is not readable.",
        target={"db": str(db_path)},
        suggested_action="Check that the database path exists and is readable.",
    )


def _lookup_node_row(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    node_ref: str,
) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    if node_ref.isdigit():
        return conn.execute(
            """
            SELECT rowid, id, type, parent_id, project_id, name, data
            FROM nodes
            WHERE rowid = ? AND project_id = ?
            """,
            (int(node_ref), project_id),
        ).fetchone()

    return conn.execute(
        """
        SELECT rowid, id, type, parent_id, project_id, name, data
        FROM nodes
        WHERE id = ? AND project_id = ?
        """,
        (node_ref, project_id),
    ).fetchone()
