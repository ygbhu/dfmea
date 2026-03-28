from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy
from dfmea_cli.services.projections import load_projection


@dataclass(frozen=True, slots=True)
class ExportMarkdownResult:
    db_path: Path
    project_id: str
    output_dir: Path
    files: list[dict[str, Any]]
    busy_timeout_ms: int
    retry: int


def export_markdown(
    *,
    db_path: str | Path,
    project_id: str,
    out_dir: str | Path,
    layout: str,
    busy_timeout_ms: int,
    retry: int,
) -> ExportMarkdownResult:
    resolved_db_path = Path(db_path)
    resolved_out_dir = Path(out_dir)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        files = db_helpers.execute_with_retry(
            lambda: _export_markdown_once(
                db_path=resolved_db_path,
                project_id=project_id,
                out_dir=resolved_out_dir,
                layout=layout,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_export_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
        ) from exc

    return ExportMarkdownResult(
        db_path=resolved_db_path,
        project_id=project_id,
        output_dir=resolved_out_dir.resolve(),
        files=files,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _export_markdown_once(
    *,
    db_path: Path,
    project_id: str,
    out_dir: Path,
    layout: str,
    busy_timeout_ms: int,
) -> list[dict[str, Any]]:
    if layout not in {"ledger", "review"}:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Unsupported export layout '{layout}'.",
            target={"layout": layout},
            suggested_action="Use --layout ledger or --layout review.",
        )

    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    conn.row_factory = sqlite3.Row
    try:
        project_row = conn.execute(
            "SELECT id, name, data FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if project_row is None:
            raise CliError(
                code="INVALID_REFERENCE",
                message=f"Project '{project_id}' does not exist in the database.",
                target={"project_id": project_id},
                suggested_action="Provide a valid project id for export.",
            )

        node_rows = conn.execute(
            """
            SELECT rowid, id, type, parent_id, project_id, name, data
            FROM nodes
            WHERE project_id = ?
            ORDER BY rowid
            """,
            (project_id,),
        ).fetchall()
        link_rows = conn.execute(
            "SELECT from_rowid, to_fm_rowid FROM fm_links ORDER BY from_rowid, to_fm_rowid"
        ).fetchall()
    finally:
        conn.close()

    if out_dir.exists() and not out_dir.is_dir():
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Output path '{out_dir}' must be a directory.",
            target={"out": str(out_dir)},
            suggested_action="Provide a directory path for --out.",
        )

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CliError(
            code="UNKNOWN",
            message=f"Failed to create output directory '{out_dir}'.",
            target={"out": str(out_dir)},
            suggested_action="Ensure the output directory is writable and retry export.",
        ) from exc

    if layout == "review":
        return _export_review_markdown(
            db_path=db_path,
            project_id=project_id,
            out_dir=out_dir,
            busy_timeout_ms=busy_timeout_ms,
        )

    export_path = (out_dir / f"{project_id}.md").resolve()
    content = _render_project_markdown(
        project_id=project_row["id"],
        project_name=project_row["name"],
        project_data=project_row["data"],
        node_rows=node_rows,
        link_rows=link_rows,
    )
    export_path.write_text(content, encoding="utf-8")

    return [
        {
            "path": str(export_path),
            "kind": "project_markdown",
            "bytes": export_path.stat().st_size,
        }
    ]


def _export_review_markdown(
    *,
    db_path: Path,
    project_id: str,
    out_dir: Path,
    busy_timeout_ms: int,
) -> list[dict[str, Any]]:
    project_root = (out_dir / project_id).resolve()
    components_dir = project_root / "components"
    functions_dir = project_root / "functions"
    actions_dir = project_root / "actions"
    components_dir.mkdir(parents=True, exist_ok=True)
    functions_dir.mkdir(parents=True, exist_ok=True)
    actions_dir.mkdir(parents=True, exist_ok=True)

    project_map = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="project_map",
        scope_ref="project",
        busy_timeout_ms=busy_timeout_ms,
        retry=0,
    )
    action_backlog = load_projection(
        db_path=db_path,
        project_id=project_id,
        kind="action_backlog",
        scope_ref="project",
        busy_timeout_ms=busy_timeout_ms,
        retry=0,
    )

    component_ids = [
        item.get("id")
        for item in project_map.data.get("structure", [])
        if item.get("type") == "COMP" and item.get("id")
    ]
    if not component_ids:
        component_ids = [
            item.get("scope_ref")
            for item in _list_projection_scope_refs(
                db_path=db_path,
                project_id=project_id,
                kind="component_bundle",
                busy_timeout_ms=busy_timeout_ms,
            )
        ]

    function_ids = [
        item.get("scope_ref")
        for item in _list_projection_scope_refs(
            db_path=db_path,
            project_id=project_id,
            kind="function_dossier",
            busy_timeout_ms=busy_timeout_ms,
        )
    ]

    index_path = project_root / "index.md"
    index_content = _render_review_index(
        project_id=project_id,
        project_map=project_map.data,
        component_ids=component_ids,
        function_ids=function_ids,
    )
    index_path.write_text(index_content, encoding="utf-8")

    files = [
        {
            "path": str(index_path),
            "kind": "review_index_markdown",
            "bytes": index_path.stat().st_size,
        }
    ]

    for comp_id in component_ids:
        if comp_id is None:
            continue
        bundle = load_projection(
            db_path=db_path,
            project_id=project_id,
            kind="component_bundle",
            scope_ref=comp_id,
            busy_timeout_ms=busy_timeout_ms,
            retry=0,
        )
        component_path = components_dir / f"{comp_id}.md"
        component_path.write_text(
            _render_component_bundle_markdown(bundle.data), encoding="utf-8"
        )
        files.append(
            {
                "path": str(component_path),
                "kind": "component_review_markdown",
                "bytes": component_path.stat().st_size,
            }
        )

    for fn_id in function_ids:
        if fn_id is None:
            continue
        dossier = load_projection(
            db_path=db_path,
            project_id=project_id,
            kind="function_dossier",
            scope_ref=fn_id,
            busy_timeout_ms=busy_timeout_ms,
            retry=0,
        )
        function_path = functions_dir / f"{fn_id}.md"
        function_path.write_text(
            _render_function_dossier_markdown(dossier.data), encoding="utf-8"
        )
        files.append(
            {
                "path": str(function_path),
                "kind": "function_review_markdown",
                "bytes": function_path.stat().st_size,
            }
        )

    open_actions_path = actions_dir / "open.md"
    open_actions_path.write_text(
        _render_open_actions_markdown(action_backlog.data), encoding="utf-8"
    )
    files.append(
        {
            "path": str(open_actions_path),
            "kind": "open_actions_markdown",
            "bytes": open_actions_path.stat().st_size,
        }
    )

    return files


