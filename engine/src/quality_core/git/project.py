from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quality_core.cli.errors import QualityCliError
from quality_core.git.paths import (
    collect_managed_project_paths,
    managed_pathspecs,
    project_relative_from_repo_path,
    relative_to_project,
    relative_to_repo,
)
from quality_core.git.runner import (
    current_branch,
    current_head,
    ensure_no_unresolved_conflicts,
    find_git_root,
    git,
    git_bytes,
)
from quality_core.methods.contracts import QualityMethod
from quality_core.methods.registry import list_active_quality_methods
from quality_core.projections import ProjectionFreshness, projection_freshness
from quality_core.resources.atomic import atomic_write_text
from quality_core.resources.envelope import resource_from_document
from quality_core.validation.engine import validate_project
from quality_core.validation.report import ValidationReport
from quality_core.workspace.config import API_VERSION
from quality_core.workspace.project import ProjectConfig, load_project_config


@dataclass(frozen=True, slots=True)
class ProjectGitResult:
    project: ProjectConfig
    repo_root: Path
    data: dict[str, Any]
    schema_versions: dict[str, str]


def project_status(*, project: ProjectConfig) -> ProjectGitResult:
    repo_root = find_git_root(project.root)
    paths = collect_managed_project_paths(project)
    dirty = _dirty_managed_paths(repo_root=repo_root, paths=paths.snapshot_paths)
    report = _validation_report(project)
    freshness = _projection_statuses(project)
    return ProjectGitResult(
        project=project,
        repo_root=repo_root,
        schema_versions=report.schema_versions,
        data={
            "git": {
                "branch": current_branch(repo_root),
                "head": current_head(repo_root),
            },
            "dirtyManagedPaths": dirty,
            "dirtyManagedCount": len(dirty),
            "validation": _validation_summary(report),
            "projections": [_freshness_entry(domain, item) for domain, item in freshness],
            "enabledPlugins": _enabled_plugins(project),
            "generatedOutputs": _generated_outputs(project),
            "managedPaths": {
                "source": _relative_paths(repo_root=repo_root, paths=paths.source_paths),
                "generated": _relative_paths(repo_root=repo_root, paths=paths.generated_paths),
            },
        },
    )


def project_snapshot(*, project: ProjectConfig, message: str | None = None) -> ProjectGitResult:
    repo_root = find_git_root(project.root)
    ensure_no_unresolved_conflicts(repo_root)
    report = _validation_report(project)
    _raise_for_validation_errors(report)
    rebuilt = _rebuild_enabled_projections(project)
    paths = collect_managed_project_paths(project)
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=paths.snapshot_paths)
    if pathspecs:
        git("add", "--", *pathspecs, cwd=repo_root, error_code="GIT_CONFLICT")
    staged = _staged_managed_paths(repo_root=repo_root, paths=paths.snapshot_paths)
    if not staged:
        return ProjectGitResult(
            project=project,
            repo_root=repo_root,
            schema_versions=report.schema_versions,
            data={
                "commit": None,
                "created": False,
                "stagedPaths": [],
                "rebuilt": rebuilt,
                "validation": _validation_summary(report),
            },
        )

    commit_message = message or f"quality(project): snapshot {project.slug}"
    git(
        "commit",
        "-m",
        commit_message,
        cwd=repo_root,
        error_code="GIT_CONFLICT",
        suggestion="Inspect staged project paths and retry the snapshot.",
    )
    commit_hash = current_head(repo_root)
    return ProjectGitResult(
        project=project,
        repo_root=repo_root,
        schema_versions=report.schema_versions,
        data={
            "commit": commit_hash,
            "created": True,
            "message": commit_message,
            "stagedPaths": staged,
            "rebuilt": rebuilt,
            "validation": _validation_summary(report),
        },
    )


