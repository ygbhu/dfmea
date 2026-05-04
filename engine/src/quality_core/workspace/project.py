from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.workspace.config import (
    API_VERSION,
    GeneratedOutputDefaults,
    WorkspaceConfig,
    load_yaml_document,
    write_yaml_document,
)

PROJECT_CONFIG_KIND = "QualityProject"
PROJECT_ID = "PRJ"
PROJECT_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    slug: str
    name: str
    root: Path
    domains: dict[str, dict[str, Any]]
    generated_outputs: GeneratedOutputDefaults

    @property
    def config_path(self) -> Path:
        return self.root / "project.yaml"


@dataclass(frozen=True, slots=True)
class ProjectCreateResult:
    project: ProjectConfig
    created_paths: tuple[Path, ...]


def project_config_path(project_root: Path) -> Path:
    return project_root / "project.yaml"


def validate_project_slug(slug: str) -> None:
    if not PROJECT_SLUG_PATTERN.fullmatch(slug):
        raise QualityCliError(
            code="INVALID_PROJECT_SLUG",
            message=(
                "Project slug must use lowercase letters, digits, and hyphens, "
                "and it must start and end with a letter or digit."
            ),
            target={"projectSlug": slug},
            suggestion="Use a slug like `cooling-fan-controller`.",
        )


def create_project(
    *,
    workspace_config: WorkspaceConfig,
    slug: str,
    name: str | None = None,
) -> ProjectCreateResult:
    validate_project_slug(slug)
    project_root = workspace_config.projects_root_path / slug
    config_path = project_config_path(project_root)
    if config_path.exists():
        raise QualityCliError(
            code="PROJECT_ALREADY_EXISTS",
            message=f"Project '{slug}' already exists.",
            path=str(config_path),
            target={"projectSlug": slug},
            suggestion="Choose a different slug or load the existing project.",
        )

    project_name = name if name is not None and name.strip() else _title_from_slug(slug)
    created_paths = [
        project_root / ".quality" / "schemas",
        project_root / ".quality" / "tombstones",
        project_root / ".quality" / "locks",
        project_root / "links",
        project_root / "exports",
        project_root / "reports",
        project_root / "evidence",
    ]
    for path in created_paths:
        path.mkdir(parents=True, exist_ok=True)

    document = default_project_document(slug=slug, name=project_name)
    write_yaml_document(config_path, document)

    project = load_project_config(project_root)
    return ProjectCreateResult(
        project=project,
        created_paths=tuple([*created_paths, config_path]),
    )


def default_project_document(*, slug: str, name: str) -> dict[str, Any]:
    generated_outputs = GeneratedOutputDefaults()
    return {
        "apiVersion": API_VERSION,
        "kind": PROJECT_CONFIG_KIND,
        "metadata": {
            "id": PROJECT_ID,
            "slug": slug,
            "name": name,
        },
        "spec": {
            "domains": {
                "dfmea": {
                    "enabled": False,
                    "root": "./dfmea",
                },
                "pfmea": {
                    "enabled": False,
                    "root": "./pfmea",
                },
                "controlPlan": {
                    "enabled": False,
                    "root": "./control-plan",
                },
            },
            "generatedOutputs": generated_outputs.to_yaml(),
        },
    }


def load_project_document(project_root: Path) -> dict[str, Any]:
    config_path = project_config_path(project_root)
    document = load_yaml_document(config_path, code="INVALID_PROJECT_CONFIG")
    _require_project_header(document=document, path=config_path)
    return document


def update_project_domain(
    *,
    project_root: Path,
    domain_key: str,
    enabled: bool,
    root: str,
) -> ProjectConfig:
    document = load_project_document(project_root)
    spec = _mapping_field(document, "spec", path=project_config_path(project_root))
    domains = spec.get("domains")
    if not isinstance(domains, dict):
        domains = {}
        spec["domains"] = domains

    domain_config = domains.get(domain_key)
    if not isinstance(domain_config, dict):
        domain_config = {}
        domains[domain_key] = domain_config

    domain_config["enabled"] = enabled
    domain_config["root"] = root
    write_yaml_document(project_config_path(project_root), document)
    return load_project_config(project_root)


