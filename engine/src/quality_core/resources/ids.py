from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin, PluginCollection
from quality_core.resources.atomic import atomic_write_text
from quality_core.resources.paths import allowed_prefixes, collection_root
from quality_core.workspace.config import API_VERSION


def tombstones_root(project_root: Path) -> Path:
    return project_root / ".quality" / "tombstones"


def tombstone_path(project_root: Path, resource_id: str) -> Path:
    return tombstones_root(project_root) / resource_id


def allocate_next_id(
    *,
    project_root: Path,
    plugin: BuiltinPlugin,
    collection: PluginCollection,
    id_prefix: str,
) -> str:
    if id_prefix not in allowed_prefixes(collection):
        raise QualityCliError(
            code="ID_PREFIX_MISMATCH",
            message=f"ID prefix '{id_prefix}' is not valid for kind '{collection.kind}'.",
            target={
                "pluginId": plugin.plugin_id,
                "kind": collection.kind,
                "idPrefix": id_prefix,
            },
            suggestion="Use an ID prefix declared by the plugin collection.",
        )

    max_sequence = 0
    pattern = re.compile(rf"^{re.escape(id_prefix)}-(\d+)$")
    source_root = collection_root(
        project_root=project_root,
        plugin=plugin,
        collection=collection,
    )
    for path in source_root.glob(f"{id_prefix}-*.yaml"):
        match = pattern.fullmatch(path.stem)
        if match is not None:
            max_sequence = max(max_sequence, int(match.group(1)))

    for path in tombstones_root(project_root).glob(f"{id_prefix}-*"):
        match = pattern.fullmatch(path.name)
        if match is not None:
            max_sequence = max(max_sequence, int(match.group(1)))

    next_sequence = max_sequence + 1
    width = max(3, len(str(next_sequence)))
    return f"{id_prefix}-{next_sequence:0{width}d}"


def write_tombstone(
    *,
    project_root: Path,
    resource_id: str,
    resource_kind: str,
) -> Path:
    path = tombstone_path(project_root, resource_id)
    deleted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    document = {
        "apiVersion": API_VERSION,
        "kind": "IdTombstone",
        "metadata": {"id": resource_id},
        "spec": {
            "deletedAt": deleted_at,
            "resourceKind": resource_kind,
        },
    }
    atomic_write_text(
        path,
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
    )
    return path
