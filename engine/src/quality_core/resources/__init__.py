"""File-backed resource foundation package."""

from quality_core.resources.envelope import Resource, make_resource
from quality_core.resources.store import ResourceStore, WriteResult

__all__ = ["Resource", "ResourceStore", "WriteResult", "make_resource"]
