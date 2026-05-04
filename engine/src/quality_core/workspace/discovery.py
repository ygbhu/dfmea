from __future__ import annotations

from pathlib import Path

from quality_core.cli.errors import QualityCliError
from quality_core.workspace.config import workspace_config_path


def discover_workspace_root(
    *,
    workspace: Path | None = None,
    start: Path | None = None,
) -> Path:
    if workspace is not None:
        root = workspace.expanduser().resolve()
        config_path = workspace_config_path(root)
        if config_path.exists():
            return root
        raise QualityCliError(
            code="WORKSPACE_NOT_FOUND",
            message=f"Workspace config was not found under '{root}'.",
            path=str(config_path),
            suggestion="Run `quality workspace init --workspace <path>` first.",
        )

    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if workspace_config_path(candidate).exists():
            return candidate

    raise QualityCliError(
        code="WORKSPACE_NOT_FOUND",
        message=f"No quality workspace was found from '{current}' upward.",
        suggestion="Run `quality workspace init` or pass --workspace to an existing workspace.",
    )
