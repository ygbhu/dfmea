from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.graph import ProjectGraph, load_project_graph
from quality_core.resources.envelope import Resource
from quality_core.resources.paths import id_prefix
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.analysis_service import (
    ACTION_KIND,
    ALLOWED_ACTION_STATUSES,
    ALLOWED_AP_VALUES,
    FAILURE_CAUSE_KIND,
    FAILURE_MODE_KIND,
)

QUERYABLE_KINDS_BY_TOKEN = {
    "DFMEA": "DfmeaAnalysis",
    "SYS": "StructureNode",
    "SUB": "StructureNode",
    "COMP": "StructureNode",
    "FN": "Function",
    "REQ": "Requirement",
    "CHAR": "Characteristic",
    "FM": "FailureMode",
    "FE": "FailureEffect",
    "FC": "FailureCause",
    "ACT": "Action",
}


@dataclass(frozen=True, slots=True)
class DfmeaQueryResult:
    project: ProjectConfig
    data: dict[str, Any]
    freshness: dict[str, Any]


def query_get(*, project: ProjectConfig, resource_id: str) -> DfmeaQueryResult:
    graph = load_project_graph(project=project)
    resource = _require_resource(graph, resource_id)
    return _result(
        project=project,
        graph=graph,
        data={
            "projectSlug": project.slug,
            "resource": resource_summary(resource, graph=graph, include_spec=True),
            "references": [
                reference.to_dict()
                for reference in graph.references_by_id.get(resource.resource_id, ())
            ],
            "links": _link_dicts_for(graph=graph, resource_id=resource.resource_id),
        },
    )


def query_list(
    *,
    project: ProjectConfig,
    node_type: str,
    parent_ref: str | None = None,
) -> DfmeaQueryResult:
    graph = load_project_graph(project=project)
    kind = _kind_from_token(node_type)
    resources = list(graph.kind(kind))
    token = node_type.upper()
    if kind == "StructureNode" and token in {"SYS", "SUB", "COMP"}:
        node_type_value = {"SYS": "system", "SUB": "subsystem", "COMP": "component"}[token]
        resources = [
            resource for resource in resources if resource.spec.get("nodeType") == node_type_value
        ]
    if parent_ref is not None:
        resources = [resource for resource in resources if _parent_ref(resource) == parent_ref]
    return _resource_collection_result(project=project, graph=graph, resources=resources)


def query_search(*, project: ProjectConfig, keyword: str) -> DfmeaQueryResult:
    normalized = keyword.strip().lower()
    if not normalized:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="--keyword must not be empty.",
            target={"option": "--keyword"},
            suggestion="Provide a non-empty keyword.",
        )
    graph = load_project_graph(project=project)
    resources = [
        resource
        for resource in graph.resources
        if normalized in _searchable_text(resource, graph=graph).lower()
    ]
    return _resource_collection_result(project=project, graph=graph, resources=resources)


def query_summary(*, project: ProjectConfig, component_ref: str) -> DfmeaQueryResult:
    graph = load_project_graph(project=project)
    component = _require_resource(graph, component_ref)
    if component.kind != "StructureNode" or component.spec.get("nodeType") != "component":
        raise QualityCliError(
            code="INVALID_PARENT",
            message=f"Resource '{component_ref}' must be a component structure node.",
            target={"resourceId": component_ref, "kind": component.kind},
            suggestion="Use an existing COMP resource ID.",
        )
    functions = [
        resource
        for resource in graph.kind("Function")
        if resource.spec.get("componentRef") == component.resource_id
    ]
    function_ids = {resource.resource_id for resource in functions}
    failure_modes = [
        resource
        for resource in graph.kind(FAILURE_MODE_KIND)
        if resource.spec.get("functionRef") in function_ids
    ]
    fm_ids = {resource.resource_id for resource in failure_modes}
    effects = _children_for_fms(graph=graph, kind="FailureEffect", fm_ids=fm_ids)
    causes = _children_for_fms(graph=graph, kind=FAILURE_CAUSE_KIND, fm_ids=fm_ids)
    actions = _children_for_fms(graph=graph, kind=ACTION_KIND, fm_ids=fm_ids)
    return _result(
        project=project,
        graph=graph,
        data={
            "projectSlug": project.slug,
            "component": resource_summary(component, graph=graph),
            "counts": {
                "functions": len(functions),
                "failureModes": len(failure_modes),
                "effects": len(effects),
                "causes": len(causes),
                "actions": len(actions),
            },
            "functions": _summaries(functions, graph=graph),
            "failureModes": _summaries(failure_modes, graph=graph),
            "actions": _summaries(actions, graph=graph),
        },
    )


