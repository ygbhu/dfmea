from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.graph import ProjectGraph, load_project_graph
from quality_core.resources.envelope import Resource
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.analysis_service import (
    ACTION_KIND,
    FAILURE_CAUSE_KIND,
    FAILURE_EFFECT_KIND,
    FAILURE_MODE_KIND,
)
from quality_methods.dfmea.query_service import freshness_metadata, resource_summary


@dataclass(frozen=True, slots=True)
class DfmeaContextResult:
    project: ProjectConfig
    data: dict[str, Any]
    freshness: dict[str, Any]


def failure_chain_context(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
) -> DfmeaContextResult:
    graph = load_project_graph(project=project)
    root = _require_failure_mode(graph, failure_mode_ref)
    related = _related_failure_chain_resources(graph=graph, failure_mode=root)
    link_ids = {root.resource_id, *(resource.resource_id for resource in related)}
    links = [
        link.to_dict()
        for link in graph.links
        if link.source_id in link_ids or link.target_id in link_ids
    ]
    paths = sorted(str(resource.path) for resource in (root, *related) if resource.path is not None)
    return DfmeaContextResult(
        project=project,
        data={
            "projectSlug": project.slug,
            "root": resource_summary(root, graph=graph, include_spec=True),
            "relatedResources": [
                resource_summary(resource, graph=graph, include_spec=True)
                for resource in sorted(related, key=lambda item: item.resource_id)
            ],
            "links": links,
            "paths": paths,
            "freshness": freshness_metadata(graph=graph),
        },
        freshness=freshness_metadata(graph=graph),
    )


def _related_failure_chain_resources(
    *,
    graph: ProjectGraph,
    failure_mode: Resource,
) -> tuple[Resource, ...]:
    related_ids: set[str] = set()
    for field in ("functionRef",):
        value = failure_mode.spec.get(field)
        if isinstance(value, str) and value:
            related_ids.add(value)
    for field in ("requirementRefs", "characteristicRefs", "effectRefs", "causeRefs", "actionRefs"):
        value = failure_mode.spec.get(field)
        if isinstance(value, list):
            related_ids.update(item for item in value if isinstance(item, str) and item)

    for kind in (FAILURE_EFFECT_KIND, FAILURE_CAUSE_KIND, ACTION_KIND):
        for resource in graph.kind(kind):
            if resource.spec.get("failureModeRef") == failure_mode.resource_id:
                related_ids.add(resource.resource_id)

    for action in graph.kind(ACTION_KIND):
        if action.resource_id not in related_ids:
            continue
        target_refs = action.spec.get("targetCauseRefs")
        if isinstance(target_refs, list):
            related_ids.update(item for item in target_refs if isinstance(item, str) and item)

    return tuple(
        resource
        for resource_id in sorted(related_ids)
        if (resource := graph.get(resource_id)) is not None
    )


def _require_failure_mode(graph: ProjectGraph, resource_id: str) -> Resource:
    resource = graph.get(resource_id)
    if resource is not None and resource.kind == FAILURE_MODE_KIND:
        return resource
    raise QualityCliError(
        code="RESOURCE_NOT_FOUND" if resource is None else "INVALID_PARENT",
        message=f"Resource '{resource_id}' must be a FailureMode.",
        target={
            "resourceId": resource_id,
            "kind": resource.kind if resource is not None else None,
        },
        suggestion="Use an existing FM resource ID.",
    )
