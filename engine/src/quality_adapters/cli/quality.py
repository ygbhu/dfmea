from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from quality_adapters.opencode import install_project_pack
from quality_core.cli.errors import QualityCliError
from quality_core.cli.output import OutputFormat, emit_payload, failure_result, success_result
from quality_core.git import (
    project_diff,
    project_history,
    project_restore,
    project_snapshot,
    project_status,
)
from quality_core.methods.registry import list_quality_methods
from quality_core.plugins.project_plugins import (
    disable_project_plugin,
    enable_project_plugin,
    list_project_plugin_statuses,
)
from quality_core.resources.repair import (
    IdConflictRepairResult,
    RenumberResult,
    renumber_project_resource_id,
    repair_project_id_conflicts,
)
from quality_core.workspace.config import (
    default_plugins_document,
    default_workspace_document,
    load_workspace_config,
    load_workspace_plugins,
    workspace_config_path,
    workspace_plugins_path,
    write_yaml_document,
)
from quality_core.workspace.discovery import discover_workspace_root
from quality_core.workspace.project import create_project, load_project_config, resolve_project_root

app = typer.Typer(no_args_is_help=True, help="Local-first quality workspace CLI.")
workspace_app = typer.Typer(no_args_is_help=True, help="Workspace commands.")
project_app = typer.Typer(no_args_is_help=True, help="Project commands.")
project_id_app = typer.Typer(no_args_is_help=True, help="Project ID commands.")
project_repair_app = typer.Typer(no_args_is_help=True, help="Project repair commands.")
plugin_app = typer.Typer(no_args_is_help=True, help="Plugin commands.")
method_app = typer.Typer(no_args_is_help=True, help="Quality method commands.")
opencode_app = typer.Typer(no_args_is_help=True, help="OpenCode adapter commands.")


@app.callback()
def root() -> None:
    """Local-first quality assistant commands."""


def main() -> None:
    app()