def _list_projection_scope_refs(
    *,
    db_path: Path,
    project_id: str,
    kind: str,
    busy_timeout_ms: int,
) -> list[dict[str, Any]]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    try:
        rows = conn.execute(
            "SELECT scope_ref FROM derived_views WHERE project_id = ? AND kind = ? ORDER BY scope_ref",
            (project_id, kind),
        ).fetchall()
    finally:
        conn.close()
    return [{"scope_ref": row[0]} for row in rows]


def _render_review_index(
    *,
    project_id: str,
    project_map: dict[str, Any],
    component_ids: list[str | None],
    function_ids: list[str | None],
) -> str:
    counts = project_map.get("counts", {})
    lines = [
        f"# DFMEA Review Export: {project_id}",
        "",
        f"- project_id: `{project_id}`",
        f"- functions: {counts.get('functions', 0)}",
        f"- failure_modes: {counts.get('failure_modes', 0)}",
        f"- open_actions: {counts.get('open_actions', 0)}",
        "",
        "## Component Reviews",
        "",
    ]
    for comp_id in component_ids:
        if comp_id:
            lines.append(f"- [`{comp_id}`](components/{comp_id}.md)")
    if not [comp_id for comp_id in component_ids if comp_id]:
        lines.append("- none")
    lines.extend(["", "## Function Dossiers", ""])
    for fn_id in function_ids:
        if fn_id:
            lines.append(f"- [`{fn_id}`](functions/{fn_id}.md)")
    if not [fn_id for fn_id in function_ids if fn_id]:
        lines.append("- none")
    lines.extend(["", "## Action Views", "", "- [Open Actions](actions/open.md)"])
    return "\n".join(lines).rstrip() + "\n"


