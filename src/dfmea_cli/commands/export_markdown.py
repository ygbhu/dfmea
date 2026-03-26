from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from dfmea_cli.contracts import failure_result, success_result
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import CliError
from dfmea_cli.output import OutputFormat, emit_payload
from dfmea_cli.resolve import resolve_project_context
from dfmea_cli.services.export_markdown import export_markdown


export_app = typer.Typer(help="Export commands.")


@export_app.command("markdown")
def export_markdown_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    out: Path = typer.Option(..., "--out", file_okay=False),
    layout: str = typer.Option("ledger", "--layout"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    """Export project data as Markdown."""

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
        result = export_markdown(
            db_path=context.db_path,
            project_id=context.project_id,
            out_dir=out,
            layout=layout,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        )
    except CliError as exc:
        _emit_failure(error=exc, output_format=output_format, meta=meta)

    payload = success_result(
        command="export markdown",
        data={
            "project_id": result.project_id,
            "output_dir": str(result.output_dir),
            "files": result.files,
        },
        meta=meta,
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)


def _emit_failure(
    *,
    error: CliError,
    output_format: OutputFormat,
    meta: dict,
) -> NoReturn:
    payload = failure_result(
        command="export markdown",
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
