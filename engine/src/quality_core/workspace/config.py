from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quality_core.cli.errors import QualityCliError

API_VERSION = "quality.ai/v1"
WORKSPACE_CONFIG_KIND = "QualityWorkspace"
WORKSPACE_PLUGINS_KIND = "WorkspacePlugins"


@dataclass(frozen=True, slots=True)
class GeneratedOutputDefaults:
    projections_managed: bool = False
    exports_managed: bool = False
    reports_managed: bool = False
    export_profiles: tuple[str, ...] = ()

    def to_yaml(self) -> dict[str, bool | list[str]]:
        return {
            "projectionsManaged": self.projections_managed,
            "exportsManaged": self.exports_managed,
            "reportsManaged": self.reports_managed,
            "exportProfiles": list(self.export_profiles),
        }


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    root: Path
    name: str
    projects_root: str
    generated_outputs: GeneratedOutputDefaults

    @property
    def projects_root_path(self) -> Path:
        return self.root / self.projects_root


@dataclass(frozen=True, slots=True)
class WorkspacePluginsConfig:
    builtins: tuple[str, ...]
    enabled_by_default: tuple[str, ...]


DEFAULT_WORKSPACE_NAME = "default"
DEFAULT_PROJECTS_ROOT = "projects"
DEFAULT_BUILTIN_PLUGINS = ("dfmea",)
DEFAULT_ENABLED_PLUGINS = ("dfmea",)


def workspace_config_path(workspace_root: Path) -> Path:
    return workspace_root / ".quality" / "workspace.yaml"


def workspace_plugins_path(workspace_root: Path) -> Path:
    return workspace_root / ".quality" / "plugins.yaml"


def default_workspace_document(name: str = DEFAULT_WORKSPACE_NAME) -> dict[str, Any]:
    return {
        "apiVersion": API_VERSION,
        "kind": WORKSPACE_CONFIG_KIND,
        "metadata": {"name": name},
        "spec": {
            "projectsRoot": DEFAULT_PROJECTS_ROOT,
            "defaults": {
                "generatedOutputs": GeneratedOutputDefaults().to_yaml(),
            },
        },
    }


def default_plugins_document() -> dict[str, Any]:
    from quality_core.methods.registry import list_active_quality_methods

    active_default_methods = tuple(
        method.method_id for method in list_active_quality_methods() if method.enabled_by_default
    )
    active_methods = tuple(method.method_id for method in list_active_quality_methods())
    return {
        "apiVersion": API_VERSION,
        "kind": WORKSPACE_PLUGINS_KIND,
        "spec": {
            "builtins": list(active_methods or DEFAULT_BUILTIN_PLUGINS),
            "enabledByDefault": list(active_default_methods or DEFAULT_ENABLED_PLUGINS),
        },
    }


def write_yaml_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
    )
    path.write_text(text, encoding="utf-8")


def load_yaml_document(path: Path, *, code: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QualityCliError(
            code=code,
            message=f"Configuration file '{path}' was not found.",
            path=str(path),
            suggestion="Run `quality workspace init` or pass --workspace to an existing workspace.",
        ) from exc
    except yaml.YAMLError as exc:
        raise QualityCliError(
            code=code,
            message=f"Configuration file '{path}' is not valid YAML.",
            path=str(path),
            suggestion="Repair the YAML file and rerun the command.",
        ) from exc

    if not isinstance(loaded, dict):
        raise QualityCliError(
            code=code,
            message=f"Configuration file '{path}' must contain a YAML mapping.",
            path=str(path),
            suggestion="Replace the file with the documented configuration shape.",
        )
    return loaded


def load_workspace_config(workspace_root: Path) -> WorkspaceConfig:
    config_path = workspace_config_path(workspace_root)
    document = load_yaml_document(config_path, code="INVALID_WORKSPACE_CONFIG")
    _require_document_header(
        document=document,
        expected_kind=WORKSPACE_CONFIG_KIND,
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )

    metadata = _mapping_field(
        document,
        "metadata",
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )
    spec = _mapping_field(
        document,
        "spec",
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )
    name = _string_field(
        metadata,
        "name",
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )
    projects_root = _string_field(
        spec,
        "projectsRoot",
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )

    generated_outputs = GeneratedOutputDefaults()
    defaults = spec.get("defaults")
    if isinstance(defaults, dict):
        raw_generated = defaults.get("generatedOutputs")
        if isinstance(raw_generated, dict):
            generated_outputs = GeneratedOutputDefaults(
                projections_managed=bool(raw_generated.get("projectionsManaged", False)),
                exports_managed=bool(raw_generated.get("exportsManaged", False)),
                reports_managed=bool(raw_generated.get("reportsManaged", False)),
                export_profiles=tuple(
                    item
                    for item in raw_generated.get("exportProfiles", [])
                    if isinstance(item, str)
                ),
            )

    return WorkspaceConfig(
        root=workspace_root,
        name=name,
        projects_root=projects_root,
        generated_outputs=generated_outputs,
    )


def load_workspace_plugins(workspace_root: Path) -> WorkspacePluginsConfig:
    config_path = workspace_plugins_path(workspace_root)
    document = load_yaml_document(config_path, code="INVALID_WORKSPACE_CONFIG")
    _require_document_header(
        document=document,
        expected_kind=WORKSPACE_PLUGINS_KIND,
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )
    spec = _mapping_field(
        document,
        "spec",
        path=config_path,
        code="INVALID_WORKSPACE_CONFIG",
    )
    return WorkspacePluginsConfig(
        builtins=tuple(_string_list_field(spec, "builtins", path=config_path)),
        enabled_by_default=tuple(_string_list_field(spec, "enabledByDefault", path=config_path)),
    )


def _require_document_header(
    *,
    document: dict[str, Any],
    expected_kind: str,
    path: Path,
    code: str,
) -> None:
    if document.get("apiVersion") != API_VERSION:
        raise QualityCliError(
            code=code,
            message=f"Configuration file '{path}' must use apiVersion '{API_VERSION}'.",
            path=str(path),
            field="apiVersion",
            suggestion="Regenerate the file with `quality workspace init` or migrate it.",
        )
    if document.get("kind") != expected_kind:
        raise QualityCliError(
            code=code,
            message=f"Configuration file '{path}' must have kind '{expected_kind}'.",
            path=str(path),
            field="kind",
            suggestion="Replace the file with the documented configuration shape.",
        )


def _mapping_field(
    document: dict[str, Any],
    field: str,
    *,
    path: Path,
    code: str,
) -> dict[str, Any]:
    value = document.get(field)
    if not isinstance(value, dict):
        raise QualityCliError(
            code=code,
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
    code: str,
) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value:
        raise QualityCliError(
            code=code,
            message=f"Field '{field}' in '{path}' must be a non-empty string.",
            path=str(path),
            field=field,
            suggestion="Repair the YAML file and rerun the command.",
        )
    return value


def _string_list_field(document: dict[str, Any], field: str, *, path: Path) -> list[str]:
    value = document.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise QualityCliError(
            code="INVALID_WORKSPACE_CONFIG",
            message=f"Field '{field}' in '{path}' must be a string list.",
            path=str(path),
            field=field,
            suggestion="Repair the YAML file and rerun the command.",
        )
    return list(value)
