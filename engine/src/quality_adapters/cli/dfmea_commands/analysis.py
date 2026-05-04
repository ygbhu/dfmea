from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Callable, NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.analysis_service import (
    AnalysisMutationResult,
    add_characteristic,
    add_failure_chain,
    add_failure_mode,
    add_function,
    add_requirement,
    delete_analysis_node,
    delete_characteristic,
    delete_function,
    delete_requirement,
    link_fm_characteristic,
    link_fm_requirement,
    unlink_fm_characteristic,
    unlink_fm_requirement,
    update_action,
    update_action_status,
    update_characteristic,
    update_failure_cause,
    update_failure_effect,
    update_failure_mode,
    update_function,
    update_requirement,
    update_risk,
)
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project

analysis_app = typer.Typer(help="Analysis commands.")

_REPEATED_GROUPING_HELP = (
    "Repeated FE/FC/ACT flags pair by occurrence order. Use --input for complex failure chains."
)


def _workspace_option():
    return typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    )


@analysis_app.command("add-function")
def add_function_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    component: str | None = typer.Option(None, "--component", "--comp"),
    title: str | None = typer.Option(None, "--title", "--name"),
    description: str | None = typer.Option(None, "--description"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis add-function",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_function(
            project=context.project,
            component_ref=_required_option(component, "--component"),
            title=_required_option(title, "--title"),
            description=description,
        ),
    )


@analysis_app.command("update-function")
def update_function_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    function_ref: str | None = typer.Option(None, "--function", "--fn"),
    title: str | None = typer.Option(None, "--title", "--name"),
    description: str | None = typer.Option(None, "--description"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-function",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_function(
            project=context.project,
            function_ref=_required_option(function_ref, "--function"),
            title=title,
            description=description,
        ),
    )


@analysis_app.command("delete-function")
def delete_function_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    function_ref: str | None = typer.Option(None, "--function", "--fn"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis delete-function",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: delete_function(
            project=context.project,
            function_ref=_required_option(function_ref, "--function"),
        ),
    )


@analysis_app.command("add-requirement")
def add_requirement_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    function_ref: str | None = typer.Option(None, "--function", "--fn"),
    text: str = typer.Option(..., "--text"),
    source: str | None = typer.Option(None, "--source"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis add-requirement",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_requirement(
            project=context.project,
            function_ref=_required_option(function_ref, "--function"),
            text=text,
            source=source,
        ),
    )


@analysis_app.command("update-requirement")
def update_requirement_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    requirement: str | None = typer.Option(None, "--requirement", "--req"),
    text: str | None = typer.Option(None, "--text"),
    source: str | None = typer.Option(None, "--source"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-requirement",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_requirement(
            project=context.project,
            requirement_ref=_required_option(requirement, "--requirement"),
            text=text,
            source=source,
        ),
    )


@analysis_app.command("delete-requirement")
def delete_requirement_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    requirement: str | None = typer.Option(None, "--requirement", "--req"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis delete-requirement",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: delete_requirement(
            project=context.project,
            requirement_ref=_required_option(requirement, "--requirement"),
        ),
    )


@analysis_app.command("add-characteristic")
def add_characteristic_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    function_ref: str | None = typer.Option(None, "--function", "--fn"),
    text: str = typer.Option(..., "--text"),
    value: str | None = typer.Option(None, "--value"),
    unit: str | None = typer.Option(None, "--unit"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis add-characteristic",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_characteristic(
            project=context.project,
            function_ref=_required_option(function_ref, "--function"),
            text=text,
            value=value,
            unit=unit,
        ),
    )


@analysis_app.command("update-characteristic")
def update_characteristic_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    characteristic: str | None = typer.Option(None, "--characteristic", "--char"),
    text: str | None = typer.Option(None, "--text"),
    value: str | None = typer.Option(None, "--value"),
    unit: str | None = typer.Option(None, "--unit"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-characteristic",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_characteristic(
            project=context.project,
            characteristic_ref=_required_option(characteristic, "--characteristic"),
            text=text,
            value=value,
            unit=unit,
        ),
    )


@analysis_app.command("delete-characteristic")
def delete_characteristic_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    characteristic: str | None = typer.Option(None, "--characteristic", "--char"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis delete-characteristic",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: delete_characteristic(
            project=context.project,
            characteristic_ref=_required_option(characteristic, "--characteristic"),
        ),
    )


