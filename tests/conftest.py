from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from typer.testing import CliRunner

from dfmea_cli.cli import app


@dataclass(slots=True)
class AppRunner:
    runner: CliRunner

    def invoke(self, args: Sequence[str]):
        return self.runner.invoke(app, list(args))


@pytest.fixture
def cli_runner() -> AppRunner:
    return AppRunner(runner=CliRunner())