def _render_component_bundle_markdown(bundle: dict[str, Any]) -> str:
    component = bundle.get("component", {})
    counts = bundle.get("counts", {})
    functions = bundle.get("functions", [])
    high_ap = sum(1 for fn in functions if fn.get("actions", 0) > 0)
    open_action_ids = [
        action_id for fn in functions for action_id in fn.get("open_action_ids", [])
    ]
    lines = [
        f"# Component Review: {component.get('id', 'unknown')}",
        "",
        f"- component_id: `{component.get('id', '')}`",
        f"- component_rowid: {component.get('rowid', '')}",
        f"- component_name: `{component.get('name', '')}`",
        f"- functions: {counts.get('functions', 0)}",
        f"- failure_modes: {counts.get('failure_modes', 0)}",
        f"- actions: {counts.get('actions', 0)}",
        f"- high_ap: {high_ap}",
        f"- severity_gte_7: {high_ap}",
        f"- open_action_ids: {', '.join(open_action_ids) if open_action_ids else 'none'}",
        "- [Back to index](../index.md)",
        "",
        "## Functions",
        "",
    ]
    for fn in functions:
        lines.append(
            f"- [`{fn.get('id')}`](../functions/{fn.get('id')}.md) (rowid {fn.get('rowid')}) - {fn.get('name', '')}"
        )
    if not functions:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _render_function_dossier_markdown(dossier: dict[str, Any]) -> str:
    function = dossier.get("function", {})
    counts = dossier.get("counts", {})
    parent = function.get("parent") or {}
    failure_modes = dossier.get("failure_modes", [])
    open_actions = sum(
        1
        for card in failure_modes
        for action in card.get("actions", [])
        if action.get("data", {}).get("status") != "completed"
    )
    lines = [
        f"# Function Dossier: {function.get('id', 'unknown')}",
        "",
        f"- function_id: `{function.get('id', '')}`",
        f"- function_rowid: {function.get('rowid', '')}",
        f"- function_name: `{function.get('name', '')}`",
        f"- parent_component: `{parent.get('id', '')}`",
        f"- requirements: {counts.get('requirements', 0)}",
        f"- characteristics: {counts.get('characteristics', 0)}",
        f"- failure_modes: {counts.get('failure_modes', 0)}",
        f"- open_actions: {open_actions}",
        f"- component_review: [`{parent.get('id', '')}`](../components/{parent.get('id', '')}.md)",
        "- [Back to index](../index.md)",
        "",
        "## Failure Modes",
        "",
    ]
    for card in failure_modes:
        fm = card.get("fm", {})
        lines.append(
            f"- `{fm.get('id')}` (rowid {fm.get('rowid')}) - {fm.get('name', '')}"
        )
        actions = card.get("actions", [])
        if actions:
            for action in actions:
                lines.append(
                    f"  - action `{action.get('id')}` status `{action.get('data', {}).get('status', '')}`"
                )
    if not failure_modes:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _render_open_actions_markdown(action_backlog: dict[str, Any]) -> str:
    items = [
        item
        for item in action_backlog.get("items", [])
        if item.get("status") != "completed"
    ]
    lines = ["# Open Actions", "", "- [Back to index](../index.md)", ""]
    for item in items:
        fm = item.get("fm") or {}
        fn = item.get("function") or {}
        comp = item.get("component") or {}
        lines.append(
            f"- `{item.get('id')}` (rowid {item.get('rowid')}) - owner `{item.get('owner', '')}` due `{item.get('due', '')}` - FM `{fm.get('id', '')}` / FN `{fn.get('id', '')}` / COMP `{comp.get('id', '')}`"
        )
    if not items:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _render_project_markdown(
    *,
    project_id: str,
    project_name: str,
    project_data: str | None,
    node_rows: list[sqlite3.Row],
    link_rows: list[sqlite3.Row],
) -> str:
    nodes = [_row_to_node(row) for row in node_rows]
    node_by_rowid = {node["rowid"]: node for node in nodes}
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        children_by_parent.setdefault(int(node["parent_id"]), []).append(node)

    lines = [
        f"# DFMEA Export: {project_id}",
        "",
        f"- project_id: `{project_id}`",
        f"- project_name: `{project_name}`",
        f"- project_data: `{_json_repr(project_data)}`",
        f"- node_count: {len(nodes)}",
        f"- trace_link_count: {len(link_rows)}",
        "",
        "## Hierarchy",
        "",
    ]

    root_nodes = children_by_parent.get(0, [])
    if root_nodes:
        for root in root_nodes:
            lines.extend(
                _render_hierarchy_lines(
                    node=root,
                    children_by_parent=children_by_parent,
                    depth=0,
                )
            )
    else:
        lines.append("- none")

    orphan_nodes = [
        node
        for node in nodes
        if int(node["parent_id"]) != 0 and int(node["parent_id"]) not in node_by_rowid
    ]
    if orphan_nodes:
        lines.extend(["", "## Orphans", ""])
        for node in orphan_nodes:
            lines.append(
                f"- {_node_label(node)} with missing parent rowid {int(node['parent_id'])}"
            )

    lines.extend(["", "## Node Ledger", ""])
    if nodes:
        for node in nodes:
            lines.extend(
                [
                    f"### {_node_label(node)}",
                    "",
                    f"- type: `{node['type']}`",
                    f"- parent: `{_parent_label(node, node_by_rowid)}`",
                    f"- name: `{node['name'] or ''}`",
                    f"- data: `{_json_repr(node['data'])}`",
                    "",
                ]
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Trace Links", ""])
    if link_rows:
        for row in link_rows:
            from_rowid = int(row["from_rowid"])
            to_fm_rowid = int(row["to_fm_rowid"])
            lines.append(
                "- "
                f"{_node_ref(node_by_rowid.get(from_rowid), fallback=f'rowid {from_rowid}')}"
                " -> "
                f"{_node_ref(node_by_rowid.get(to_fm_rowid), fallback=f'rowid {to_fm_rowid}')}"
            )
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _render_hierarchy_lines(
    *,
    node: dict[str, Any],
    children_by_parent: dict[int, list[dict[str, Any]]],
    depth: int,
) -> list[str]:
    indent = "  " * depth
    lines = [
        f"{indent}- {_node_label(node)} - {node['name'] or ''}".rstrip(),
        f"{indent}  - data: `{_json_repr(node['data'])}`",
    ]
    for child in children_by_parent.get(int(node["rowid"]), []):
        lines.extend(
            _render_hierarchy_lines(
                node=child,
                children_by_parent=children_by_parent,
                depth=depth + 1,
            )
        )
    return lines


def _row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "rowid": int(row["rowid"]),
        "id": row["id"],
        "type": row["type"],
        "parent_id": int(row["parent_id"]),
        "project_id": row["project_id"],
        "name": row["name"],
        "data": _decode_for_export(row["data"]),
    }


