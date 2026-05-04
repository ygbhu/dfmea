from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.lifecycle import initialize_dfmea_domain


def init_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="DFMEA analysis display name. Defaults to the project name.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Initialize the DFMEA domain for a local-first quality project."""

    command = "dfmea init"
    try:
        result = initialize_dfmea_domain(
            workspace=workspace,
            project=project,
            name=name,
        )
    except QualityCliError as exc:
        _emit_failure(command=command, error=exc, output_format=output_format)

    write = result.analysis_write
    changed_paths = [str(path) for path in write.changed_paths] if write is not None else []
    payload = success_result(
        command=command,
        data={
            "analysis": {
                "id": result.analysis.resource_id,
                "kind": result.analysis.kind,
                "path": str(result.analysis.path),
                "alreadyInitialized": result.already_initialized,
            },
            "plugin": {
                "id": "dfmea",
                "enabled": True,
                "alreadyEnabled": result.already_enabled,
            },
            "createdDirectories": [str(path) for path in result.created_directories],
            "changedPaths": changed_paths,
            "affectedObjects": [
                {
                    "kind": result.analysis.kind,
                    "id": result.analysis.resource_id,
                    "path": str(result.analysis.path),
                }
            ],
        },
        meta={
            "workspaceRoot": str(result.context.workspace_root),
            "projectSlug": result.context.project.slug,
            "projectRoot": str(result.context.project.root),
            "schemaVersions": {"dfmea": result.context.schema_version},
        },
    )
    emit_payload(payload, output_format, quiet=quiet)


def _emit_failure(
    *,
    command: str,
    error: QualityCliError,
    output_format: OutputFormat,
) -> NoReturn:
    payload = failure_result(command=command, errors=[error.to_error()])
    emit_payload(
        payload,
        output_format,
        quiet=False,
        exit_code=error.resolved_exit_code,
    )
