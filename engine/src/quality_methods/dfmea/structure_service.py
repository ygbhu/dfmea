from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.resources.envelope import Resource, make_resource
from quality_core.resources.paths import ResourceSelector, id_prefix
from quality_core.resources.store import ResourceStore, WriteResult
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.plugin import get_plugin

STRUCTURE_KIND = "StructureNode"
STRUCTURE_PREFIX_BY_TYPE = {
    "SYS": "SYS",
    "SYSTEM": "SYS",
    "SYSTEM_NODE": "SYS",
    "SUB": "SUB",
    "SUBSYSTEM": "SUB",
    "SUBSYSTEM_NODE": "SUB",
    "COMP": "COMP",
    "COMPONENT": "COMP",
    "COMPONENT_NODE": "COMP",
}
STRUCTURE_TYPE_BY_PREFIX = {
    "SYS": "system",
    "SUB": "subsystem",
    "COMP": "component",
}
PARENT_PREFIX_BY_PREFIX = {
    "SYS": None,
    "SUB": "SYS",
    "COMP": "SUB",
}


@dataclass(frozen=True, slots=True)
class StructureMutationResult:
    project: ProjectConfig
    resource: Resource
    write_result: WriteResult
    node_id: str
    node_type: str
    parent_id: str | None

    @property
    def path(self) -> Path:
        return self.write_result.path


