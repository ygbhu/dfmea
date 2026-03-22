from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, NoReturn

import typer

from dfmea_cli.contracts import failure_result, success_result
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import CliError
from dfmea_cli.output import OutputFormat, emit_payload
from dfmea_cli.resolve import ResolvedProjectContext, resolve_project_context
from dfmea_cli.services.query import (
    QueryResult,
    query_actions,
    query_by_ap,
    query_by_severity,
    query_get,
    query_list,
    query_search,
    query_summary,
)


query_app = typer.Typer(help="Query commands.")


@query_app.command("get")
def query_get_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node: str | None = typer.Option(None, "--node"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query get",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_get(
            db_path=context.db_path,
            project_id=context.project_id,
            node_ref=_require_option(
                node, option_name="node", command_name="query get"
            ),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@query_app.command("list")
def query_list_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node_type: str | None = typer.Option(None, "--type"),
    parent: str | None = typer.Option(None, "--parent"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query list",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_list(
            db_path=context.db_path,
            project_id=context.project_id,
            node_type=_require_option(
                node_type,
                option_name="type",
                command_name="query list",
            ),
            parent_ref=parent,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@query_app.command("search")
def query_search_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    keyword: str | None = typer.Option(None, "--keyword"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query search",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_search(
            db_path=context.db_path,
            project_id=context.project_id,
            keyword=_require_option(
                keyword,
                option_name="keyword",
                command_name="query search",
            ),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@query_app.command("summary")
def query_summary_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    comp: str | None = typer.Option(None, "--comp"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query summary",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_summary(
            db_path=context.db_path,
            project_id=context.project_id,
            comp_ref=_require_option(
                comp, option_name="comp", command_name="query summary"
            ),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@query_app.command("by-ap")
def query_by_ap_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    ap: str | None = typer.Option(None, "--ap"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query by-ap",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_by_ap(
            db_path=context.db_path,
            project_id=context.project_id,
            ap=_require_option(ap, option_name="ap", command_name="query by-ap"),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@query_app.command("by-severity")
def query_by_severity_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    gte: str | None = typer.Option(None, "--gte"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query by-severity",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_by_severity(
            db_path=context.db_path,
            project_id=context.project_id,
            gte=_parse_int_option(
                gte,
                option_name="gte",
                command_name="query by-severity",
            ),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@query_app.command("actions")
def query_actions_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    status: str | None = typer.Option(None, "--status"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_query_command(
        command_name="query actions",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: query_actions(
            db_path=context.db_path,
            project_id=context.project_id,
            status=_require_option(
                status,
                option_name="status",
                command_name="query actions",
            ),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


def _emit_failure(
    *,
    command_name: str,
    output_format: OutputFormat,
    error: CliError,
    meta: dict,
) -> NoReturn:
    payload = failure_result(command=command_name, errors=[error.to_error()], meta=meta)
    emit_payload(
        payload,
        output_format=output_format,
        quiet=False,
        exit_code=error.resolved_exit_code,
    )
    raise AssertionError("unreachable")


def _require_option(value: str | None, *, option_name: str, command_name: str) -> str:
    if value is not None:
        return value
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"Command '{command_name}' requires option '--{option_name}'.",
        target={"option": option_name},
        suggested_action=f"Provide --{option_name} and retry the command.",
    )


def _parse_int_option(value: str | None, *, option_name: str, command_name: str) -> int:
    resolved = _require_option(
        value, option_name=option_name, command_name=command_name
    )
    try:
        return int(resolved)
    except ValueError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"Option '--{option_name}' must be a valid integer.",
            target={"option": option_name, "value": resolved},
            suggested_action=f"Provide an integer value for --{option_name}.",
        ) from exc


def _run_query_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], QueryResult],
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
    except sqlite3.Error as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=CliError(
                code="UNKNOWN",
                message="Query command failed due to a SQLite error.",
                target={"db": meta["db"], "project_id": meta.get("project_id")},
                suggested_action="Retry the command. If it persists, inspect SQLite state and database integrity.",
            ),
            meta=meta,
        )

    payload = success_result(command=command_name, data=result.data, meta=meta)
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")
