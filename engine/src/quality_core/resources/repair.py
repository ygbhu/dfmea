from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin, PluginCollection
from quality_core.plugins.registry import list_builtin_plugins
from quality_core.resources.atomic import atomic_write_text
from quality_core.resources.envelope import Resource, dump_resource, load_resource
from quality_core.resources.ids import tombstone_path, tombstones_root
from quality_core.resources.locks import ProjectWriteLock
from quality_core.resources.paths import (
    allowed_prefixes,
    collection_root,
    find_collection,
    id_prefix,
    resource_path_for_collection_id,
    validate_resource_path,
)
from quality_core.workspace.project import ProjectConfig


@dataclass(frozen=True, slots=True)
class ChangedReference:
    path: Path
    field_path: str
    old_value: str
    new_value: str


@dataclass(frozen=True, slots=True)
class RenumberResult:
    project: ProjectConfig
    kind: str
    from_id: str
    to_id: str
    old_path: Path
    new_path: Path
    changed_paths: tuple[Path, ...]
    changed_references: tuple[ChangedReference, ...]


@dataclass(frozen=True, slots=True)
class IdConflictRepairResult:
    project: ProjectConfig
    renumbers: tuple[RenumberResult, ...]

    @property
    def changed_paths(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        for result in self.renumbers:
            paths.extend(result.changed_paths)
        return _unique_paths(paths)


@dataclass(frozen=True, slots=True)
class _ResourceFile:
    plugin: BuiltinPlugin
    collection: PluginCollection
    path: Path
    resource: Resource

    @property
    def path_id(self) -> str:
        return self.path.stem


def renumber_project_resource_id(
    *,
    project: ProjectConfig,
    from_id: str,
    to_id: str,
) -> RenumberResult:
    if from_id == to_id:
        raise QualityCliError(
            code="ID_CONFLICT",
            message="The source and target resource IDs are identical.",
            target={"fromId": from_id, "toId": to_id},
            suggestion="Provide a different target ID.",
        )

    with ProjectWriteLock(project.root):
        entries = _list_collection_resource_files(project)
        matches = [entry for entry in entries if entry.resource.resource_id == from_id]
        if not matches:
            raise QualityCliError(
                code="RESOURCE_NOT_FOUND",
                message=f"Resource ID '{from_id}' was not found in project '{project.slug}'.",
                target={"fromId": from_id, "projectSlug": project.slug},
                suggestion="Check the source ID or run validation to inspect ID conflicts.",
            )
        if len(matches) > 1:
            raise QualityCliError(
                code="ID_CONFLICT",
                message=f"Resource ID '{from_id}' is used by multiple files.",
                target={"fromId": from_id, "paths": [str(entry.path) for entry in matches]},
                suggestion="Run `quality project repair id-conflicts` before explicit renumbering.",
            )

        entry = matches[0]
        _validate_target_id(project=project, entries=entries, entry=entry, to_id=to_id)
        return _renumber_entry_locked(
            project=project,
            entry=entry,
            to_id=to_id,
            update_references=True,
        )


def repair_project_id_conflicts(*, project: ProjectConfig) -> IdConflictRepairResult:
    with ProjectWriteLock(project.root):
        entries = _list_collection_resource_files(project)
        planned: list[tuple[_ResourceFile, str]] = []
        planned_paths: set[Path] = set()

        by_id: dict[str, list[_ResourceFile]] = {}
        for entry in entries:
            by_id.setdefault(entry.resource.resource_id, []).append(entry)

        for resource_id, group in sorted(by_id.items()):
            if len(group) < 2:
                continue
            keep = _choose_duplicate_keep_entry(group, resource_id)
            for entry in group:
                if entry.path == keep.path:
                    continue
                planned.append(
                    (
                        entry,
                        _repair_target_id(
                            project=project,
                            entries=entries,
                            entry=entry,
                            planned_paths=planned_paths,
                        ),
                    )
                )

        planned_source_paths = {entry.path for entry, _ in planned}
        for entry in entries:
            if entry.path in planned_source_paths:
                continue
            if entry.path_id == entry.resource.resource_id:
                continue
            planned.append(
                (
                    entry,
                    _repair_target_id(
                        project=project,
                        entries=entries,
                        entry=entry,
                        planned_paths=planned_paths,
                    ),
                )
            )

        results = tuple(
            _renumber_entry_locked(
                project=project,
                entry=entry,
                to_id=to_id,
                update_references=False,
            )
            for entry, to_id in planned
        )
        return IdConflictRepairResult(project=project, renumbers=results)


def _renumber_entry_locked(
    *,
    project: ProjectConfig,
    entry: _ResourceFile,
    to_id: str,
    update_references: bool,
) -> RenumberResult:
    old_id = entry.resource.resource_id
    old_path = entry.path
    new_path = resource_path_for_collection_id(
        project_root=project.root,
        plugin=entry.plugin,
        kind=entry.resource.kind,
        resource_id=to_id,
    )
    metadata = dict(entry.resource.metadata)
    metadata["id"] = to_id
    updated_resource = Resource(
        api_version=entry.resource.api_version,
        kind=entry.resource.kind,
        metadata=metadata,
        spec=dict(entry.resource.spec),
        status=dict(entry.resource.status) if entry.resource.status is not None else None,
    )
    validate_resource_path(plugin=entry.plugin, resource=updated_resource, path=new_path)
    atomic_write_text(new_path, dump_resource(updated_resource.with_path(new_path)))
    if old_path != new_path and old_path.exists():
        old_path.unlink()

    changed_paths: list[Path] = [old_path, new_path]
    changed_refs: list[ChangedReference] = []
    reference_entries = (
        _list_collection_resource_files(project)
        if update_references
        else [
            _ResourceFile(
                plugin=entry.plugin,
                collection=entry.collection,
                path=new_path,
                resource=load_resource(new_path),
            )
        ]
    )
    for ref_entry in reference_entries:
        resource = ref_entry.resource
        new_spec, spec_refs = _replace_references(
            resource.spec,
            old_id=old_id,
            new_id=to_id,
            path_prefix="spec",
            source_path=ref_entry.path,
        )
        new_status: dict[str, Any] | None = None
        status_refs: list[ChangedReference] = []
        if resource.status is not None:
            replaced_status, status_refs = _replace_references(
                resource.status,
                old_id=old_id,
                new_id=to_id,
                path_prefix="status",
                source_path=ref_entry.path,
            )
            new_status = replaced_status
        if not spec_refs and not status_refs:
            continue
        rewritten = Resource(
            api_version=resource.api_version,
            kind=resource.kind,
            metadata=dict(resource.metadata),
            spec=new_spec,
            path=ref_entry.path,
            status=new_status,
        )
        atomic_write_text(ref_entry.path, dump_resource(rewritten.with_path(ref_entry.path)))
        changed_paths.append(ref_entry.path)
        changed_refs.extend(spec_refs)
        changed_refs.extend(status_refs)

    return RenumberResult(
        project=project,
        kind=entry.resource.kind,
        from_id=old_id,
        to_id=to_id,
        old_path=old_path,
        new_path=new_path,
        changed_paths=_unique_paths(changed_paths),
        changed_references=tuple(changed_refs),
    )


def _list_collection_resource_files(project: ProjectConfig) -> list[_ResourceFile]:
    entries: list[_ResourceFile] = []
    for plugin in _enabled_plugins(project):
        for collection in plugin.collections:
            root = collection_root(
                project_root=project.root,
                plugin=plugin,
                collection=collection,
            )
            if not root.exists():
                continue
            for path in sorted(root.glob("*.yaml")):
                resource = load_resource(path)
                if resource.kind != collection.kind:
                    raise QualityCliError(
                        code="INVALID_PROJECT_CONFIG",
                        message=(
                            f"Resource file '{path}' has kind '{resource.kind}', "
                            f"expected '{collection.kind}'."
                        ),
                        path=str(path),
                        field="kind",
                        suggestion=(
                            "Move the file to the declared collection or repair the resource kind."
                        ),
                    )
                entries.append(
                    _ResourceFile(
                        plugin=plugin,
                        collection=collection,
                        path=path,
                        resource=resource,
                    )
                )
    return entries


def _enabled_plugins(project: ProjectConfig) -> list[BuiltinPlugin]:
    enabled: list[BuiltinPlugin] = []
    for plugin in list_builtin_plugins():
        domain = project.domains.get(plugin.domain_key)
        if isinstance(domain, dict) and domain.get("enabled") is True:
            enabled.append(plugin)
    return enabled


def _validate_target_id(
    *,
    project: ProjectConfig,
    entries: list[_ResourceFile],
    entry: _ResourceFile,
    to_id: str,
) -> None:
    find_collection(entry.plugin, kind=entry.resource.kind, resource_id=to_id)
    for candidate in entries:
        if candidate.path == entry.path:
            continue
        if candidate.path_id == to_id or candidate.resource.resource_id == to_id:
            raise QualityCliError(
                code="ID_CONFLICT",
                message=f"Target ID '{to_id}' is already used.",
                path=str(candidate.path),
                target={"toId": to_id, "existingPath": str(candidate.path)},
                suggestion="Choose an unused ID.",
            )
    target_path = resource_path_for_collection_id(
        project_root=project.root,
        plugin=entry.plugin,
        kind=entry.resource.kind,
        resource_id=to_id,
    )
    if target_path.exists() and target_path != entry.path:
        raise QualityCliError(
            code="ID_CONFLICT",
            message=f"Target path '{target_path}' already exists.",
            path=str(target_path),
            target={"toId": to_id},
            suggestion="Choose an unused ID.",
        )
    tombstone = tombstone_path(project.root, to_id)
    if tombstone.exists():
        raise QualityCliError(
            code="ID_CONFLICT",
            message=f"Target ID '{to_id}' is tombstoned and cannot be reused.",
            path=str(tombstone),
            target={"toId": to_id},
            suggestion="Choose an ID greater than existing source and tombstone sequences.",
        )


def _choose_duplicate_keep_entry(group: list[_ResourceFile], resource_id: str) -> _ResourceFile:
    for entry in group:
        if entry.path_id == resource_id:
            return entry
    return sorted(group, key=lambda item: str(item.path))[0]


def _repair_target_id(
    *,
    project: ProjectConfig,
    entries: list[_ResourceFile],
    entry: _ResourceFile,
    planned_paths: set[Path],
) -> str:
    if _is_valid_id_for_entry(entry, entry.path_id) and not _id_is_reserved(
        project=project,
        entries=entries,
        entry=entry,
        resource_id=entry.path_id,
    ):
        planned_paths.add(entry.path)
        return entry.path_id

    target_id = _next_available_id(project=project, entries=entries, entry=entry)
    target_path = resource_path_for_collection_id(
        project_root=project.root,
        plugin=entry.plugin,
        kind=entry.resource.kind,
        resource_id=target_id,
    )
    if target_path in planned_paths:
        target_id = _next_available_id(
            project=project,
            entries=entries,
            entry=entry,
            extra_reserved={target_id},
        )
        target_path = resource_path_for_collection_id(
            project_root=project.root,
            plugin=entry.plugin,
            kind=entry.resource.kind,
            resource_id=target_id,
        )
    planned_paths.add(target_path)
    return target_id


def _is_valid_id_for_entry(entry: _ResourceFile, resource_id: str) -> bool:
    try:
        find_collection(entry.plugin, kind=entry.resource.kind, resource_id=resource_id)
    except QualityCliError:
        return False
    return True


def _id_is_reserved(
    *,
    project: ProjectConfig,
    entries: list[_ResourceFile],
    entry: _ResourceFile,
    resource_id: str,
) -> bool:
    for candidate in entries:
        if candidate.path == entry.path:
            continue
        if candidate.path_id == resource_id or candidate.resource.resource_id == resource_id:
            return True
    return tombstone_path(project.root, resource_id).exists()


def _next_available_id(
    *,
    project: ProjectConfig,
    entries: list[_ResourceFile],
    entry: _ResourceFile,
    extra_reserved: set[str] | None = None,
) -> str:
    prefix = id_prefix(entry.resource.resource_id)
    if prefix not in allowed_prefixes(entry.collection):
        prefix = allowed_prefixes(entry.collection)[0]
    reserved = set(extra_reserved or set())
    for candidate in entries:
        if candidate.collection == entry.collection:
            reserved.add(candidate.path_id)
            reserved.add(candidate.resource.resource_id)
    tombstone_root = tombstones_root(project.root)
    if tombstone_root.exists():
        for path in tombstone_root.glob(f"{prefix}-*"):
            reserved.add(path.name)

    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    max_sequence = 0
    for resource_id in reserved:
        match = pattern.fullmatch(resource_id)
        if match is not None:
            max_sequence = max(max_sequence, int(match.group(1)))
    next_sequence = max_sequence + 1
    while True:
        width = max(3, len(str(next_sequence)))
        candidate = f"{prefix}-{next_sequence:0{width}d}"
        if candidate not in reserved:
            return candidate
        next_sequence += 1


def _replace_references(
    value: Any,
    *,
    old_id: str,
    new_id: str,
    path_prefix: str,
    source_path: Path,
) -> tuple[Any, list[ChangedReference]]:
    if isinstance(value, str):
        if value == old_id:
            return new_id, [
                ChangedReference(
                    path=source_path,
                    field_path=path_prefix,
                    old_value=old_id,
                    new_value=new_id,
                )
            ]
        return value, []
    if isinstance(value, list):
        changed_refs: list[ChangedReference] = []
        changed_values: list[Any] = []
        for index, item in enumerate(value):
            changed_value, item_refs = _replace_references(
                item,
                old_id=old_id,
                new_id=new_id,
                path_prefix=f"{path_prefix}[{index}]",
                source_path=source_path,
            )
            changed_values.append(changed_value)
            changed_refs.extend(item_refs)
        return changed_values, changed_refs
    if isinstance(value, dict):
        changed_refs = []
        changed_mapping: dict[str, Any] = {}
        for key, item in value.items():
            changed_value, item_refs = _replace_references(
                item,
                old_id=old_id,
                new_id=new_id,
                path_prefix=f"{path_prefix}.{key}",
                source_path=source_path,
            )
            changed_mapping[key] = changed_value
            changed_refs.extend(item_refs)
        return changed_mapping, changed_refs
    return value, []


def _unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return tuple(result)
