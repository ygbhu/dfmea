from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from dfmea_cli.contracts import failure_result, success_result
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import CliError
from dfmea_cli.output import OutputFormat, emit_payload
from dfmea_cli.resolve import resolve_project_context
from dfmea_cli.services.projections import get_projection_status, rebuild_projections


projection_app = typer.Typer(help="Projection management commands.")


@projection_app.command("status")
def projection_status_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
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
        result = get_projection_status(
            db_path=context.db_path,
            project_id=context.project_id,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        )
    except CliError as exc:
        _emit_failure(
            command_name="projection status",
            output_format=output_format,
            error=exc,
            meta=meta,
        )

    payload = success_result(
        command="projection status",
        data=result.data,
        meta=meta,
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)


@projection_app.command("rebuild")
def projection_rebuild_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
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
        result = rebuild_projections(
            db_path=context.db_path,
            project_id=context.project_id,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        )
    except CliError as exc:
        _emit_failure(
            command_name="projection rebuild",
            output_format=output_format,
            error=exc,
            meta=meta,
        )

    payload = success_result(
        command="projection rebuild",
        data=result.data,
        meta=meta,
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)


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
