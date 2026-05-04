from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quality_core.validation.issue import ValidationIssue
from quality_core.workspace.project import ProjectConfig


@dataclass(frozen=True, slots=True)
class ValidationReport:
    project: ProjectConfig
    issues: tuple[ValidationIssue, ...]
    schema_versions: dict[str, str]

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def to_data(self) -> dict[str, Any]:
        return {
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "issues": len(self.issues),
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }
