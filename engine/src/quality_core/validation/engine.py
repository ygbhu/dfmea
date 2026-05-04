from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

from quality_core.cli.errors import QualityCliError
from quality_core.methods.registry import list_active_quality_methods
from quality_core.plugins.contracts import BuiltinPlugin
from quality_core.plugins.schema_snapshots import (
    PluginSchemaSnapshot,
    ensure_project_schema_snapshot_current,
)
from quality_core.resources.envelope import Resource, resource_from_document
from quality_core.resources.paths import (
    allowed_prefixes,
    collection_root,
    find_collection,
    id_prefix,
    singleton_path,
    validate_resource_path,
)
from quality_core.validation.issue import ValidationIssue, error_issue
from quality_core.validation.json_schema import load_json_schema, validate_json_schema_subset
from quality_core.validation.report import ValidationReport
from quality_core.workspace.project import ProjectConfig


class PluginValidator(Protocol):
    def __call__(
        self,
        *,
        project: ProjectConfig,
        resources: tuple[Resource, ...],
    ) -> list[ValidationIssue]: ...


@dataclass(frozen=True, slots=True)
class ResourceLoadFailure:
    path: Path
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class ResourceScan:
    resources: tuple[Resource, ...]
    load_failures: tuple[ResourceLoadFailure, ...]
    resource_plugins: dict[Path, BuiltinPlugin]
    resource_schemas: dict[Path, Path]