def _decode_for_export(raw_data: str | None) -> Any:
    try:
        return json.loads(raw_data or "{}")
    except json.JSONDecodeError:
        return {"_raw_data": raw_data, "_export_warning": "malformed_json"}


def _json_repr(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _node_label(node: dict[str, Any]) -> str:
    if node["id"] is not None:
        return f"`{node['id']}` (rowid {int(node['rowid'])})"
    return f"`{node['type']} rowid {int(node['rowid'])}`"


def _node_ref(node: dict[str, Any] | None, *, fallback: str) -> str:
    if node is None:
        return f"`{fallback}`"
    if node["id"] is not None:
        return f"`{node['id']}` (rowid {int(node['rowid'])})"
    return f"`{node['type']} rowid {int(node['rowid'])}`"


def _parent_label(
    node: dict[str, Any], node_by_rowid: dict[int, dict[str, Any]]
) -> str:
    parent_id = int(node["parent_id"])
    if parent_id == 0:
        return "ROOT"
    return _node_ref(node_by_rowid.get(parent_id), fallback=f"rowid {parent_id}")


def _normalize_export_storage_error(
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
            suggested_action="Initialize a valid DFMEA database before running export markdown.",
        )
    return CliError(
        code="UNKNOWN",
        message=f"Failed to export markdown for project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and filesystem permissions.",
    )
