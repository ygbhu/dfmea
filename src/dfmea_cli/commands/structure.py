from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, NoReturn

import typer

from dfmea_cli.contracts import failure_result, success_result
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import CliError
from dfmea_cli.output import OutputFormat, emit_payload
from dfmea_cli.resolve import ResolvedProjectContext, resolve_project_context
from dfmea_cli.services.structure import (
    StructureMutationResult,
    add_structure_node,
    delete_structure_node,
    move_structure_node,
    update_structure_node,
)


structure_app = typer.Typer(help="Structure commands.")


@structure_app.command("add")
def structure_add_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node_type: str = typer.Option(..., "--type"),
    name: str = typer.Option(..., "--name"),
    parent: str | None = typer.Option(None, "--parent"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_structure_command(
        command_name="structure add",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: add_structure_node(
            db_path=context.db_path,
            project_id=context.project_id,
            node_type=node_type,
            name=name,
            parent_ref=parent,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        include_parent=True,
    )


@structure_app.command("update")
def structure_update_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node: str = typer.Option(..., "--node"),
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    metadata: str | None = typer.Option(None, "--metadata"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_structure_command(
        command_name="structure update",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_structure_node(
            db_path=context.db_path,
            project_id=context.project_id,
            node_ref=node,
            name=name,
            description=description,
            metadata=_parse_metadata(metadata),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@structure_app.command("move")
def structure_move_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node: str = typer.Option(..., "--node"),
    parent: str = typer.Option(..., "--parent"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_structure_command(
        command_name="structure move",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: move_structure_node(
            db_path=context.db_path,
            project_id=context.project_id,
            node_ref=node,
            parent_ref=parent,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        include_parent=True,
    )


@structure_app.command("delete")
def structure_delete_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node: str = typer.Option(..., "--node"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_structure_command(
        command_name="structure delete",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: delete_structure_node(
            db_path=context.db_path,
            project_id=context.project_id,
            node_ref=node,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


def _parse_metadata(metadata: str | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Option '--metadata' must be valid JSON.",
            target={"option": "metadata"},
            suggested_action="Provide a JSON object string for --metadata.",
        ) from exc
    if not isinstance(parsed, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message="Option '--metadata' must decode to a JSON object.",
            target={"option": "metadata"},
            suggested_action="Provide a JSON object string for --metadata.",
        )
    return parsed


def _emit_failure(
    *,
    command_name: str,
    output_format: OutputFormat,
    error: CliError,
    meta: dict[str, Any],
) -> NoReturn:
    payload = failure_result(
        command=command_name,
        errors=[error.to_error()],
        meta=meta,
    )
    emit_payload(
        payload,
        output_format=output_format,
        quiet=False,
        exit_code=error.resolved_exit_code,
    )
    raise AssertionError("unreachable")


def _run_structure_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], StructureMutationResult],
    include_parent: bool = False,
) -> NoReturn:
    meta = {
        "db": str(db),
        "project_id": project,
        "busy_timeout_ms": busy_timeout_ms,
        "retry": retry,
    }
    try:
        context = resolve_project_context(
            db_path=db,
            project_id=project,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
        meta = {
            "db": str(context.db_path),
            "project_id": context.project_id,
            "busy_timeout_ms": context.retry_policy.busy_timeout_ms,
            "retry": context.retry_policy.retry,
        }
        result = action(context)
    except CliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=meta,
        )
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=_normalize_structure_command_error(exc=exc, meta=meta),
            meta=meta,
        )

    success_meta = {
        "db": str(result.db_path),
        "project_id": result.project_id,
        "busy_timeout_ms": result.busy_timeout_ms,
        "retry": result.retry,
    }
    data = {
        "project_id": result.project_id,
        "node_id": result.node_id,
        "affected_objects": [
            {"type": result.node_type, "id": result.node_id, "rowid": result.rowid}
        ],
    }
    if include_parent:
        data["parent_id"] = result.parent_id
    payload = success_result(command=command_name, data=data, meta=success_meta)
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _normalize_structure_command_error(
    *, exc: sqlite3.Error | json.JSONDecodeError, meta: dict[str, Any]
) -> CliError:
    if isinstance(exc, sqlite3.Error):
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            return CliError(
                code="DB_BUSY",
                message="Database is busy and retries were exhausted.",
                target={"db": meta["db"]},
                suggested_action="Retry later or increase --busy-timeout-ms and --retry.",
            )
        return CliError(
            code="UNKNOWN",
            message="Structure command failed due to a SQLite error.",
            target={"db": meta["db"], "project_id": meta.get("project_id")},
            suggested_action="Retry the command. If it persists, inspect SQLite state and database integrity.",
        )
    return CliError(
        code="INVALID_REFERENCE",
        message="Structure command encountered malformed JSON data.",
        target={"db": meta["db"], "project_id": meta.get("project_id")},
        suggested_action="Repair malformed JSON inputs or stored node/project data before retrying.",
    )
