from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath

from quality_core.cli.errors import QualityCliError
from quality_core.resources.atomic import atomic_write_text

TEMPLATE_PACKAGE = "quality_adapters.opencode.templates"


@dataclass(frozen=True, slots=True)
class OpenCodeInstallResult:
    target_root: Path
    written_paths: tuple[Path, ...]
    skipped_paths: tuple[Path, ...]
    config_path: Path | None = None
    config_written: bool = False
    local_plugin: bool = True
    npm_plugin: bool = False

    @property
    def changed_paths(self) -> tuple[Path, ...]:
        return self.written_paths

    def data(self) -> dict[str, object]:
        return {
            "targetRoot": str(self.target_root),
            "writtenPaths": [str(path) for path in self.written_paths],
            "skippedPaths": [str(path) for path in self.skipped_paths],
            "commands": [
                path.stem
                for path in self.target_root.joinpath("commands").glob("*.md")
                if path.is_file()
            ],
            "skills": [
                path.parent.name
                for path in self.target_root.joinpath("skills").glob("*/SKILL.md")
                if path.is_file()
            ],
            "plugins": [
                path.name
                for path in self.target_root.joinpath("plugins").glob("*.js")
                if path.is_file()
            ],
            "opencodeConfig": (
                {
                    "path": str(self.config_path),
                    "written": self.config_written,
                    "plugin": "opencode-quality-assistant",
                }
                if self.config_path is not None
                else None
            ),
            "mode": {
                "localPlugin": self.local_plugin,
                "npmPlugin": self.npm_plugin,
            },
        }


def install_project_pack(
    *,
    workspace_root: Path,
    force: bool = False,
    local_plugin: bool = True,
    npm_plugin: bool = False,
) -> OpenCodeInstallResult:
    """Install the project-local OpenCode adapter pack into ``<workspace>/.opencode``."""

    workspace = workspace_root.expanduser().resolve()
    result = install_pack(
        target_root=workspace / ".opencode",
        force=force,
        local_plugin=local_plugin,
    )
    config_path: Path | None = None
    config_written = False
    if npm_plugin:
        config_path, config_written = ensure_opencode_config(workspace_root=workspace, force=force)
    return OpenCodeInstallResult(
        target_root=result.target_root,
        written_paths=(
            (*result.written_paths, config_path)
            if config_written and config_path is not None
            else result.written_paths
        ),
        skipped_paths=result.skipped_paths,
        config_path=config_path,
        config_written=config_written,
        local_plugin=local_plugin,
        npm_plugin=npm_plugin,
    )


def install_pack(
    *,
    target_root: Path,
    force: bool = False,
    local_plugin: bool = True,
) -> OpenCodeInstallResult:
    target = target_root.expanduser().resolve()
    written: list[Path] = []
    skipped: list[Path] = []

    for relative_path, content in template_files().items():
        if not local_plugin and relative_path.startswith("plugins/"):
            continue
        destination = target / Path(relative_path)
        if destination.exists():
            existing = destination.read_text(encoding="utf-8")
            if existing == content:
                skipped.append(destination)
                continue
            if not force:
                raise QualityCliError(
                    code="OPENCODE_ADAPTER_CONFLICT",
                    message=(
                        "OpenCode adapter file already exists with different content: "
                        f"{destination}"
                    ),
                    path=str(destination),
                    suggestion=(
                        "Re-run with --force if you want to overwrite generated adapter files."
                    ),
                )

        atomic_write_text(destination, content)
        written.append(destination)

    return OpenCodeInstallResult(
        target_root=target,
        written_paths=tuple(written),
        skipped_paths=tuple(skipped),
        local_plugin=local_plugin,
    )


def ensure_opencode_config(*, workspace_root: Path, force: bool = False) -> tuple[Path, bool]:
    config_path = workspace_root / "opencode.json"
    desired = {"plugin": ["opencode-quality-assistant"]}
    desired_text = json.dumps(desired, indent=2) + "\n"

    if not config_path.exists():
        atomic_write_text(config_path, desired_text)
        return config_path, True

    existing_text = config_path.read_text(encoding="utf-8")
    try:
        existing = json.loads(existing_text)
    except json.JSONDecodeError as exc:
        if not force:
            raise QualityCliError(
                code="OPENCODE_ADAPTER_CONFLICT",
                message=f"OpenCode config is not valid JSON: {config_path}",
                path=str(config_path),
                suggestion="Fix opencode.json or re-run with --force to rewrite it.",
            ) from exc
        atomic_write_text(config_path, desired_text)
        return config_path, True

    plugins = existing.get("plugin")
    if plugins is None:
        existing["plugin"] = ["opencode-quality-assistant"]
    elif isinstance(plugins, list):
        if "opencode-quality-assistant" in plugins:
            return config_path, False
        existing["plugin"] = [*plugins, "opencode-quality-assistant"]
    else:
        if not force:
            raise QualityCliError(
                code="OPENCODE_ADAPTER_CONFLICT",
                message="OpenCode config field 'plugin' must be a list.",
                path=str(config_path),
                field="plugin",
                suggestion="Make plugin a list or re-run with --force to rewrite opencode.json.",
            )
        existing = desired

    atomic_write_text(config_path, json.dumps(existing, indent=2) + "\n")
    return config_path, True


def template_files() -> dict[str, str]:
    root = files(TEMPLATE_PACKAGE)
    result: dict[str, str] = {}

    def walk(node, prefix: PurePosixPath = PurePosixPath()) -> None:
        for child in node.iterdir():
            if child.name in {"__init__.py", "__pycache__"}:
                continue
            child_prefix = prefix / child.name
            if child.is_dir():
                walk(child, child_prefix)
                continue
            result[str(child_prefix)] = child.read_text(encoding="utf-8")

    walk(root)
    return dict(sorted(result.items()))