@workspace_app.command("init")
def workspace_init_command(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root to initialize.",
    ),
    name: str = typer.Option("default", "--name", help="Workspace display name."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing workspace config."),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Create workspace-level quality configuration files."""

    workspace_root = workspace.expanduser().resolve()
    command = "quality workspace init"
    try:
        config_path = workspace_config_path(workspace_root)
        plugins_path = workspace_plugins_path(workspace_root)
        if not force and (config_path.exists() or plugins_path.exists()):
            existing = [str(path) for path in (config_path, plugins_path) if path.exists()]
            raise QualityCliError(
                code="WORKSPACE_ALREADY_EXISTS",
                message="Workspace configuration already exists.",
                target={"existingPaths": existing},
                suggestion="Use --force only when you intentionally want to rewrite defaults.",
            )

        write_yaml_document(config_path, default_workspace_document(name=name))
        write_yaml_document(plugins_path, default_plugins_document())
        workspace_config = load_workspace_config(workspace_root)
        plugins_config = load_workspace_plugins(workspace_root)
    except QualityCliError as exc:
        _emit_failure(command=command, error=exc, output_format=output_format)

    payload = success_result(
        command=command,
        data={
            "workspace": {
                "name": workspace_config.name,
                "projectsRoot": workspace_config.projects_root,
            },
            "plugins": {
                "builtins": list(plugins_config.builtins),
                "enabledByDefault": list(plugins_config.enabled_by_default),
            },
            "createdPaths": [str(config_path), str(plugins_path)],
        },
        meta={"workspaceRoot": str(workspace_root)},
    )
    emit_payload(payload, output_format, quiet=quiet)


@project_app.command("create")
def project_create_command(
    slug: str = typer.Argument(..., help="Project directory slug."),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Defaults to upward discovery.",
    ),
    name: str | None = typer.Option(None, "--name", help="Project display name."),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Create a quality project under the workspace projects root."""

    command = "quality project create"
    try:
        workspace_root = discover_workspace_root(workspace=workspace)
        workspace_config = load_workspace_config(workspace_root)
        result = create_project(
            workspace_config=workspace_config,
            slug=slug,
            name=name,
        )
    except QualityCliError as exc:
        _emit_failure(command=command, error=exc, output_format=output_format)

    project = result.project
    payload = success_result(
        command=command,
        data={
            "project": {
                "id": "PRJ",
                "slug": project.slug,
                "name": project.name,
                "path": str(project.root),
                "configPath": str(project.config_path),
            },
            "createdPaths": [str(path) for path in result.created_paths],
        },
        meta={
            "workspaceRoot": str(workspace_root),
            "projectSlug": project.slug,
            "projectRoot": str(project.root),
        },
    )
    emit_payload(payload, output_format, quiet=quiet)


@project_id_app.command("renumber")
def project_id_renumber_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
    from_id: str = typer.Option(..., "--from", help="Existing resource ID."),
    to_id: str = typer.Option(..., "--to", help="New resource ID."),
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
    """Renumber one project resource and update project-local references."""

    command = "quality project id renumber"
    workspace_root: Path | None = None
    project_config = None
    try:
        workspace_root, project_config = _resolve_project_context(
            workspace=workspace,
            project=project,
        )
        result = renumber_project_resource_id(
            project=project_config,
            from_id=from_id,
            to_id=to_id,
        )
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    payload = success_result(
        command=command,
        data={"renumber": _renumber_payload(result)},
        meta=_project_meta(workspace_root=workspace_root, project=result.project),
    )
    emit_payload(payload, output_format, quiet=quiet)


@project_repair_app.command("id-conflicts")
def project_repair_id_conflicts_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
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
    """Repair collection files whose path ID and metadata.id conflict."""

    command = "quality project repair id-conflicts"
    workspace_root: Path | None = None
    project_config = None
    try:
        workspace_root, project_config = _resolve_project_context(
            workspace=workspace,
            project=project,
        )
        result = repair_project_id_conflicts(project=project_config)
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    payload = success_result(
        command=command,
        data=_repair_payload(result),
        meta=_project_meta(workspace_root=workspace_root, project=result.project),
    )
    emit_payload(payload, output_format, quiet=quiet)


@project_app.command("status")
def project_status_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
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
    """Report project-scoped Git, validation, and projection status."""

    _run_project_git_command(
        command="quality project status",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda project_config: project_status(project=project_config),
    )


@project_app.command("snapshot")
def project_snapshot_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
    message: str | None = typer.Option(None, "--message", "-m", help="Git commit message."),
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
    """Validate, rebuild, stage managed paths, and commit a project snapshot."""

    _run_project_git_command(
        command="quality project snapshot",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda project_config: project_snapshot(
            project=project_config,
            message=message,
        ),
    )


@project_app.command("history")
def project_history_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum commits to return."),
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
    """List Git commits that changed this project's managed paths."""

    _run_project_git_command(
        command="quality project history",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda project_config: project_history(
            project=project_config,
            limit=limit,
        ),
    )


@project_app.command("diff")
def project_diff_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
    from_ref: str | None = typer.Option(None, "--from", help="Base ref for Git diff."),
    to_ref: str | None = typer.Option(None, "--to", help="Target ref for Git diff."),
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
    """Show raw Git file changes plus parsed resource summaries."""

    _run_project_git_command(
        command="quality project diff",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda project_config: project_diff(
            project=project_config,
            from_ref=from_ref,
            to_ref=to_ref,
        ),
    )


@project_app.command("restore")
def project_restore_command(
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
    ref: str = typer.Option(..., "--ref", help="Git ref to restore from."),
    message: str | None = typer.Option(None, "--message", "-m", help="Forward restore commit."),
    force_with_backup: bool = typer.Option(
        False,
        "--force-with-backup",
        help="Allow dirty managed paths and record a restore backup manifest.",
    ),
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
    """Restore managed non-generated project files from a ref and create a forward commit."""

    _run_project_git_command(
        command="quality project restore",
        workspace=workspace,
        project=project,
        output_format=output_format,
        quiet=quiet,
        action=lambda project_config: project_restore(
            project=project_config,
            ref=ref,
            message=message,
            force_with_backup=force_with_backup,
        ),
    )


@plugin_app.command("list")
def plugin_list_command(
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Required when --project is provided.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project slug or directory name for enabled-state reporting.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """List built-in plugins and optional project enablement state."""

    command = "quality plugin list"
    workspace_root: Path | None = None
    project_config = None
    try:
        if project is not None:
            workspace_root = discover_workspace_root(workspace=workspace)
            workspace_config = load_workspace_config(workspace_root)
            project_root = resolve_project_root(
                workspace_config=workspace_config,
                project=project,
            )
            project_config = load_project_config(project_root)
            statuses = list_project_plugin_statuses(project_config)
        else:
            statuses = list_project_plugin_statuses()
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    payload = success_result(
        command=command,
        data={"plugins": [_plugin_status_payload(status) for status in statuses]},
        meta=_project_meta(workspace_root=workspace_root, project=project_config),
    )
    emit_payload(payload, output_format, quiet=quiet)


@plugin_app.command("enable")
def plugin_enable_command(
    plugin_id: str = typer.Argument(..., help="Built-in plugin id."),
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
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
    """Enable a built-in plugin for one project and copy its schema snapshot."""

    command = "quality plugin enable"
    workspace_root: Path | None = None
    project_config = None
    try:
        workspace_root = discover_workspace_root(workspace=workspace)
        workspace_config = load_workspace_config(workspace_root)
        project_root = resolve_project_root(
            workspace_config=workspace_config,
            project=project,
        )
        result = enable_project_plugin(project_root=project_root, plugin_id=plugin_id)
        project_config = result.project
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    payload = success_result(
        command=command,
        data={
            "plugin": {
                "id": result.plugin.plugin_id,
                "version": result.plugin.version,
                "domain": result.plugin.domain_key,
                "enabled": True,
                "alreadyEnabled": result.already_enabled,
                "schemaSnapshotPath": str(result.schema_snapshot.root),
                "domainRoot": str(result.domain_root),
            }
        },
        meta={
            **_project_meta(workspace_root=workspace_root, project=result.project),
            "schemaVersions": {result.plugin.plugin_id: result.schema_snapshot.version},
        },
    )
    emit_payload(payload, output_format, quiet=quiet)


@plugin_app.command("disable")
def plugin_disable_command(
    plugin_id: str = typer.Argument(..., help="Built-in plugin id."),
    project: str = typer.Option(..., "--project", help="Project slug or directory name."),
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
    """Disable an enabled plugin when no domain source resources exist."""

    command = "quality plugin disable"
    workspace_root: Path | None = None
    project_config = None
    try:
        workspace_root = discover_workspace_root(workspace=workspace)
        workspace_config = load_workspace_config(workspace_root)
        project_root = resolve_project_root(
            workspace_config=workspace_config,
            project=project,
        )
        result = disable_project_plugin(project_root=project_root, plugin_id=plugin_id)
        project_config = result.project
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    payload = success_result(
        command=command,
        data={
            "plugin": {
                "id": result.plugin.plugin_id,
                "version": result.plugin.version,
                "domain": result.plugin.domain_key,
                "enabled": False,
                "schemaSnapshotPath": (
                    str(result.schema_snapshot_path)
                    if result.schema_snapshot_path is not None
                    else None
                ),
            }
        },
        meta=_project_meta(workspace_root=workspace_root, project=result.project),
    )
    emit_payload(payload, output_format, quiet=quiet)


@method_app.command("list")
def method_list_command(
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace root. Required when --project is provided.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project slug or directory name for enabled-state reporting.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """List quality methods such as DFMEA and planned PFMEA."""

    command = "quality method list"
    workspace_root: Path | None = None
    project_config = None
    try:
        if project is not None:
            workspace_root, project_config = _resolve_project_context(
                workspace=workspace,
                project=project,
            )
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    methods = list_quality_methods()
    payload = success_result(
        command=command,
        data={"methods": [method.data(project=project_config) for method in methods]},
        meta=_project_meta(workspace_root=workspace_root, project=project_config),
    )
    emit_payload(payload, output_format, quiet=quiet)


@opencode_app.command("init")
def opencode_init_command(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        file_okay=False,
        resolve_path=True,
        help="Workspace or repository root where .opencode should be installed.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite generated OpenCode adapter files.",
    ),
    npm_plugin: bool = typer.Option(
        False,
        "--npm-plugin",
        help=(
            "Also write opencode.json with plugin ['opencode-quality-assistant'] "
            "for npm-installed usage."
        ),
    ),
    no_local_plugin: bool = typer.Option(
        False,
        "--no-local-plugin",
        help="Do not install .opencode/plugins/quality-assistant.js.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Install project-local OpenCode plugin, commands, and skills."""

    command = "quality opencode init"
    workspace_root = workspace.expanduser().resolve()
    try:
        result = install_project_pack(
            workspace_root=workspace_root,
            force=force,
            local_plugin=not no_local_plugin,
            npm_plugin=npm_plugin,
        )
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta={
                "workspaceRoot": str(workspace_root),
                "opencodeRoot": str(workspace_root / ".opencode"),
            },
        )

    payload = success_result(
        command=command,
        data=result.data(),
        meta={
            "workspaceRoot": str(workspace_root),
            "opencodeRoot": str(result.target_root),
            "adapter": "opencode",
            "strategy": "opencode-first-adapter",
            "productHost": "opencode",
        },
    )
    emit_payload(payload, output_format, quiet=quiet)


def _emit_failure(
    *,
    command: str,
    error: QualityCliError,
    output_format: OutputFormat,
    meta: dict[str, object] | None = None,
) -> NoReturn:
    payload = failure_result(command=command, errors=[error.to_error()], meta=meta)
    emit_payload(
        payload,
        output_format,
        quiet=False,
        exit_code=error.resolved_exit_code,
    )


def _plugin_status_payload(status) -> dict[str, object]:
    schema_version = status.schema_snapshot.version if status.schema_snapshot is not None else None
    return {
        "id": status.plugin.plugin_id,
        "version": status.plugin.version,
        "domain": status.plugin.domain_key,
        "builtin": True,
        "enabled": status.enabled,
        "schemaSnapshotVersion": schema_version,
        "schemaSnapshotPath": (
            str(status.schema_snapshot_path) if status.schema_snapshot_path is not None else None
        ),
    }


def _resolve_project_context(
    *,
    workspace: Path | None,
    project: str,
) -> tuple[Path, object]:
    workspace_root = discover_workspace_root(workspace=workspace)
    workspace_config = load_workspace_config(workspace_root)
    project_root = resolve_project_root(
        workspace_config=workspace_config,
        project=project,
    )
    return workspace_root, load_project_config(project_root)


def _renumber_payload(result: RenumberResult) -> dict[str, object]:
    return {
        "kind": result.kind,
        "fromId": result.from_id,
        "toId": result.to_id,
        "oldPath": str(result.old_path),
        "newPath": str(result.new_path),
        "changedPaths": [str(path) for path in result.changed_paths],
        "changedReferences": [
            {
                "path": str(reference.path),
                "fieldPath": reference.field_path,
                "oldValue": reference.old_value,
                "newValue": reference.new_value,
            }
            for reference in result.changed_references
        ],
    }


def _repair_payload(result: IdConflictRepairResult) -> dict[str, object]:
    return {
        "changedPaths": [str(path) for path in result.changed_paths],
        "renumbers": [_renumber_payload(renumber) for renumber in result.renumbers],
    }


def _run_project_git_command(
    *,
    command: str,
    workspace: Path | None,
    project: str,
    output_format: OutputFormat,
    quiet: bool,
    action,
) -> None:
    workspace_root: Path | None = None
    project_config = None
    try:
        workspace_root, project_config = _resolve_project_context(
            workspace=workspace,
            project=project,
        )
        result = action(project_config)
    except QualityCliError as exc:
        _emit_failure(
            command=command,
            error=exc,
            output_format=output_format,
            meta=_project_meta(workspace_root=workspace_root, project=project_config),
        )

    payload = success_result(
        command=command,
        data=result.data,
        meta={
            **_project_meta(workspace_root=workspace_root, project=result.project),
            "repoRoot": str(result.repo_root),
            "schemaVersions": result.schema_versions,
        },
    )
    emit_payload(payload, output_format, quiet=quiet)


def _project_meta(*, workspace_root: Path | None, project) -> dict[str, object]:
    meta: dict[str, object] = {}
    if workspace_root is not None:
        meta["workspaceRoot"] = str(workspace_root)
    if project is not None:
        meta["projectSlug"] = project.slug
        meta["projectRoot"] = str(project.root)
    return meta


project_app.add_typer(project_id_app, name="id")
project_app.add_typer(project_repair_app, name="repair")
app.add_typer(workspace_app, name="workspace")
app.add_typer(project_app, name="project")
app.add_typer(plugin_app, name="plugin")
app.add_typer(method_app, name="method")
app.add_typer(opencode_app, name="opencode")
