from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quality_core.projections import collect_project_source_paths
from quality_core.workspace.project import ProjectConfig


@dataclass(frozen=True, slots=True)
class ManagedProjectPaths:
    source_paths: tuple[Path, ...]
    generated_paths: tuple[Path, ...]
    restore_paths: tuple[Path, ...]

    @property
    def snapshot_paths(self) -> tuple[Path, ...]:
        return _unique_paths((*self.source_paths, *self.generated_paths))


def collect_managed_project_paths(project: ProjectConfig) -> ManagedProjectPaths:
    source_paths = [*collect_project_source_paths(project)]

    evidence_root = project.root / "evidence"
    if evidence_root.exists():
        source_paths.extend(_files_under(evidence_root))

    generated_paths: list[Path] = []
    if project.generated_outputs.projections_managed:
        generated_paths.extend(_generated_domain_files(project, "projections"))
    if project.generated_outputs.exports_managed:
        generated_paths.extend(_files_under(project.root / "exports"))
        generated_paths.extend(_generated_domain_files(project, "exports"))
    if project.generated_outputs.reports_managed:
        generated_paths.extend(_files_under(project.root / "reports"))
        generated_paths.extend(_generated_domain_files(project, "reports"))

    resolved_sources = _exclude_locks(project=project, paths=source_paths)
    resolved_generated = _exclude_locks(project=project, paths=generated_paths)
    return ManagedProjectPaths(
        source_paths=resolved_sources,
        generated_paths=resolved_generated,
        restore_paths=resolved_sources,
    )


def relative_to_repo(*, repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def relative_to_project(*, project: ProjectConfig, path: Path) -> str:
    return path.resolve().relative_to(project.root.resolve()).as_posix()


def project_relative_from_repo_path(*, repo_root: Path, project: ProjectConfig, path: str) -> str:
    absolute = (repo_root / path).resolve()
    return relative_to_project(project=project, path=absolute)


def managed_pathspecs(*, repo_root: Path, paths: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(relative_to_repo(repo_root=repo_root, path=path) for path in paths)


def project_pathspec(project: ProjectConfig) -> str:
    return project.root.as_posix()


def _generated_domain_files(project: ProjectConfig, directory: str) -> list[Path]:
    paths: list[Path] = []
    for config in project.domains.values():
        if not isinstance(config, dict) or config.get("enabled") is not True:
            continue
        root_value = config.get("root")
        if not isinstance(root_value, str) or not root_value:
            continue
        paths.extend(_files_under(project.root / root_value / directory))
    return paths


def _files_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _exclude_locks(*, project: ProjectConfig, paths: list[Path]) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _unique_paths(paths)
        if not _is_lock_path(project=project, path=path)
    )


def _is_lock_path(*, project: ProjectConfig, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project.root.resolve())
    except ValueError:
        return False
    return (
        len(relative.parts) >= 3
        and relative.parts[0] == ".quality"
        and relative.parts[1] == "locks"
    )


def _unique_paths(paths: tuple[Path, ...] | list[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return tuple(sorted(result))