@analysis_app.command("add-failure-mode")
def add_failure_mode_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    function_ref: str | None = typer.Option(None, "--function", "--fn"),
    title: str | None = typer.Option(None, "--title", "--description"),
    severity: int = typer.Option(..., "--severity"),
    requirement: Annotated[
        list[str] | None,
        typer.Option("--requirement", "--violates-req"),
    ] = None,
    characteristic: Annotated[
        list[str] | None,
        typer.Option("--characteristic", "--related-char"),
    ] = None,
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis add-failure-mode",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_failure_mode(
            project=context.project,
            function_ref=_required_option(function_ref, "--function"),
            title=_required_option(title, "--title"),
            severity=severity,
            requirement_refs=list(requirement or []),
            characteristic_refs=list(characteristic or []),
        ),
    )


@analysis_app.command(
    "add-failure-chain",
    help="Create an FM under an FN and optionally create FE, FC, and ACT children.",
)
def add_failure_chain_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    function_ref: str | None = typer.Option(None, "--function", "--fn"),
    input_path: Path | None = typer.Option(
        None,
        "--input",
        exists=False,
        dir_okay=False,
        readable=True,
        help="Read structured failure-chain JSON from a file.",
    ),
    fm_description: str | None = typer.Option(None, "--fm-description"),
    severity: int | None = typer.Option(None, "--severity"),
    requirement: Annotated[
        list[str] | None,
        typer.Option("--requirement", "--violates-req"),
    ] = None,
    characteristic: Annotated[
        list[str] | None,
        typer.Option("--characteristic", "--related-char"),
    ] = None,
    fe_description: Annotated[
        list[str] | None,
        typer.Option("--fe-description", help=_REPEATED_GROUPING_HELP),
    ] = None,
    fe_level: Annotated[
        list[str] | None,
        typer.Option("--fe-level", help=_REPEATED_GROUPING_HELP),
    ] = None,
    fc_description: Annotated[
        list[str] | None,
        typer.Option("--fc-description", help=_REPEATED_GROUPING_HELP),
    ] = None,
    occurrence: Annotated[
        list[int] | None,
        typer.Option("--occurrence", help=_REPEATED_GROUPING_HELP),
    ] = None,
    detection: Annotated[
        list[int] | None,
        typer.Option("--detection", help=_REPEATED_GROUPING_HELP),
    ] = None,
    ap: Annotated[
        list[str] | None,
        typer.Option("--ap", help=_REPEATED_GROUPING_HELP),
    ] = None,
    act_description: Annotated[
        list[str] | None,
        typer.Option("--act-description", help=_REPEATED_GROUPING_HELP),
    ] = None,
    kind: Annotated[
        list[str] | None,
        typer.Option("--kind", help=_REPEATED_GROUPING_HELP),
    ] = None,
    status: Annotated[
        list[str] | None,
        typer.Option("--status", help=_REPEATED_GROUPING_HELP),
    ] = None,
    owner: Annotated[
        list[str] | None,
        typer.Option("--owner", help=_REPEATED_GROUPING_HELP),
    ] = None,
    due: Annotated[
        list[str] | None,
        typer.Option("--due", help=_REPEATED_GROUPING_HELP),
    ] = None,
    target_causes: Annotated[
        list[str] | None,
        typer.Option(
            "--target-causes",
            help="Comma-separated 1-based FC creation-order indexes for each ACT item.",
        ),
    ] = None,
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis add-failure-chain",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_failure_chain(
            project=context.project,
            function_ref=_required_option(function_ref, "--function"),
            chain_spec=_load_failure_chain_input(
                input_path=input_path,
                fm_description=fm_description,
                severity=severity,
                requirement=list(requirement or []),
                characteristic=list(characteristic or []),
                fe_descriptions=list(fe_description or []),
                fe_levels=list(fe_level or []),
                fc_descriptions=list(fc_description or []),
                occurrences=list(occurrence or []),
                detections=list(detection or []),
                aps=list(ap or []),
                act_descriptions=list(act_description or []),
                kinds=list(kind or []),
                statuses=list(status or []),
                owners=list(owner or []),
                dues=list(due or []),
                target_causes=list(target_causes or []),
            ),
        ),
    )


