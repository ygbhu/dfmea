from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import normalize_retry_policy, resolve_node_reference
from dfmea_cli.services.query import _get_structured_node


@dataclass(frozen=True, slots=True)
class TraceResult:
    db_path: Path
    project_id: str
    data: dict[str, Any]
    busy_timeout_ms: int
    retry: int


def trace_causes(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    depth: int,
    busy_timeout_ms: int,
    retry: int,
) -> TraceResult:
    return _run_trace_operation(
        db_path=db_path,
        project_id=project_id,
        fm_ref=fm_ref,
        depth=depth,
        source_type="FC",
        direction="causes",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def trace_effects(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    depth: int,
    busy_timeout_ms: int,
    retry: int,
) -> TraceResult:
    return _run_trace_operation(
        db_path=db_path,
        project_id=project_id,
        fm_ref=fm_ref,
        depth=depth,
        source_type="FE",
        direction="effects",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def _run_trace_operation(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    depth: int,
    source_type: str,
    direction: str,
    busy_timeout_ms: int,
    retry: int,
) -> TraceResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    if depth < 0:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Option '--depth' must be a non-negative integer.",
            target={"option": "depth", "value": depth},
            suggested_action="Provide 0 or a larger integer for --depth.",
        )

    try:
        data = db_helpers.execute_with_retry(
            lambda: _execute_trace_once(
                db_path=resolved_db_path,
                project_id=project_id,
                fm_ref=fm_ref,
                depth=depth,
                source_type=source_type,
                direction=direction,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_trace_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            direction=direction,
        ) from exc

    return TraceResult(
        db_path=resolved_db_path,
        project_id=project_id,
        data=data,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _execute_trace_once(
    *,
    db_path: Path,
    project_id: str,
    fm_ref: str,
    depth: int,
    source_type: str,
    direction: str,
    busy_timeout_ms: int,
) -> dict[str, Any]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)
    conn.row_factory = sqlite3.Row
    try:
        return _trace_chain_with_connection(
            conn,
            project_id=project_id,
            fm_ref=fm_ref,
            depth=depth,
            source_type=source_type,
            direction=direction,
        )
    finally:
        conn.close()


def _trace_chain_with_connection(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    fm_ref: str,
    depth: int,
    source_type: str,
    direction: str,
) -> dict[str, Any]:
    root = resolve_node_reference(conn, project_id=project_id, node_ref=fm_ref)
    if root.type != "FM":
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Node '{fm_ref}' must be an FM node.",
            target={"node": fm_ref, "type": root.type},
            suggested_action="Provide an FM id or rowid for trace commands.",
        )

    rows = conn.execute(
        """
        WITH RECURSIVE trace_chain AS (
            SELECT
                root.rowid AS fm_rowid,
                CAST(NULL AS INTEGER) AS via_rowid,
                CAST(NULL AS INTEGER) AS link_target_rowid,
                0 AS depth,
                ',' || CAST(root.rowid AS TEXT) || ',' AS visited_fms,
                printf('%010d', root.rowid) AS order_path
            FROM nodes AS root
            WHERE root.rowid = ?

            UNION ALL

            SELECT
                target.rowid AS fm_rowid,
                source.rowid AS via_rowid,
                link.to_fm_rowid AS link_target_rowid,
                trace_chain.depth + 1 AS depth,
                CASE
                    WHEN target.rowid IS NULL THEN trace_chain.visited_fms
                    ELSE trace_chain.visited_fms || CAST(target.rowid AS TEXT) || ','
                END AS visited_fms,
                trace_chain.order_path
                    || '/'
                    || printf('%010d', source.rowid)
                    || ':'
                    || printf('%010d', link.to_fm_rowid) AS order_path
            FROM trace_chain
            JOIN nodes AS source
                ON source.parent_id = trace_chain.fm_rowid
               AND source.project_id = ?
               AND source.type = ?
            JOIN fm_links AS link
                ON link.from_rowid = source.rowid
            LEFT JOIN nodes AS target
                ON target.rowid = link.to_fm_rowid
               AND target.project_id = ?
               AND target.type = 'FM'
            WHERE trace_chain.depth < ?
              AND (
                    target.rowid IS NULL
                    OR instr(
                        trace_chain.visited_fms,
                        ',' || CAST(target.rowid AS TEXT) || ','
                    ) = 0
                  )
        )
        SELECT fm_rowid, via_rowid, link_target_rowid, depth, order_path
        FROM trace_chain
        ORDER BY depth, order_path
        """,
        (root.rowid, project_id, source_type, project_id, depth),
    ).fetchall()

    seen_fm_rowids: set[int] = set()
    chain: list[dict[str, Any]] = []
    for row in rows:
        if row["fm_rowid"] is None:
            raise CliError(
                code="INVALID_REFERENCE",
                message=(
                    "Trace traversal encountered a dangling fm_links target while "
                    f"walking {direction}."
                ),
                target={
                    "from_rowid": int(row["via_rowid"]),
                    "to_fm_rowid": int(row["link_target_rowid"]),
                    "project_id": project_id,
                },
                suggested_action=(
                    "Repair the dangling fm_links target or restore the missing FM node before retrying the trace command."
                ),
            )

        fm_rowid = int(row["fm_rowid"])
        if fm_rowid in seen_fm_rowids:
            continue
        seen_fm_rowids.add(fm_rowid)

        via = None
        if row["via_rowid"] is not None:
            via = _get_structured_node(
                conn,
                project_id=project_id,
                node_ref=str(int(row["via_rowid"])),
            )

        chain.append(
            {
                "depth": int(row["depth"]),
                "fm": _get_structured_node(
                    conn,
                    project_id=project_id,
                    node_ref=str(fm_rowid),
                ),
                "via": via,
            }
        )

    return {
        "project_id": project_id,
        "direction": direction,
        "target_fm": {"id": root.id, "rowid": root.rowid},
        "depth_limit": depth,
        "chain": chain,
    }


def _normalize_trace_storage_error(
    *, exc: sqlite3.Error, db_path: Path, project_id: str, direction: str
) -> CliError:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return DbBusyError(db_path=db_path)
    if "no such table" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message="Database does not expose the expected DFMEA schema.",
            target={"db": str(db_path)},
            suggested_action="Initialize a valid DFMEA database before running trace commands.",
        )
    return CliError(
        code="UNKNOWN",
        message=f"Trace {direction} failed in project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and SQLite state.",
    )
