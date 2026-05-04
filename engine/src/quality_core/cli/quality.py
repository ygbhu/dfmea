"""Compatibility module for the quality CLI adapter.

New entrypoints should import from ``quality_adapters.cli.quality``.
"""

from quality_adapters.cli.quality import app, main

__all__ = ["app", "main"]
