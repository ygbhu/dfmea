from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from quality_core.plugins.contracts import BuiltinPlugin
from quality_core.workspace.project import ProjectConfig


class MethodValidator(Protocol):
    def __call__(
        self,
        *,
        project: ProjectConfig,
        resources: tuple[Any, ...],
    ) -> list[Any]: ...


class ProjectionRebuilder(Protocol):
    def __call__(self, *, project: ProjectConfig) -> Any: ...


@dataclass(frozen=True, slots=True)
class MethodCommand:
    name: str
    description: str
    example: str

    def data(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "example": self.example,
        }


@dataclass(frozen=True, slots=True)
class QualityMethod:
    method_id: str
    display_name: str
    status: str
    enabled_by_default: bool
    domain_key: str
    command_namespace: str | None
    plugin: BuiltinPlugin | None
    commands: tuple[MethodCommand, ...] = ()
    validator: MethodValidator | None = None
    projection_rebuilder: ProjectionRebuilder | None = None

    @property
    def implemented(self) -> bool:
        return self.status == "active" and self.plugin is not None

    def enabled_for_project(self, project: ProjectConfig | None) -> bool:
        if project is None:
            return False
        domain = project.domains.get(self.domain_key)
        return isinstance(domain, dict) and domain.get("enabled") is True

    def data(self, *, project: ProjectConfig | None = None) -> dict[str, Any]:
        return {
            "id": self.method_id,
            "displayName": self.display_name,
            "status": self.status,
            "implemented": self.implemented,
            "enabledByDefault": self.enabled_by_default,
            "enabled": self.enabled_for_project(project),
            "domain": self.domain_key,
            "commandNamespace": self.command_namespace,
            "pluginId": self.plugin.plugin_id if self.plugin is not None else None,
            "version": self.plugin.version if self.plugin is not None else None,
            "commands": [command.data() for command in self.commands],
        }


@dataclass(frozen=True, slots=True)
class MethodStatus:
    method: QualityMethod
    enabled: bool
    schema_snapshot_version: str | None
    schema_snapshot_path: str | None

    def data(self) -> dict[str, Any]:
        payload = self.method.data()
        payload["enabled"] = self.enabled
        payload["schemaSnapshotVersion"] = self.schema_snapshot_version
        payload["schemaSnapshotPath"] = self.schema_snapshot_path
        return payload


MethodFactory = Callable[[], QualityMethod]