def add_structure_node(
    *,
    project: ProjectConfig,
    node_type: str,
    title: str,
    parent_ref: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructureMutationResult:
    plugin = get_plugin()
    store = ResourceStore(project=project, plugin=plugin)
    prefix = normalize_structure_prefix(node_type)
    parent_id = _resolve_parent_id(store=store, child_prefix=prefix, parent_ref=parent_ref)

    resolved_metadata = dict(metadata or {})
    resolved_metadata["title"] = title
    spec: dict[str, Any] = {"nodeType": STRUCTURE_TYPE_BY_PREFIX[prefix]}
    if parent_id is not None:
        spec["parentRef"] = parent_id
    if description is not None:
        spec["description"] = description

    write_result = store.create_collection_resource(
        kind=STRUCTURE_KIND,
        id_prefix=prefix,
        metadata=resolved_metadata,
        spec=spec,
    )
    resource = store.load(store.ref(kind=STRUCTURE_KIND, resource_id=write_result.resource_id))
    return StructureMutationResult(
        project=project,
        resource=resource,
        write_result=write_result,
        node_id=resource.resource_id,
        node_type=prefix,
        parent_id=parent_id,
    )


def update_structure_node(
    *,
    project: ProjectConfig,
    node_ref: str,
    title: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructureMutationResult:
    plugin = get_plugin()
    store = ResourceStore(project=project, plugin=plugin)
    resource = _load_structure_resource(store=store, node_ref=node_ref)
    prefix = normalize_structure_prefix(resource.resource_id)

    resolved_metadata = dict(resource.metadata)
    if metadata is not None:
        resolved_metadata.update(metadata)
    if title is not None:
        resolved_metadata["title"] = title
    resolved_metadata["id"] = resource.resource_id

    spec = dict(resource.spec)
    if description is not None:
        spec["description"] = description

    updated = make_resource(
        kind=STRUCTURE_KIND,
        resource_id=resource.resource_id,
        metadata=resolved_metadata,
        spec=spec,
    )
    write_result = store.update(updated)
    stored = store.load(store.ref(kind=STRUCTURE_KIND, resource_id=resource.resource_id))
    return StructureMutationResult(
        project=project,
        resource=stored,
        write_result=write_result,
        node_id=stored.resource_id,
        node_type=prefix,
        parent_id=_string_or_none(stored.spec.get("parentRef")),
    )


def move_structure_node(
    *,
    project: ProjectConfig,
    node_ref: str,
    parent_ref: str | None,
) -> StructureMutationResult:
    plugin = get_plugin()
    store = ResourceStore(project=project, plugin=plugin)
    resource = _load_structure_resource(store=store, node_ref=node_ref)
    prefix = normalize_structure_prefix(resource.resource_id)
    parent_id = _resolve_parent_id(store=store, child_prefix=prefix, parent_ref=parent_ref)
    if parent_id == resource.resource_id:
        raise QualityCliError(
            code="INVALID_PARENT",
            message="A structure node cannot be its own parent.",
            target={"nodeId": resource.resource_id, "parentRef": parent_ref},
            suggestion="Choose a different parent structure node.",
        )

    spec = dict(resource.spec)
    if parent_id is None:
        spec.pop("parentRef", None)
    else:
        spec["parentRef"] = parent_id
    updated = make_resource(
        kind=STRUCTURE_KIND,
        resource_id=resource.resource_id,
        metadata=dict(resource.metadata),
        spec=spec,
    )
    write_result = store.update(updated)
    stored = store.load(store.ref(kind=STRUCTURE_KIND, resource_id=resource.resource_id))
    return StructureMutationResult(
        project=project,
        resource=stored,
        write_result=write_result,
        node_id=stored.resource_id,
        node_type=prefix,
        parent_id=parent_id,
    )


def delete_structure_node(
    *,
    project: ProjectConfig,
    node_ref: str,
) -> StructureMutationResult:
    plugin = get_plugin()
    store = ResourceStore(project=project, plugin=plugin)
    resource = _load_structure_resource(store=store, node_ref=node_ref)
    children = [
        candidate.resource_id
        for candidate in store.list(ResourceSelector(kind=STRUCTURE_KIND))
        if candidate.spec.get("parentRef") == resource.resource_id
    ]
    if children:
        raise QualityCliError(
            code="NODE_NOT_EMPTY",
            message=f"Structure node '{resource.resource_id}' still has child nodes.",
            target={"nodeId": resource.resource_id, "children": children},
            suggestion="Delete or move child structure nodes first.",
        )

    write_result = store.delete(store.ref(kind=STRUCTURE_KIND, resource_id=resource.resource_id))
    return StructureMutationResult(
        project=project,
        resource=resource,
        write_result=write_result,
        node_id=resource.resource_id,
        node_type=normalize_structure_prefix(resource.resource_id),
        parent_id=_string_or_none(resource.spec.get("parentRef")),
    )


def normalize_structure_prefix(value: str) -> str:
    candidate = id_prefix(value).upper().replace("-", "_")
    prefix = STRUCTURE_PREFIX_BY_TYPE.get(candidate)
    if prefix is None:
        raise QualityCliError(
            code="ID_PREFIX_MISMATCH",
            message=f"Unsupported structure node type or ID '{value}'.",
            target={"value": value},
            suggestion="Use SYS, SUB, COMP, system, subsystem, or component.",
        )
    return prefix


def _load_structure_resource(*, store: ResourceStore, node_ref: str) -> Resource:
    normalize_structure_prefix(node_ref)
    resource = store.load(store.ref(kind=STRUCTURE_KIND, resource_id=node_ref))
    normalize_structure_prefix(resource.resource_id)
    return resource


def _resolve_parent_id(
    *,
    store: ResourceStore,
    child_prefix: str,
    parent_ref: str | None,
) -> str | None:
    expected_prefix = PARENT_PREFIX_BY_PREFIX[child_prefix]
    if expected_prefix is None:
        if parent_ref is not None:
            raise QualityCliError(
                code="INVALID_PARENT",
                message="System structure nodes must not specify a parent.",
                target={"nodeType": child_prefix, "parentRef": parent_ref},
                suggestion="Omit --parent for system structure nodes.",
            )
        return None

    if parent_ref is None:
        raise QualityCliError(
            code="INVALID_PARENT",
            message=f"{child_prefix} structure nodes require a {expected_prefix} parent.",
            target={"nodeType": child_prefix, "parentRef": None},
            suggestion=f"Provide --parent with an existing {expected_prefix} node.",
        )

    parent_prefix = normalize_structure_prefix(parent_ref)
    if parent_prefix != expected_prefix:
        raise QualityCliError(
            code="INVALID_PARENT",
            message=f"{child_prefix} structure nodes require a {expected_prefix} parent.",
            target={
                "nodeType": child_prefix,
                "parentRef": parent_ref,
                "parentType": parent_prefix,
            },
            suggestion=f"Use a {expected_prefix} parent for {child_prefix} nodes.",
        )
    parent = store.load(store.ref(kind=STRUCTURE_KIND, resource_id=parent_ref))
    return parent.resource_id


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
