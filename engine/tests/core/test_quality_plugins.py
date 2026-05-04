from __future__ import annotations

import importlib
import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.quality import app

runner = CliRunner()


def test_plugin_list_shows_builtin_plugins() -> None:
    result = runner.invoke(app, ["plugin", "list"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    plugins = {plugin["id"]: plugin for plugin in payload["data"]["plugins"]}
    assert plugins["dfmea"] == {
        "id": "dfmea",
        "version": "dfmea.ai/v1",
        "domain": "dfmea",
        "builtin": True,
        "enabled": False,
        "schemaSnapshotVersion": None,
        "schemaSnapshotPath": None,
    }
    assert set(plugins) == {"dfmea"}


def test_method_list_reports_active_dfmea_and_planned_pfmea(tmp_path) -> None:
    _create_workspace_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "method",
            "list",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "quality method list"
    methods = {method["id"]: method for method in payload["data"]["methods"]}
    assert methods["dfmea"]["status"] == "active"
    assert methods["dfmea"]["implemented"] is True
    assert methods["dfmea"]["commandNamespace"] == "dfmea"
    assert methods["dfmea"]["enabled"] is False
    assert methods["pfmea"]["status"] == "planned"
    assert methods["pfmea"]["implemented"] is False
    assert methods["pfmea"]["commandNamespace"] is None


def test_plugin_enable_writes_schema_snapshot_and_project_domain(tmp_path) -> None:
    _create_workspace_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    assert payload["meta"]["projectSlug"] == "cooling-fan-controller"
    assert payload["meta"]["schemaVersions"] == {"dfmea": "dfmea.ai/v1"}

    project_root = tmp_path / "projects" / "cooling-fan-controller"
    snapshot_root = project_root / ".quality" / "schemas" / "dfmea"
    assert (snapshot_root / "plugin.yaml").exists()
    assert (snapshot_root / "failure-mode.schema.json").exists()
    assert (project_root / "dfmea").is_dir()

    project_doc = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))
    assert project_doc["spec"]["domains"]["dfmea"] == {
        "enabled": True,
        "root": "./dfmea",
    }


def test_plugin_list_with_project_reports_enabled_snapshot(tmp_path) -> None:
    _create_workspace_project(tmp_path)
    enable_result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert enable_result.exit_code == 0, enable_result.output

    result = runner.invoke(
        app,
        [
            "plugin",
            "list",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    plugins = {plugin["id"]: plugin for plugin in payload["data"]["plugins"]}
    plugin = plugins["dfmea"]
    assert plugin["id"] == "dfmea"
    assert plugin["enabled"] is True
    assert plugin["schemaSnapshotVersion"] == "dfmea.ai/v1"
    assert plugin["schemaSnapshotPath"].endswith(
        "projects\\cooling-fan-controller\\.quality\\schemas\\dfmea"
    ) or plugin["schemaSnapshotPath"].endswith(
        "projects/cooling-fan-controller/.quality/schemas/dfmea"
    )


def test_method_list_reports_project_enabled_state(tmp_path) -> None:
    _create_workspace_project(tmp_path)
    enable_result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert enable_result.exit_code == 0, enable_result.output

    result = runner.invoke(
        app,
        [
            "method",
            "list",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    methods = {method["id"]: method for method in payload["data"]["methods"]}
    assert methods["dfmea"]["enabled"] is True
    assert methods["pfmea"]["enabled"] is False


def test_plugin_disable_disables_empty_domain_without_deleting_snapshot(tmp_path) -> None:
    _create_workspace_project(tmp_path)
    enable_result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert enable_result.exit_code == 0, enable_result.output

    result = runner.invoke(
        app,
        [
            "plugin",
            "disable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["plugin"]["enabled"] is False

    project_root = tmp_path / "projects" / "cooling-fan-controller"
    assert (project_root / ".quality" / "schemas" / "dfmea" / "plugin.yaml").exists()
    project_doc = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))
    assert project_doc["spec"]["domains"]["dfmea"]["enabled"] is False


def test_plugin_disable_fails_when_not_enabled(tmp_path) -> None:
    _create_workspace_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "plugin",
            "disable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "PLUGIN_NOT_ENABLED"


def test_plugin_enable_unknown_plugin_fails(tmp_path) -> None:
    _create_workspace_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "unknown",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "PLUGIN_NOT_FOUND"


def test_pfmea_is_placeholder_not_builtin(tmp_path) -> None:
    _create_workspace_project(tmp_path)

    module = importlib.import_module("quality_methods.pfmea")
    assert "placeholder" in (module.__doc__ or "").lower()

    result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "pfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "PLUGIN_NOT_FOUND"


def test_project_plugin_list_fails_on_schema_snapshot_version_mismatch(tmp_path) -> None:
    _create_workspace_project(tmp_path)
    enable_result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "dfmea",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert enable_result.exit_code == 0, enable_result.output

    snapshot_descriptor = (
        tmp_path
        / "projects"
        / "cooling-fan-controller"
        / ".quality"
        / "schemas"
        / "dfmea"
        / "plugin.yaml"
    )
    descriptor = yaml.safe_load(snapshot_descriptor.read_text(encoding="utf-8"))
    descriptor["metadata"]["version"] = "dfmea.ai/v0"
    snapshot_descriptor.write_text(
        yaml.safe_dump(descriptor, sort_keys=False),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "plugin",
            "list",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 7, result.output
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "SCHEMA_VERSION_MISMATCH"
    assert payload["errors"][0]["target"]["snapshotVersion"] == "dfmea.ai/v0"


def _create_workspace_project(root: Path) -> None:
    workspace_result = runner.invoke(app, ["workspace", "init", "--workspace", str(root)])
    assert workspace_result.exit_code == 0, workspace_result.output
    project_result = runner.invoke(
        app,
        [
            "project",
            "create",
            "cooling-fan-controller",
            "--workspace",
            str(root),
        ],
    )
    assert project_result.exit_code == 0, project_result.output
