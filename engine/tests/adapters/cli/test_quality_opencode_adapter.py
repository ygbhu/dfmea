from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from quality_adapters.cli.quality import app
from quality_adapters.opencode.installer import template_files

runner = CliRunner()


def test_opencode_init_installs_project_pack(tmp_path) -> None:
    result = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    assert payload["command"] == "quality opencode init"
    assert payload["meta"]["adapter"] == "opencode"
    assert payload["meta"]["strategy"] == "opencode-first-adapter"

    root = tmp_path / ".opencode"
    assert (root / "commands" / "quality-status.md").exists()
    assert (root / "skills" / "quality-core" / "SKILL.md").exists()
    assert (root / "skills" / "dfmea" / "SKILL.md").exists()
    assert not (tmp_path / "opencode.json").exists()
    plugin_path = root / "plugins" / "quality-assistant.js"
    assert plugin_path.exists()
    assert "OpenCode-bound quality assistant" in plugin_path.read_text(encoding="utf-8")
    assert "<using-quality-assistant>" in plugin_path.read_text(encoding="utf-8")
    assert "Method discovery:" in plugin_path.read_text(encoding="utf-8")
    assert payload["data"]["opencodeConfig"] is None
    assert payload["data"]["mode"] == {"localPlugin": True, "npmPlugin": False}

    assert set(payload["data"]["commands"]) == {
        "dfmea-smoke",
        "quality-bootstrap",
        "quality-check",
        "quality-status",
    }
    assert set(payload["data"]["skills"]) == {"dfmea", "quality-core"}
    assert payload["data"]["plugins"] == ["quality-assistant.js"]


def test_opencode_init_is_idempotent_for_unchanged_files(tmp_path) -> None:
    first = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path)])
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path)])

    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["data"]["writtenPaths"] == []
    assert len(payload["data"]["skippedPaths"]) == len(template_files())


def test_opencode_init_reports_conflict_and_force_overwrites(tmp_path) -> None:
    root = tmp_path / ".opencode"
    command_path = root / "commands" / "quality-status.md"
    command_path.parent.mkdir(parents=True)
    command_path.write_text("custom local command", encoding="utf-8")

    conflict = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path)])

    assert conflict.exit_code == 4, conflict.output
    payload = json.loads(conflict.output)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "OPENCODE_ADAPTER_CONFLICT"
    assert payload["errors"][0]["path"] == str(command_path)

    forced = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path), "--force"])

    assert forced.exit_code == 0, forced.output
    assert "Inspect local quality project state" in command_path.read_text(encoding="utf-8")
    assert "quality method list" in command_path.read_text(encoding="utf-8")


def test_opencode_init_merges_existing_opencode_config(tmp_path) -> None:
    config_path = tmp_path / "opencode.json"
    config_path.write_text(
        json.dumps({"plugin": ["existing-plugin"], "model": "test/model"}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path), "--npm-plugin"])

    assert result.exit_code == 0, result.output
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config == {
        "plugin": ["existing-plugin", "opencode-quality-assistant"],
        "model": "test/model",
    }


def test_opencode_init_npm_mode_writes_opencode_config(tmp_path) -> None:
    result = runner.invoke(app, ["opencode", "init", "--workspace", str(tmp_path), "--npm-plugin"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    config_path = tmp_path / "opencode.json"
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "plugin": ["opencode-quality-assistant"]
    }
    assert payload["data"]["opencodeConfig"] == {
        "path": str(config_path),
        "written": True,
        "plugin": "opencode-quality-assistant",
    }
    assert payload["data"]["mode"] == {"localPlugin": True, "npmPlugin": True}


def test_template_files_do_not_include_python_package_markers() -> None:
    paths = set(template_files())

    assert "__init__.py" not in paths
    assert all("__pycache__" not in Path(path).parts for path in paths)
    assert "plugins/quality-assistant.js" in paths
