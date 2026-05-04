from __future__ import annotations

from pathlib import Path
from typing import Callable, NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.exports import DfmeaExportResult, export_markdown, export_risk_csv
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project

export_app = typer.Typer(help="Export commands.")


def _workspace_option():
    return typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    )


@export_app.command("markdown")
def export_markdown_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    out: Path | None = typer.Option(None, "--out", file_okay=False, resolve_path=True),
    layout: str = typer.Option("review", "--layout"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Export project data as Markdown."""

    _run_export_command(
        command_name="dfmea export markdown",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: export_markdown(
            project=context.project,
            out_dir=out,
            layout=layout,
        ),
    )


@export_app.command("risk-csv")
def export_risk_csv_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    out: Path | None = typer.Option(None, "--out", file_okay=False, resolve_path=True),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_export_command(
        command_name="dfmea export risk-csv",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: export_risk_csv(
            project=context.project,
            out_dir=out,
        ),
    )


def _run_export_command(
    *,
    command_name: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action: Callable[[DfmeaProjectContext], DfmeaExportResult],
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
        data={
            "projectSlug": result.project.slug,
            "outputDir": str(result.output_dir),
            "files": list(result.files),
            "generatedOutputs": result.generated_outputs,
        },
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
