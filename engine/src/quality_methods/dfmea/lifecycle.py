from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.project_plugins import enable_project_plugin
from quality_core.plugins.schema_snapshots import ensure_project_schema_snapshot_current
from quality_core.resources.envelope import Resource, make_resource
from quality_core.resources.paths import collection_root, singleton_path
from quality_core.resources.store import ResourceStore, WriteResult
from quality_core.workspace.config import load_workspace_config
from quality_core.workspace.discovery import discover_workspace_root
from quality_core.workspace.project import (
    ProjectConfig,
    load_project_config,
    resolve_project_root,
)
from quality_methods.dfmea.plugin import get_plugin

DFMEA_ANALYSIS_KIND = "DfmeaAnalysis"
DFMEA_ANALYSIS_ID = "DFMEA"


@dataclass(frozen=True, slots=True)
class DfmeaProjectContext:
    workspace_root: Path
    project: ProjectConfig
    schema_version: str


@dataclass(frozen=True, slots=True)
class DfmeaInitResult:
    context: DfmeaProjectContext
    analysis: Resource
    analysis_write: WriteResult | None
    created_directories: tuple[Path, ...]
    already_initialized: bool
    already_enabled: bool


def initialize_dfmea_domain(
    *,
    workspace: Path | None,
    project: str,
    name: str | None = None,
) -> DfmeaInitResult:
    workspace_root = discover_workspace_root(workspace=workspace)
    workspace_config = load_workspace_config(workspace_root)
    project_root = resolve_project_root(
        workspace_config=workspace_config,
        project=project,
    )
    plugin = get_plugin()
    enable_result = enable_project_plugin(project_root=project_root, plugin_id=plugin.plugin_id)
    initialized_project = enable_result.project

    created_directories = _ensure_domain_directories(project=initialized_project)
    store = ResourceStore(project=initialized_project, plugin=plugin)
    analysis_path = singleton_path(
        project_root=initialized_project.root,
        plugin=plugin,
        kind=DFMEA_ANALYSIS_KIND,
        resource_id=DFMEA_ANALYSIS_ID,
    )
    already_initialized = analysis_path.exists()
    if already_initialized:
        analysis = store.load(store.ref(kind=DFMEA_ANALYSIS_KIND, resource_id=DFMEA_ANALYSIS_ID))
        write_result = None
    else:
        analysis = make_resource(
            kind=DFMEA_ANALYSIS_KIND,
            resource_id=DFMEA_ANALYSIS_ID,
            metadata={"name": name or initialized_project.name},
            spec={"projectRef": initialized_project.slug},
        )
        write_result = store.create(analysis)
        analysis = store.load(store.ref(kind=DFMEA_ANALYSIS_KIND, resource_id=DFMEA_ANALYSIS_ID))

    snapshot = ensure_project_schema_snapshot_current(
        plugin=plugin,
        project_root=initialized_project.root,
    )
    return DfmeaInitResult(
        context=DfmeaProjectContext(
            workspace_root=workspace_root,
            project=initialized_project,
            schema_version=snapshot.version,
        ),
        analysis=analysis,
        analysis_write=write_result,
        created_directories=created_directories,
        already_initialized=already_initialized,
        already_enabled=enable_result.already_enabled,
    )


def load_initialized_dfmea_project(
    *,
    workspace: Path | None,
    project: str,
) -> DfmeaProjectContext:
    workspace_root = discover_workspace_root(workspace=workspace)
    workspace_config = load_workspace_config(workspace_root)
    project_root = resolve_project_root(
        workspace_config=workspace_config,
        project=project,
    )
    project_config = load_project_config(project_root)
    plugin = get_plugin()
    domain = project_config.domains.get(plugin.domain_key)
    if not isinstance(domain, dict) or domain.get("enabled") is not True:
        raise QualityCliError(
            code="PLUGIN_NOT_ENABLED",
            message=f"DFMEA is not initialized for project '{project_config.slug}'.",
            target={"pluginId": plugin.plugin_id, "projectSlug": project_config.slug},
            suggestion=f"Run `dfmea init --project {project_config.slug}` first.",
        )
    snapshot = ensure_project_schema_snapshot_current(
        plugin=plugin,
        project_root=project_config.root,
    )
    analysis_path = singleton_path(
        project_root=project_config.root,
        plugin=plugin,
        kind=DFMEA_ANALYSIS_KIND,
        resource_id=DFMEA_ANALYSIS_ID,
    )
    if not analysis_path.exists():
        raise QualityCliError(
            code="PLUGIN_NOT_ENABLED",
            message=f"DFMEA analysis root is missing for project '{project_config.slug}'.",
            path=str(analysis_path),
            target={"pluginId": plugin.plugin_id, "projectSlug": project_config.slug},
            suggestion=f"Run `dfmea init --project {project_config.slug}` first.",
        )
    return DfmeaProjectContext(
        workspace_root=workspace_root,
        project=project_config,
        schema_version=snapshot.version,
    )


def _ensure_domain_directories(*, project: ProjectConfig) -> tuple[Path, ...]:
    plugin = get_plugin()
    directories = [project.root / plugin.domain_root]
    directories.extend(
        collection_root(
            project_root=project.root,
            plugin=plugin,
            collection=collection,
        )
        for collection in plugin.collections
    )
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)
    return tuple(directories)