def load_project_config(project_root: Path) -> ProjectConfig:
    config_path = project_config_path(project_root)
    document = load_yaml_document(config_path, code="INVALID_PROJECT_CONFIG")
    _require_project_header(document=document, path=config_path)
    metadata = _mapping_field(document, "metadata", path=config_path)
    spec = _mapping_field(document, "spec", path=config_path)

    project_id = _string_field(metadata, "id", path=config_path)
    if project_id != PROJECT_ID:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Project config '{config_path}' must use metadata.id '{PROJECT_ID}'.",
            path=str(config_path),
            field="metadata.id",
            suggestion="Project object identity is the fixed singleton ID `PRJ` in V1.",
        )

    slug = _string_field(metadata, "slug", path=config_path)
    if slug != project_root.name:
        raise QualityCliError(
            code="PROJECT_ADDRESS_MISMATCH",
            message=(f"Project slug '{slug}' does not match directory name '{project_root.name}'."),
            path=str(config_path),
            field="metadata.slug",
            target={"projectSlug": slug, "directory": project_root.name},
            suggestion="Use a project directory whose name matches metadata.slug.",
        )

    name = _string_field(metadata, "name", path=config_path)
    domains = spec.get("domains")
    if not isinstance(domains, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Project config '{config_path}' must define spec.domains.",
            path=str(config_path),
            field="spec.domains",
            suggestion="Regenerate the project config with `quality project create`.",
        )

    raw_generated = spec.get("generatedOutputs")
    generated_outputs = GeneratedOutputDefaults()
    if isinstance(raw_generated, dict):
        generated_outputs = GeneratedOutputDefaults(
            projections_managed=bool(raw_generated.get("projectionsManaged", False)),
            exports_managed=bool(raw_generated.get("exportsManaged", False)),
            reports_managed=bool(raw_generated.get("reportsManaged", False)),
            export_profiles=tuple(
                item for item in raw_generated.get("exportProfiles", []) if isinstance(item, str)
            ),
        )

    return ProjectConfig(
        slug=slug,
        name=name,
        root=project_root,
        domains=domains,
        generated_outputs=generated_outputs,
    )


def resolve_project_root(
    *,
    workspace_config: WorkspaceConfig,
    project: str,
) -> Path:
    candidate = workspace_config.projects_root_path / project
    if project_config_path(candidate).exists():
        return candidate

    matches: list[Path] = []
    projects_root = workspace_config.projects_root_path
    if projects_root.exists():
        for child in projects_root.iterdir():
            if not child.is_dir() or not project_config_path(child).exists():
                continue
            try:
                loaded = load_project_config(child)
            except QualityCliError:
                continue
            if loaded.slug == project:
                matches.append(child)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise QualityCliError(
            code="PROJECT_AMBIGUOUS",
            message=f"Project reference '{project}' matched multiple project directories.",
            target={"project": project, "matches": [str(path) for path in matches]},
            suggestion="Use the project directory name explicitly.",
        )

    raise QualityCliError(
        code="PROJECT_NOT_FOUND",
        message=f"Project '{project}' was not found.",
        target={"project": project},
        suggestion="Create the project with `quality project create <slug>`.",
    )


def _require_project_header(*, document: dict[str, Any], path: Path) -> None:
    if document.get("apiVersion") != API_VERSION:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Project config '{path}' must use apiVersion '{API_VERSION}'.",
            path=str(path),
            field="apiVersion",
            suggestion="Regenerate or migrate the project configuration.",
        )
    if document.get("kind") != PROJECT_CONFIG_KIND:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Project config '{path}' must have kind '{PROJECT_CONFIG_KIND}'.",
            path=str(path),
            field="kind",
            suggestion="Regenerate the project config with `quality project create`.",
        )


def _mapping_field(
    document: dict[str, Any],
    field: str,
    *,
    path: Path,
) -> dict[str, Any]:
    value = document.get(field)
    if not isinstance(value, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Field '{field}' in '{path}' must be a mapping.",
            path=str(path),
            field=field,
            suggestion="Repair the YAML file and rerun the command.",
        )
    return value


def _string_field(
    document: dict[str, Any],
    field: str,
    *,
    path: Path,
) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Field '{field}' in '{path}' must be a non-empty string.",
            path=str(path),
            field=field,
            suggestion="Repair the YAML file and rerun the command.",
        )
    return value


def _title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))