def project_history(*, project: ProjectConfig, limit: int = 20) -> ProjectGitResult:
    repo_root = find_git_root(project.root)
    paths = collect_managed_project_paths(project)
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=paths.snapshot_paths)
    entries: list[dict[str, Any]] = []
    if pathspecs:
        output = git(
            "log",
            f"-n{limit}",
            "--date=iso-strict",
            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
            "--",
            *pathspecs,
            cwd=repo_root,
            error_code="GIT_CONFLICT",
        ).stdout
        for line in output.splitlines():
            if not line.strip():
                continue
            commit_hash, author, date, subject = _split_log_line(line)
            changed = _commit_changed_paths(
                repo_root=repo_root,
                commit=commit_hash,
                paths=paths.snapshot_paths,
            )
            entries.append(
                {
                    "commit": commit_hash,
                    "author": author,
                    "date": date,
                    "subject": subject,
                    "changedPaths": changed,
                    "resources": _resource_summaries_for_paths(
                        repo_root=repo_root,
                        project=project,
                        paths=changed,
                        ref=commit_hash,
                    ),
                }
            )
    return ProjectGitResult(
        project=project,
        repo_root=repo_root,
        schema_versions={},
        data={"history": entries, "limit": limit},
    )


def project_diff(
    *,
    project: ProjectConfig,
    from_ref: str | None = None,
    to_ref: str | None = None,
) -> ProjectGitResult:
    repo_root = find_git_root(project.root)
    paths = collect_managed_project_paths(project)
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=paths.snapshot_paths)
    diff_args = _diff_args(from_ref=from_ref, to_ref=to_ref)
    changed = _changed_paths_for_diff(repo_root=repo_root, diff_args=diff_args, pathspecs=pathspecs)
    return ProjectGitResult(
        project=project,
        repo_root=repo_root,
        schema_versions={},
        data={
            "from": from_ref,
            "to": to_ref,
            "changedPaths": changed,
            "resources": _resource_summaries_for_paths(
                repo_root=repo_root,
                project=project,
                paths=[item["path"] for item in changed],
                ref=to_ref,
            ),
        },
    )


def project_restore(
    *,
    project: ProjectConfig,
    ref: str,
    message: str | None = None,
    force_with_backup: bool = False,
) -> ProjectGitResult:
    repo_root = find_git_root(project.root)
    ensure_no_unresolved_conflicts(repo_root)
    paths = collect_managed_project_paths(project)
    dirty = _dirty_managed_paths(repo_root=repo_root, paths=paths.restore_paths)
    if dirty and not force_with_backup:
        raise QualityCliError(
            code="GIT_DIRTY",
            message="Managed project paths are dirty; restore would overwrite local changes.",
            target={"dirtyManagedPaths": dirty},
            suggestion="Snapshot or discard local changes, or rerun with --force-with-backup.",
        )

    backup_path = _write_restore_backup(
        repo_root=repo_root,
        project=project,
        dirty=dirty,
        force_with_backup=force_with_backup,
    )
    restored_paths = _restore_non_generated_paths(repo_root=repo_root, project=project, ref=ref)
    restored_project = load_project_config(project.root)
    rebuilt = _rebuild_enabled_projections(restored_project)
    report = _validation_report(restored_project)
    _raise_for_validation_errors(report)
    refreshed_paths = collect_managed_project_paths(restored_project)
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=refreshed_paths.snapshot_paths)
    if pathspecs:
        git("add", "--", *pathspecs, cwd=repo_root, error_code="GIT_CONFLICT")
    staged = _staged_managed_paths(repo_root=repo_root, paths=refreshed_paths.snapshot_paths)
    if not staged:
        return ProjectGitResult(
            project=restored_project,
            repo_root=repo_root,
            schema_versions=report.schema_versions,
            data={
                "commit": None,
                "created": False,
                "ref": ref,
                "restoredPaths": restored_paths,
                "backupPath": str(backup_path) if backup_path is not None else None,
                "rebuilt": rebuilt,
                "validation": _validation_summary(report),
            },
        )

    commit_message = message or f"quality(restore): restore {project.slug} to {ref}"
    git(
        "commit",
        "-m",
        commit_message,
        cwd=repo_root,
        error_code="GIT_CONFLICT",
        suggestion="Inspect staged restored paths and retry the restore commit.",
    )
    return ProjectGitResult(
            project=restored_project,
            repo_root=repo_root,
            schema_versions=report.schema_versions,
        data={
            "commit": current_head(repo_root),
            "created": True,
            "message": commit_message,
            "ref": ref,
            "restoredPaths": restored_paths,
            "stagedPaths": staged,
            "backupPath": str(backup_path) if backup_path is not None else None,
            "rebuilt": rebuilt,
            "validation": _validation_summary(report),
        },
    )


