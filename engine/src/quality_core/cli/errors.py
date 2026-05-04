from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONFIG_ERROR_CODES = {
    "WORKSPACE_NOT_FOUND",
    "WORKSPACE_ALREADY_EXISTS",
    "PROJECT_NOT_FOUND",
    "PROJECT_ALREADY_EXISTS",
    "PROJECT_AMBIGUOUS",
    "PROJECT_ADDRESS_MISMATCH",
    "INVALID_WORKSPACE_CONFIG",
    "INVALID_PROJECT_CONFIG",
    "INVALID_PROJECT_SLUG",
    "PLUGIN_NOT_FOUND",
    "PLUGIN_NOT_ENABLED",
    "PLUGIN_DISABLE_BLOCKED",
    "METHOD_NOT_FOUND",
    "RESOURCE_NOT_FOUND",
    "ID_CONFLICT",
    "ID_PREFIX_MISMATCH",
    "INVALID_PARENT",
    "NODE_NOT_EMPTY",
    "OPENCODE_ADAPTER_CONFLICT",
}
GIT_ERROR_CODES = {"GIT_DIRTY", "GIT_CONFLICT", "RESTORE_PRECONDITION_FAILED"}
WRITE_ERROR_CODES = {"FILE_LOCKED", "ATOMIC_WRITE_FAILED", "FILE_WRITE_FAILED"}
SCHEMA_ERROR_CODES = {
    "SCHEMA_VERSION_MISMATCH",
    "MIGRATION_REQUIRED",
}


def exit_code_for_error(code: str) -> int:
    if code == "VALIDATION_FAILED":
        return 3
    if code in CONFIG_ERROR_CODES:
        return 4
    if code in GIT_ERROR_CODES:
        return 5
    if code in WRITE_ERROR_CODES:
        return 6
    if code in SCHEMA_ERROR_CODES:
        return 7
    return 1


@dataclass(slots=True)
class QualityCliError(Exception):
    code: str
    message: str
    path: str | None = None
    field: str | None = None
    suggestion: str | None = None
    target: dict[str, Any] | None = None
    severity: str = "error"

    @property
    def resolved_exit_code(self) -> int:
        return exit_code_for_error(self.code)

    def to_error(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.path is not None:
            error["path"] = self.path
        if self.field is not None:
            error["field"] = self.field
        if self.suggestion is not None:
            error["suggestion"] = self.suggestion
        if self.target is not None:
            error["target"] = self.target
        return error
