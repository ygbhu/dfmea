from __future__ import annotations

from typing import Any

from quality_core.methods.contracts import MethodCommand, QualityMethod
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.plugin import get_plugin


def validate_method_project(
    *,
    project: ProjectConfig,
    resources: tuple[Any, ...],
) -> list[Any]:
    from quality_methods.dfmea.validators import validate_dfmea_project

    return validate_dfmea_project(project=project, resources=resources)


def rebuild_method_projections(*, project: ProjectConfig) -> Any:
    from quality_methods.dfmea.projections import rebuild_projections

    return rebuild_projections(project=project)


def get_method() -> QualityMethod:
    return QualityMethod(
        method_id="dfmea",
        display_name="DFMEA",
        status="active",
        enabled_by_default=True,
        domain_key="dfmea",
        command_namespace="dfmea",
        plugin=get_plugin(),
        validator=validate_method_project,
        projection_rebuilder=rebuild_method_projections,
        commands=(
            MethodCommand(
                name="init",
                description="Initialize DFMEA project files and schema snapshot.",
                example="dfmea init --workspace . --project <slug>",
            ),
            MethodCommand(
                name="validate",
                description="Validate DFMEA source resources and methodology rules.",
                example="dfmea validate --workspace . --project <slug>",
            ),
            MethodCommand(
                name="projection rebuild",
                description="Rebuild DFMEA generated projection files from source resources.",
                example="dfmea projection rebuild --workspace . --project <slug>",
            ),
            MethodCommand(
                name="export markdown",
                description="Generate a Markdown DFMEA review export.",
                example="dfmea export markdown --workspace . --project <slug>",
            ),
        ),
    )
