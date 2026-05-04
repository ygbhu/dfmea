from __future__ import annotations

import json

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.quality import app
from quality_core.cli.output import CONTRACT_VERSION
from quality_core.workspace.config import load_workspace_config, load_workspace_plugins
from quality_core.workspace.project import load_project_config
from quality_methods.dfmea import PLUGIN_ID

runner = CliRunner()


def test_quality_packages_import_cleanly() -> None:
    assert CONTRACT_VERSION == "quality.ai/v1"
    assert PLUGIN_ID == "dfmea"


def test_workspace_init_creates_workspace_configs(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["workspace", "init", "--workspace", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    assert payload["command"] == "quality workspace init"
    assert payload["meta"]["workspaceRoot"] == str(tmp_path)

    workspace_path = tmp_path / ".quality" / "workspace.yaml"
    plugins_path = tmp_path / ".quality" / "plugins.yaml"
    assert workspace_path.exists()
    assert plugins_path.exists()

    workspace_doc = yaml.safe_load(workspace_path.read_text(encoding="utf-8"))
    assert workspace_doc["apiVersion"] == "quality.ai/v1"
    assert workspace_doc["kind"] == "QualityWorkspace"
    assert workspace_doc["spec"]["projectsRoot"] == "projects"

    plugins_doc = yaml.safe_load(plugins_path.read_text(encoding="utf-8"))
    assert plugins_doc["kind"] == "WorkspacePlugins"
    assert plugins_doc["spec"]["builtins"] == ["dfmea"]
    assert plugins_doc["spec"]["enabledByDefault"] == ["dfmea"]

    workspace_config = load_workspace_config(tmp_path)
    plugins_config = load_workspace_plugins(tmp_path)
    assert workspace_config.projects_root == "projects"
    assert plugins_config.builtins == ("dfmea",)


def test_project_create_creates_project_config_and_quality_dirs(tmp_path) -> None:
    init_result = runner.invoke(app, ["workspace", "init", "--workspace", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    result = runner.invoke(
        app,
        [
            "project",
            "create",
            "cooling-fan-controller",
            "--workspace",
            str(tmp_path),
            "--name",
            "Cooling Fan Controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    assert payload["meta"]["projectSlug"] == "cooling-fan-controller"

    project_root = tmp_path / "projects" / "cooling-fan-controller"
    assert payload["meta"]["projectRoot"] == str(project_root)
    assert (project_root / ".quality" / "schemas").is_dir()
    assert (project_root / ".quality" / "tombstones").is_dir()
    assert (project_root / ".quality" / "locks").is_dir()
    assert (project_root / "project.yaml").exists()

    project_doc = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))
    assert project_doc["apiVersion"] == "quality.ai/v1"
    assert project_doc["kind"] == "QualityProject"
    assert project_doc["metadata"]["id"] == "PRJ"
    assert project_doc["metadata"]["slug"] == "cooling-fan-controller"
    assert project_doc["metadata"]["name"] == "Cooling Fan Controller"

    project_config = load_project_config(project_root)
    assert project_config.slug == "cooling-fan-controller"
    assert project_config.name == "Cooling Fan Controller"


def test_project_create_discovers_workspace_from_current_directory(
    tmp_path,
    monkeypatch,
) -> None:
    init_result = runner.invoke(app, ["workspace", "init", "--workspace", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    nested = tmp_path / "nested" / "work"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    result = runner.invoke(app, ["project", "create", "brake-controller"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["meta"]["workspaceRoot"] == str(tmp_path)
    assert payload["meta"]["projectSlug"] == "brake-controller"
    assert (tmp_path / "projects" / "brake-controller" / "project.yaml").exists()
