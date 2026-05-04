from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import (
    OutputFormat,
    emit_payload,
    failure_result,
    validation_result,
)
from quality_core.validation.engine import validate_project
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project
from quality_methods.dfmea.validators import validate_dfmea_project


def validate_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Validate DFMEA project source resources."""

    command = "dfmea validate"
    context: DfmeaProjectContext | None = None
    try:
        context = load_initialized_dfmea_project(workspace=workspace, project=project)
        report = validate_project(
            project=context.project,
            plugin_validators={"dfmea": validate_dfmea_project},
        )
    except QualityCliError as exc:
        _emit_failure(
            command_name=command,
            error=exc,
            output_format=output_format,
            meta=_meta(context=context),
        )

    payload = validation_result(
        command=command,
        data=report.to_data(),
        ok=report.ok,
        meta={
            **_meta(context=context),
            "schemaVersions": report.schema_versions,
        },
    )
    emit_payload(
        payload,
        output_format,
        quiet=quiet,
        exit_code=0 if report.ok else 3,
    )


def _emit_failure(
    *,
    command_name: str,
    error: QualityCliError,
    output_format: OutputFormat,
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
