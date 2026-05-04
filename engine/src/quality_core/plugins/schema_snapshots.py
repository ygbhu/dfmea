from __future__ import annotations

import shutil
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin
from quality_core.workspace.config import load_yaml_document

PLUGIN_DESCRIPTOR_FILE = "plugin.yaml"


@dataclass(frozen=True, slots=True)
class PluginSchemaSnapshot:
    plugin_id: str
    version: str
    root: Path
    descriptor_path: Path


def project_schema_snapshot_root(project_root: Path, plugin_id: str) -> Path:
    return project_root / ".quality" / "schemas" / plugin_id


def copy_plugin_schema_snapshot(*, plugin: BuiltinPlugin, project_root: Path) -> Path:
    target_root = project_schema_snapshot_root(project_root, plugin.plugin_id)
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    _copy_traversable_tree(plugin.snapshot_root, target_root)
    return target_root


def load_project_schema_snapshot(
    *,
    plugin: BuiltinPlugin,
    project_root: Path,
) -> PluginSchemaSnapshot:
    snapshot_root = project_schema_snapshot_root(project_root, plugin.plugin_id)
    descriptor_path = snapshot_root / PLUGIN_DESCRIPTOR_FILE
    if not descriptor_path.exists():
        raise QualityCliError(
            code="PLUGIN_NOT_ENABLED",
            message=f"Plugin '{plugin.plugin_id}' is enabled but has no schema snapshot.",
            path=str(descriptor_path),
            target={"pluginId": plugin.plugin_id},
            suggestion=f"Re-enable the plugin with `quality plugin enable {plugin.plugin_id}`.",
        )

    descriptor = load_yaml_document(descriptor_path, code="SCHEMA_VERSION_MISMATCH")
    snapshot_plugin_id = _metadata_string(
        descriptor,
        field="pluginId",
        path=descriptor_path,
    )
    version = _metadata_string(
        descriptor,
        field="version",
        path=descriptor_path,
    )
    if snapshot_plugin_id != plugin.plugin_id:
        raise QualityCliError(
            code="SCHEMA_VERSION_MISMATCH",
            message=(
                f"Schema snapshot plugin id '{snapshot_plugin_id}' does not match "
                f"expected plugin '{plugin.plugin_id}'."
            ),
            path=str(descriptor_path),
            field="metadata.pluginId",
            target={
                "pluginId": plugin.plugin_id,
                "snapshotPluginId": snapshot_plugin_id,
            },
            suggestion="Run the future plugin migration command before mutating project files.",
        )

    return PluginSchemaSnapshot(
        plugin_id=snapshot_plugin_id,
        version=version,
        root=snapshot_root,
        descriptor_path=descriptor_path,
    )


def ensure_project_schema_snapshot_current(
    *,
    plugin: BuiltinPlugin,
    project_root: Path,
) -> PluginSchemaSnapshot:
    snapshot = load_project_schema_snapshot(plugin=plugin, project_root=project_root)
    if snapshot.version != plugin.version:
        raise QualityCliError(
            code="SCHEMA_VERSION_MISMATCH",
            message=(
                f"Project schema snapshot for plugin '{plugin.plugin_id}' is "
                f"'{snapshot.version}', but tooling expects '{plugin.version}'."
            ),
            path=str(snapshot.descriptor_path),
            field="metadata.version",
            target={
                "pluginId": plugin.plugin_id,
                "snapshotVersion": snapshot.version,
                "toolingVersion": plugin.version,
            },
            suggestion="Run the future plugin migration command before mutating project files.",
        )
    return snapshot


def _copy_traversable_tree(source: Traversable, target: Path) -> None:
    for item in source.iterdir():
        target_item = target / item.name
        if item.is_dir():
            target_item.mkdir(parents=True, exist_ok=True)
            _copy_traversable_tree(item, target_item)
        else:
            target_item.write_bytes(item.read_bytes())


def _metadata_string(document: dict[str, Any], *, field: str, path: Path) -> str:
    metadata = document.get("metadata")
    value = metadata.get(field) if isinstance(metadata, dict) else None
    if not isinstance(value, str) or not value:
        raise QualityCliError(
            code="SCHEMA_VERSION_MISMATCH",
            message=f"Schema snapshot '{path}' must define metadata.{field}.",
            path=str(path),
            field=f"metadata.{field}",
            suggestion="Restore the schema snapshot from the tooling plugin descriptor.",
        )
    return value
