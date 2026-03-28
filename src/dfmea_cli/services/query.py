from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy, resolve_node_reference
from dfmea_cli.services.analysis import ALLOWED_ACTION_STATUSES, ALLOWED_AP_VALUES
from dfmea_cli.services.projections import load_projection


QUERYABLE_NODE_TYPES = {
    "SYS",
    "SUB",
    "COMP",
    "FN",
    "REQ",
    "CHAR",
    "FM",
    "FE",
    "FC",
    "ACT",
}


@dataclass(frozen=True, slots=True)
class QueryResult:
    db_path: Path
    project_id: str
    data: dict[str, Any]
    busy_timeout_ms: int
    retry: int
    projection_meta: dict[str, Any] | None = None


def query_get(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    return _run_query_operation(
        db_path=db_path,
        project_id=project_id,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda conn: {
            "project_id": project_id,
            "node": _get_structured_node(
                conn, project_id=project_id, node_ref=node_ref
            ),
        },
    )


def query_list(
    *,
    db_path: str | Path,
    project_id: str,
    node_type: str,
    parent_ref: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    resolved_type = _normalize_node_type(node_type)

    def action(conn: sqlite3.Connection) -> dict[str, Any]:
        parent_rowid: int | None = None
        if parent_ref is not None:
            parent_rowid = resolve_node_reference(
                conn, project_id=project_id, node_ref=parent_ref
            ).rowid
        nodes = _query_structured_nodes(
            conn,
            project_id=project_id,
            node_type=resolved_type,
            parent_rowid=parent_rowid,
        )
        return {
            "project_id": project_id,
            "count": len(nodes),
            "nodes": nodes,
        }

    return _run_query_operation(
        db_path=db_path,
        project_id=project_id,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=action,
    )


def query_search(
    *,
    db_path: str | Path,
    project_id: str,
    keyword: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    normalized_keyword = keyword.strip().lower()
    if not normalized_keyword:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Option '--keyword' must not be empty.",
            target={"option": "keyword"},
            suggested_action="Provide a non-empty keyword for query search.",
        )

    def action(conn: sqlite3.Connection) -> dict[str, Any]:
        nodes = _query_structured_nodes(conn, project_id=project_id)
        matched = [
            node
            for node in nodes
            if normalized_keyword in _searchable_text(node).lower()
        ]
        return {
            "project_id": project_id,
            "count": len(matched),
            "nodes": matched,
        }

    return _run_query_operation(
        db_path=db_path,
        project_id=project_id,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=action,
    )


def query_summary(
    *,
    db_path: str | Path,
    project_id: str,
    comp_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    projection = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="component_bundle",
        scope_ref=comp_ref,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    return QueryResult(
        db_path=Path(db_path),
        project_id=project_id,
        data={k: v for k, v in projection.data.items() if k != "_projection_status"},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        projection_meta={
            "canonical_revision": projection.canonical_revision,
            "kind": projection.kind,
            "scope_ref": projection.scope_ref,
            "status": projection.data.get("_projection_status", "fresh"),
        },
    )


def query_map(
    *,
    db_path: str | Path,
    project_id: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    projection = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="project_map",
        scope_ref="project",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    return QueryResult(
        db_path=Path(db_path),
        project_id=project_id,
        data={k: v for k, v in projection.data.items() if k != "_projection_status"},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        projection_meta={
            "canonical_revision": projection.canonical_revision,
            "kind": projection.kind,
            "scope_ref": projection.scope_ref,
            "status": projection.data.get("_projection_status", "fresh"),
        },
    )


def query_bundle(
    *,
    db_path: str | Path,
    project_id: str,
    comp_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    return query_summary(
        db_path=db_path,
        project_id=project_id,
        comp_ref=comp_ref,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def query_dossier(
    *,
    db_path: str | Path,
    project_id: str,
    fn_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    projection = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="function_dossier",
        scope_ref=fn_ref,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    return QueryResult(
        db_path=Path(db_path),
        project_id=project_id,
        data={k: v for k, v in projection.data.items() if k != "_projection_status"},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        projection_meta={
            "canonical_revision": projection.canonical_revision,
            "kind": projection.kind,
            "scope_ref": projection.scope_ref,
            "status": projection.data.get("_projection_status", "fresh"),
        },
    )


def query_by_ap(
    *,
    db_path: str | Path,
    project_id: str,
    ap: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    if ap not in ALLOWED_AP_VALUES:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Unsupported AP value '{ap}'.",
            target={"ap": ap},
            suggested_action="Use one of High, Medium, or Low.",
        )

    projection = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="risk_register",
        scope_ref="project",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    nodes = [
        node
        for node in projection.data["nodes"]
        if node["type"] == "FC" and node["data"].get("ap") == ap
    ]
    return QueryResult(
        db_path=Path(db_path),
        project_id=project_id,
        data={"project_id": project_id, "count": len(nodes), "nodes": nodes},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        projection_meta={
            "canonical_revision": projection.canonical_revision,
            "kind": projection.kind,
            "scope_ref": projection.scope_ref,
            "status": projection.data.get("_projection_status", "fresh"),
        },
    )


def query_by_severity(
    *,
    db_path: str | Path,
    project_id: str,
    gte: int,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    resolved_threshold = _validate_score_threshold(gte, option_name="gte")

    projection = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="risk_register",
        scope_ref="project",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    matched = []
    for node in projection.data["nodes"]:
        if node["type"] != "FM":
            continue
        severity = _read_int_field(
            node, field_name="severity", option_name="by-severity"
        )
        if severity >= resolved_threshold:
            matched.append(node)
    return QueryResult(
        db_path=Path(db_path),
        project_id=project_id,
        data={"project_id": project_id, "count": len(matched), "nodes": matched},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        projection_meta={
            "canonical_revision": projection.canonical_revision,
            "kind": projection.kind,
            "scope_ref": projection.scope_ref,
            "status": projection.data.get("_projection_status", "fresh"),
        },
    )


def query_actions(
    *,
    db_path: str | Path,
    project_id: str,
    status: str,
    busy_timeout_ms: int,
    retry: int,
) -> QueryResult:
    if status not in ALLOWED_ACTION_STATUSES:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Unsupported action status '{status}'.",
            target={"status": status},
            suggested_action="Use one of planned, in-progress, or completed.",
        )

    projection = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="action_backlog",
        scope_ref="project",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )
    matched = [
        {
            "id": item.get("id"),
            "rowid": item.get("rowid"),
            "type": "ACT",
            "project_id": project_id,
            "name": item.get("description"),
            "parent": item.get("fm"),
            "data": dict(item.get("data") or {}),
        }
        for item in projection.data["items"]
        if item.get("status") == status
    ]
    return QueryResult(
        db_path=Path(db_path),
        project_id=project_id,
        data={"project_id": project_id, "count": len(matched), "nodes": matched},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        projection_meta={
            "canonical_revision": projection.canonical_revision,
            "kind": projection.kind,
            "scope_ref": projection.scope_ref,
            "status": projection.data.get("_projection_status", "fresh"),
        },
    )


def _run_query_operation(
    *,
    db_path: str | Path,
    project_id: str,
    busy_timeout_ms: int,
    retry: int,
    action,
) -> QueryResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        data = db_helpers.execute_with_retry(
            lambda: _execute_query_once(
                db_path=resolved_db_path,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
                action=action,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_query_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
        ) from exc

    return QueryResult(
        db_path=resolved_db_path,
        project_id=project_id,
        data=data,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _execute_query_once(*, db_path: Path, busy_timeout_ms: int, action):
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    conn.row_factory = sqlite3.Row
    try:
        return action(conn)
    finally:
        conn.close()


def _get_structured_node(
    conn: sqlite3.Connection, *, project_id: str, node_ref: str
) -> dict[str, Any]:
    resolved = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
    row = _fetch_node_rows(
        conn,
        project_id=project_id,
        where_clause="n.rowid = ?",
        params=(resolved.rowid,),
    )
    if not row:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{node_ref}' does not exist in project '{project_id}'.",
            target={"node": node_ref, "project_id": project_id},
            suggested_action="Provide an existing node id or rowid from the same project.",
        )
    return _serialize_node_row(row[0])


def _query_structured_nodes(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    node_type: str | None = None,
    parent_rowid: int | None = None,
    parent_rowids: list[int] | None = None,
) -> list[dict[str, Any]]:
    where_parts: list[str] = []
    params: list[Any] = []

    if node_type is not None:
        where_parts.append("n.type = ?")
        params.append(node_type)
    if parent_rowid is not None:
        where_parts.append("n.parent_id = ?")
        params.append(parent_rowid)
    elif parent_rowids is not None:
        if not parent_rowids:
            return []
        placeholders = ", ".join("?" for _ in parent_rowids)
        where_parts.append(f"n.parent_id IN ({placeholders})")
        params.extend(parent_rowids)

    rows = _fetch_node_rows(
        conn,
        project_id=project_id,
        where_clause=" AND ".join(where_parts) if where_parts else None,
        params=tuple(params),
    )
    return [_serialize_node_row(row) for row in rows]


def _fetch_node_rows(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    where_clause: str | None,
    params: tuple[Any, ...],
) -> list[sqlite3.Row]:
    sql = """
        SELECT
            n.rowid AS rowid,
            n.id AS id,
            n.type AS type,
            n.parent_id AS parent_id,
            n.project_id AS project_id,
            n.name AS name,
            n.data AS data,
            p.rowid AS parent_rowid,
            p.id AS parent_business_id,
            p.type AS parent_type,
            p.name AS parent_name
        FROM nodes AS n
        LEFT JOIN nodes AS p ON p.rowid = n.parent_id AND n.parent_id <> 0
        WHERE n.project_id = ?
    """
    full_params: tuple[Any, ...] = (project_id, *params)
    if where_clause:
        sql += f" AND {where_clause}"
    sql += " ORDER BY n.rowid"
    return list(conn.execute(sql, full_params).fetchall())


def _serialize_node_row(row: sqlite3.Row) -> dict[str, Any]:
    node_ref = row["id"] if row["id"] is not None else str(row["rowid"])
    parent = None
    if int(row["parent_id"]) != 0:
        if row["parent_rowid"] is None or row["parent_type"] is None:
            raise CliError(
                code="INVALID_REFERENCE",
                message=(
                    f"Node '{node_ref}' has a dangling parent reference to rowid "
                    f"{int(row['parent_id'])}."
                ),
                target={
                    "node": node_ref,
                    "parent_rowid": int(row["parent_id"]),
                },
                suggested_action=(
                    "Repair the stored parent_id or restore the missing parent node before retrying this query."
                ),
            )
        parent = {
            "rowid": int(row["parent_rowid"]),
            "id": row["parent_business_id"],
            "type": row["parent_type"],
            "name": row["parent_name"],
        }

    return {
        "rowid": int(row["rowid"]),
        "id": row["id"],
        "type": row["type"],
        "project_id": row["project_id"],
        "name": row["name"],
        "parent": parent,
        "data": _decode_node_data(row["data"], node_ref=node_ref),
    }


def _decode_node_data(raw_data: str | None, *, node_ref: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_data or "{}")
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{node_ref}' has malformed JSON data.",
            target={"node": node_ref},
            suggested_action="Repair the stored node JSON before retrying this query.",
        ) from exc
    if not isinstance(decoded, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{node_ref}' data must decode to a JSON object.",
            target={"node": node_ref},
            suggested_action="Repair the stored node JSON object before retrying this query.",
        )
    return decoded


def _normalize_node_type(node_type: str) -> str:
    resolved_type = node_type.upper()
    if resolved_type not in QUERYABLE_NODE_TYPES:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Unsupported node type '{node_type}'.",
            target={"type": node_type},
            suggested_action="Use one of SYS, SUB, COMP, FN, REQ, CHAR, FM, FE, FC, or ACT.",
        )
    return resolved_type


def _ensure_node_type(actual_type: str, *, expected_type: str, node_ref: str) -> None:
    if actual_type == expected_type:
        return
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"Node '{node_ref}' must be a {expected_type} node.",
        target={"node": node_ref, "type": actual_type},
        suggested_action=f"Provide a valid {expected_type} id or rowid.",
    )


def _validate_score_threshold(value: int, *, option_name: str) -> int:
    if 1 <= value <= 10:
        return value
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"Option '--{option_name}' must be between 1 and 10.",
        target={"option": option_name, "value": value},
        suggested_action=f"Provide a value from 1 to 10 for --{option_name}.",
    )


def _read_int_field(node: dict[str, Any], *, field_name: str, option_name: str) -> int:
    value = node["data"].get(field_name, 0)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        node_ref = node["id"] or str(node["rowid"])
        raise CliError(
            code="INVALID_REFERENCE",
            message=(
                f"Node '{node_ref}' has malformed '{field_name}' data for query {option_name}."
            ),
            target={"node": node_ref, "field": field_name, "value": value},
            suggested_action=(
                f"Repair the stored {field_name} value before rerunning query {option_name}."
            ),
        ) from exc


def _searchable_text(node: dict[str, Any]) -> str:
    parts = [
        node["type"],
        node["id"] or "",
        node["name"] or "",
        json.dumps(node["data"], sort_keys=True),
    ]
    parent = node.get("parent")
    if parent is not None:
        parts.extend([parent.get("id") or "", parent.get("name") or ""])
    return " ".join(parts)


def _normalize_query_storage_error(
    *, exc: sqlite3.Error, db_path: Path, project_id: str
) -> CliError:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return DbBusyError(db_path=db_path)
    if "no such table" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message="Database does not expose the expected DFMEA schema.",
            target={"db": str(db_path)},
            suggested_action="Initialize a valid DFMEA database before running query commands.",
        )
    return CliError(
        code="UNKNOWN",
        message=f"Query command failed in project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and SQLite state.",
    )
