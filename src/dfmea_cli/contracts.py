from __future__ import annotations

from typing import Any


CONTRACT_VERSION = "1.0"


def success_result(
    *,
    command: str,
    data: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "ok": True,
        "command": command,
        "data": data if data is not None else {},
        "warnings": warnings if warnings is not None else [],
        "errors": [],
        "meta": meta if meta is not None else {},
    }


def failure_result(
    *,
    command: str,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "ok": False,
        "command": command,
        "data": None,
        "warnings": warnings if warnings is not None else [],
        "errors": errors,
        "meta": meta if meta is not None else {},
    }


def validation_result(
    *,
    issues: list[dict[str, Any]],
    command: str = "validate",
    warnings: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error_count = sum(1 for issue in issues if issue.get("level") == "error")
    warning_count = sum(1 for issue in issues if issue.get("level") == "warning")
    resolved_errors = list(errors) if errors is not None else []

    if error_count > 0 and not any(
        error.get("code") == "VALIDATION_FAILED" for error in resolved_errors
    ):
        resolved_errors.append(
            {
                "code": "VALIDATION_FAILED",
                "message": "Validation reported one or more error-level issues.",
                "suggested_action": "Review data.issues and fix the reported validation errors.",
            }
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "ok": error_count == 0 and not resolved_errors,
        "command": command,
        "data": {
            "summary": {
                "errors": error_count,
                "warnings": warning_count,
            },
            "issues": issues,
        },
        "warnings": warnings if warnings is not None else [],
        "errors": resolved_errors,
        "meta": meta if meta is not None else {},
    }
