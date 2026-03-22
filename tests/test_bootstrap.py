from typer.testing import CliRunner

from dfmea_cli.cli import app


def test_package_version_is_importable():
    from dfmea_cli import __version__

    assert __version__


def test_root_help_lists_major_command_groups():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for name in [
        "init",
        "structure",
        "analysis",
        "query",
        "trace",
        "validate",
        "export",
    ]:
        assert name in result.stdout


def test_init_command_requires_required_options() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["init"])

    assert result.exit_code != 0
    assert "not implemented yet" not in result.stdout.lower()
    assert "usage:" in result.stdout.lower()
    assert "--db" in result.stdout
