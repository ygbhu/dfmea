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
from dfmea_cli.services.trace import TraceResult, trace_causes, trace_effects


trace_app = typer.Typer(help="Trace commands.")


@trace_app.command("causes")
def trace_causes_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str | None = typer.Option(None, "--fm"),
    depth: int = typer.Option(10, "--depth"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_trace_command(
        command_name="trace causes",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: trace_causes(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=_require_option(fm, option_name="fm", command_name="trace causes"),
            depth=depth,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@trace_app.command("effects")
def trace_effects_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str | None = typer.Option(None, "--fm"),
    depth: int = typer.Option(10, "--depth"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_trace_command(
        command_name="trace effects",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: trace_effects(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=_require_option(fm, option_name="fm", command_name="trace effects"),
            depth=depth,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


def _require_option(value: str | None, *, option_name: str, command_name: str) -> str:
    if value is not None:
        return value
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"Command '{command_name}' requires option '--{option_name}'.",
        target={"option": option_name},
        suggested_action=f"Provide --{option_name} and retry the command.",
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


def _run_trace_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], TraceResult],
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
    except sqlite3.Error:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=CliError(
                code="UNKNOWN",
                message="Trace command failed due to a SQLite error.",
                target={"db": meta["db"], "project_id": meta.get("project_id")},
                suggested_action="Retry the command. If it persists, inspect SQLite state and database integrity.",
            ),
            meta=meta,
        )

    payload = success_result(command=command_name, data=result.data, meta=meta)
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")
