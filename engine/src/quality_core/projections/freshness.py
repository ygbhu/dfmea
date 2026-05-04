from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.resources.atomic import atomic_write_text
from quality_core.workspace.config import API_VERSION
from quality_core.workspace.project import ProjectConfig


@dataclass(frozen=True, slots=True)
class ProjectionFreshness:
    status: str
    stale: bool
    reasons: tuple[str, ...]
    source_hash: str | None
    current_source_hash: str
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stale": self.stale,
            "reasons": list(self.reasons),
            "sourceHash": self.source_hash,
            "currentSourceHash": self.current_source_hash,
            "manifestPath": str(self.manifest_path),
        }


def projection_manifest_path(*, project: ProjectConfig, domain: str) -> Path:
    return project.root / domain / "projections" / "manifest.json"


def collect_project_source_hashes(project: ProjectConfig) -> dict[str, str]:
    source_paths = collect_project_source_paths(project)
    return {
        _relative_path(project=project, path=path): _file_hash(path)
        for path in source_paths
        if path.exists() and path.is_file()
    }


def collect_project_source_paths(project: ProjectConfig) -> tuple[Path, ...]:
    """Return source inputs that projection freshness tracks."""

    return tuple(_projection_source_paths(project))


def total_source_hash(sources: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, file_hash in sorted(sources.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def load_projection_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Projection manifest '{path}' is not valid JSON.",
            path=str(path),
            suggestion="Rebuild projections to replace the malformed manifest.",
        ) from exc
    if not isinstance(loaded, dict):
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Projection manifest '{path}' must contain a JSON object.",
            path=str(path),
            suggestion="Rebuild projections to replace the malformed manifest.",
        )
    return loaded


def projection_freshness(*, project: ProjectConfig, domain: str) -> ProjectionFreshness:
    path = projection_manifest_path(project=project, domain=domain)
    sources = collect_project_source_hashes(project)
    current_source_hash = total_source_hash(sources)
    manifest = load_projection_manifest(path)
    if manifest is None:
        return ProjectionFreshness(
            status="missing",
            stale=True,
            reasons=("manifest_missing",),
            source_hash=None,
            current_source_hash=current_source_hash,
            manifest_path=path,
        )

    reasons: list[str] = []
    manifest_sources = manifest.get("sources")
    if not isinstance(manifest_sources, dict):
        reasons.append("manifest_sources_missing")
    elif dict(manifest_sources) != sources:
        reasons.append("sources_changed")

    source_hash = manifest.get("sourceHash")
    if source_hash != current_source_hash:
        reasons.append("source_hash_changed")

    if manifest.get("apiVersion") != API_VERSION or manifest.get("kind") != "ProjectionManifest":
        reasons.append("manifest_header_invalid")

    status = "stale" if reasons else "fresh"
    return ProjectionFreshness(
        status=status,
        stale=bool(reasons),
        reasons=tuple(reasons),
        source_hash=source_hash if isinstance(source_hash, str) else None,
        current_source_hash=current_source_hash,
        manifest_path=path,
    )


def write_projection_manifest(
    *,
    project: ProjectConfig,
    domain: str,
    schema_versions: dict[str, str],
    projections: dict[str, str],
) -> dict[str, Any]:
    sources = collect_project_source_hashes(project)
    manifest = {
        "apiVersion": API_VERSION,
        "kind": "ProjectionManifest",
        "projectSlug": project.slug,
        "projectRoot": _relative_path(project=project, path=project.root),
        "builtAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "schemaVersions": {"core": API_VERSION, **schema_versions},
        "sourceHash": total_source_hash(sources),
        "sources": sources,
        "projections": projections,
    }
    path = projection_manifest_path(project=project, domain=domain)
    atomic_write_text(path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return manifest


def _projection_source_paths(project: ProjectConfig) -> list[Path]:
    paths: list[Path] = [project.config_path]

    schema_root = project.root / ".quality" / "schemas"
    if schema_root.exists():
        paths.extend(_files_under(schema_root))

    for domain_key, config in sorted(project.domains.items()):
        if not isinstance(config, dict) or config.get("enabled") is not True:
            continue
        root_value = config.get("root")
        if not isinstance(root_value, str) or not root_value:
            continue
        domain_root = (project.root / root_value).resolve()
        if domain_root.exists():
            paths.extend(
                path
                for path in _files_under(domain_root)
                if "projections" not in path.relative_to(domain_root).parts
                and "exports" not in path.relative_to(domain_root).parts
                and "reports" not in path.relative_to(domain_root).parts
            )

    link_root = project.root / "links"
    if link_root.exists():
        paths.extend(_files_under(link_root))

    tombstone_root = project.root / ".quality" / "tombstones"
    if tombstone_root.exists():
        paths.extend(_files_under(tombstone_root))

    return sorted({path.resolve() for path in paths if path.exists() and path.is_file()})


def _files_under(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _relative_path(*, project: ProjectConfig, path: Path) -> str:
    try:
        return path.resolve().relative_to(project.root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