def _validation_report(project: ProjectConfig) -> ValidationReport:
    return validate_project(
        project=project,
        plugin_validators={
            method.method_id: method.validator
            for method in list_active_quality_methods()
            if method.validator is not None
        },
    )


def _raise_for_validation_errors(report: ValidationReport) -> None:
    if report.ok:
        return
    raise QualityCliError(
        code="VALIDATION_FAILED",
        message="Project validation reported error-level issues.",
        target={"summary": report.to_data()["summary"], "issues": report.to_data()["issues"]},
        suggestion="Run `dfmea validate --project <project>` and fix the reported issues.",
    )


def _projection_statuses(project: ProjectConfig) -> list[tuple[str, ProjectionFreshness]]:
    statuses: list[tuple[str, ProjectionFreshness]] = []
    for method in _enabled_active_methods(project):
        statuses.append(
            (
                method.domain_key,
                projection_freshness(project=project, domain=method.domain_key),
            )
        )
    return statuses


def _rebuild_enabled_projections(project: ProjectConfig) -> list[dict[str, Any]]:
    rebuilt: list[dict[str, Any]] = []
    for method in _enabled_active_methods(project):
        if method.projection_rebuilder is None:
            continue
        result = method.projection_rebuilder(project=project)
        rebuilt.append({"domain": method.domain_key, "written": result.data.get("written", [])})
    return rebuilt


def _dirty_managed_paths(*, repo_root: Path, paths: tuple[Path, ...]) -> list[dict[str, str]]:
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=paths)
    if not pathspecs:
        return []
    output = git(
        "status",
        "--porcelain=v1",
        "--",
        *pathspecs,
        cwd=repo_root,
        error_code="GIT_CONFLICT",
    ).stdout
    return [_parse_porcelain_line(line) for line in output.splitlines() if line.strip()]


def _staged_managed_paths(*, repo_root: Path, paths: tuple[Path, ...]) -> list[str]:
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=paths)
    if not pathspecs:
        return []
    output = git(
        "diff",
        "--cached",
        "--name-only",
        "--",
        *pathspecs,
        cwd=repo_root,
        error_code="GIT_CONFLICT",
    ).stdout
    return [line for line in output.splitlines() if line.strip()]


def _commit_changed_paths(
    *,
    repo_root: Path,
    commit: str,
    paths: tuple[Path, ...],
) -> list[dict[str, str]]:
    pathspecs = managed_pathspecs(repo_root=repo_root, paths=paths)
    output = git(
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        commit,
        "--",
        *pathspecs,
        cwd=repo_root,
        error_code="GIT_CONFLICT",
    ).stdout
    return [_parse_name_status(line) for line in output.splitlines() if line.strip()]


def _changed_paths_for_diff(
    *,
    repo_root: Path,
    diff_args: tuple[str, ...],
    pathspecs: tuple[str, ...],
) -> list[dict[str, str]]:
    if not pathspecs:
        return []
    output = git(
        "diff",
        "--name-status",
        *diff_args,
        "--",
        *pathspecs,
        cwd=repo_root,
        error_code="GIT_CONFLICT",
    ).stdout
    return [_parse_name_status(line) for line in output.splitlines() if line.strip()]


