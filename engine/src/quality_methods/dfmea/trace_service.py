from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.graph import ProjectGraph, load_project_graph
from quality_core.resources.envelope import Resource
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.analysis_service import (
    FAILURE_CAUSE_KIND,
    FAILURE_EFFECT_KIND,
    FAILURE_MODE_KIND,
)
from quality_methods.dfmea.query_service import freshness_metadata, resource_summary


@dataclass(frozen=True, slots=True)
class DfmeaTraceResult:
    project: ProjectConfig
    data: dict[str, Any]
    freshness: dict[str, Any]


def trace_causes(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    depth: int,
) -> DfmeaTraceResult:
    return _trace(
        project=project,
        failure_mode_ref=failure_mode_ref,
        depth=depth,
        direction="causes",
        via_kind=FAILURE_CAUSE_KIND,
    )


def trace_effects(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    depth: int,
) -> DfmeaTraceResult:
    return _trace(
        project=project,
        failure_mode_ref=failure_mode_ref,
        depth=depth,
        direction="effects",
        via_kind=FAILURE_EFFECT_KIND,
    )


def _trace(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    depth: int,
    direction: str,
    via_kind: str,
) -> DfmeaTraceResult:
    if depth < 0:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message="--depth must be a non-negative integer.",
            target={"option": "--depth", "value": depth},
            suggestion="Provide 0 or a larger integer for --depth.",
        )
    graph = load_project_graph(project=project)
    root = _require_failure_mode(graph, failure_mode_ref)
    chain = _walk_trace(graph=graph, root=root, depth=depth, via_kind=via_kind)
    return DfmeaTraceResult(
        project=project,
        data={
            "projectSlug": project.slug,
            "direction": direction,
            "root": resource_summary(root, graph=graph),
            "depthLimit": depth,
            "chain": chain,
        },
        freshness=freshness_metadata(graph=graph),
    )


def _walk_trace(
    *,
    graph: ProjectGraph,
    root: Resource,
    depth: int,
    via_kind: str,
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = [
        {
            "depth": 0,
            "failureMode": resource_summary(root, graph=graph),
            "via": None,
            "link": None,
        }
    ]
    queue: list[tuple[Resource, int]] = [(root, 0)]
    visited = {root.resource_id}

    while queue:
        current, current_depth = queue.pop(0)
        if current_depth >= depth:
            continue

        for via, target, link in _next_trace_steps(
            graph=graph,
            failure_mode=current,
            via_kind=via_kind,
        ):
            if target.resource_id in visited:
                continue
            visited.add(target.resource_id)
            next_depth = current_depth + 1
            chain.append(
                {
                    "depth": next_depth,
                    "failureMode": resource_summary(target, graph=graph),
                    "via": resource_summary(via, graph=graph),
                    "link": link.to_dict() if link is not None else None,
                }
            )
            queue.append((target, next_depth))
    return chain


def _next_trace_steps(
    *,
    graph: ProjectGraph,
    failure_mode: Resource,
    via_kind: str,
):
    via_resources = [
        resource
        for resource in graph.kind(via_kind)
        if resource.spec.get("failureModeRef") == failure_mode.resource_id
    ]
    for via in via_resources:
        for link in graph.links_by_source.get(via.resource_id, ()):
            target = graph.get(link.target_id)
            if target is not None and target.kind == FAILURE_MODE_KIND:
                yield via, target, link


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
