from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from quality_core.cli.errors import QualityCliError
from quality_core.graph.model import GraphLink, GraphReference, ProjectGraph
from quality_core.methods.registry import list_active_quality_methods
from quality_core.plugins.contracts import BuiltinPlugin
from quality_core.plugins.schema_snapshots import ensure_project_schema_snapshot_current
from quality_core.resources.envelope import Resource, load_resource, resource_from_document
from quality_core.resources.paths import collection_root, singleton_path, validate_resource_path
from quality_core.workspace.project import ProjectConfig


def load_project_graph(*, project: ProjectConfig) -> ProjectGraph:
    resources: list[Resource] = []
    resource_domains: dict[str, str] = {}
    enabled_plugins = _enabled_builtin_plugins(project)

    for plugin in enabled_plugins:
        ensure_project_schema_snapshot_current(plugin=plugin, project_root=project.root)
        for resource in _load_plugin_resources(project=project, plugin=plugin):
            resources.append(resource)
            resource_domains[resource.resource_id] = plugin.domain_key

    link_sets = _load_project_link_sets(project)
    resources.extend(link_sets)
    for resource in link_sets:
        resource_domains[resource.resource_id] = "project"

    return _build_graph(project=project, resources=tuple(resources), domains=resource_domains)


def _load_plugin_resources(*, project: ProjectConfig, plugin: BuiltinPlugin) -> list[Resource]:
    resources: list[Resource] = []
    for singleton in plugin.singletons:
        path = singleton_path(
            project_root=project.root,
            plugin=plugin,
            kind=singleton.kind,
            resource_id=singleton.resource_id,
        )
        if not path.exists():
            raise QualityCliError(
                code="RESOURCE_NOT_FOUND",
                message=f"Required singleton resource '{singleton.kind}' is missing.",
                path=str(path),
                target={"kind": singleton.kind, "resourceId": singleton.resource_id},
                suggestion="Run the domain init command or restore the missing resource.",
            )
        resource = load_resource(path)
        validate_resource_path(plugin=plugin, resource=resource, path=path)
        resources.append(resource)

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
            validate_resource_path(plugin=plugin, resource=resource, path=path)
            resources.append(resource)
    return resources