@analysis_app.command("update-fm")
def update_fm_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    title: str | None = typer.Option(None, "--title", "--description"),
    severity: int | None = typer.Option(None, "--severity"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-fm",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_failure_mode(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
            title=title,
            severity=severity,
        ),
    )


@analysis_app.command("update-fe")
def update_fe_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_effect: str | None = typer.Option(None, "--failure-effect", "--fe"),
    title: str | None = typer.Option(None, "--title", "--description"),
    level: str | None = typer.Option(None, "--level"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-fe",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_failure_effect(
            project=context.project,
            failure_effect_ref=_required_option(failure_effect, "--failure-effect"),
            title=title,
            level=level,
        ),
    )


@analysis_app.command("update-fc")
def update_fc_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_cause: str | None = typer.Option(None, "--failure-cause", "--fc"),
    title: str | None = typer.Option(None, "--title", "--description"),
    occurrence: int | None = typer.Option(None, "--occurrence"),
    detection: int | None = typer.Option(None, "--detection"),
    ap: str | None = typer.Option(None, "--ap"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-fc",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_failure_cause(
            project=context.project,
            failure_cause_ref=_required_option(failure_cause, "--failure-cause"),
            title=title,
            occurrence=occurrence,
            detection=detection,
            ap=ap,
        ),
    )


@analysis_app.command("update-risk")
def update_risk_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    failure_cause: str | None = typer.Option(None, "--failure-cause", "--fc"),
    severity: int | None = typer.Option(None, "--severity"),
    occurrence: int | None = typer.Option(None, "--occurrence"),
    detection: int | None = typer.Option(None, "--detection"),
    ap: str | None = typer.Option(None, "--ap"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-risk",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_risk(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
            failure_cause_ref=failure_cause,
            severity=severity,
            occurrence=occurrence,
            detection=detection,
            ap=ap,
        ),
    )


@analysis_app.command("update-act")
def update_act_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    action_ref: str | None = typer.Option(None, "--action", "--act"),
    title: str | None = typer.Option(None, "--title", "--description"),
    kind: str | None = typer.Option(None, "--kind"),
    status: str | None = typer.Option(None, "--status"),
    owner: str | None = typer.Option(None, "--owner"),
    due: str | None = typer.Option(None, "--due"),
    target_causes: str | None = typer.Option(None, "--target-causes"),
    effectiveness_status: str | None = typer.Option(None, "--effectiveness-status"),
    revised_severity: int | None = typer.Option(None, "--revised-severity"),
    revised_occurrence: int | None = typer.Option(None, "--revised-occurrence"),
    revised_detection: int | None = typer.Option(None, "--revised-detection"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-act",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_action(
            project=context.project,
            action_ref=_required_option(action_ref, "--action"),
            title=title,
            kind=kind,
            status=status,
            owner=owner,
            due=due,
            target_cause_refs=_parse_ref_list(target_causes) if target_causes is not None else None,
            effectiveness_status=effectiveness_status,
            revised_severity=revised_severity,
            revised_occurrence=revised_occurrence,
            revised_detection=revised_detection,
        ),
    )


@analysis_app.command("update-action-status")
def update_action_status_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    action_ref: str | None = typer.Option(None, "--action", "--act"),
    status: str = typer.Option(..., "--status"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis update-action-status",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_action_status(
            project=context.project,
            action_ref=_required_option(action_ref, "--action"),
            status=status,
        ),
    )


@analysis_app.command("link-fm-requirement")
def link_fm_requirement_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    requirement: str | None = typer.Option(None, "--requirement", "--req"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis link-fm-requirement",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: link_fm_requirement(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
            requirement_ref=_required_option(requirement, "--requirement"),
        ),
    )


@analysis_app.command("unlink-fm-requirement")
def unlink_fm_requirement_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    requirement: str | None = typer.Option(None, "--requirement", "--req"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis unlink-fm-requirement",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: unlink_fm_requirement(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
            requirement_ref=_required_option(requirement, "--requirement"),
        ),
    )


