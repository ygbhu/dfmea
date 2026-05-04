from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.validation.issue import ValidationIssue, error_issue


def load_json_schema(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"JSON schema file '{path}' was not found.",
            path=str(path),
            suggestion="Restore the plugin schema snapshot or re-enable the plugin.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"JSON schema file '{path}' is not valid JSON.",
            path=str(path),
            suggestion="Restore the plugin schema snapshot or re-enable the plugin.",
        ) from exc

    if not isinstance(loaded, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"JSON schema file '{path}' must contain an object.",
            path=str(path),
            suggestion="Restore the plugin schema snapshot or re-enable the plugin.",
        )
    return loaded


def validate_json_schema_subset(
    *,
    document: dict[str, Any],
    schema: dict[str, Any],
    path: Path,
    resource_id: str | None = None,
    kind: str | None = None,
) -> list[ValidationIssue]:
    """Validate the JSON Schema subset used by V1 plugin snapshots."""
    issues: list[ValidationIssue] = []
    issues.extend(
        _validate_node(
            value=document,
            schema=schema,
            path=path,
            field="$",
            resource_id=resource_id,
            kind=kind,
        )
    )
    return issues


def _validate_node(
    *,
    value: Any,
    schema: dict[str, Any],
    path: Path,
    field: str,
    resource_id: str | None,
    kind: str | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected_const = schema.get("const")
    if expected_const is not None and value != expected_const:
        return [
            _schema_issue(
                path=path,
                resource_id=resource_id,
                kind=kind,
                field=field,
                message=f"Field '{field}' must equal '{expected_const}'.",
                suggestion="Repair the resource field to match the plugin schema.",
            )
        ]

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        return [
            _schema_issue(
                path=path,
                resource_id=resource_id,
                kind=kind,
                field=field,
                message=f"Field '{field}' must be {expected_type}.",
                suggestion="Repair the resource field type to match the plugin schema.",
            )
        ]

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        issues.append(
            _schema_issue(
                path=path,
                resource_id=resource_id,
                kind=kind,
                field=field,
                message=f"Field '{field}' must be one of {enum_values}.",
                suggestion="Use one of the values declared by the plugin schema.",
            )
        )

    pattern = schema.get("pattern")
    if isinstance(pattern, str) and isinstance(value, str):
        import re

        if re.fullmatch(pattern, value) is None:
            issues.append(
                _schema_issue(
                    path=path,
                    resource_id=resource_id,
                    kind=kind,
                    field=field,
                    message=f"Field '{field}' does not match pattern '{pattern}'.",
                    suggestion="Repair the field value to match the plugin schema pattern.",
                )
            )

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for required_field in required:
                if isinstance(required_field, str) and required_field not in value:
                    issues.append(
                        _schema_issue(
                            path=path,
                            resource_id=resource_id,
                            kind=kind,
                            field=_join_field(field, required_field),
                            message=f"Required field '{required_field}' is missing.",
                            suggestion="Add the required field or repair the resource.",
                        )
                    )
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for property_name, property_schema in properties.items():
                if property_name not in value or not isinstance(property_schema, dict):
                    continue
                issues.extend(
                    _validate_node(
                        value=value[property_name],
                        schema=property_schema,
                        path=path,
                        field=_join_field(field, property_name),
                        resource_id=resource_id,
                        kind=kind,
                    )
                )

    return issues


def _matches_type(value: Any, expected_type: Any) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _schema_issue(
    *,
    path: Path,
    resource_id: str | None,
    kind: str | None,
    field: str,
    message: str,
    suggestion: str,
) -> ValidationIssue:
    return error_issue(
        code="SCHEMA_VALIDATION_FAILED",
        message=message,
        path=path,
        resource_id=resource_id,
        kind=kind,
        field=field.replace("$.", ""),
        suggestion=suggestion,
    )


def _join_field(prefix: str, field: str) -> str:
    if prefix == "$":
        return field
    return f"{prefix}.{field}"
