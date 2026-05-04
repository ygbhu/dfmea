from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin, PluginCollection, PluginSingleton
from quality_core.resources.envelope import Resource


@dataclass(frozen=True, slots=True)
class ResourceRef:
    domain: str
    kind: str
    resource_id: str
    path: Path


@dataclass(frozen=True, slots=True)
class ResourceSelector:
    kind: str | None = None
    id_prefix: str | None = None


def id_prefix(resource_id: str) -> str:
    if "-" not in resource_id:
        return resource_id
    return resource_id.split("-", 1)[0]


def allowed_prefixes(collection: PluginCollection) -> tuple[str, ...]:
    return tuple(part for part in collection.id_prefix.split("|") if part)


def find_collection(
    plugin: BuiltinPlugin,
    *,
    kind: str,
    resource_id: str | None = None,
    id_prefix_value: str | None = None,
) -> PluginCollection:
    candidates = [collection for collection in plugin.collections if collection.kind == kind]
    if not candidates:
        raise QualityCliError(
            code="RESOURCE_NOT_FOUND",
            message=f"Plugin '{plugin.plugin_id}' has no collection for kind '{kind}'.",
            target={"pluginId": plugin.plugin_id, "kind": kind},
            suggestion="Check the plugin collection descriptor.",
        )
    prefix = id_prefix_value or (id_prefix(resource_id) if resource_id is not None else None)
    if prefix is None:
        if len(candidates) == 1:
            return candidates[0]
        raise QualityCliError(
            code="ID_PREFIX_MISMATCH",
            message=f"Kind '{kind}' requires an ID prefix to choose a collection.",
            target={"pluginId": plugin.plugin_id, "kind": kind},
            suggestion="Provide an ID or ID prefix declared by the plugin.",
        )
    for collection in candidates:
        if prefix in allowed_prefixes(collection):
            return collection
    raise QualityCliError(
        code="ID_PREFIX_MISMATCH",
        message=f"ID prefix '{prefix}' is not valid for kind '{kind}'.",
        target={"pluginId": plugin.plugin_id, "kind": kind, "idPrefix": prefix},
        suggestion="Use an ID prefix declared by the plugin collection.",
    )


def find_singleton(
    plugin: BuiltinPlugin,
    *,
    kind: str,
    resource_id: str | None = None,
) -> PluginSingleton | None:
    for singleton in plugin.singletons:
        if singleton.kind != kind:
            continue
        if resource_id is None or singleton.resource_id == resource_id:
            return singleton
    return None


def domain_root(project_root: Path, plugin: BuiltinPlugin) -> Path:
    return project_root / plugin.domain_root


def collection_root(
    *,
    project_root: Path,
    plugin: BuiltinPlugin,
    collection: PluginCollection,
) -> Path:
    return domain_root(project_root, plugin) / collection.directory


def resource_path_for_collection_id(
    *,
    project_root: Path,
    plugin: BuiltinPlugin,
    kind: str,
    resource_id: str,
) -> Path:
    collection = find_collection(plugin, kind=kind, resource_id=resource_id)
    return collection_root(
        project_root=project_root,
        plugin=plugin,
        collection=collection,
    ) / collection.file_name.replace("{id}", resource_id)


def singleton_path(
    *,
    project_root: Path,
    plugin: BuiltinPlugin,
    kind: str,
    resource_id: str | None = None,
) -> Path:
    singleton = find_singleton(plugin, kind=kind, resource_id=resource_id)
    if singleton is None:
        raise QualityCliError(
            code="RESOURCE_NOT_FOUND",
            message=f"Plugin '{plugin.plugin_id}' has no singleton for kind '{kind}'.",
            target={"pluginId": plugin.plugin_id, "kind": kind, "resourceId": resource_id},
            suggestion="Check the plugin singleton descriptor.",
        )
    return domain_root(project_root, plugin) / singleton.file


def resource_path(
    *,
    project_root: Path,
    plugin: BuiltinPlugin,
    resource: Resource,
) -> Path:
    singleton = find_singleton(
        plugin,
        kind=resource.kind,
    )
    if singleton is not None:
        return singleton_path(
            project_root=project_root,
            plugin=plugin,
            kind=resource.kind,
            resource_id=singleton.resource_id,
        )
    return resource_path_for_collection_id(
        project_root=project_root,
        plugin=plugin,
        kind=resource.kind,
        resource_id=resource.resource_id,
    )


def validate_resource_path(
    *,
    plugin: BuiltinPlugin,
    resource: Resource,
    path: Path,
) -> None:
    singleton = find_singleton(
        plugin,
        kind=resource.kind,
    )
    if singleton is not None:
        if path.name != singleton.file or resource.resource_id != singleton.resource_id:
            raise QualityCliError(
                code="ID_PREFIX_MISMATCH",
                message="Singleton resource path or ID does not match plugin declaration.",
                path=str(path),
                target={
                    "kind": resource.kind,
                    "resourceId": resource.resource_id,
                    "expectedId": singleton.resource_id,
                    "expectedFile": singleton.file,
                },
                suggestion="Use the singleton fixed ID and fixed file name declared by the plugin.",
            )
        return

    collection = find_collection(
        plugin,
        kind=resource.kind,
        resource_id=resource.resource_id,
    )
    expected_name = collection.file_name.replace("{id}", resource.resource_id)
    if path.name != expected_name:
        raise QualityCliError(
            code="ID_PREFIX_MISMATCH",
            message="Collection resource file name must match metadata.id.",
            path=str(path),
            target={
                "kind": resource.kind,
                "resourceId": resource.resource_id,
                "expectedFile": expected_name,
            },
            suggestion="Rename the file or repair metadata.id so both match.",
        )