@analysis_app.command("link-fm-characteristic")
def link_fm_characteristic_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    characteristic: str | None = typer.Option(None, "--characteristic", "--char"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis link-fm-characteristic",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: link_fm_characteristic(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
            characteristic_ref=_required_option(characteristic, "--characteristic"),
        ),
    )


@analysis_app.command("unlink-fm-characteristic")
def unlink_fm_characteristic_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    failure_mode: str | None = typer.Option(None, "--failure-mode", "--fm"),
    characteristic: str | None = typer.Option(None, "--characteristic", "--char"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis unlink-fm-characteristic",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: unlink_fm_characteristic(
            project=context.project,
            failure_mode_ref=_required_option(failure_mode, "--failure-mode"),
            characteristic_ref=_required_option(characteristic, "--characteristic"),
        ),
    )


@analysis_app.command("delete-node")
def delete_node_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    node: str = typer.Option(..., "--node"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_analysis_command(
        command_name="dfmea analysis delete-node",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: delete_analysis_node(
            project=context.project,
            node_ref=node,
        ),
    )


def _run_analysis_command(
    *,
    command_name: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action: Callable[[DfmeaProjectContext], AnalysisMutationResult],
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
        data=_result_payload(result),
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


def _result_payload(result: AnalysisMutationResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "resource": _resource_payload(result.resource),
        "changedPaths": [str(path) for path in result.changed_paths],
        "affectedObjects": list(result.affected_objects),
    }
    if result.tombstone_paths:
        payload["tombstonePaths"] = [str(path) for path in result.tombstone_paths]
    return payload


def _resource_payload(resource) -> dict[str, Any] | None:
    if resource is None:
        return None
    title = resource.metadata.get("title")
    if not isinstance(title, str):
        title = resource.spec.get("description")
    return {
        "id": resource.resource_id,
        "kind": resource.kind,
        "title": title if isinstance(title, str) else None,
        "path": str(resource.path) if resource.path is not None else None,
    }


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


def _load_failure_chain_input(
    *,
    input_path: Path | None,
    fm_description: str | None,
    severity: int | None,
    requirement: list[str],
    characteristic: list[str],
    fe_descriptions: list[str],
    fe_levels: list[str],
    fc_descriptions: list[str],
    occurrences: list[int],
    detections: list[int],
    aps: list[str],
    act_descriptions: list[str],
    kinds: list[str],
    statuses: list[str],
    owners: list[str],
    dues: list[str],
    target_causes: list[str],
) -> dict[str, Any]:
    if input_path is not None:
        conflicting_flags = [
            name
            for name, value in (
                ("--fm-description", fm_description),
                ("--severity", severity),
                ("--requirement", requirement),
                ("--characteristic", characteristic),
                ("--fe-description", fe_descriptions),
                ("--fe-level", fe_levels),
                ("--fc-description", fc_descriptions),
                ("--occurrence", occurrences),
                ("--detection", detections),
                ("--ap", aps),
                ("--act-description", act_descriptions),
                ("--kind", kinds),
                ("--status", statuses),
                ("--owner", owners),
                ("--due", dues),
                ("--target-causes", target_causes),
            )
            if value not in (None, [])
        ]
        if conflicting_flags:
            raise QualityCliError(
                code="VALIDATION_FAILED",
                message="--input cannot be combined with failure-chain creation flags.",
                target={"input": str(input_path), "conflicts": conflicting_flags},
                suggestion="Use either --input or repeated creation flags.",
            )
        try:
            loaded = json.loads(input_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise QualityCliError(
                code="RESOURCE_NOT_FOUND",
                message=f"Failure-chain input file '{input_path}' was not found.",
                path=str(input_path),
                suggestion="Provide an existing JSON file path for --input.",
            ) from exc
        except json.JSONDecodeError as exc:
            raise QualityCliError(
                code="VALIDATION_FAILED",
                message=f"Failure-chain input file '{input_path}' contains malformed JSON.",
                path=str(input_path),
                suggestion="Fix the JSON file and retry.",
            ) from exc
        if not isinstance(loaded, dict):
            raise QualityCliError(
                code="VALIDATION_FAILED",
                message="Failure-chain input must decode to a JSON object.",
                target={"input": str(input_path)},
                suggestion="Provide an object with fm, fe, fc, and act sections.",
            )
        return loaded

    if fm_description is None or severity is None:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="Repeated-flag mode requires --fm-description and --severity.",
            target={"field": "fm"},
            suggestion="Provide --fm-description and --severity, or use --input.",
        )

    return {
        "fm": {
            "description": fm_description,
            "severity": severity,
            "requirementRefs": requirement,
            "characteristicRefs": characteristic,
        },
        "fe": _group_fe_flags(descriptions=fe_descriptions, levels=fe_levels),
        "fc": _group_fc_flags(
            descriptions=fc_descriptions,
            occurrences=occurrences,
            detections=detections,
            aps=aps,
        ),
        "act": _group_act_flags(
            descriptions=act_descriptions,
            kinds=kinds,
            statuses=statuses,
            owners=owners,
            dues=dues,
            target_causes=target_causes,
        ),
    }


def _group_fe_flags(*, descriptions: list[str], levels: list[str]) -> list[dict[str, Any]]:
    count = max(len(descriptions), len(levels))
    return [
        {
            "description": _required_group_value(
                descriptions,
                index=index,
                field="--fe-description",
                group="FE",
            ),
            "level": _optional_group_value(levels, index=index),
        }
        for index in range(count)
    ]


def _group_fc_flags(
    *,
    descriptions: list[str],
    occurrences: list[int],
    detections: list[int],
    aps: list[str],
) -> list[dict[str, Any]]:
    count = max(len(descriptions), len(occurrences), len(detections), len(aps))
    return [
        {
            "description": _required_group_value(
                descriptions,
                index=index,
                field="--fc-description",
                group="FC",
            ),
            "occurrence": _required_group_value(
                occurrences,
                index=index,
                field="--occurrence",
                group="FC",
            ),
            "detection": _required_group_value(
                detections,
                index=index,
                field="--detection",
                group="FC",
            ),
            "ap": _optional_group_value(aps, index=index),
        }
        for index in range(count)
    ]


def _group_act_flags(
    *,
    descriptions: list[str],
    kinds: list[str],
    statuses: list[str],
    owners: list[str],
    dues: list[str],
    target_causes: list[str],
) -> list[dict[str, Any]]:
    count = max(
        len(descriptions),
        len(kinds),
        len(statuses),
        len(owners),
        len(dues),
        len(target_causes),
    )
    return [
        {
            "description": _required_group_value(
                descriptions,
                index=index,
                field="--act-description",
                group="ACT",
            ),
            "kind": _optional_group_value(kinds, index=index),
            "status": _optional_group_value(statuses, index=index),
            "owner": _optional_group_value(owners, index=index),
            "due": _optional_group_value(dues, index=index),
            "targetCauseIndexes": _parse_int_list(
                _optional_group_value(target_causes, index=index),
                option_name="--target-causes",
            ),
        }
        for index in range(count)
    ]


def _required_group_value(
    values: list[Any],
    *,
    index: int,
    field: str,
    group: str,
) -> Any:
    if index < len(values):
        return values[index]
    raise QualityCliError(
        code="VALIDATION_FAILED",
        message=f"{group} repeated flags require {field} for item {index + 1}.",
        target={"field": field, "group": group, "index": index + 1},
        suggestion=f"Add {field} for {group} item {index + 1}, or use --input.",
    )


def _optional_group_value(values: list[Any], *, index: int) -> Any | None:
    if index < len(values):
        return values[index]
    return None


def _parse_int_list(raw_value: str | None, *, option_name: str) -> list[int]:
    if raw_value is None or raw_value.strip() == "":
        return []
    try:
        return [int(part.strip()) for part in raw_value.split(",") if part.strip()]
    except ValueError as exc:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message=f"{option_name} must be a comma-separated list of integers.",
            target={"option": option_name, "value": raw_value},
            suggestion="Use comma-separated integers like 1 or 1,2.",
        ) from exc


def _parse_ref_list(raw_value: str | None) -> list[str]:
    if raw_value is None or raw_value.strip() == "":
        return []
    refs = [part.strip() for part in raw_value.split(",") if part.strip()]
    if not refs:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="--target-causes must include at least one FC resource ID.",
            target={"option": "--target-causes"},
            suggestion="Use comma-separated FC IDs like FC-001 or FC-001,FC-002.",
        )
    return refs
