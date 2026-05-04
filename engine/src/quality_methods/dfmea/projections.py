from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from quality_core.graph import ProjectGraph, load_project_graph
from quality_core.projections import (
    projection_freshness,
    write_projection_manifest,
)
from quality_core.resources.atomic import atomic_write_text
from quality_core.resources.envelope import Resource
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.analysis_service import (
    ACTION_KIND,
    FAILURE_CAUSE_KIND,
    FAILURE_MODE_KIND,
)
from quality_methods.dfmea.plugin import PLUGIN_ID, PLUGIN_VERSION
from quality_methods.dfmea.query_service import resource_summary

DOMAIN = "dfmea"


@dataclass(frozen=True, slots=True)
class DfmeaProjectionResult:
    project: ProjectConfig
    data: dict[str, Any]


def get_projection_status(*, project: ProjectConfig) -> DfmeaProjectionResult:
    freshness = projection_freshness(project=project, domain=DOMAIN)
    return DfmeaProjectionResult(
        project=project,
        data={
            "projectSlug": project.slug,
            "freshness": freshness.to_dict(),
            "generatedOutputs": {
                "projectionsManaged": project.generated_outputs.projections_managed,
                "exportsManaged": project.generated_outputs.exports_managed,
                "reportsManaged": project.generated_outputs.reports_managed,
                "exportProfiles": list(project.generated_outputs.export_profiles),
            },
        },
    )


def rebuild_projections(*, project: ProjectConfig) -> DfmeaProjectionResult:
    graph = load_project_graph(project=project)
    projection_payloads = {
        "dfmea/projections/tree.json": build_tree_projection(graph=graph),
        "dfmea/projections/risk-register.json": build_risk_register_projection(graph=graph),
        "dfmea/projections/action-backlog.json": build_action_backlog_projection(graph=graph),
        "dfmea/projections/traceability.json": build_traceability_projection(graph=graph),
    }
    projection_hashes: dict[str, str] = {}
    written: list[dict[str, Any]] = []
    for relative_path, payload in projection_payloads.items():
        path = project.root / relative_path
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        atomic_write_text(path, content)
        projection_hashes[relative_path] = _content_hash(content)
        written.append(
            {
                "path": str(path),
                "relativePath": relative_path,
                "kind": payload["kind"],
                "bytes": path.stat().st_size,
            }
        )

    manifest = write_projection_manifest(
        project=project,
        domain=DOMAIN,
        schema_versions={PLUGIN_ID: PLUGIN_VERSION},
        projections=projection_hashes,
    )
    freshness = projection_freshness(project=project, domain=DOMAIN)
    return DfmeaProjectionResult(
        project=project,
        data={
            "projectSlug": project.slug,
            "written": [
                *written,
                {
                    "path": str(project.root / "dfmea" / "projections" / "manifest.json"),
                    "relativePath": "dfmea/projections/manifest.json",
                    "kind": "ProjectionManifest",
                },
            ],
            "manifest": manifest,
            "freshness": freshness.to_dict(),
        },
    )


def build_tree_projection(*, graph: ProjectGraph) -> dict[str, Any]:
    structure = sorted(graph.kind("StructureNode"), key=lambda resource: resource.resource_id)
    by_parent: dict[str | None, list[Resource]] = {}
    for resource in structure:
        parent_ref = _string_or_none(resource.spec.get("parentRef"))
        by_parent.setdefault(parent_ref, []).append(resource)

    def node(resource: Resource) -> dict[str, Any]:
        return {
            **resource_summary(resource, graph=graph),
            "children": [node(child) for child in by_parent.get(resource.resource_id, [])],
        }

    roots = [
        node(resource)
        for resource in by_parent.get(None, [])
        if resource.spec.get("nodeType") == "system"
    ]
    return {
        "apiVersion": "quality.ai/v1",
        "kind": "DfmeaStructureTreeProjection",
        "projectSlug": graph.project.slug,
        "roots": roots,
        "resources": [resource_summary(resource, graph=graph) for resource in structure],
    }


def build_risk_register_projection(*, graph: ProjectGraph) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for fm in sorted(graph.kind(FAILURE_MODE_KIND), key=lambda resource: resource.resource_id):
        causes = [
            resource
            for resource in graph.kind(FAILURE_CAUSE_KIND)
            if resource.spec.get("failureModeRef") == fm.resource_id
        ]
        if not causes:
            rows.append(_risk_row(graph=graph, fm=fm, cause=None))
            continue
        for cause in causes:
            rows.append(_risk_row(graph=graph, fm=fm, cause=cause))
    return {
        "apiVersion": "quality.ai/v1",
        "kind": "DfmeaRiskRegisterProjection",
        "projectSlug": graph.project.slug,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "highAp": sum(1 for row in rows if row.get("ap") == "High"),
            "severityGte7": sum(
                1 for row in rows if isinstance(row.get("severity"), int) and row["severity"] >= 7
            ),
        },
    }


def build_action_backlog_projection(*, graph: ProjectGraph) -> dict[str, Any]:
    actions = sorted(graph.kind(ACTION_KIND), key=lambda resource: resource.resource_id)
    items = [
        {
            **resource_summary(action, graph=graph),
            "status": action.spec.get("status"),
            "owner": action.spec.get("owner"),
            "due": action.spec.get("due"),
            "failureModeRef": action.spec.get("failureModeRef"),
            "targetCauseRefs": action.spec.get("targetCauseRefs", []),
        }
        for action in actions
    ]
    return {
        "apiVersion": "quality.ai/v1",
        "kind": "DfmeaActionBacklogProjection",
        "projectSlug": graph.project.slug,
        "items": items,
        "summary": {
            "items": len(items),
            "open": sum(1 for item in items if item.get("status") != "completed"),
        },
    }


def build_traceability_projection(*, graph: ProjectGraph) -> dict[str, Any]:
    inline_refs = [
        reference.to_dict()
        for references in graph.references_by_id.values()
        for reference in references
    ]
    return {
        "apiVersion": "quality.ai/v1",
        "kind": "DfmeaTraceabilityProjection",
        "projectSlug": graph.project.slug,
        "inlineReferences": sorted(
            inline_refs,
            key=lambda item: (item["sourceId"], item["field"], item["targetId"]),
        ),
        "links": [link.to_dict() for link in graph.links],
        "summary": {
            "inlineReferences": len(inline_refs),
            "links": len(graph.links),
        },
    }


def _risk_row(
    *,
    graph: ProjectGraph,
    fm: Resource,
    cause: Resource | None,
) -> dict[str, Any]:
    function = graph.get(str(fm.spec.get("functionRef")))
    row = {
        "failureMode": resource_summary(fm, graph=graph),
        "failureModeId": fm.resource_id,
        "failureModePath": str(fm.path) if fm.path is not None else None,
        "functionId": function.resource_id if function is not None else fm.spec.get("functionRef"),
        "severity": fm.spec.get("severity"),
        "description": fm.spec.get("description"),
    }
    if cause is not None:
        row.update(
            {
                "cause": resource_summary(cause, graph=graph),
                "causeId": cause.resource_id,
                "causePath": str(cause.path) if cause.path is not None else None,
                "occurrence": cause.spec.get("occurrence"),
                "detection": cause.spec.get("detection"),
                "ap": cause.spec.get("ap"),
                "causeDescription": cause.spec.get("description"),
            }
        )
    return row


def _content_hash(content: str) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
