from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, NoReturn

import typer

from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_methods.dfmea.lifecycle import DfmeaProjectContext, load_initialized_dfmea_project
from quality_methods.dfmea.structure_service import (
    StructureMutationResult,
    add_structure_node,
    delete_structure_node,
    move_structure_node,
    update_structure_node,
)

structure_app = typer.Typer(help="Structure commands.")


def _workspace_option():
    return typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    )


@structure_app.command("add-system")
def structure_add_system_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    title: str = typer.Option(..., "--title", help="System title."),
    workspace: Path | None = _workspace_option(),
    description: str | None = typer.Option(None, "--description"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure add-system",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_structure_node(
            project=context.project,
            node_type="SYS",
            title=title,
            description=description,
        ),
    )


@structure_app.command("add-subsystem")
def structure_add_subsystem_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    parent: str = typer.Option(..., "--parent", help="Parent SYS node ID."),
    title: str = typer.Option(..., "--title", help="Subsystem title."),
    workspace: Path | None = _workspace_option(),
    description: str | None = typer.Option(None, "--description"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure add-subsystem",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_structure_node(
            project=context.project,
            node_type="SUB",
            title=title,
            parent_ref=parent,
            description=description,
        ),
        include_parent=True,
    )


@structure_app.command("add-component")
def structure_add_component_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    parent: str = typer.Option(..., "--parent", help="Parent SUB node ID."),
    title: str = typer.Option(..., "--title", help="Component title."),
    workspace: Path | None = _workspace_option(),
    description: str | None = typer.Option(None, "--description"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure add-component",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_structure_node(
            project=context.project,
            node_type="COMP",
            title=title,
            parent_ref=parent,
            description=description,
        ),
        include_parent=True,
    )


@structure_app.command("add")
def structure_add_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    node_type: str = typer.Option(..., "--type", help="SYS, SUB, or COMP."),
    title: str | None = typer.Option(None, "--title", help="Structure node title."),
    name: str | None = typer.Option(None, "--name", help="Alias for --title."),
    parent: str | None = typer.Option(None, "--parent"),
    workspace: Path | None = _workspace_option(),
    description: str | None = typer.Option(None, "--description"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure add",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: add_structure_node(
            project=context.project,
            node_type=node_type,
            title=_resolve_title(title=title, name=name),
            parent_ref=parent,
            description=description,
        ),
        include_parent=True,
    )


@structure_app.command("update")
def structure_update_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    node: str = typer.Option(..., "--node", help="Structure node ID."),
    title: str | None = typer.Option(None, "--title", help="New title."),
    name: str | None = typer.Option(None, "--name", help="Alias for --title."),
    description: str | None = typer.Option(None, "--description"),
    metadata: str | None = typer.Option(None, "--metadata"),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure update",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: update_structure_node(
            project=context.project,
            node_ref=node,
            title=title if title is not None else name,
            description=description,
            metadata=_parse_metadata(metadata),
        ),
    )


@structure_app.command("move")
def structure_move_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    node: str = typer.Option(..., "--node", help="Structure node ID."),
    parent: str = typer.Option(..., "--parent", help="New parent structure node ID."),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure move",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: move_structure_node(
            project=context.project,
            node_ref=node,
            parent_ref=parent,
        ),
        include_parent=True,
    )


@structure_app.command("delete")
def structure_delete_command(
    project: str = typer.Option(..., "--project", help="Quality project slug."),
    node: str = typer.Option(..., "--node", help="Structure node ID."),
    workspace: Path | None = _workspace_option(),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    _run_structure_command(
        command_name="dfmea structure delete",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda context: delete_structure_node(
            project=context.project,
            node_ref=node,
        ),
    )


def _run_structure_command(
    *,
    command_name: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action: Callable[[DfmeaProjectContext], StructureMutationResult],
    include_parent: bool = False,
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

    data = {
        "resource": _resource_payload(result),
        "changedPaths": [str(path) for path in result.write_result.changed_paths],
        "affectedObjects": [
            {
                "kind": result.resource.kind,
                "id": result.node_id,
                "path": str(result.path),
            }
        ],
    }
    if include_parent:
        data["parentId"] = result.parent_id
    if result.write_result.tombstone_path is not None:
        data["tombstonePath"] = str(result.write_result.tombstone_path)

    payload = success_result(
        command=command_name,
        data=data,
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


def _resource_payload(result: StructureMutationResult) -> dict[str, object]:
    title = result.resource.metadata.get("title")
    return {
        "id": result.node_id,
        "kind": result.resource.kind,
        "nodeType": result.node_type,
        "title": title if isinstance(title, str) else None,
        "parentId": result.parent_id,
        "path": str(result.path),
    }


def _meta(*, context: DfmeaProjectContext | None) -> dict[str, object]:
    if context is None:
        return {}
    return {
        "workspaceRoot": str(context.workspace_root),
        "projectSlug": context.project.slug,
        "projectRoot": str(context.project.root),
    }


def _parse_metadata(metadata: str | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="Option '--metadata' must be valid JSON.",
            target={"option": "metadata"},
            suggestion="Provide a JSON object string for --metadata.",
        ) from exc
    if not isinstance(parsed, dict):
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="Option '--metadata' must decode to a JSON object.",
            target={"option": "metadata"},
            suggestion="Provide a JSON object string for --metadata.",
        )
    return parsed


def _resolve_title(*, title: str | None, name: str | None) -> str:
    resolved = title if title is not None else name
    if resolved is None or not resolved.strip():
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="Structure node title is required.",
            target={"option": "title"},
            suggestion="Provide --title or --name.",
        )
    return resolved
