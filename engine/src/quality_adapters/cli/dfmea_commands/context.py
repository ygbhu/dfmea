from __future__ import annotations

from pathlib import Path
from typing import Callable, NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.context_service import DfmeaContextResult, failure_chain_context
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project

context_app = typer.Typer(help="Context bundle commands.")


def _workspace_option():
    return typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    )


@context_app.command("failure-chain")
def failure_chain_context_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_context_command(
        command_name="dfmea context failure-chain",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: failure_chain_context(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
        ),
    )


def _run_context_command(
    *,
    command_name: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action: Callable[[DfmeaProjectContext], DfmeaContextResult],
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
            "freshness": result.freshness,
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


def _required_option(value: str | None, option_name: str) -> str:
    if value is not None and value.strip():
        return value.strip()
    raise QualityCliError(
        code="VALIDATION_FAILED",
        message=f"{option_name} is required.",
        target={"option": option_name},
        suggestion=f"Provide {option_name}.",
    )
