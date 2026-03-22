from __future__ import annotations

import typer

from dfmea_cli.commands.analysis import analysis_app
from dfmea_cli.commands.export_markdown import export_app
from dfmea_cli.commands.init import init_command
from dfmea_cli.commands.query import query_app
from dfmea_cli.commands.structure import structure_app
from dfmea_cli.commands.trace import trace_app
from dfmea_cli.commands.validate import validate_command


app = typer.Typer(no_args_is_help=True, help="DFMEA command line interface.")


@app.callback()
def root() -> None:
    """DFMEA command line interface."""


app.command("init")(init_command)


app.command("validate")(validate_command)


app.add_typer(structure_app, name="structure")
app.add_typer(analysis_app, name="analysis")
app.add_typer(query_app, name="query")
app.add_typer(trace_app, name="trace")
app.add_typer(export_app, name="export")


def main() -> None:
    app()
