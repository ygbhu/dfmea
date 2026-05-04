from __future__ import annotations

from pathlib import Path
from typing import Callable, NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project
from quality_methods.dfmea.projections import (
    DfmeaProjectionResult,
    get_projection_status,
    rebuild_projections,
)

projection_app = typer.Typer(help="Projection management commands.")


def _workspace_option():
    return typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    )


@projection_app.command("status")
def projection_status_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_projection_command(
        command_name="dfmea projection status",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: get_projection_status(project=context.project),
    )


@projection_app.command("rebuild")
def projection_rebuild_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_projection_command(
        command_name="dfmea projection rebuild",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: rebuild_projections(project=context.project),
    )


def _run_projection_command(
    *,
    command_name: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action: Callable[[DfmeaProjectContext], DfmeaProjectionResult],
) -> NoReturn:
    context: DfmeaProjectContext | None = None
    try:
        context = load_initialized_dfmea_project(workspace=workspace, project=project)
        result = action(context)
    except QualityCliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=_meta(context=context),
        )

    payload = success_result(
        command=command_name,
        data=result.data,
        meta={
            **_meta(context=context),
            "schemaVersions": {"dfmea": context.schema_version if context else None},
        },
    )
    emit_payload(payload, output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _emit_failure(
    *,
    command_name: str,
    output_format: OutputFormat,
    error: QualityCliError,
    meta: dict[str, object],
) -> NoReturn:
    payload = failure_result(
        command=command_name,
        errors=[error.to_error()],
        meta=meta,
    )
    emit_payload(
        payload,
        output_format,
        quiet=False,
        exit_code=error.resolved_exit_code,
    )
    raise AssertionError("unreachable")


def _meta(*, context: DfmeaProjectContext | None) -> dict[str, object]:
    if context is None:
        return {}
    return {
        "workspaceRoot": str(context.workspace_root),
        "projectSlug": context.project.slug,
        "projectRoot": str(context.project.root),
    }
