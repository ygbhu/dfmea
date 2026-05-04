from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.dfmea import app as dfmea_app
from quality_adapters.cli.quality import app as quality_app

runner = CliRunner()


def test_dfmea_init_creates_analysis_root_and_declared_directories(tmp_path) -> None:
    _create_workspace_project(tmp_path)

    result = runner.invoke(
        dfmea_app,
        [
            "init",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["command"] == "dfmea init"
    assert payload["meta"]["projectSlug"] == "cooling-fan-controller"
    assert payload["meta"]["schemaVersions"] == {"dfmea": "dfmea.ai/v1"}

    project_root = tmp_path / "projects" / "cooling-fan-controller"
    analysis_path = project_root / "dfmea" / "dfmea.yaml"
    assert analysis_path.exists()
    analysis = yaml.safe_load(analysis_path.read_text(encoding="utf-8"))
    assert analysis["kind"] == "DfmeaAnalysis"
    assert analysis["metadata"]["id"] == "DFMEA"
    assert analysis["spec"]["projectRef"] == "cooling-fan-controller"

    for directory in (
        "structure",
        "functions",
        "requirements",
        "characteristics",
        "failure-modes",
        "effects",
        "causes",
        "actions",
    ):
        assert (project_root / "dfmea" / directory).is_dir()


def test_dfmea_structure_commands_write_and_update_yaml_resources(tmp_path) -> None:
    project_root = _create_initialized_dfmea_project(tmp_path)

    system = _invoke_json(
        [
            "structure",
            "add-system",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Fan Controller",
        ]
    )
    assert system["data"]["resource"]["id"] == "SYS-001"

    subsystem = _invoke_json(
        [
            "structure",
            "add-subsystem",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-001",
            "--title",
            "Motor Control",
        ]
    )
    assert subsystem["data"]["resource"]["id"] == "SUB-001"
    assert subsystem["data"]["parentId"] == "SYS-001"

    component = _invoke_json(
        [
            "structure",
            "add-component",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SUB-001",
            "--title",
            "Motor Driver",
        ]
    )
    assert component["data"]["resource"]["id"] == "COMP-001"
    component_path = project_root / "dfmea" / "structure" / "COMP-001.yaml"
    component_doc = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    assert component_doc["metadata"]["title"] == "Motor Driver"
    assert component_doc["spec"]["nodeType"] == "component"
    assert component_doc["spec"]["parentRef"] == "SUB-001"

    _invoke_json(
        [
            "structure",
            "update",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--node",
            "COMP-001",
            "--title",
            "Motor Driver Assembly",
            "--description",
            "Controls fan motor current",
            "--metadata",
            '{"owner":"ME"}',
        ]
    )
    updated_doc = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    assert updated_doc["metadata"]["title"] == "Motor Driver Assembly"
    assert updated_doc["metadata"]["owner"] == "ME"
    assert updated_doc["spec"]["description"] == "Controls fan motor current"

    _invoke_json(
        [
            "structure",
            "add-subsystem",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-001",
            "--title",
            "Diagnostics",
        ]
    )
    moved = _invoke_json(
        [
            "structure",
            "move",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--node",
            "COMP-001",
            "--parent",
            "SUB-002",
        ]
    )
    assert moved["data"]["parentId"] == "SUB-002"
    moved_doc = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    assert moved_doc["spec"]["parentRef"] == "SUB-002"


def test_dfmea_structure_delete_creates_tombstone(tmp_path) -> None:
    project_root = _create_initialized_dfmea_project(tmp_path)
    _invoke_json(
        [
            "structure",
            "add-system",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Fan Controller",
        ]
    )

    deleted = _invoke_json(
        [
            "structure",
            "delete",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--node",
            "SYS-001",
        ]
    )

    assert deleted["data"]["resource"]["id"] == "SYS-001"
    assert deleted["data"]["tombstonePath"] == str(
        project_root / ".quality" / "tombstones" / "SYS-001"
    )
    assert not (project_root / "dfmea" / "structure" / "SYS-001.yaml").exists()
    tombstone = yaml.safe_load(
        (project_root / ".quality" / "tombstones" / "SYS-001").read_text(encoding="utf-8")
    )
    assert tombstone["kind"] == "IdTombstone"
    assert tombstone["metadata"]["id"] == "SYS-001"


def test_dfmea_structure_delete_rejects_node_with_children(tmp_path) -> None:
    _create_initialized_dfmea_project(tmp_path)
    _invoke_json(
        [
            "structure",
            "add-system",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Fan Controller",
        ]
    )
    _invoke_json(
        [
            "structure",
            "add-subsystem",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-001",
            "--title",
            "Motor Control",
        ]
    )

    result = runner.invoke(
        dfmea_app,
        [
            "structure",
            "delete",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--node",
            "SYS-001",
        ],
    )

    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "NODE_NOT_EMPTY"


def test_dfmea_structure_missing_parent_returns_expected_error(tmp_path) -> None:
    _create_initialized_dfmea_project(tmp_path)

    result = runner.invoke(
        dfmea_app,
        [
            "structure",
            "add-subsystem",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-999",
            "--title",
            "Missing parent",
        ],
    )

    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["errors"][0]["code"] == "RESOURCE_NOT_FOUND"


def test_dfmea_structure_invalid_parent_type_returns_expected_error(tmp_path) -> None:
    _create_initialized_dfmea_project(tmp_path)
    _invoke_json(
        [
            "structure",
            "add-system",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Fan Controller",
        ]
    )

    result = runner.invoke(
        dfmea_app,
        [
            "structure",
            "add-component",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-001",
            "--title",
            "Wrong parent",
        ],
    )

    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "INVALID_PARENT"


def _create_workspace_project(root: Path) -> None:
    workspace_result = runner.invoke(
        quality_app,
        ["workspace", "init", "--workspace", str(root)],
    )
    assert workspace_result.exit_code == 0, workspace_result.output
    project_result = runner.invoke(
        quality_app,
        [
            "project",
            "create",
            "cooling-fan-controller",
            "--workspace",
            str(root),
        ],
    )
    assert project_result.exit_code == 0, project_result.output


def _create_initialized_dfmea_project(root: Path) -> Path:
    _create_workspace_project(root)
    init_result = runner.invoke(
        dfmea_app,
        [
            "init",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert init_result.exit_code == 0, init_result.output
    return root / "projects" / "cooling-fan-controller"


def _invoke_json(args: list[str]) -> dict:
    result = runner.invoke(dfmea_app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    return payload
