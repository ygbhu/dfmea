from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy


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
    busy_timeout_ms: int,
) -> list[dict[str, Any]]:
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
