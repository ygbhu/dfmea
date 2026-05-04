from __future__ import annotations

from dataclasses import dataclass
from importlib.resources.abc import Traversable


@dataclass(frozen=True, slots=True)
class PluginSingleton:
    kind: str
    resource_id: str
    file: str
    schema: str


@dataclass(frozen=True, slots=True)
class PluginCollection:
    kind: str
    directory: str
    file_name: str
    id_prefix: str
    schema: str
    title_field: str


@dataclass(frozen=True, slots=True)
class BuiltinPlugin:
    plugin_id: str
    version: str
    domain_key: str
    domain_root: str
    snapshot_root: Traversable
    singletons: tuple[PluginSingleton, ...]
    collections: tuple[PluginCollection, ...]
