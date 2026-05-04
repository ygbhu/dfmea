from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.graph import load_project_graph
from quality_core.resources.atomic import atomic_write_text
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.projections import (
    build_action_backlog_projection,
    build_risk_register_projection,
    build_tree_projection,
)


@dataclass(frozen=True, slots=True)
class DfmeaExportResult:
    project: ProjectConfig
    output_dir: Path
    files: tuple[dict[str, Any], ...]
    generated_outputs: dict[str, Any]


def export_markdown(
    *,
    project: ProjectConfig,
    out_dir: Path | None = None,
    layout: str = "review",
) -> DfmeaExportResult:
    if layout not in {"review", "ledger"}:
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message=f"Unsupported export layout '{layout}'.",
            target={"layout": layout},
            suggestion="Use --layout review or --layout ledger.",
        )
    graph = load_project_graph(project=project)
    output_dir = _output_dir(project=project, out_dir=out_dir)
    export_path = output_dir / f"{project.slug}-dfmea-{layout}.md"
    content = _render_markdown(
        project=project,
        tree=build_tree_projection(graph=graph),
        risk=build_risk_register_projection(graph=graph),
        actions=build_action_backlog_projection(graph=graph),
        layout=layout,
    )
    atomic_write_text(export_path, content)
    return _result(
        project=project,
        output_dir=output_dir,
        files=(_file_entry(export_path, "markdown"),),
    )


def export_risk_csv(
    *,
    project: ProjectConfig,
    out_dir: Path | None = None,
) -> DfmeaExportResult:
    graph = load_project_graph(project=project)
    output_dir = _output_dir(project=project, out_dir=out_dir)
    export_path = output_dir / f"{project.slug}-dfmea-risk-register.csv"
    risk = build_risk_register_projection(graph=graph)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "failureModeId",
                "failureModePath",
                "description",
                "severity",
                "causeId",
                "causePath",
                "causeDescription",
                "occurrence",
                "detection",
                "ap",
            ],
        )
        writer.writeheader()
        for row in risk["rows"]:
            writer.writerow(
                {
                    "failureModeId": row.get("failureModeId"),
                    "failureModePath": row.get("failureModePath"),
                    "description": row.get("description"),
                    "severity": row.get("severity"),
                    "causeId": row.get("causeId"),
                    "causePath": row.get("causePath"),
                    "causeDescription": row.get("causeDescription"),
                    "occurrence": row.get("occurrence"),
                    "detection": row.get("detection"),
                    "ap": row.get("ap"),
                }
            )
    return _result(project=project, output_dir=output_dir, files=(_file_entry(export_path, "csv"),))


def _render_markdown(
    *,
    project: ProjectConfig,
    tree: dict[str, Any],
    risk: dict[str, Any],
    actions: dict[str, Any],
    layout: str,
) -> str:
    lines = [
        f"# {project.name} DFMEA",
        "",
        f"- Project: `{project.slug}`",
        f"- Layout: `{layout}`",
        "",
        "## Structure",
        "",
    ]
    for root in tree["roots"]:
        _append_tree(lines=lines, node=root, level=0)
    if not tree["roots"]:
        lines.append("- No structure nodes")
    lines.extend(["", "## Risk Register", ""])
    for row in risk["rows"]:
        lines.extend(
            [
                f"### {row.get('failureModeId')} - {row.get('description')}",
                "",
                f"- Source: `{row.get('failureModePath')}`",
                f"- Severity: `{row.get('severity')}`",
                f"- Cause: `{row.get('causeId')}` {row.get('causeDescription') or ''}".rstrip(),
                f"- Cause Source: `{row.get('causePath')}`",
                f"- Occurrence: `{row.get('occurrence')}`",
                f"- Detection: `{row.get('detection')}`",
                f"- AP: `{row.get('ap')}`",
                "",
            ]
        )
    if not risk["rows"]:
        lines.append("No risk rows.")
    lines.extend(["", "## Actions", ""])
    for item in actions["items"]:
        lines.extend(
            [
                f"- `{item.get('id')}` {item.get('title') or ''}".rstrip(),
                f"  - Source: `{item.get('path')}`",
                f"  - Status: `{item.get('status')}`",
                f"  - Failure Mode: `{item.get('failureModeRef')}`",
            ]
        )
    if not actions["items"]:
        lines.append("No actions.")
    lines.append("")
    return "\n".join(lines)


def _append_tree(*, lines: list[str], node: dict[str, Any], level: int) -> None:
    indent = "  " * level
    lines.append(
        f"{indent}- `{node.get('id')}` {node.get('title') or ''} "
        f"({node.get('kind')}, `{node.get('path')}`)"
    )
    for child in node.get("children", []):
        if isinstance(child, dict):
            _append_tree(lines=lines, node=child, level=level + 1)


def _output_dir(*, project: ProjectConfig, out_dir: Path | None) -> Path:
    output_dir = out_dir if out_dir is not None else project.root / "exports" / "dfmea"
    if output_dir.exists() and not output_dir.is_dir():
        raise QualityCliError(
            code="VALIDATION_FAILED",
            message=f"Output path '{output_dir}' must be a directory.",
            path=str(output_dir),
            target={"out": str(output_dir)},
            suggestion="Provide a directory path for --out.",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _result(
    *,
    project: ProjectConfig,
    output_dir: Path,
    files: tuple[dict[str, Any], ...],
) -> DfmeaExportResult:
    return DfmeaExportResult(
        project=project,
        output_dir=output_dir,
        files=files,
        generated_outputs={
            "exportsManaged": project.generated_outputs.exports_managed,
            "exportProfiles": list(project.generated_outputs.export_profiles),
        },
    )


def _file_entry(path: Path, kind: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "kind": kind,
        "bytes": path.stat().st_size,
    }