def _restore_non_generated_paths(*, repo_root: Path, project: ProjectConfig, ref: str) -> list[str]:
    restore_prefixes = (
        "project.yaml",
        ".quality/schemas",
        ".quality/tombstones",
        "links",
        "evidence",
        *tuple(_enabled_domain_root_values(project)),
    )
    target_paths = _tree_paths(repo_root=repo_root, ref=ref, project=project)
    paths_to_write = [
        path
        for path in target_paths
        if _is_restorable_path(path=path, prefixes=restore_prefixes)
    ]
    current_paths = [
        relative_to_project(project=project, path=path)
        for path in collect_managed_project_paths(project).restore_paths
    ]
    for relative_path in sorted(set(current_paths) - set(paths_to_write)):
        absolute = project.root / relative_path
        if absolute.exists():
            absolute.unlink()

    restored: list[str] = []
    for relative_path in paths_to_write:
        content = git_bytes(
            "show",
            f"{ref}:{relative_to_repo(repo_root=repo_root, path=project.root / relative_path)}",
            cwd=repo_root,
            error_code="RESTORE_PRECONDITION_FAILED",
            suggestion="Check the restore ref and project path.",
        )
        target = project.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        restored.append(relative_to_repo(repo_root=repo_root, path=target))
    return restored


def _tree_paths(*, repo_root: Path, ref: str, project: ProjectConfig) -> list[str]:
    project_rel = relative_to_repo(repo_root=repo_root, path=project.root)
    output = git(
        "ls-tree",
        "-r",
        "--name-only",
        ref,
        "--",
        project_rel,
        cwd=repo_root,
        error_code="RESTORE_PRECONDITION_FAILED",
        suggestion="Check the restore ref and project path.",
    ).stdout
    paths: list[str] = []
    prefix = f"{project_rel}/"
    for line in output.splitlines():
        if line.startswith(prefix):
            paths.append(line[len(prefix) :])
    return paths


