from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXIT_CODE_BY_ERROR_CODE = {
    "UNKNOWN": 1,
    "INVALID_REFERENCE": 2,
    "INVALID_PARENT": 2,
    "NODE_NOT_EMPTY": 2,
    "PROJECT_DB_MISMATCH": 2,
    "DB_BUSY": 3,
    "VALIDATION_FAILED": 4,
}


@dataclass(slots=True)
class CliError(Exception):
    code: str = "UNKNOWN"
    message: str = "An unknown CLI error occurred."
    target: dict[str, Any] | None = None
    suggested_action: str | None = None

    @property
    def resolved_exit_code(self) -> int:
        return EXIT_CODE_BY_ERROR_CODE.get(
            self.code, EXIT_CODE_BY_ERROR_CODE["UNKNOWN"]
        )

    def to_error(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.target is not None:
            payload["target"] = self.target
        if self.suggested_action is not None:
            payload["suggested_action"] = self.suggested_action
        return payload


class ProjectDbMismatchError(CliError):
    def __init__(self, *, db_project_id: str, requested_project_id: str):
        super().__init__(
            code="PROJECT_DB_MISMATCH",
            message=(
                f"Database project '{db_project_id}' does not match requested project "
                f"'{requested_project_id}'."
            ),
            target={
                "project_id": requested_project_id,
                "db_project_id": db_project_id,
            },
            suggested_action=(
                f"Use --project {db_project_id} or point --db at the correct project database."
            ),
        )


class DbBusyError(CliError):
    def __init__(self, *, db_path: str | Path):
        super().__init__(
            code="DB_BUSY",
            message="Database is busy and retries were exhausted.",
            target={"db": str(db_path)},
            suggested_action="Retry later or increase --busy-timeout-ms and --retry.",
        )


class InvalidOptionValueError(CliError):
    def __init__(self, *, option: str, value: int):
        super().__init__(
            code="INVALID_REFERENCE",
            message=f"Option '{option}' must be >= 0.",
            target={"option": option, "value": value},
            suggested_action=f"Provide a non-negative value for --{option.replace('_', '-')}.",
        )
