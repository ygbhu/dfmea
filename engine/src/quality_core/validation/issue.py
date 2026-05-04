from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    path: Path | str | None = None
    resource_id: str | None = None
    kind: str | None = None
    field: str | None = None
    suggestion: str | None = None
    target: dict[str, Any] | None = None
    plugin_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.path is not None:
            payload["path"] = str(self.path)
        if self.resource_id is not None:
            payload["resourceId"] = self.resource_id
        if self.kind is not None:
            payload["kind"] = self.kind
        if self.field is not None:
            payload["field"] = self.field
        if self.suggestion is not None:
            payload["suggestion"] = self.suggestion
        if self.target is not None:
            payload["target"] = self.target
        if self.plugin_id is not None:
            payload["pluginId"] = self.plugin_id
        return payload


def error_issue(
    *,
    code: str,
    message: str,
    path: Path | str | None = None,
    resource_id: str | None = None,
    kind: str | None = None,
    field: str | None = None,
    suggestion: str | None = None,
    target: dict[str, Any] | None = None,
    plugin_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity="error",
        message=message,
        path=path,
        resource_id=resource_id,
        kind=kind,
        field=field,
        suggestion=suggestion,
        target=target,
        plugin_id=plugin_id,
    )


def warning_issue(
    *,
    code: str,
    message: str,
    path: Path | str | None = None,
    resource_id: str | None = None,
    kind: str | None = None,
    field: str | None = None,
    suggestion: str | None = None,
    target: dict[str, Any] | None = None,
    plugin_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity="warning",
        message=message,
        path=path,
        resource_id=resource_id,
        kind=kind,
        field=field,
        suggestion=suggestion,
        target=target,
        plugin_id=plugin_id,
    )
