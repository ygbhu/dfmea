from __future__ import annotations

from pathlib import Path
from typing import Callable, NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project
from quality_methods.dfmea.query_service import (
    DfmeaQueryResult,
    query_actions,
    query_by_ap,
    query_by_severity,
    query_get,
    query_list,
    query_map,
    query_search,
    query_summary,
)

query_app = typer.Typer(help="Query commands.")


def _workspace_option():
    return typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    )


@query_app.command("get")
def query_get_command(
    resource_id: str = typer.Argument(..., help="Project-local resource ID."),
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query get",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_get(
            project=context.project,
            resource_id=resource_id,
        ),
    )


@query_app.command("list")
def query_list_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    node_type: str | None = typer.Option(None, "--type"),
    parent: str | None = typer.Option(None, "--parent"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query list",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_list(
            project=context.project,
            node_type=_required_option(node_type, "--type"),
            parent_ref=parent,
        ),
    )


@query_app.command("search")
def query_search_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    keyword: str | None = typer.Option(None, "--keyword"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query search",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_search(
            project=context.project,
            keyword=_required_option(keyword, "--keyword"),
        ),
    )


@query_app.command("summary")
def query_summary_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    comp: str | None = typer.Option(None, "--comp", "--component"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query summary",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_summary(
            project=context.project,
            component_ref=_required_option(comp, "--comp"),
        ),
    )


@query_app.command("map")
def query_map_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query map",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_map(project=context.project),
    )


@query_app.command("bundle")
def query_bundle_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    comp: str | None = typer.Option(None, "--comp", "--component"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query bundle",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_summary(
            project=context.project,
            component_ref=_required_option(comp, "--comp"),
        ),
    )


@query_app.command("dossier")
def query_dossier_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    fn: str | None = typer.Option(None, "--fn", "--function"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query dossier",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_list(
            project=context.project,
            node_type="FM",
            parent_ref=_required_option(fn, "--fn"),
        ),
    )


@query_app.command("by-ap")
def query_by_ap_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    ap: str | None = typer.Option(None, "--ap"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query by-ap",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_by_ap(
            project=context.project,
            ap=_required_option(ap, "--ap"),
        ),
    )


@query_app.command("by-severity")
def query_by_severity_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    gte: str | None = typer.Option(None, "--gte"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query by-severity",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_by_severity(
            project=context.project,
            gte=_parse_int_option(gte, "--gte"),
        ),
    )


@query_app.command("actions")
def query_actions_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    status: str | None = typer.Option(None, "--status"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_query_command(
        command_name="dfmea query actions",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: query_actions(
            project=context.project,
            status=_required_option(status, "--status"),
        ),
    )


def _run_query_command(
    *,
    command_name: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action: Callable[[DfmeaProjectContext], DfmeaQueryResult],
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


def _parse_int_option(value: str | None, option_name: str) -> int:
    resolved = _required_option(value, option_name)
    try:
        return int(resolved)
    except ValueError as exc:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message=f"{option_name} must be an integer.",
            target={"option": option_name, "value": resolved},
            suggestion=f"Provide an integer for {option_name}.",
        ) from exc
