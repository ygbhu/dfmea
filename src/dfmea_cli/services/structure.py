from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy, resolve_node_reference


STRUCTURE_TYPES = ("SYS", "SUB", "COMP")
PARENT_TYPE_BY_NODE_TYPE = {
    "SYS": None,
    "SUB": "SYS",
    "COMP": "SUB",
}


@dataclass(frozen=True, slots=True)
class StructureMutationResult:
    db_path: Path
    project_id: str
    node_id: str
    node_type: str
    rowid: int
    parent_id: str | None
    busy_timeout_ms: int
    retry: int


def add_structure_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_type: str,
    name: str,
    parent_ref: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> StructureMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, rowid, resolved_parent_id = db_helpers.execute_with_retry(
            lambda: _add_structure_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                node_type=node_type,
                name=name,
                parent_ref=parent_ref,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_structure_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="add",
        ) from exc

    return StructureMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_id=node_id,
        node_type=node_type,
        rowid=rowid,
        parent_id=resolved_parent_id,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def update_structure_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    name: str | None,
    description: str | None,
    metadata: dict[str, Any] | None,
    busy_timeout_ms: int,
    retry: int,
) -> StructureMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, node_type, rowid = db_helpers.execute_with_retry(
            lambda: _update_structure_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                node_ref=node_ref,
                name=name,
                description=description,
                metadata=metadata,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_structure_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="update",
        ) from exc

    return StructureMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_id=node_id,
        node_type=node_type,
        rowid=rowid,
        parent_id=None,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def move_structure_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    parent_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> StructureMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, node_type, rowid, resolved_parent_id = db_helpers.execute_with_retry(
            lambda: _move_structure_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                node_ref=node_ref,
                parent_ref=parent_ref,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_structure_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="move",
        ) from exc

    return StructureMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_id=node_id,
        node_type=node_type,
        rowid=rowid,
        parent_id=resolved_parent_id,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def delete_structure_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> StructureMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, node_type, rowid = db_helpers.execute_with_retry(
            lambda: _delete_structure_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                node_ref=node_ref,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_structure_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="delete",
        ) from exc

    return StructureMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_id=node_id,
        node_type=node_type,
        rowid=rowid,
        parent_id=None,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _add_structure_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_type: str,
    name: str,
    parent_ref: str | None,
    busy_timeout_ms: int,
) -> tuple[str, int, str | None]:
    _validate_structure_type(node_type)
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        parent = _resolve_parent_for_create(
            conn,
            project_id=project_id,
            node_type=node_type,
            parent_ref=parent_ref,
        )
        node_id = _allocate_business_id(
            conn, project_id=project_id, node_type=node_type
        )
        timestamp = _utc_now()
        cursor = conn.execute(
            """
            INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                node_type,
                0 if parent is None else parent.rowid,
                project_id,
                name,
                json.dumps({}, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        rowid = cursor.lastrowid
        if rowid is None:
            raise CliError(
                code="UNKNOWN",
                message="Structure node insert did not return a rowid.",
                target={"type": node_type, "project_id": project_id},
                suggested_action="Retry the command. If it persists, inspect SQLite insert behavior.",
            )
        rowid = cast(int, rowid)
        conn.commit()
        return node_id, rowid, None if parent is None else parent.id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_structure_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    name: str | None,
    description: str | None,
    metadata: dict[str, Any] | None,
    busy_timeout_ms: int,
) -> tuple[str, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_structure_node(node.type)
        merged_data = _decode_node_data(node.data, node_ref=_node_identity(node))
        if metadata is not None:
            merged_data.update(metadata)
        if description is not None:
            merged_data["description"] = description

        update_name = node.name if name is None else name
        conn.execute(
            "UPDATE nodes SET name = ?, data = ?, updated = ? WHERE rowid = ?",
            (
                update_name,
                json.dumps(merged_data, sort_keys=True),
                _utc_now(),
                node.rowid,
            ),
        )
        conn.commit()
        return _node_identity(node), node.type, node.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _move_structure_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    parent_ref: str,
    busy_timeout_ms: int,
) -> tuple[str, str, int, str | None]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_structure_node(node.type)
        parent = _resolve_parent_for_create(
            conn,
            project_id=project_id,
            node_type=node.type,
            parent_ref=parent_ref,
        )
        conn.execute(
            "UPDATE nodes SET parent_id = ?, updated = ? WHERE rowid = ?",
            (0 if parent is None else parent.rowid, _utc_now(), node.rowid),
        )
        conn.commit()
        return (
            _node_identity(node),
            node.type,
            node.rowid,
            None if parent is None else parent.id,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_structure_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    busy_timeout_ms: int,
) -> tuple[str, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_structure_node(node.type)
        child_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE parent_id = ?",
            (node.rowid,),
        ).fetchone()[0]
        if child_count > 0:
            raise CliError(
                code="NODE_NOT_EMPTY",
                message=f"{_node_identity(node)} still has child nodes.",
                target={
                    "type": node.type,
                    "id": _node_identity(node),
                    "rowid": node.rowid,
                },
                suggested_action="Delete or move child nodes first.",
            )
        conn.execute("DELETE FROM nodes WHERE rowid = ?", (node.rowid,))
        conn.commit()
        return _node_identity(node), node.type, node.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _resolve_parent_for_create(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    node_type: str,
    parent_ref: str | None,
):
    expected_parent_type = PARENT_TYPE_BY_NODE_TYPE[node_type]
    if expected_parent_type is None:
        if parent_ref is not None:
            raise CliError(
                code="INVALID_PARENT",
                message="SYS nodes must not specify a parent.",
                target={"node_type": node_type, "parent_ref": parent_ref},
                suggested_action="Omit --parent when creating SYS nodes.",
            )
        return None

    if parent_ref is None:
        raise CliError(
            code="INVALID_PARENT",
            message=f"{node_type} nodes require a {expected_parent_type} parent.",
            target={"node_type": node_type, "parent_ref": None},
            suggested_action=f"Provide --parent with an existing {expected_parent_type} node.",
        )

    parent = resolve_node_reference(conn, project_id=project_id, node_ref=parent_ref)
    if parent.type != expected_parent_type:
        raise CliError(
            code="INVALID_PARENT",
            message=f"{node_type} nodes require a {expected_parent_type} parent.",
            target={
                "node_type": node_type,
                "parent_ref": parent_ref,
                "parent_type": parent.type,
            },
            suggested_action=f"Use a {expected_parent_type} parent for {node_type} nodes.",
        )
    return parent


def _allocate_business_id(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    node_type: str,
) -> str:
    row = conn.execute(
        "SELECT data FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Project '{project_id}' does not exist.",
            target={"project_id": project_id},
            suggested_action="Initialize or select an existing DFMEA project first.",
        )

    project_data = _decode_project_data(row[0], project_id=project_id)
    counters = project_data.get("id_counters")
    if not isinstance(counters, dict):
        counters = {}

    next_value = int(counters.get(node_type, 0)) + 1
    counters[node_type] = next_value
    project_data["id_counters"] = counters
    conn.execute(
        "UPDATE projects SET data = ?, updated = ? WHERE id = ?",
        (json.dumps(project_data, sort_keys=True), _utc_now(), project_id),
    )
    return f"{node_type}-{next_value:03d}"


def _validate_structure_type(node_type: str) -> None:
    if node_type not in STRUCTURE_TYPES:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Unsupported structure node type '{node_type}'.",
            target={"type": node_type},
            suggested_action="Use one of SYS, SUB, or COMP.",
        )


def _ensure_structure_node(node_type: str) -> None:
    if node_type not in STRUCTURE_TYPES:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node type '{node_type}' is not managed by structure commands.",
            target={"type": node_type},
            suggested_action="Use structure commands only with SYS, SUB, or COMP nodes.",
        )


def _node_identity(node) -> str:
    return node.id if node.id is not None else str(node.rowid)


def _decode_node_data(raw_data: str | None, *, node_ref: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_data or "{}")
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{node_ref}' has malformed JSON data.",
            target={"node": node_ref},
            suggested_action="Repair the stored node JSON before updating this structure node.",
        ) from exc
    if not isinstance(decoded, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{node_ref}' data must decode to a JSON object.",
            target={"node": node_ref},
            suggested_action="Repair the stored node JSON object before updating this structure node.",
        )
    return decoded


def _decode_project_data(raw_data: str | None, *, project_id: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_data or "{}")
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Project '{project_id}' has malformed JSON data.",
            target={"project_id": project_id},
            suggested_action="Repair the stored project JSON before creating structure nodes.",
        ) from exc
    if not isinstance(decoded, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Project '{project_id}' data must decode to a JSON object.",
            target={"project_id": project_id},
            suggested_action="Repair the stored project JSON object before creating structure nodes.",
        )
    return decoded


def _normalize_structure_storage_error(
    *,
    exc: sqlite3.Error,
    db_path: Path,
    project_id: str,
    operation: str,
) -> CliError:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return DbBusyError(db_path=db_path)
    if "no such table" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message="Database does not expose the expected DFMEA schema.",
            target={"db": str(db_path)},
            suggested_action="Initialize a valid DFMEA database before running structure commands.",
        )
    return CliError(
        code="UNKNOWN",
        message=f"Failed to {operation} structure node in project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and SQLite state.",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
