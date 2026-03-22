from __future__ import annotations

import json
from enum import Enum
from typing import Any

import typer


class OutputFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def render_text(payload: dict[str, Any]) -> str:
    project_id = payload.get("meta", {}).get("project_id")
    if payload.get("ok"):
        suffix = f" for project {project_id}" if project_id else ""
        return f"{payload['command']} ok{suffix}"
    first_error = payload.get("errors", [{}])[0]
    return f"{payload['command']} failed: {first_error.get('message', 'unknown error')}"


def render_markdown(payload: dict[str, Any]) -> str:
    project_id = payload.get("meta", {}).get("project_id", "unknown")
    status = "ok" if payload.get("ok") else "failed"
    return f"# {payload['command']}\n\n- status: {status}\n- project: {project_id}"


def render_payload(
    payload: dict[str, Any], output_format: OutputFormat, *, quiet: bool
) -> str:
    if output_format is OutputFormat.JSON:
        return render_json(payload)
    if quiet and payload.get("ok"):
        return ""
    if output_format is OutputFormat.TEXT:
        return render_text(payload)
    return render_markdown(payload)


def emit_payload(
    payload: dict[str, Any],
    output_format: OutputFormat,
    *,
    quiet: bool,
    exit_code: int = 0,
) -> None:
    rendered = render_payload(payload, output_format, quiet=quiet)
    if rendered:
        typer.echo(rendered)
    raise typer.Exit(code=exit_code)
