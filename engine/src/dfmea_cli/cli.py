"""Compatibility wrapper for the historical ``dfmea_cli`` package."""

from quality_adapters.cli.dfmea import app as app
from quality_adapters.cli.dfmea import main as main

__all__ = ["app", "main"]