def _load_project_link_sets(project: ProjectConfig) -> list[Resource]:
    link_root = project.root / "links"
    if not link_root.exists():
        return []

    resources: list[Resource] = []
    for path in sorted(link_root.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise QualityCliError(
                code="INVALID_PROJECT_CONFIG",
                message=f"Trace link set '{path}' is not valid YAML.",
                path=str(path),
                suggestion="Repair the link set YAML before querying the graph.",
            ) from exc
        if not isinstance(loaded, dict):
            raise QualityCliError(
                code="INVALID_PROJECT_CONFIG",
                message=f"Trace link set '{path}' must contain a YAML mapping.",
                path=str(path),
                suggestion="Repair the link set resource envelope.",
            )
        resource = resource_from_document(loaded, path=path)
        if resource.kind != "TraceLinkSet":
            raise QualityCliError(
                code="INVALID_PROJECT_CONFIG",
                message=f"Project link resource '{path}' must use kind TraceLinkSet.",
                path=str(path),
                field="kind",
                suggestion="Move non-link resources under a plugin domain directory.",
            )
        if resource.resource_id != path.stem:
            raise QualityCliError(
                code="ID_PREFIX_MISMATCH",
                message="TraceLinkSet file name must match metadata.id.",
                path=str(path),
                target={"resourceId": resource.resource_id, "expectedFile": f"{path.stem}.yaml"},
                suggestion="Rename the link file or repair metadata.id.",
            )
        resources.append(resource)
    return resources


def _build_graph(
    *,
    project: ProjectConfig,
    resources: tuple[Resource, ...],
    domains: dict[str, str],
) -> ProjectGraph:
    by_id: dict[str, Resource] = {}
    by_kind_lists: dict[str, list[Resource]] = defaultdict(list)
    by_path: dict[Path, Resource] = {}
    references_by_id_lists: dict[str, list[GraphReference]] = defaultdict(list)
    links: list[GraphLink] = []
    links_by_source_lists: dict[str, list[GraphLink]] = defaultdict(list)
    links_by_target_lists: dict[str, list[GraphLink]] = defaultdict(list)
    actions_by_status_lists: dict[str, list[Resource]] = defaultdict(list)
    risks_by_ap_lists: dict[str, list[Resource]] = defaultdict(list)

    for resource in resources:
        by_id[resource.resource_id] = resource
        by_kind_lists[resource.kind].append(resource)
        if resource.path is not None:
            by_path[resource.path] = resource

    for resource in resources:
        for reference in _scan_inline_references(resource):
            references_by_id_lists[reference.target_id].append(reference)

        if resource.kind == "Action":
            status = _string_or_none(resource.spec.get("status"))
            if status is not None:
                actions_by_status_lists[status].append(resource)

        if resource.kind == "FailureCause":
            ap = _string_or_none(resource.spec.get("ap"))
            if ap is not None:
                risks_by_ap_lists[ap].append(resource)

        if resource.kind == "TraceLinkSet":
            for link in _scan_trace_links(resource):
                links.append(link)
                links_by_source_lists[link.source_id].append(link)
                links_by_target_lists[link.target_id].append(link)

    return ProjectGraph(
        project=project,
        resources=resources,
        resource_domains=domains,
        resources_by_id=by_id,
        resources_by_kind={kind: tuple(items) for kind, items in by_kind_lists.items()},
        resources_by_path=by_path,
        references_by_id={
            resource_id: tuple(items) for resource_id, items in references_by_id_lists.items()
        },
        links=tuple(links),
        links_by_source={
            resource_id: tuple(items) for resource_id, items in links_by_source_lists.items()
        },
        links_by_target={
            resource_id: tuple(items) for resource_id, items in links_by_target_lists.items()
        },
        actions_by_status={
            status: tuple(items) for status, items in actions_by_status_lists.items()
        },
        risks_by_ap={ap: tuple(items) for ap, items in risks_by_ap_lists.items()},
    )


def _scan_inline_references(resource: Resource) -> list[GraphReference]:
    references: list[GraphReference] = []
    _collect_references(
        value=resource.spec,
        source_id=resource.resource_id,
        field_path="spec",
        references=references,
    )
    if resource.status is not None:
        _collect_references(
            value=resource.status,
            source_id=resource.resource_id,
            field_path="status",
            references=references,
        )
    return references


def _collect_references(
    *,
    value: Any,
    source_id: str,
    field_path: str,
    references: list[GraphReference],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{field_path}.{key}"
            if _is_reference_field(key):
                for target_id in _reference_values(item):
                    references.append(
                        GraphReference(
                            source_id=source_id,
                            target_id=target_id,
                            field=child_path,
                        )
                    )
            else:
                _collect_references(
                    value=item,
                    source_id=source_id,
                    field_path=child_path,
                    references=references,
                )
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_references(
                value=item,
                source_id=source_id,
                field_path=f"{field_path}[{index}]",
                references=references,
            )


def _scan_trace_links(resource: Resource) -> list[GraphLink]:
    links = resource.spec.get("links")
    if not isinstance(links, list):
        return []

    graph_links: list[GraphLink] = []
    for item in links:
        if not isinstance(item, dict):
            continue
        link_id = _string_or_none(item.get("id"))
        source = item.get("from")
        target = item.get("to")
        source_id = _endpoint_id(source)
        target_id = _endpoint_id(target)
        if link_id is None or source_id is None or target_id is None:
            continue
        graph_links.append(
            GraphLink(
                link_set_id=resource.resource_id,
                link_id=link_id,
                source_id=source_id,
                target_id=target_id,
                relationship=_string_or_none(item.get("relationship")),
                path=resource.path,
                source=source if isinstance(source, dict) else None,
                target=target if isinstance(target, dict) else None,
            )
        )
    return graph_links


def _enabled_builtin_plugins(project: ProjectConfig) -> list[BuiltinPlugin]:
    enabled: list[BuiltinPlugin] = []
    for method in list_active_quality_methods():
        if method.plugin is None:
            continue
        if method.enabled_for_project(project):
            enabled.append(method.plugin)
    return enabled


def _is_reference_field(key: str) -> bool:
    return key.endswith("Ref") or key.endswith("Refs")


def _reference_values(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _endpoint_id(value: Any) -> str | None:
    if isinstance(value, str):
        return _string_or_none(value)
    if isinstance(value, dict):
        return _string_or_none(value.get("id"))
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