def validate_project(
    *,
    project: ProjectConfig,
    plugin_validators: dict[str, PluginValidator] | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    schema_versions: dict[str, str] = {}
    enabled_plugins = _enabled_builtin_plugins(project)
    snapshots: dict[str, PluginSchemaSnapshot] = {}

    for plugin in enabled_plugins:
        try:
            snapshot = ensure_project_schema_snapshot_current(
                plugin=plugin,
                project_root=project.root,
            )
        except QualityCliError as exc:
            issues.append(_issue_from_error(exc, plugin_id=plugin.plugin_id))
            continue
        schema_versions[plugin.plugin_id] = snapshot.version
        snapshots[plugin.plugin_id] = snapshot

    scan = scan_project_resources(
        project=project,
        plugins=tuple(enabled_plugins),
        snapshots=snapshots,
    )
    issues.extend(issue for failure in scan.load_failures for issue in failure.issues)
    issues.extend(
        _validate_core_resources(
            project=project,
            resources=scan.resources,
            resource_plugins=scan.resource_plugins,
            resource_schemas=scan.resource_schemas,
        )
    )

    plugin_validators = plugin_validators or {}
    for plugin in enabled_plugins:
        validator = plugin_validators.get(plugin.plugin_id)
        if validator is None:
            continue
        plugin_resources = tuple(
            resource
            for resource in scan.resources
            if resource.path is not None and scan.resource_plugins.get(resource.path) == plugin
        )
        issues.extend(validator(project=project, resources=plugin_resources))

    return ValidationReport(
        project=project,
        issues=tuple(issues),
        schema_versions=schema_versions,
    )


def scan_project_resources(
    *,
    project: ProjectConfig,
    plugins: tuple[BuiltinPlugin, ...],
    snapshots: dict[str, PluginSchemaSnapshot],
) -> ResourceScan:
    resources: list[Resource] = []
    failures: list[ResourceLoadFailure] = []
    resource_plugins: dict[Path, BuiltinPlugin] = {}
    resource_schemas: dict[Path, Path] = {}

    for plugin in plugins:
        snapshot = snapshots.get(plugin.plugin_id)
        if snapshot is None:
            continue
        for singleton in plugin.singletons:
            path = singleton_path(
                project_root=project.root,
                plugin=plugin,
                kind=singleton.kind,
                resource_id=singleton.resource_id,
            )
            schema_path = snapshot.root / singleton.schema
            if not path.exists():
                failures.append(
                    ResourceLoadFailure(
                        path=path,
                        issues=(
                            error_issue(
                                code="RESOURCE_NOT_FOUND",
                                message=(
                                    f"Required singleton resource '{singleton.kind}' is missing."
                                ),
                                path=path,
                                resource_id=singleton.resource_id,
                                kind=singleton.kind,
                                suggestion=(
                                    "Run the domain init command or restore the missing resource."
                                ),
                                plugin_id=plugin.plugin_id,
                            ),
                        ),
                    )
                )
                continue
            loaded, load_issues = _load_resource_document(path)
            if load_issues:
                failures.append(ResourceLoadFailure(path=path, issues=tuple(load_issues)))
                continue
            resources.append(loaded)
            resource_plugins[path] = plugin
            resource_schemas[path] = schema_path

        for collection in plugin.collections:
            root = collection_root(
                project_root=project.root,
                plugin=plugin,
                collection=collection,
            )
            if not root.exists():
                continue
            schema_path = snapshot.root / collection.schema
            for path in sorted(root.glob("*.yaml")):
                loaded, load_issues = _load_resource_document(path)
                if load_issues:
                    failures.append(ResourceLoadFailure(path=path, issues=tuple(load_issues)))
                    continue
                resources.append(loaded)
                resource_plugins[path] = plugin
                resource_schemas[path] = schema_path

    return ResourceScan(
        resources=tuple(resources),
        load_failures=tuple(failures),
        resource_plugins=resource_plugins,
        resource_schemas=resource_schemas,
    )


def _validate_core_resources(
    *,
    project: ProjectConfig,
    resources: tuple[Resource, ...],
    resource_plugins: dict[Path, BuiltinPlugin],
    resource_schemas: dict[Path, Path],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(
        _validate_schema_and_path(
            resources=resources,
            resource_plugins=resource_plugins,
            resource_schemas=resource_schemas,
        )
    )
    issues.extend(_validate_duplicate_ids(resources))
    issues.extend(
        _validate_nested_link_ids(
            resources=resources,
            project=project,
        )
    )
    return issues


def _validate_schema_and_path(
    *,
    resources: tuple[Resource, ...],
    resource_plugins: dict[Path, BuiltinPlugin],
    resource_schemas: dict[Path, Path],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for resource in resources:
        if resource.path is None:
            continue
        plugin = resource_plugins.get(resource.path)
        if plugin is None:
            continue
        try:
            validate_resource_path(
                plugin=plugin,
                resource=resource,
                path=resource.path,
            )
        except QualityCliError as exc:
            issues.append(_issue_from_error(exc, plugin_id=plugin.plugin_id))

        schema_path = resource_schemas.get(resource.path)
        if schema_path is None:
            continue
        try:
            schema = load_json_schema(schema_path)
        except QualityCliError as exc:
            issues.append(_issue_from_error(exc, plugin_id=plugin.plugin_id))
            continue
        issues.extend(
            validate_json_schema_subset(
                document=resource.to_document(),
                schema=schema,
                path=resource.path,
                resource_id=_safe_resource_id(resource),
                kind=resource.kind,
            )
        )

        collection_issue = _validate_collection_prefix(plugin=plugin, resource=resource)
        if collection_issue is not None:
            issues.append(collection_issue)
    return issues


def _validate_duplicate_ids(resources: tuple[Resource, ...]) -> list[ValidationIssue]:
    by_id: dict[str, list[Resource]] = {}
    for resource in resources:
        resource_id = _safe_resource_id(resource)
        if resource_id is None:
            continue
        by_id.setdefault(resource_id, []).append(resource)

    issues: list[ValidationIssue] = []
    for resource_id, matches in sorted(by_id.items()):
        if len(matches) < 2:
            continue
        issues.append(
            error_issue(
                code="DUPLICATE_ID",
                message=f"Resource ID '{resource_id}' is used by multiple resources.",
                resource_id=resource_id,
                target={"paths": [str(resource.path) for resource in matches]},
                suggestion="Run `quality project repair id-conflicts` or renumber one resource.",
            )
        )
    return issues


def _validate_nested_link_ids(
    *,
    resources: tuple[Resource, ...],
    project: ProjectConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    link_sets = [*resources, *_load_project_link_sets(project)]
    for resource in link_sets:
        links = resource.spec.get("links")
        if not isinstance(links, list):
            continue
        seen: dict[str, int] = {}
        for index, link in enumerate(links):
            if not isinstance(link, dict):
                issues.append(
                    error_issue(
                        code="SCHEMA_VALIDATION_FAILED",
                        message="Trace link entries must be mappings.",
                        path=resource.path,
                        resource_id=_safe_resource_id(resource),
                        kind=resource.kind,
                        field=f"spec.links[{index}]",
                        suggestion="Repair the link entry shape.",
                    )
                )
                continue
            link_id = link.get("id")
            if not isinstance(link_id, str) or not link_id:
                issues.append(
                    error_issue(
                        code="SCHEMA_VALIDATION_FAILED",
                        message="Trace link entries must define a non-empty id.",
                        path=resource.path,
                        resource_id=_safe_resource_id(resource),
                        kind=resource.kind,
                        field=f"spec.links[{index}].id",
                        suggestion="Add a local LINK-* ID to the link entry.",
                    )
                )
                continue
            if link_id in seen:
                issues.append(
                    error_issue(
                        code="DUPLICATE_ID",
                        message=f"Nested link ID '{link_id}' is duplicated in this link set.",
                        path=resource.path,
                        resource_id=_safe_resource_id(resource),
                        kind=resource.kind,
                        field=f"spec.links[{index}].id",
                        target={"firstIndex": seen[link_id], "duplicateIndex": index},
                        suggestion="Renumber one nested LINK-* entry inside the link set.",
                    )
                )
            else:
                seen[link_id] = index
    return issues


def _load_project_link_sets(project: ProjectConfig) -> list[Resource]:
    link_root = project.root / "links"
    resources: list[Resource] = []
    if not link_root.exists():
        return resources
    for path in sorted(link_root.glob("*.yaml")):
        loaded, issues = _load_resource_document(path)
        if issues:
            resources.append(
                Resource(
                    api_version="quality.ai/v1",
                    kind="TraceLinkSet",
                    metadata={"id": path.stem},
                    spec={},
                    path=path,
                )
            )
            continue
        resources.append(loaded)
    return resources


def _validate_collection_prefix(
    *, plugin: BuiltinPlugin, resource: Resource
) -> ValidationIssue | None:
    try:
        collection = find_collection(
            plugin,
            kind=resource.kind,
            resource_id=resource.resource_id,
        )
    except QualityCliError as exc:
        if exc.code == "RESOURCE_NOT_FOUND":
            return None
        return _issue_from_error(exc, plugin_id=plugin.plugin_id)

    prefix = id_prefix(resource.resource_id)
    if prefix in allowed_prefixes(collection):
        return None
    return error_issue(
        code="ID_PREFIX_MISMATCH",
        message=f"ID prefix '{prefix}' is not valid for kind '{resource.kind}'.",
        path=resource.path,
        resource_id=resource.resource_id,
        kind=resource.kind,
        suggestion="Repair metadata.id to use a prefix declared by the plugin.",
        plugin_id=plugin.plugin_id,
    )


def _load_resource_document(path: Path) -> tuple[Resource, list[ValidationIssue]]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _placeholder(path), [
            error_issue(
                code="RESOURCE_NOT_FOUND",
                message=f"Resource file '{path}' was not found.",
                path=path,
                suggestion="Restore the missing resource file.",
            )
        ]
    except yaml.YAMLError as exc:
        return _placeholder(path), [
            error_issue(
                code="SCHEMA_VALIDATION_FAILED",
                message=f"Resource file '{path}' is not valid YAML.",
                path=path,
                suggestion="Repair the YAML syntax before retrying validation.",
                target={"yamlError": str(exc)},
            )
        ]
    if not isinstance(loaded, dict):
        return _placeholder(path), [
            error_issue(
                code="SCHEMA_VALIDATION_FAILED",
                message=f"Resource file '{path}' must contain a YAML mapping.",
                path=path,
                suggestion="Replace the file content with a resource mapping.",
            )
        ]
    try:
        return resource_from_document(loaded, path=path), []
    except QualityCliError as exc:
        return _placeholder(path), [_issue_from_error(exc)]


def _enabled_builtin_plugins(project: ProjectConfig) -> list[BuiltinPlugin]:
    enabled: list[BuiltinPlugin] = []
    for method in list_active_quality_methods():
        if method.plugin is None:
            continue
        if method.enabled_for_project(project):
            enabled.append(method.plugin)
    return enabled


def _issue_from_error(
    error: QualityCliError,
    *,
    plugin_id: str | None = None,
) -> ValidationIssue:
    return error_issue(
        code=error.code,
        message=error.message,
        path=error.path,
        field=error.field,
        suggestion=error.suggestion,
        target=error.target,
        plugin_id=plugin_id,
    )


def _safe_resource_id(resource: Resource) -> str | None:
    value = resource.metadata.get("id")
    return value if isinstance(value, str) and value else None


def _placeholder(path: Path) -> Resource:
    return Resource(
        api_version="quality.ai/v1",
        kind="InvalidResource",
        metadata={"id": path.stem},
        spec={},
        path=path,
    )
