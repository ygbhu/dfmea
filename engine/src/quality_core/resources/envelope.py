from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quality_core.cli.errors import QualityCliError
from quality_core.workspace.config import API_VERSION


@dataclass(frozen=True, slots=True)
class Resource:
    api_version: str
    kind: str
    metadata: dict[str, Any]
    spec: dict[str, Any]
    path: Path | None = None
    status: dict[str, Any] | None = None

    @property
    def resource_id(self) -> str:
        value = self.metadata.get("id")
        if not isinstance(value, str) or not value:
            raise QualityCliError(
                code="INVALID_PROJECT_CONFIG",
                message="Resource metadata.id must be a non-empty string.",
                path=str(self.path) if self.path is not None else None,
                field="metadata.id",
                suggestion="Repair the resource envelope before retrying the operation.",
            )
        return value

    def with_path(self, path: Path) -> Resource:
        return Resource(
            api_version=self.api_version,
            kind=self.kind,
            metadata=dict(self.metadata),
            spec=dict(self.spec),
            path=path,
            status=dict(self.status) if self.status is not None else None,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": self.metadata,
            "spec": self.spec,
        }
        if self.status is not None:
            document["status"] = self.status
        return document


def make_resource(
    *,
    kind: str,
    resource_id: str,
    spec: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    api_version: str = API_VERSION,
) -> Resource:
    resolved_metadata = dict(metadata or {})
    resolved_metadata["id"] = resource_id
    return Resource(
        api_version=api_version,
        kind=kind,
        metadata=resolved_metadata,
        spec=dict(spec or {}),
    )


def resource_from_document(document: dict[str, Any], *, path: Path | None = None) -> Resource:
    api_version = document.get("apiVersion")
    kind = document.get("kind")
    metadata = document.get("metadata")
    spec = document.get("spec")
    status = document.get("status")
    if api_version != API_VERSION:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource '{path}' must use apiVersion '{API_VERSION}'.",
            path=str(path) if path is not None else None,
            field="apiVersion",
            suggestion="Migrate or repair the resource envelope.",
        )
    if not isinstance(kind, str) or not kind:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource '{path}' must define a non-empty kind.",
            path=str(path) if path is not None else None,
            field="kind",
            suggestion="Repair the resource envelope before retrying the operation.",
        )
    if not isinstance(metadata, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource '{path}' must define metadata as a mapping.",
            path=str(path) if path is not None else None,
            field="metadata",
            suggestion="Repair the resource envelope before retrying the operation.",
        )
    if not isinstance(spec, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource '{path}' must define spec as a mapping.",
            path=str(path) if path is not None else None,
            field="spec",
            suggestion="Repair the resource envelope before retrying the operation.",
        )
    if status is not None and not isinstance(status, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource '{path}' status must be a mapping when present.",
            path=str(path) if path is not None else None,
            field="status",
            suggestion="Repair the resource envelope before retrying the operation.",
        )
    return Resource(
        api_version=api_version,
        kind=kind,
        metadata=metadata,
        spec=spec,
        path=path,
        status=status,
    )


def load_resource(path: Path) -> Resource:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QualityCliError(
            code="RESOURCE_NOT_FOUND",
            message=f"Resource file '{path}' was not found.",
            path=str(path),
            suggestion="Check the resource ID and project path.",
        ) from exc
    except yaml.YAMLError as exc:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource file '{path}' is not valid YAML.",
            path=str(path),
            suggestion="Repair the YAML file before retrying the operation.",
        ) from exc

    if not isinstance(loaded, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource file '{path}' must contain a YAML mapping.",
            path=str(path),
            suggestion="Repair the resource envelope before retrying the operation.",
        )
    return resource_from_document(loaded, path=path)


def dump_resource(resource: Resource) -> str:
    return yaml.safe_dump(
        resource.to_document(),
        sort_keys=False,
        allow_unicode=True,
    )
