from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_core.resources.envelope import Resource
from quality_core.workspace.project import ProjectConfig


@dataclass(frozen=True, slots=True)
class GraphReference:
    source_id: str
    target_id: str
    field: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class GraphLink:
    link_set_id: str
    link_id: str
    source_id: str
    target_id: str
    relationship: str | None
    path: Path | None = None
    source: dict[str, Any] | None = None
    target: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "linkSetId": self.link_set_id,
            "id": self.link_id,
            "sourceId": self.source_id,
            "targetId": self.target_id,
        }
        if self.relationship is not None:
            payload["relationship"] = self.relationship
        if self.path is not None:
            payload["path"] = str(self.path)
        if self.source is not None:
            payload["source"] = self.source
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(frozen=True, slots=True)
class ResourceNode:
    resource: Resource
    domain: str


@dataclass(frozen=True, slots=True)
class ProjectGraph:
    project: ProjectConfig
    resources: tuple[Resource, ...]
    resource_domains: dict[str, str]
    resources_by_id: dict[str, Resource]
    resources_by_kind: dict[str, tuple[Resource, ...]]
    resources_by_path: dict[Path, Resource]
    references_by_id: dict[str, tuple[GraphReference, ...]]
    links: tuple[GraphLink, ...]
    links_by_source: dict[str, tuple[GraphLink, ...]]
    links_by_target: dict[str, tuple[GraphLink, ...]]
    actions_by_status: dict[str, tuple[Resource, ...]]
    risks_by_ap: dict[str, tuple[Resource, ...]]

    def get(self, resource_id: str) -> Resource | None:
        return self.resources_by_id.get(resource_id)

    def kind(self, kind: str) -> tuple[Resource, ...]:
        return self.resources_by_kind.get(kind, ())

    def domain_for(self, resource_id: str) -> str | None:
        return self.resource_domains.get(resource_id)