def query_map(*, project: ProjectConfig) -> DfmeaQueryResult:
    graph = load_project_graph(project=project)
    structure = _summaries(graph.kind("StructureNode"), graph=graph)
    functions = _summaries(graph.kind("Function"), graph=graph)
    failure_modes = _summaries(graph.kind(FAILURE_MODE_KIND), graph=graph)
    return _result(
        project=project,
        graph=graph,
        data={
            "projectSlug": project.slug,
            "counts": {
                "resources": len(graph.resources),
                "structureNodes": len(structure),
                "functions": len(functions),
                "failureModes": len(failure_modes),
                "links": len(graph.links),
            },
            "structure": structure,
            "functions": functions,
            "failureModes": failure_modes,
            "links": [link.to_dict() for link in graph.links],
        },
    )


def query_by_ap(*, project: ProjectConfig, ap: str) -> DfmeaQueryResult:
    if ap not in ALLOWED_AP_VALUES:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message=f"Unsupported AP value '{ap}'.",
            target={"ap": ap},
            suggestion="Use one of High, Medium, or Low.",
        )
    graph = load_project_graph(project=project)
    resources = list(graph.risks_by_ap.get(ap, ()))
    return _resource_collection_result(project=project, graph=graph, resources=resources)


def query_by_severity(*, project: ProjectConfig, gte: int) -> DfmeaQueryResult:
    if gte < 1 or gte > 10:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="--gte must be between 1 and 10.",
            target={"option": "--gte", "value": gte},
            suggestion="Provide a severity threshold from 1 to 10.",
        )
    graph = load_project_graph(project=project)
    resources: list[Resource] = []
    for resource in graph.kind(FAILURE_MODE_KIND):
        severity = _int_or_none(resource.spec.get("severity"))
        if severity is not None and severity >= gte:
            resources.append(resource)
    return _resource_collection_result(project=project, graph=graph, resources=resources)


def query_actions(*, project: ProjectConfig, status: str) -> DfmeaQueryResult:
    if status not in ALLOWED_ACTION_STATUSES:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message=f"Unsupported action status '{status}'.",
            target={"status": status},
            suggestion="Use one of planned, in-progress, or completed.",
        )
    graph = load_project_graph(project=project)
    resources = list(graph.actions_by_status.get(status, ()))
    return _resource_collection_result(project=project, graph=graph, resources=resources)


def resource_summary(
    resource: Resource,
    *,
    graph: ProjectGraph,
    include_spec: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": resource.resource_id,
        "kind": resource.kind,
        "domain": graph.domain_for(resource.resource_id),
        "path": str(resource.path) if resource.path is not None else None,
        "title": _title(resource),
        "summary": _summary(resource),
    }
    parent_ref = _parent_ref(resource)
    if parent_ref is not None:
        payload["parentRef"] = parent_ref
    if include_spec:
        payload["metadata"] = resource.metadata
        payload["spec"] = resource.spec
        if resource.status is not None:
            payload["status"] = resource.status
    return payload


def freshness_metadata(*, graph: ProjectGraph) -> dict[str, Any]:
    source_paths = sorted(
        str(resource.path) for resource in graph.resources if resource.path is not None
    )
    return {
        "mode": "source-scan",
        "projectionStatus": "not-built",
        "stale": False,
        "resourceCount": len(graph.resources),
        "linkCount": len(graph.links),
        "sourcePaths": source_paths,
    }


def _resource_collection_result(
    *,
    project: ProjectConfig,
    graph: ProjectGraph,
    resources: list[Resource],
) -> DfmeaQueryResult:
    return _result(
        project=project,
        graph=graph,
        data={
            "projectSlug": project.slug,
            "count": len(resources),
            "resources": _summaries(resources, graph=graph),
        },
    )


