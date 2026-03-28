from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy
from dfmea_cli.schema import bootstrap_schema


PROJECTION_SCHEMA_VERSION = "1.0"
PROJECTION_METADATA_DEFAULTS = {
    "canonical_revision": 0,
    "last_projection_build_at": None,
    "last_projection_revision": 0,
    "projection_dirty": False,
    "projection_schema_version": PROJECTION_SCHEMA_VERSION,
}


@dataclass(frozen=True, slots=True)
class ProjectionStatusResult:
    db_path: Path
    project_id: str
    data: dict[str, Any]
    busy_timeout_ms: int
    retry: int


@dataclass(frozen=True, slots=True)
class ProjectionRebuildResult:
    db_path: Path
    project_id: str
    data: dict[str, Any]
    busy_timeout_ms: int
    retry: int


@dataclass(frozen=True, slots=True)
class LoadedProjection:
    kind: str
    scope_ref: str
    canonical_revision: int
    data: dict[str, Any]


def get_projection_status(
    *,
    db_path: str | Path,
    project_id: str,
    busy_timeout_ms: int,
    retry: int,
) -> ProjectionStatusResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        data = db_helpers.execute_with_retry(
            lambda: _get_projection_status_once(
                db_path=resolved_db_path,
                project_id=project_id,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_projection_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            action="read projection status",
        ) from exc

    return ProjectionStatusResult(
        db_path=resolved_db_path,
        project_id=project_id,
        data=data,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def rebuild_projections(
    *,
    db_path: str | Path,
    project_id: str,
    busy_timeout_ms: int,
    retry: int,
) -> ProjectionRebuildResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        data = db_helpers.execute_with_retry(
            lambda: _rebuild_projections_once(
                db_path=resolved_db_path,
                project_id=project_id,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_projection_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            action="rebuild projections",
        ) from exc

    return ProjectionRebuildResult(
        db_path=resolved_db_path,
        project_id=project_id,
        data=data,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def load_projection(
    *,
    db_path: str | Path,
    project_id: str,
    kind: str,
    scope_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> LoadedProjection:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        return db_helpers.execute_with_retry(
            lambda: _load_projection_once(
                db_path=resolved_db_path,
                project_id=project_id,
                kind=kind,
                scope_ref=scope_ref,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_projection_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            action=f"load projection '{kind}'",
        ) from exc


def ensure_projection_schema(
    conn: sqlite3.Connection,
    *,
    project_id: str,
) -> dict[str, Any]:
    bootstrap_schema(conn)

    row = conn.execute(
        "SELECT data FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Project '{project_id}' does not exist in the database.",
            target={"project_id": project_id},
            suggested_action="Provide a valid project id for projection commands.",
        )

    try:
        current = json.loads(row[0]) if row[0] else {}
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Project metadata is not valid JSON.",
            target={"project_id": project_id},
            suggested_action="Repair projects.data before using projection commands.",
        ) from exc

    if not isinstance(current, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message="Project metadata must be a JSON object.",
            target={"project_id": project_id},
            suggested_action="Repair projects.data before using projection commands.",
        )

    metadata = dict(current)
    upgraded = False
    for key, value in PROJECTION_METADATA_DEFAULTS.items():
        if key not in metadata:
            metadata[key] = value
            upgraded = True

    if metadata.get("projection_schema_version") != PROJECTION_SCHEMA_VERSION:
        metadata["projection_schema_version"] = PROJECTION_SCHEMA_VERSION
        upgraded = True

    if upgraded:
        metadata["projection_dirty"] = True
        conn.execute(
            "UPDATE projects SET data = ?, updated = ? WHERE id = ?",
            (json.dumps(metadata, sort_keys=True), _utc_now(), project_id),
        )

    return metadata


def mark_projection_dirty(
    conn: sqlite3.Connection, *, project_id: str
) -> dict[str, Any]:
    metadata = ensure_projection_schema(conn, project_id=project_id)
    metadata["canonical_revision"] = int(metadata.get("canonical_revision", 0)) + 1
    metadata["projection_dirty"] = True
    metadata["projection_schema_version"] = PROJECTION_SCHEMA_VERSION
    conn.execute(
        "UPDATE projects SET data = ?, updated = ? WHERE id = ?",
        (json.dumps(metadata, sort_keys=True), _utc_now(), project_id),
    )
    return metadata


def _get_projection_status_once(
    *,
    db_path: Path,
    project_id: str,
    busy_timeout_ms: int,
) -> dict[str, Any]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    try:
        conn.execute("BEGIN")
        metadata = ensure_projection_schema(conn, project_id=project_id)
        conn.commit()
        return _projection_status_payload(project_id=project_id, metadata=metadata)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rebuild_projections_once(
    *,
    db_path: Path,
    project_id: str,
    busy_timeout_ms: int,
) -> dict[str, Any]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        metadata = ensure_projection_schema(conn, project_id=project_id)
        project = conn.execute(
            "SELECT id, name FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if project is None:
            raise CliError(
                code="INVALID_REFERENCE",
                message=f"Project '{project_id}' does not exist in the database.",
                target={"project_id": project_id},
                suggested_action="Provide a valid project id for projection commands.",
            )

        node_rows = conn.execute(
            "SELECT rowid, id, type, parent_id, name, data FROM nodes WHERE project_id = ? ORDER BY rowid",
            (project_id,),
        ).fetchall()

        canonical_revision = int(metadata.get("canonical_revision", 0))
        built_at = _utc_now()
        payloads = {
            "project_map": _build_project_map(
                project_id=project["id"],
                project_name=project["name"],
                node_rows=node_rows,
            ),
            **_build_component_bundles(project_id=project_id, node_rows=node_rows),
            **_build_function_dossiers(project_id=project_id, node_rows=node_rows),
            "risk_register": _build_risk_register(
                project_id=project_id, node_rows=node_rows
            ),
            "action_backlog": _build_action_backlog(
                project_id=project_id, node_rows=node_rows
            ),
        }

        conn.execute("DELETE FROM derived_views WHERE project_id = ?", (project_id,))
        rebuilt_counts = {
            "action_backlog": 0,
            "component_bundle": 0,
            "function_dossier": 0,
            "project_map": 0,
            "risk_register": 0,
        }
        for projection_key, payload in payloads.items():
            kind, scope_ref = _split_projection_key(projection_key)
            conn.execute(
                "INSERT INTO derived_views (project_id, kind, scope_ref, canonical_revision, built_at, data) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    kind,
                    scope_ref,
                    canonical_revision,
                    built_at,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            rebuilt_counts[kind] = rebuilt_counts.get(kind, 0) + 1

        metadata["projection_dirty"] = False
        metadata["last_projection_revision"] = canonical_revision
        metadata["last_projection_build_at"] = built_at
        metadata["projection_schema_version"] = PROJECTION_SCHEMA_VERSION
        conn.execute(
            "UPDATE projects SET data = ?, updated = ? WHERE id = ?",
            (json.dumps(metadata, sort_keys=True), built_at, project_id),
        )
        conn.commit()

        return {
            "project_id": project_id,
            "projection_dirty": False,
            "last_projection_revision": canonical_revision,
            "rebuilt_counts": rebuilt_counts,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _projection_status_payload(
    *, project_id: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "canonical_revision": int(metadata.get("canonical_revision", 0)),
        "last_projection_build_at": metadata.get("last_projection_build_at"),
        "last_projection_revision": int(metadata.get("last_projection_revision", 0)),
        "projection_dirty": bool(metadata.get("projection_dirty", False)),
        "projection_schema_version": str(
            metadata.get("projection_schema_version", PROJECTION_SCHEMA_VERSION)
        ),
    }


def _build_project_map(
    *,
    project_id: str,
    project_name: str,
    node_rows: list[sqlite3.Row],
) -> dict[str, Any]:
    counts_by_type = {
        "SYS": 0,
        "SUB": 0,
        "COMP": 0,
        "FN": 0,
        "FM": 0,
        "ACT": 0,
    }
    for row in node_rows:
        node_type = row["type"]
        if node_type in counts_by_type:
            counts_by_type[node_type] += 1

    return {
        "project": {"id": project_id, "name": project_name},
        "counts": {
            "systems": counts_by_type["SYS"],
            "subsystems": counts_by_type["SUB"],
            "components": counts_by_type["COMP"],
            "functions": counts_by_type["FN"],
            "failure_modes": counts_by_type["FM"],
            "open_actions": counts_by_type["ACT"],
        },
        "structure": [],
        "risk_summary": {"ap": {"High": 0, "Medium": 0, "Low": 0}, "severity_gte_7": 0},
    }


def _load_projection_once(
    *,
    db_path: Path,
    project_id: str,
    kind: str,
    scope_ref: str,
    busy_timeout_ms: int,
) -> LoadedProjection:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        metadata = ensure_projection_schema(conn, project_id=project_id)
        canonical_revision = int(metadata.get("canonical_revision", 0))
        projection_status = "fresh"
        row = conn.execute(
            "SELECT kind, scope_ref, canonical_revision, data FROM derived_views WHERE project_id = ? AND kind = ? AND scope_ref = ?",
            (project_id, kind, scope_ref),
        ).fetchone()
        if (
            row is None
            or bool(metadata.get("projection_dirty", False))
            or int(row["canonical_revision"]) != canonical_revision
        ):
            conn.rollback()
            _rebuild_projections_once(
                db_path=db_path,
                project_id=project_id,
                busy_timeout_ms=busy_timeout_ms,
            )
            conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN")
            metadata = ensure_projection_schema(conn, project_id=project_id)
            row = conn.execute(
                "SELECT kind, scope_ref, canonical_revision, data FROM derived_views WHERE project_id = ? AND kind = ? AND scope_ref = ?",
                (project_id, kind, scope_ref),
            ).fetchone()
            projection_status = "rebuilt"
        if row is None:
            raise CliError(
                code="INVALID_REFERENCE",
                message=f"Projection '{kind}' for scope '{scope_ref}' is missing.",
                target={"project_id": project_id, "kind": kind, "scope_ref": scope_ref},
                suggested_action="Run `dfmea projection rebuild` and retry the query.",
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return LoadedProjection(
        kind=str(row["kind"]),
        scope_ref=str(row["scope_ref"]),
        canonical_revision=int(row["canonical_revision"]),
        data={
            **_decode_projection_data(
                raw_data=row["data"],
                kind=str(row["kind"]),
                scope_ref=str(row["scope_ref"]),
            ),
            "_projection_status": projection_status,
        },
    )


def _decode_projection_data(
    *, raw_data: str, kind: str, scope_ref: str
) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_data)
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Projection '{kind}' for '{scope_ref}' is malformed JSON.",
            target={"kind": kind, "scope_ref": scope_ref},
            suggested_action="Rebuild projections and retry the command.",
        ) from exc
    if not isinstance(decoded, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Projection '{kind}' for '{scope_ref}' must decode to a JSON object.",
            target={"kind": kind, "scope_ref": scope_ref},
            suggested_action="Rebuild projections and retry the command.",
        )
    return decoded


def _build_component_bundles(
    *,
    project_id: str,
    node_rows: list[sqlite3.Row],
) -> dict[str, dict[str, Any]]:
    structured = _structured_nodes(node_rows=node_rows, project_id=project_id)
    components = [node for node in structured if node["type"] == "COMP"]
    functions = [node for node in structured if node["type"] == "FN"]
    requirements = [node for node in structured if node["type"] == "REQ"]
    characteristics = [node for node in structured if node["type"] == "CHAR"]
    failure_modes = [node for node in structured if node["type"] == "FM"]
    failure_effects = [node for node in structured if node["type"] == "FE"]
    failure_causes = [node for node in structured if node["type"] == "FC"]
    actions = [node for node in structured if node["type"] == "ACT"]

    functions_by_comp: dict[int, list[dict[str, Any]]] = {}
    for node in functions:
        parent = node.get("parent")
        if parent is not None:
            functions_by_comp.setdefault(int(parent["rowid"]), []).append(node)

    requirements_by_fn = _count_children_by_parent(requirements)
    characteristics_by_fn = _count_children_by_parent(characteristics)
    failure_modes_by_fn = _count_children_by_parent(failure_modes)

    fm_to_fn: dict[int, int] = {}
    for node in failure_modes:
        parent = node.get("parent")
        if parent is not None:
            fm_to_fn[node["rowid"]] = int(parent["rowid"])

    action_counts_by_fn: dict[int, int] = {}
    action_ids_by_fn: dict[int, list[str]] = {}
    for node in actions:
        parent = node.get("parent")
        if parent is None:
            continue
        fn_rowid = fm_to_fn.get(int(parent["rowid"]))
        if fn_rowid is not None:
            action_counts_by_fn[fn_rowid] = action_counts_by_fn.get(fn_rowid, 0) + 1
            if node.get("id"):
                action_ids_by_fn.setdefault(fn_rowid, []).append(str(node["id"]))

    fe_counts_by_fm = _count_children_by_parent(failure_effects)
    fc_counts_by_fm = _count_children_by_parent(failure_causes)
    act_counts_by_fm = _count_children_by_parent(actions)

    bundles: dict[str, dict[str, Any]] = {}
    for component in components:
        component_functions = functions_by_comp.get(component["rowid"], [])
        function_rowids = {node["rowid"] for node in component_functions}
        component_fms = [
            node
            for node in failure_modes
            if node["rowid"]
            in {
                fm["rowid"]
                for fm in failure_modes
                if fm_to_fn.get(fm["rowid"]) in function_rowids
            }
        ]
        fm_rowids = {node["rowid"] for node in component_fms}

        function_summaries = [
            {
                "id": node["id"],
                "rowid": node["rowid"],
                "name": node["name"],
                "requirements": requirements_by_fn.get(node["rowid"], 0),
                "characteristics": characteristics_by_fn.get(node["rowid"], 0),
                "failure_modes": failure_modes_by_fn.get(node["rowid"], 0),
                "actions": action_counts_by_fn.get(node["rowid"], 0),
                "open_action_ids": action_ids_by_fn.get(node["rowid"], []),
            }
            for node in component_functions
        ]

        bundles[f"component_bundle::{component['id']}"] = {
            "project_id": project_id,
            "component": component,
            "counts": {
                "functions": len(component_functions),
                "requirements": sum(
                    requirements_by_fn.get(rowid, 0) for rowid in function_rowids
                ),
                "characteristics": sum(
                    characteristics_by_fn.get(rowid, 0) for rowid in function_rowids
                ),
                "failure_modes": sum(
                    failure_modes_by_fn.get(rowid, 0) for rowid in function_rowids
                ),
                "failure_effects": sum(
                    fe_counts_by_fm.get(rowid, 0) for rowid in fm_rowids
                ),
                "failure_causes": sum(
                    fc_counts_by_fm.get(rowid, 0) for rowid in fm_rowids
                ),
                "actions": sum(act_counts_by_fm.get(rowid, 0) for rowid in fm_rowids),
            },
            "functions": function_summaries,
        }
    return bundles


def _build_risk_register(
    *, project_id: str, node_rows: list[sqlite3.Row]
) -> dict[str, Any]:
    structured = _structured_nodes(node_rows=node_rows, project_id=project_id)
    nodes = [node for node in structured if node["type"] in {"FM", "FC"}]
    return {"nodes": nodes}


def _build_action_backlog(
    *, project_id: str, node_rows: list[sqlite3.Row]
) -> dict[str, Any]:
    structured = _structured_nodes(node_rows=node_rows, project_id=project_id)
    node_by_rowid = {node["rowid"]: node for node in structured}
    items = []
    for node in structured:
        if node["type"] != "ACT":
            continue
        fm = node.get("parent") or {}
        fm_full = node_by_rowid.get(fm.get("rowid", -1), {})
        fn = fm_full.get("parent") or {}
        fn_full = node_by_rowid.get(fn.get("rowid", -1), {})
        comp = fn_full.get("parent") or {}
        items.append(
            {
                "id": node.get("id"),
                "rowid": node.get("rowid"),
                "description": node.get("name", ""),
                "data": dict(node.get("data") or {}),
                "status": node.get("data", {}).get("status"),
                "owner": node.get("data", {}).get("owner"),
                "due": node.get("data", {}).get("due"),
                "fm": {
                    "id": fm.get("id"),
                    "rowid": fm.get("rowid"),
                    "name": fm.get("name"),
                },
                "function": {
                    "id": fn.get("id"),
                    "rowid": fn.get("rowid"),
                    "name": fn.get("name"),
                },
                "component": {
                    "id": comp.get("id"),
                    "rowid": comp.get("rowid"),
                    "name": comp.get("name"),
                },
            }
        )
    return {"items": items}


def _build_function_dossiers(
    *, project_id: str, node_rows: list[sqlite3.Row]
) -> dict[str, dict[str, Any]]:
    structured = _structured_nodes(node_rows=node_rows, project_id=project_id)
    functions = [node for node in structured if node["type"] == "FN"]
    requirements = [node for node in structured if node["type"] == "REQ"]
    characteristics = [node for node in structured if node["type"] == "CHAR"]
    failure_modes = [node for node in structured if node["type"] == "FM"]
    failure_effects = [node for node in structured if node["type"] == "FE"]
    failure_causes = [node for node in structured if node["type"] == "FC"]
    actions = [node for node in structured if node["type"] == "ACT"]

    dossiers: dict[str, dict[str, Any]] = {}
    for fn in functions:
        fn_rowid = fn["rowid"]
        fn_requirements = [
            node
            for node in requirements
            if node.get("parent", {}).get("rowid") == fn_rowid
        ]
        fn_characteristics = [
            node
            for node in characteristics
            if node.get("parent", {}).get("rowid") == fn_rowid
        ]
        fn_failure_modes = [
            node
            for node in failure_modes
            if node.get("parent", {}).get("rowid") == fn_rowid
        ]
        fm_rowids = {node["rowid"] for node in fn_failure_modes}

        fm_cards = []
        for fm in fn_failure_modes:
            fm_rowid = fm["rowid"]
            fm_cards.append(
                {
                    "fm": fm,
                    "effects": [
                        node
                        for node in failure_effects
                        if node.get("parent", {}).get("rowid") == fm_rowid
                    ],
                    "causes": [
                        node
                        for node in failure_causes
                        if node.get("parent", {}).get("rowid") == fm_rowid
                    ],
                    "actions": [
                        node
                        for node in actions
                        if node.get("parent", {}).get("rowid") == fm_rowid
                    ],
                }
            )

        dossiers[f"function_dossier::{fn['id']}"] = {
            "project_id": project_id,
            "function": fn,
            "requirements": fn_requirements,
            "characteristics": fn_characteristics,
            "failure_modes": fm_cards,
            "counts": {
                "requirements": len(fn_requirements),
                "characteristics": len(fn_characteristics),
                "failure_modes": len(fn_failure_modes),
                "linked_rows": len(fm_rowids),
            },
        }

    return dossiers


def _structured_nodes(
    *, node_rows: list[sqlite3.Row], project_id: str
) -> list[dict[str, Any]]:
    node_by_rowid: dict[int, dict[str, Any]] = {}
    raw_nodes: list[dict[str, Any]] = []
    for row in node_rows:
        node = {
            "rowid": int(row["rowid"]),
            "id": row["id"],
            "type": row["type"],
            "project_id": project_id,
            "name": row["name"],
            "parent_id": int(row["parent_id"]),
            "data": _decode_projection_data(
                raw_data=row["data"],
                kind="node",
                scope_ref=row["id"] or str(row["rowid"]),
            ),
        }
        raw_nodes.append(node)
        node_by_rowid[node["rowid"]] = node

    structured: list[dict[str, Any]] = []
    for node in raw_nodes:
        parent = None
        if node["parent_id"] != 0:
            parent_node = node_by_rowid.get(node["parent_id"])
            if parent_node is not None:
                parent = {
                    "rowid": parent_node["rowid"],
                    "id": parent_node["id"],
                    "type": parent_node["type"],
                    "name": parent_node["name"],
                }
        structured.append(
            {
                "rowid": node["rowid"],
                "id": node["id"],
                "type": node["type"],
                "project_id": node["project_id"],
                "name": node["name"],
                "parent": parent,
                "data": node["data"],
            }
        )
    return structured


def _count_children_by_parent(nodes: list[dict[str, Any]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for node in nodes:
        parent = node.get("parent")
        if parent is None:
            continue
        parent_rowid = int(parent["rowid"])
        counts[parent_rowid] = counts.get(parent_rowid, 0) + 1
    return counts


def _split_projection_key(projection_key: str) -> tuple[str, str]:
    if "::" not in projection_key:
        return projection_key, "project"
    kind, scope_ref = projection_key.split("::", 1)
    return kind, scope_ref


def _normalize_projection_storage_error(
    *,
    exc: sqlite3.Error,
    db_path: Path,
    project_id: str,
    action: str,
) -> CliError:
    return CliError(
        code="UNKNOWN",
        message=f"Failed to {action} for project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and projection metadata.",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
