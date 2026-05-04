from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin
from quality_core.plugins.registry import get_builtin_plugin, list_builtin_plugins
from quality_core.plugins.schema_snapshots import (
    PluginSchemaSnapshot,
    copy_plugin_schema_snapshot,
    ensure_project_schema_snapshot_current,
    project_schema_snapshot_root,
)
from quality_core.workspace.project import (
    ProjectConfig,
    load_project_config,
    update_project_domain,
)


@dataclass(frozen=True, slots=True)
class PluginStatus:
    plugin: BuiltinPlugin
    enabled: bool
    schema_snapshot: PluginSchemaSnapshot | None
    schema_snapshot_path: Path | None


@dataclass(frozen=True, slots=True)
class PluginEnableResult:
    project: ProjectConfig
    plugin: BuiltinPlugin
    schema_snapshot: PluginSchemaSnapshot
    domain_root: Path
    already_enabled: bool


@dataclass(frozen=True, slots=True)
class PluginDisableResult:
    project: ProjectConfig
    plugin: BuiltinPlugin
    schema_snapshot_path: Path | None


def list_project_plugin_statuses(project: ProjectConfig | None = None) -> list[PluginStatus]:
    statuses: list[PluginStatus] = []
    for plugin in list_builtin_plugins():
        enabled = _is_plugin_enabled(project, plugin) if project is not None else False
        snapshot: PluginSchemaSnapshot | None = None
        snapshot_path: Path | None = None
        if project is not None:
            snapshot_path = project_schema_snapshot_root(project.root, plugin.plugin_id)
        if project is not None and enabled:
            snapshot = ensure_project_schema_snapshot_current(
                plugin=plugin,
                project_root=project.root,
            )
            snapshot_path = snapshot.root
        statuses.append(
            PluginStatus(
                plugin=plugin,
                enabled=enabled,
                schema_snapshot=snapshot,
                schema_snapshot_path=snapshot_path,
            )
        )
    return statuses


def enable_project_plugin(*, project_root: Path, plugin_id: str) -> PluginEnableResult:
    plugin = get_builtin_plugin(plugin_id)
    project = load_project_config(project_root)
    already_enabled = _is_plugin_enabled(project, plugin)

    if already_enabled:
        snapshot = ensure_project_schema_snapshot_current(
            plugin=plugin,
            project_root=project.root,
        )
        return PluginEnableResult(
            project=project,
            plugin=plugin,
            schema_snapshot=snapshot,
            domain_root=_domain_root(project, plugin),
            already_enabled=True,
        )

    copy_plugin_schema_snapshot(plugin=plugin, project_root=project.root)
    domain_root = project.root / plugin.domain_root
    domain_root.mkdir(parents=True, exist_ok=True)
    updated_project = update_project_domain(
        project_root=project.root,
        domain_key=plugin.domain_key,
        enabled=True,
        root=f"./{plugin.domain_root}",
    )
    snapshot = ensure_project_schema_snapshot_current(
        plugin=plugin,
        project_root=updated_project.root,
    )
    return PluginEnableResult(
        project=updated_project,
        plugin=plugin,
        schema_snapshot=snapshot,
        domain_root=domain_root,
        already_enabled=False,
    )


def disable_project_plugin(*, project_root: Path, plugin_id: str) -> PluginDisableResult:
    plugin = get_builtin_plugin(plugin_id)
    project = load_project_config(project_root)
    if not _is_plugin_enabled(project, plugin):
        raise QualityCliError(
            code="PLUGIN_NOT_ENABLED",
            message=f"Plugin '{plugin.plugin_id}' is not enabled for project '{project.slug}'.",
            target={"pluginId": plugin.plugin_id, "projectSlug": project.slug},
            suggestion=(
                f"Run `quality plugin enable {plugin.plugin_id} --project {project.slug}` first."
            ),
        )

    ensure_project_schema_snapshot_current(plugin=plugin, project_root=project.root)
    domain_root = _domain_root(project, plugin)
    source_files = sorted(domain_root.rglob("*.yaml")) if domain_root.exists() else []
    if source_files:
        raise QualityCliError(
            code="PLUGIN_DISABLE_BLOCKED",
            message=(
                f"Plugin '{plugin.plugin_id}' cannot be disabled because domain source "
                "resources exist."
            ),
            target={
                "pluginId": plugin.plugin_id,
                "projectSlug": project.slug,
                "sourceFiles": [str(path) for path in source_files],
            },
            suggestion="Delete or migrate domain source resources before disabling this plugin.",
        )

    updated_project = update_project_domain(
        project_root=project.root,
        domain_key=plugin.domain_key,
        enabled=False,
        root=f"./{plugin.domain_root}",
    )
    snapshot_path = project_schema_snapshot_root(updated_project.root, plugin.plugin_id)
    return PluginDisableResult(
        project=updated_project,
        plugin=plugin,
        schema_snapshot_path=snapshot_path if snapshot_path.exists() else None,
    )


def _is_plugin_enabled(project: ProjectConfig | None, plugin: BuiltinPlugin) -> bool:
    if project is None:
        return False
    domain = project.domains.get(plugin.domain_key)
    return isinstance(domain, dict) and domain.get("enabled") is True


def _domain_root(project: ProjectConfig, plugin: BuiltinPlugin) -> Path:
    domain = project.domains.get(plugin.domain_key)
    configured_root: Any = domain.get("root") if isinstance(domain, dict) else None
    if not isinstance(configured_root, str) or not configured_root:
        configured_root = f"./{plugin.domain_root}"
    return project.root / configured_root
