from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy


REQUIRED_TABLES = ("projects", "nodes", "fm_links", "derived_views")
PARENT_TYPE_BY_NODE_TYPE = {
    "SYS": None,
    "SUB": "SYS",
    "COMP": "SUB",
    "FN": "COMP",
    "REQ": "FN",
    "CHAR": "FN",
    "FM": "FN",
    "FE": "FM",
    "FC": "FM",
    "ACT": "FM",
}
BUSINESS_ID_PATTERN = re.compile(r"^(SYS|SUB|COMP|FN|FM|ACT)-\d{3,6}$")
REQUIRES_BUSINESS_ID = {"SYS", "SUB", "COMP", "FN", "FM", "ACT"}
FORBIDS_BUSINESS_ID = {"REQ", "CHAR", "FE", "FC"}


@dataclass(frozen=True, slots=True)
class ValidationReport:
    db_path: Path
    project_id: str
    issues: list[dict[str, Any]]
    busy_timeout_ms: int
    retry: int


@dataclass(frozen=True, slots=True)
class NodeRecord:
    rowid: int
    id: str | None
    type: str
    parent_id: int
    project_id: str
    name: str | None
    raw_data: str | None
    data: dict[str, Any] | None


def run_validation(
    *,
    db_path: str | Path,
    project_id: str,
    busy_timeout_ms: int,
    retry: int,
) -> ValidationReport:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        issues = db_helpers.execute_with_retry(
            lambda: _run_validation_once(
                db_path=resolved_db_path,
                project_id=project_id,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_validation_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
        ) from exc

    return ValidationReport(
        db_path=resolved_db_path,
        project_id=project_id,
        issues=issues,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _run_validation_once(
    *,
    db_path: Path,
    project_id: str,
    busy_timeout_ms: int,
) -> list[dict[str, Any]]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    conn.row_factory = sqlite3.Row

    try:
        issues: list[dict[str, Any]] = []
        table_names = _read_table_names(conn)

        for table_name in REQUIRED_TABLES:
            if table_name not in table_names:
                issues.append(
                    _issue(
                        level="error",
                        scope="schema",
                        kind="MISSING_TABLE",
                        target={"table": table_name},
                        reason=f"Required table '{table_name}' is missing.",
                        suggested_action=(
                            "Initialize or repair the DFMEA schema before relying on validation results."
                        ),
                    )
                )

        nodes = _load_project_nodes(conn, project_id=project_id, issues=issues)
        node_by_rowid = {node.rowid: node for node in nodes}

        issues.extend(_validate_graph(nodes=nodes, node_by_rowid=node_by_rowid))
        issues.extend(_validate_duplicate_business_ids(conn, project_id=project_id))
        issues.extend(
            _validate_local_references(nodes=nodes, node_by_rowid=node_by_rowid)
        )
        issues.extend(
            _validate_fm_links(
                conn,
                project_id=project_id,
                node_by_rowid=node_by_rowid,
                issues=issues,
            )
        )
        issues.extend(_validate_projection_state(conn, project_id=project_id))

        return issues
    finally:
        conn.close()


def _read_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _load_project_nodes(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    issues: list[dict[str, Any]],
) -> list[NodeRecord]:
    try:
        rows = conn.execute(
            """
            SELECT rowid, id, type, parent_id, project_id, name, data
            FROM nodes
            WHERE project_id = ?
            ORDER BY rowid
            """,
            (project_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        issues.append(
            _issue(
                level="error",
                scope="schema",
                kind="INVALID_NODES_SCHEMA",
                target={"table": "nodes"},
                reason=f"Could not read nodes table: {exc}",
                suggested_action="Repair the nodes table schema before re-running validation.",
            )
        )
        return []

    loaded: list[NodeRecord] = []
    for row in rows:
        node = NodeRecord(
            rowid=int(row["rowid"]),
            id=row["id"],
            type=row["type"],
            parent_id=int(row["parent_id"]),
            project_id=row["project_id"],
            name=row["name"],
            raw_data=row["data"],
            data=None,
        )
        issues.extend(_validate_node_schema(node))
        decoded, schema_issues = _decode_json_object(node)
        issues.extend(schema_issues)
        loaded.append(
            NodeRecord(
                rowid=node.rowid,
                id=node.id,
                type=node.type,
                parent_id=node.parent_id,
                project_id=node.project_id,
                name=node.name,
                raw_data=node.raw_data,
                data=decoded,
            )
        )
    return loaded


def _validate_node_schema(node: NodeRecord) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if node.type not in PARENT_TYPE_BY_NODE_TYPE:
        issues.append(
            _issue(
                level="error",
                scope="schema",
                kind="UNKNOWN_NODE_TYPE",
                target=_node_target(node),
                reason=f"Node type '{node.type}' is not recognized.",
                suggested_action="Repair the stored node type to a supported DFMEA node type.",
            )
        )
        return issues

    if node.type in REQUIRES_BUSINESS_ID:
        if node.id is None:
            issues.append(
                _issue(
                    level="error",
                    scope="schema",
                    kind="MISSING_BUSINESS_ID",
                    target=_node_target(node),
                    reason=f"{node.type} nodes must carry a business id.",
                    suggested_action="Repair the stored node id to the expected business-id format.",
                )
            )
        elif not BUSINESS_ID_PATTERN.fullmatch(node.id):
            issues.append(
                _issue(
                    level="error",
                    scope="schema",
                    kind="INVALID_BUSINESS_ID",
                    target=_node_target(node),
                    reason=f"Business id '{node.id}' does not match the expected pattern.",
                    suggested_action="Use an id like SYS-001, FN-001, FM-001, or ACT-001.",
                )
            )
    elif node.type in FORBIDS_BUSINESS_ID and node.id is not None:
        issues.append(
            _issue(
                level="error",
                scope="schema",
                kind="UNEXPECTED_BUSINESS_ID",
                target=_node_target(node),
                reason=f"{node.type} nodes must not carry a business id.",
                suggested_action="Clear the stored business id for this row-only node type.",
            )
        )
    return issues


def _decode_json_object(
    node: NodeRecord,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        decoded = json.loads(node.raw_data or "{}")
    except json.JSONDecodeError:
        return None, [
            _issue(
                level="error",
                scope="schema",
                kind="MALFORMED_JSON",
                target=_node_target(node),
                reason="Node data contains malformed JSON.",
                suggested_action="Repair the stored JSON string for this node.",
            )
        ]

    if not isinstance(decoded, dict):
        return None, [
            _issue(
                level="error",
                scope="schema",
                kind="INVALID_JSON_OBJECT",
                target=_node_target(node),
                reason="Node data must decode to a JSON object.",
                suggested_action="Store a JSON object in nodes.data for this node.",
            )
        ]

    return decoded, []


def _validate_graph(
    *,
    nodes: list[NodeRecord],
    node_by_rowid: dict[int, NodeRecord],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in nodes:
        expected_parent_type = PARENT_TYPE_BY_NODE_TYPE.get(node.type)
        if expected_parent_type is None:
            if node.parent_id != 0:
                issues.append(
                    _issue(
                        level="error",
                        scope="graph",
                        kind="INVALID_ROOT_PARENT",
                        target=_node_target(node),
                        reason=f"{node.type} nodes must use parent_id = 0.",
                        suggested_action="Reset the stored parent_id to 0 for this root node.",
                    )
                )
            continue

        if node.parent_id == 0:
            issues.append(
                _issue(
                    level="error",
                    scope="graph",
                    kind="MISSING_PARENT",
                    target=_node_target(node),
                    reason=f"{node.type} nodes require a {expected_parent_type} parent.",
                    suggested_action="Attach the node to a valid parent row in the same project.",
                )
            )
            continue

        parent = node_by_rowid.get(node.parent_id)
        if parent is None:
            issues.append(
                _issue(
                    level="error",
                    scope="graph",
                    kind="DANGLING_PARENT",
                    target=_node_target(node),
                    reason=f"Parent rowid {node.parent_id} does not exist.",
                    suggested_action="Repair the stored parent_id or restore the missing parent node.",
                )
            )
            continue

        if parent.project_id != node.project_id:
            issues.append(
                _issue(
                    level="error",
                    scope="graph",
                    kind="CROSS_PROJECT_PARENT",
                    target=_node_target(node),
                    reason="Node parent belongs to a different project.",
                    suggested_action="Reattach the node to a parent in the same project.",
                )
            )
        elif parent.type != expected_parent_type:
            issues.append(
                _issue(
                    level="error",
                    scope="graph",
                    kind="INVALID_PARENT_TYPE",
                    target=_node_target(node),
                    reason=(
                        f"{node.type} nodes require a {expected_parent_type} parent, "
                        f"but rowid {parent.rowid} is {parent.type}."
                    ),
                    suggested_action="Move or repair the node so its parent has the correct type.",
                )
            )
    return issues


def _validate_duplicate_business_ids(
    conn: sqlite3.Connection,
    *,
    project_id: str,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT id, COUNT(*) AS count, GROUP_CONCAT(rowid, ',') AS rowids
            FROM nodes
            WHERE project_id = ? AND id IS NOT NULL
            GROUP BY id
            HAVING COUNT(*) > 1
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        return [
            _issue(
                level="error",
                scope="integrity",
                kind="DUPLICATE_ID_CHECK_FAILED",
                target={"table": "nodes"},
                reason=f"Could not verify business-id uniqueness: {exc}",
                suggested_action="Repair the nodes table schema before relying on id-integrity checks.",
            )
        ]

    issues: list[dict[str, Any]] = []
    for row in rows:
        rowids = [int(item) for item in str(row["rowids"]).split(",") if item]
        issues.append(
            _issue(
                level="error",
                scope="integrity",
                kind="DUPLICATE_BUSINESS_ID",
                target={"id": row["id"], "rowids": rowids},
                reason=f"Business id '{row['id']}' is used by multiple nodes.",
                suggested_action="Assign unique business ids and repair references if needed.",
            )
        )
    return issues


def _validate_projection_state(
    conn: sqlite3.Connection,
    *,
    project_id: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    project_row = conn.execute(
        "SELECT data FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if project_row is None:
        return issues

    try:
        project_data = json.loads(project_row[0] or "{}")
    except json.JSONDecodeError:
        return issues
    if not isinstance(project_data, dict):
        return issues

    canonical_revision = int(project_data.get("canonical_revision", 0))
    last_projection_revision = int(project_data.get("last_projection_revision", 0))
    projection_dirty = bool(project_data.get("projection_dirty", False))

    if projection_dirty or last_projection_revision != canonical_revision:
        issues.append(
            _issue(
                level="warning",
                scope="projection",
                kind="STALE_PROJECTION",
                target={
                    "project_id": project_id,
                    "canonical_revision": canonical_revision,
                    "last_projection_revision": last_projection_revision,
                },
                reason="Projection data is stale relative to the canonical revision.",
                suggested_action="Run `dfmea projection rebuild` to refresh derived views.",
            )
        )

    rows = conn.execute(
        "SELECT kind, scope_ref, data FROM derived_views WHERE project_id = ? ORDER BY kind, scope_ref",
        (project_id,),
    ).fetchall()
    for row in rows:
        try:
            decoded = json.loads(row["data"])
        except json.JSONDecodeError:
            issues.append(
                _issue(
                    level="error",
                    scope="projection",
                    kind="PROJECTION_CORRUPT",
                    target={
                        "project_id": project_id,
                        "kind": row["kind"],
                        "scope_ref": row["scope_ref"],
                    },
                    reason="Projection data contains malformed JSON.",
                    suggested_action="Run `dfmea projection rebuild` to recreate the corrupted derived view.",
                )
            )
            continue

        if not isinstance(decoded, dict):
            issues.append(
                _issue(
                    level="error",
                    scope="projection",
                    kind="PROJECTION_CORRUPT",
                    target={
                        "project_id": project_id,
                        "kind": row["kind"],
                        "scope_ref": row["scope_ref"],
                    },
                    reason="Projection data must decode to a JSON object.",
                    suggested_action="Run `dfmea projection rebuild` to recreate the corrupted derived view.",
                )
            )

    return issues


def _validate_local_references(
    *,
    nodes: list[NodeRecord],
    node_by_rowid: dict[int, NodeRecord],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in nodes:
        if node.data is None:
            continue
        if node.type == "FM":
            issues.extend(
                _validate_reference_field(
                    node=node,
                    node_by_rowid=node_by_rowid,
                    field="violates_requirements",
                    expected_type="REQ",
                    expected_parent_rowid=node.parent_id,
                )
            )
            issues.extend(
                _validate_reference_field(
                    node=node,
                    node_by_rowid=node_by_rowid,
                    field="related_characteristics",
                    expected_type="CHAR",
                    expected_parent_rowid=node.parent_id,
                )
            )
        elif node.type == "ACT":
            issues.extend(
                _validate_reference_field(
                    node=node,
                    node_by_rowid=node_by_rowid,
                    field="target_causes",
                    expected_type="FC",
                    expected_parent_rowid=node.parent_id,
                )
            )
    return issues


def _validate_reference_field(
    *,
    node: NodeRecord,
    node_by_rowid: dict[int, NodeRecord],
    field: str,
    expected_type: str,
    expected_parent_rowid: int,
) -> list[dict[str, Any]]:
    refs, field_issues = _decode_int_list_field(node=node, field=field)
    if field_issues:
        return field_issues

    issues: list[dict[str, Any]] = []
    for ref_rowid in refs:
        referenced = node_by_rowid.get(ref_rowid)
        if referenced is None:
            issues.append(
                _issue(
                    level="error",
                    scope="integrity",
                    kind="BROKEN_LOCAL_REFERENCE",
                    target={
                        **_node_target(node),
                        "field": field,
                        "ref_rowid": ref_rowid,
                    },
                    reason=f"Field '{field}' references missing rowid {ref_rowid}.",
                    suggested_action="Remove or repair the broken local reference.",
                )
            )
            continue

        if (
            referenced.type != expected_type
            or referenced.parent_id != expected_parent_rowid
            or referenced.project_id != node.project_id
        ):
            issues.append(
                _issue(
                    level="error",
                    scope="integrity",
                    kind="BROKEN_LOCAL_REFERENCE",
                    target={
                        **_node_target(node),
                        "field": field,
                        "ref_rowid": ref_rowid,
                    },
                    reason=(
                        f"Field '{field}' must reference a sibling {expected_type} row in the same scope."
                    ),
                    suggested_action="Repair the stored rowid list so each reference points at a valid sibling node.",
                )
            )
    return issues


def _decode_int_list_field(
    *,
    node: NodeRecord,
    field: str,
) -> tuple[list[int], list[dict[str, Any]]]:
    if node.data is None:
        return [], []

    raw_value = node.data.get(field)
    if raw_value is None:
        return [], []

    if not isinstance(raw_value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in raw_value
    ):
        return [], [
            _issue(
                level="error",
                scope="schema",
                kind="INVALID_REFERENCE_LIST",
                target={**_node_target(node), "field": field},
                reason=f"Field '{field}' must be an integer list.",
                suggested_action="Repair the stored JSON so the field contains only integer rowids.",
            )
        ]

    return list(raw_value), []


def _validate_fm_links(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    node_by_rowid: dict[int, NodeRecord],
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            "SELECT from_rowid, to_fm_rowid FROM fm_links ORDER BY from_rowid, to_fm_rowid"
        ).fetchall()
    except sqlite3.Error as exc:
        issues.append(
            _issue(
                level="error",
                scope="schema",
                kind="INVALID_FM_LINKS_SCHEMA",
                target={"table": "fm_links"},
                reason=f"Could not read fm_links table: {exc}",
                suggested_action="Repair the fm_links table schema before re-running validation.",
            )
        )
        return []

    findings: list[dict[str, Any]] = []
    for row in rows:
        from_rowid = int(row["from_rowid"])
        to_fm_rowid = int(row["to_fm_rowid"])
        source = node_by_rowid.get(from_rowid)
        target = node_by_rowid.get(to_fm_rowid)

        if source is None or target is None:
            findings.append(
                _issue(
                    level="error",
                    scope="integrity",
                    kind="DANGLING_FM_LINK",
                    target={"from_rowid": from_rowid, "to_fm_rowid": to_fm_rowid},
                    reason="fm_links contains a rowid that does not resolve to a node in this project.",
                    suggested_action="Remove the dangling fm_links row or restore the missing node.",
                )
            )
            continue

        if source.project_id != project_id or target.project_id != project_id:
            findings.append(
                _issue(
                    level="error",
                    scope="integrity",
                    kind="CROSS_PROJECT_FM_LINK",
                    target={"from_rowid": from_rowid, "to_fm_rowid": to_fm_rowid},
                    reason="fm_links must stay within a single project.",
                    suggested_action="Repair the link so both endpoints belong to the validated project.",
                )
            )
            continue

        if source.type not in {"FE", "FC"}:
            findings.append(
                _issue(
                    level="error",
                    scope="integrity",
                    kind="INVALID_FM_LINK_SOURCE",
                    target={"from_rowid": from_rowid, "to_fm_rowid": to_fm_rowid},
                    reason="fm_links sources must be FE or FC rows.",
                    suggested_action="Recreate the trace link from a valid FE or FC node.",
                )
            )

        if target.type != "FM":
            findings.append(
                _issue(
                    level="error",
                    scope="integrity",
                    kind="INVALID_FM_LINK_TARGET",
                    target={"from_rowid": from_rowid, "to_fm_rowid": to_fm_rowid},
                    reason="fm_links targets must be FM rows.",
                    suggested_action="Repair the trace link target so it points at an FM node.",
                )
            )

        if (
            source.type in {"FE", "FC"}
            and target.type == "FM"
            and source.name != target.name
        ):
            findings.append(
                _issue(
                    level="warning",
                    scope="integrity",
                    kind="DESCRIPTION_DRIFT",
                    target={"from_rowid": from_rowid, "to_fm_rowid": to_fm_rowid},
                    reason="Linked FE/FC description differs from the traced FM description.",
                    suggested_action="Review whether the snapshot description should be synchronized.",
                )
            )
    return findings


def _node_target(node: NodeRecord) -> dict[str, Any]:
    target: dict[str, Any] = {"rowid": node.rowid, "type": node.type}
    if node.id is not None:
        target["id"] = node.id
    return target


def _issue(
    *,
    level: str,
    scope: str,
    kind: str,
    target: dict[str, Any],
    reason: str,
    suggested_action: str,
) -> dict[str, Any]:
    return {
        "level": level,
        "scope": scope,
        "kind": kind,
        "target": target,
        "reason": reason,
        "suggested_action": suggested_action,
    }


def _normalize_validation_storage_error(
    *,
    exc: sqlite3.Error,
    db_path: Path,
    project_id: str,
) -> CliError:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return DbBusyError(db_path=db_path)
    if "no such table" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message="Database does not expose the expected DFMEA schema.",
            target={"db": str(db_path)},
            suggested_action="Initialize a valid DFMEA database before running validate.",
        )
    return CliError(
        code="UNKNOWN",
        message=f"Failed to validate project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and SQLite state.",
    )