def _result(
    *,
    project: ProjectConfig,
    graph: ProjectGraph,
    data: dict[str, Any],
) -> DfmeaQueryResult:
    return DfmeaQueryResult(
        project=project,
        data=data,
        freshness=freshness_metadata(graph=graph),
    )


def _summaries(
    resources: tuple[Resource, ...] | list[Resource],
    *,
    graph: ProjectGraph,
) -> list[dict]:
    return [
        resource_summary(resource, graph=graph) for resource in sorted(resources, key=_sort_key)
    ]


def _children_for_fms(*, graph: ProjectGraph, kind: str, fm_ids: set[str]) -> list[Resource]:
    return [
        resource for resource in graph.kind(kind) if resource.spec.get("failureModeRef") in fm_ids
    ]


def _require_resource(graph: ProjectGraph, resource_id: str) -> Resource:
    resource = graph.get(resource_id)
    if resource is not None:
        return resource
    raise QualityCliError(
        code="RESOURCE_NOT_FOUND",
        message=f"Resource '{resource_id}' was not found.",
        target={"resourceId": resource_id},
        suggestion="Use an existing project-local resource ID.",
    )


def _kind_from_token(token: str) -> str:
    normalized = token.strip()
    if not normalized:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="--type must not be empty.",
            target={"option": "--type"},
            suggestion="Use a resource kind or ID prefix such as FM.",
        )
    upper = normalized.upper()
    if upper in QUERYABLE_KINDS_BY_TOKEN:
        return QUERYABLE_KINDS_BY_TOKEN[upper]
    for kind in set(QUERYABLE_KINDS_BY_TOKEN.values()):
        if normalized == kind:
            return kind
    raise QualityCliError(
        code="VALIDATION_FAILED",
        message=f"Unsupported query type '{token}'.",
        target={"type": token},
        suggestion="Use one of SYS, SUB, COMP, FN, REQ, CHAR, FM, FE, FC, ACT.",
    )


def _parent_ref(resource: Resource) -> str | None:
    for field in ("parentRef", "componentRef", "functionRef", "failureModeRef"):
        value = resource.spec.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def _title(resource: Resource) -> str | None:
    for value in (
        resource.metadata.get("title"),
        resource.metadata.get("name"),
        resource.spec.get("description"),
        resource.spec.get("text"),
    ):
        if isinstance(value, str) and value:
            return value
    return None


def _summary(resource: Resource) -> str | None:
    if resource.kind == "StructureNode":
        node_type = resource.spec.get("nodeType")
        title = _title(resource)
        return f"{node_type}: {title}" if isinstance(node_type, str) and title else title
    if resource.kind == FAILURE_MODE_KIND:
        severity = resource.spec.get("severity")
        title = _title(resource)
        return f"S{severity}: {title}" if isinstance(severity, int) and title else title
    if resource.kind == FAILURE_CAUSE_KIND:
        ap = resource.spec.get("ap")
        title = _title(resource)
        return f"AP {ap}: {title}" if isinstance(ap, str) and title else title
    if resource.kind == ACTION_KIND:
        status = resource.spec.get("status")
        title = _title(resource)
        return f"{status}: {title}" if isinstance(status, str) and title else title
    return _title(resource)


def _searchable_text(resource: Resource, *, graph: ProjectGraph) -> str:
    parts = [
        resource.resource_id,
        resource.kind,
        _title(resource) or "",
        _summary(resource) or "",
        str(resource.metadata),
        str(resource.spec),
        graph.domain_for(resource.resource_id) or "",
    ]
    return " ".join(parts)


def _link_dicts_for(*, graph: ProjectGraph, resource_id: str) -> list[dict[str, Any]]:
    return [
        link.to_dict()
        for link in (
            *graph.links_by_source.get(resource_id, ()),
            *graph.links_by_target.get(resource_id, ()),
        )
    ]


def _sort_key(resource: Resource) -> tuple[str, str]:
    return (id_prefix(resource.resource_id), resource.resource_id)


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
