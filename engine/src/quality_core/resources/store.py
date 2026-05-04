from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin
from quality_core.resources.atomic import atomic_write_text
from quality_core.resources.envelope import Resource, dump_resource, load_resource, make_resource
from quality_core.resources.ids import allocate_next_id, write_tombstone
from quality_core.resources.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, ProjectWriteLock
from quality_core.resources.paths import (
    ResourceRef,
    ResourceSelector,
    allowed_prefixes,
    collection_root,
    find_collection,
    resource_path,
    resource_path_for_collection_id,
    singleton_path,
    validate_resource_path,
)
from quality_core.workspace.project import ProjectConfig


@dataclass(frozen=True, slots=True)
class WriteResult:
    resource_id: str
    kind: str
    path: Path
    changed_paths: tuple[Path, ...]
    lock_path: Path
    tombstone_path: Path | None = None


class ResourceStore:
    def __init__(
        self,
        *,
        project: ProjectConfig,
        plugin: BuiltinPlugin,
        lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self.project = project
        self.plugin = plugin
        self.lock_timeout_seconds = lock_timeout_seconds

    def ref(self, *, kind: str, resource_id: str) -> ResourceRef:
        path = self._path_for_ref(kind=kind, resource_id=resource_id)
        return ResourceRef(
            domain=self.plugin.domain_key,
            kind=kind,
            resource_id=resource_id,
            path=path,
        )

    def load(self, ref: ResourceRef) -> Resource:
        resource = load_resource(ref.path)
        validate_resource_path(
            plugin=self.plugin,
            resource=resource,
            path=ref.path,
        )
        return resource

    def list(self, selector: ResourceSelector | None = None) -> list[Resource]:
        selector = selector or ResourceSelector()
        resources: list[Resource] = []
        for singleton in self.plugin.singletons:
            if selector.kind is not None and singleton.kind != selector.kind:
                continue
            path = singleton_path(
                project_root=self.project.root,
                plugin=self.plugin,
                kind=singleton.kind,
                resource_id=singleton.resource_id,
            )
            if path.exists():
                resources.append(load_resource(path))

        for collection in self.plugin.collections:
            if selector.kind is not None and collection.kind != selector.kind:
                continue
            if selector.id_prefix is not None and selector.id_prefix not in allowed_prefixes(
                collection
            ):
                continue
            root = collection_root(
                project_root=self.project.root,
                plugin=self.plugin,
                collection=collection,
            )
            if not root.exists():
                continue
            for path in sorted(root.glob("*.yaml")):
                resource = load_resource(path)
                validate_resource_path(
                    plugin=self.plugin,
                    resource=resource,
                    path=path,
                )
                resources.append(resource)
        return resources

    def create(self, resource: Resource) -> WriteResult:
        path = resource_path(
            project_root=self.project.root,
            plugin=self.plugin,
            resource=resource,
        )
        validate_resource_path(plugin=self.plugin, resource=resource, path=path)
        with ProjectWriteLock(
            self.project.root,
            timeout_seconds=self.lock_timeout_seconds,
        ) as lock:
            if path.exists():
                raise QualityCliError(
                    code="ID_CONFLICT",
                    message=f"Resource '{resource.resource_id}' already exists.",
                    path=str(path),
                    target={"kind": resource.kind, "resourceId": resource.resource_id},
                    suggestion="Allocate a new ID or update the existing resource.",
                )
            atomic_write_text(path, dump_resource(resource.with_path(path)))
            return WriteResult(
                resource_id=resource.resource_id,
                kind=resource.kind,
                path=path,
                changed_paths=(path,),
                lock_path=lock.path,
            )

    def create_collection_resource(
        self,
        *,
        kind: str,
        id_prefix: str,
        spec: dict,
        metadata: dict | None = None,
    ) -> WriteResult:
        collection = find_collection(
            self.plugin,
            kind=kind,
            id_prefix_value=id_prefix,
        )
        with ProjectWriteLock(
            self.project.root,
            timeout_seconds=self.lock_timeout_seconds,
        ) as lock:
            resource_id = allocate_next_id(
                project_root=self.project.root,
                plugin=self.plugin,
                collection=collection,
                id_prefix=id_prefix,
            )
            resource = make_resource(
                kind=kind,
                resource_id=resource_id,
                metadata=metadata,
                spec=spec,
            )
            path = resource_path_for_collection_id(
                project_root=self.project.root,
                plugin=self.plugin,
                kind=kind,
                resource_id=resource_id,
            )
            validate_resource_path(
                plugin=self.plugin,
                resource=resource,
                path=path,
            )
            atomic_write_text(path, dump_resource(resource.with_path(path)))
            return WriteResult(
                resource_id=resource_id,
                kind=kind,
                path=path,
                changed_paths=(path,),
                lock_path=lock.path,
            )

    def update(self, resource: Resource) -> WriteResult:
        path = resource_path(
            project_root=self.project.root,
            plugin=self.plugin,
            resource=resource,
        )
        validate_resource_path(plugin=self.plugin, resource=resource, path=path)
        with ProjectWriteLock(
            self.project.root,
            timeout_seconds=self.lock_timeout_seconds,
        ) as lock:
            if not path.exists():
                raise QualityCliError(
                    code="RESOURCE_NOT_FOUND",
                    message=f"Resource '{resource.resource_id}' does not exist.",
                    path=str(path),
                    target={"kind": resource.kind, "resourceId": resource.resource_id},
                    suggestion="Create the resource before updating it.",
                )
            atomic_write_text(path, dump_resource(resource.with_path(path)))
            return WriteResult(
                resource_id=resource.resource_id,
                kind=resource.kind,
                path=path,
                changed_paths=(path,),
                lock_path=lock.path,
            )

    def delete(self, ref: ResourceRef) -> WriteResult:
        with ProjectWriteLock(
            self.project.root,
            timeout_seconds=self.lock_timeout_seconds,
        ) as lock:
            resource = self.load(ref)
            try:
                ref.path.unlink()
            except FileNotFoundError as exc:
                raise QualityCliError(
                    code="RESOURCE_NOT_FOUND",
                    message=f"Resource file '{ref.path}' was not found.",
                    path=str(ref.path),
                    suggestion="Check the resource ID and retry.",
                ) from exc
            tombstone = write_tombstone(
                project_root=self.project.root,
                resource_id=resource.resource_id,
                resource_kind=resource.kind,
            )
            return WriteResult(
                resource_id=resource.resource_id,
                kind=resource.kind,
                path=ref.path,
                changed_paths=(ref.path, tombstone),
                lock_path=lock.path,
                tombstone_path=tombstone,
            )

    def _path_for_ref(self, *, kind: str, resource_id: str) -> Path:
        try:
            return singleton_path(
                project_root=self.project.root,
                plugin=self.plugin,
                kind=kind,
                resource_id=resource_id,
            )
        except QualityCliError as exc:
            if exc.code != "RESOURCE_NOT_FOUND":
                raise
            return resource_path_for_collection_id(
                project_root=self.project.root,
                plugin=self.plugin,
                kind=kind,
                resource_id=resource_id,
            )