def _is_restorable_path(*, path: str, prefixes: tuple[str, ...]) -> bool:
    if path.startswith(".quality/locks/"):
        return False
    if "/projections/" in f"/{path}" or "/exports/" in f"/{path}" or "/reports/" in f"/{path}":
        return False
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _resource_summaries_for_paths(
    *,
    repo_root: Path,
    project: ProjectConfig,
    paths: list[dict[str, str]] | list[str],
    ref: str | None,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in paths:
        path = item["path"] if isinstance(item, dict) else item
        summary = _resource_summary_for_path(
            repo_root=repo_root,
            project=project,
            path=path,
            ref=ref,
        )
        if summary is not None:
            summaries.append(summary)
    return summaries


def _resource_summary_for_path(
    *,
    repo_root: Path,
    project: ProjectConfig,
    path: str,
    ref: str | None,
) -> dict[str, Any] | None:
    if not path.endswith((".yaml", ".yml")):
        return None
    content: str | None = None
    if ref is not None:
        completed = git(
            "show",
            f"{ref}:{path}",
            cwd=repo_root,
            error_code="GIT_CONFLICT",
            allow_failure=True,
        )
        content = completed.stdout if completed.stdout else None
    else:
        absolute = repo_root / path
        if absolute.exists():
            content = absolute.read_text(encoding="utf-8")
    if content is None:
        return None
    try:
        loaded = yaml.safe_load(content)
        if not isinstance(loaded, dict):
            return None
        resource = resource_from_document(loaded, path=repo_root / path)
    except (QualityCliError, yaml.YAMLError):
        return {
            "path": path,
            "parseable": False,
            "projectPath": project_relative_from_repo_path(
                repo_root=repo_root,
                project=project,
                path=path,
            ),
        }
    return {
        "path": path,
        "projectPath": project_relative_from_repo_path(
            repo_root=repo_root,
            project=project,
            path=path,
        ),
        "parseable": True,
        "id": resource.resource_id,
        "kind": resource.kind,
        "title": _resource_title(resource.metadata, resource.spec),
    }


def _write_restore_backup(
    *,
    repo_root: Path,
    project: ProjectConfig,
    dirty: list[dict[str, str]],
    force_with_backup: bool,
) -> Path | None:
    if not dirty or not force_with_backup:
        return None
    head = current_head(repo_root)
    backup_path = project.root / ".quality" / "restore-backup.yaml"
    document = {
        "apiVersion": API_VERSION,
        "kind": "RestoreBackup",
        "metadata": {"id": "RESTORE-BACKUP"},
        "spec": {
            "head": head,
            "dirtyManagedPaths": dirty,
        },
    }
    atomic_write_text(backup_path, yaml.safe_dump(document, sort_keys=False))
    return backup_path


def _diff_args(*, from_ref: str | None, to_ref: str | None) -> tuple[str, ...]:
    if from_ref is not None and to_ref is not None:
        return (from_ref, to_ref)
    if from_ref is not None:
        return (from_ref,)
    if to_ref is not None:
        return ("HEAD", to_ref)
    return ()


def _parse_porcelain_line(line: str) -> dict[str, str]:
    status = line[:2]
    path = line[3:]
    if " -> " in path:
        old_path, new_path = path.split(" -> ", 1)
        return {"status": status.strip(), "path": new_path, "oldPath": old_path}
    return {"status": status.strip(), "path": path}


def _parse_name_status(line: str) -> dict[str, str]:
    parts = line.split("\t")
    if len(parts) >= 3 and parts[0].startswith("R"):
        return {"status": parts[0], "path": parts[2], "oldPath": parts[1]}
    if len(parts) >= 2:
        return {"status": parts[0], "path": parts[1]}
    return {"status": "", "path": line}


def _split_log_line(line: str) -> tuple[str, str, str, str]:
    parts = line.split("\x1f", 3)
    while len(parts) < 4:
        parts.append("")
    return parts[0], parts[1], parts[2], parts[3]


def _validation_summary(report: ValidationReport) -> dict[str, Any]:
    return report.to_data()["summary"]


def _freshness_entry(domain: str, freshness: ProjectionFreshness) -> dict[str, Any]:
    return {"domain": domain, **freshness.to_dict()}


def _enabled_plugins(project: ProjectConfig) -> list[str]:
    return [method.method_id for method in _enabled_active_methods(project)]


def _enabled_active_methods(project: ProjectConfig) -> list[QualityMethod]:
    return [
        method
        for method in list_active_quality_methods()
        if method.enabled_for_project(project)
    ]


def _enabled_domain_root_values(project: ProjectConfig) -> list[str]:
    roots: list[str] = []
    for config in project.domains.values():
        if not isinstance(config, dict) or config.get("enabled") is not True:
            continue
        root = config.get("root")
        if isinstance(root, str) and root:
            roots.append(root.removeprefix("./").rstrip("/"))
    return roots


def _generated_outputs(project: ProjectConfig) -> dict[str, Any]:
    return {
        "projectionsManaged": project.generated_outputs.projections_managed,
        "exportsManaged": project.generated_outputs.exports_managed,
        "reportsManaged": project.generated_outputs.reports_managed,
        "exportProfiles": list(project.generated_outputs.export_profiles),
    }


def _relative_paths(*, repo_root: Path, paths: tuple[Path, ...]) -> list[str]:
    return [relative_to_repo(repo_root=repo_root, path=path) for path in paths]


def _resource_title(metadata: dict[str, Any], spec: dict[str, Any]) -> str | None:
    for value in (
        metadata.get("title"),
        metadata.get("name"),
        spec.get("description"),
        spec.get("summary"),
    ):
        if isinstance(value, str) and value:
            return value
    return None
