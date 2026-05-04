from __future__ import annotations

import json
from enum import Enum
from typing import Any, NoReturn

import typer

CONTRACT_VERSION = "quality.ai/v1"


class OutputFormat(str, Enum):
    JSON = "json"
    TEXT = "text"


def success_result(
    *,
    command: str,
    data: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contractVersion": CONTRACT_VERSION,
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
        "contractVersion": CONTRACT_VERSION,
        "ok": False,
        "command": command,
        "data": None,
        "warnings": warnings if warnings is not None else [],
        "errors": errors,
        "meta": meta if meta is not None else {},
    }


def validation_result(
    *,
    command: str,
    data: dict[str, Any],
    ok: bool,
    warnings: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_errors = list(errors or [])
    if not ok and not any(error.get("code") == "VALIDATION_FAILED" for error in resolved_errors):
        resolved_errors.append(
            {
                "code": "VALIDATION_FAILED",
                "severity": "error",
                "message": "Validation reported one or more error-level issues.",
                "suggestion": "Review data.issues and fix the reported validation errors.",
            }
        )
    return {
        "contractVersion": CONTRACT_VERSION,
        "ok": ok and not resolved_errors,
        "command": command,
        "data": data,
        "warnings": warnings if warnings is not None else [],
        "errors": resolved_errors,
        "meta": meta if meta is not None else {},
    }


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def render_text(payload: dict[str, Any]) -> str:
    if payload.get("ok"):
        meta = payload.get("meta", {})
        project_slug = meta.get("projectSlug")
        suffix = f" for project {project_slug}" if project_slug else ""
        return f"{payload['command']} ok{suffix}"

    first_error = payload.get("errors", [{}])[0]
    return f"{payload['command']} failed: {first_error.get('message', 'unknown error')}"


def render_payload(
    payload: dict[str, Any],
    output_format: OutputFormat,
    *,
    quiet: bool,
) -> str:
    if output_format is OutputFormat.JSON:
        return render_json(payload)
    if quiet and payload.get("ok"):
        return ""
    return render_text(payload)


def emit_payload(
    payload: dict[str, Any],
    output_format: OutputFormat,
    *,
    quiet: bool,
    exit_code: int = 0,
) -> NoReturn:
    rendered = render_payload(payload, output_format, quiet=quiet)
    if rendered:
        typer.echo(rendered)
    raise typer.Exit(code=exit_code)
