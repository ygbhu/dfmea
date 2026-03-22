from __future__ import annotations

from pathlib import Path

import typer

from dfmea_cli.contracts import failure_result, success_result
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import CliError
from dfmea_cli.output import OutputFormat, emit_payload
from dfmea_cli.services.projects import initialize_project


def init_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False),
    project: str = typer.Option(..., "--project"),
    name: str = typer.Option(..., "--name"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    """Initialize a DFMEA project database."""

    try:
        result = initialize_project(
            db_path=db,
            project_id=project,
            name=name,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
    except CliError as exc:
        payload = failure_result(
            command="init",
            errors=[exc.to_error()],
            meta={
                "db": str(db),
                "project_id": project,
                "busy_timeout_ms": busy_timeout_ms,
                "retry": retry,
            },
        )
        emit_payload(
            payload,
            output_format=output_format,
            quiet=False,
            exit_code=exc.resolved_exit_code,
        )

    payload = success_result(
        command="init",
        data={
            "project_id": result.project_id,
            "affected_objects": [{"type": "PROJECT", "id": result.project_id}],
        },
        meta={
            "db": str(result.db_path),
            "project_id": result.project_id,
            "busy_timeout_ms": result.busy_timeout_ms,
            "retry": result.retry,
        },
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)
