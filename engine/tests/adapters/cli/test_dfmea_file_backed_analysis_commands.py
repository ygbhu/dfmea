from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.dfmea import app as dfmea_app
from quality_adapters.cli.quality import app as quality_app
from quality_methods.dfmea.analysis_service import compute_ap

runner = CliRunner()


def test_dfmea_analysis_add_function_creates_yaml_resource(tmp_path) -> None:
    project_root = _create_initialized_project_with_component(tmp_path)

    payload = _invoke_dfmea_json(
        [
            "analysis",
            "add-function",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--component",
            "COMP-001",
            "--title",
            "Drive fan motor",
            "--description",
            "Convert controller output to motor torque",
        ]
    )

    assert payload["command"] == "dfmea analysis add-function"
    assert payload["data"]["resource"]["id"] == "FN-001"
    function_path = project_root / "dfmea" / "functions" / "FN-001.yaml"
    function_doc = yaml.safe_load(function_path.read_text(encoding="utf-8"))
    assert function_doc["kind"] == "Function"
    assert function_doc["metadata"]["id"] == "FN-001"
    assert function_doc["metadata"]["title"] == "Drive fan motor"
    assert function_doc["spec"]["componentRef"] == "COMP-001"


def test_dfmea_analysis_failure_chain_and_action_status(tmp_path) -> None:
    project_root = _create_initialized_project_with_function(tmp_path)

    chain = _invoke_dfmea_json(
        [
            "analysis",
            "add-failure-chain",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--function",
            "FN-001",
            "--fm-description",
            "Motor stalls",
            "--severity",
            "8",
            "--fe-description",
            "Airflow lost",
            "--fe-level",
            "vehicle",
            "--fc-description",
            "Bearing seizure",
            "--occurrence",
            "4",
            "--detection",
            "5",
            "--act-description",
            "Add current spike detection",
            "--kind",
            "detection",
            "--status",
            "planned",
            "--target-causes",
            "1",
        ]
    )

    assert chain["data"]["resource"]["id"] == "FM-001"
    affected = {(item["kind"], item["id"]) for item in chain["data"]["affectedObjects"]}
    assert affected == {
        ("FailureMode", "FM-001"),
        ("FailureEffect", "FE-001"),
        ("FailureCause", "FC-001"),
        ("Action", "ACT-001"),
    }

    fm_doc = _read_yaml(project_root / "dfmea" / "failure-modes" / "FM-001.yaml")
    fe_doc = _read_yaml(project_root / "dfmea" / "effects" / "FE-001.yaml")
    fc_doc = _read_yaml(project_root / "dfmea" / "causes" / "FC-001.yaml")
    act_doc = _read_yaml(project_root / "dfmea" / "actions" / "ACT-001.yaml")
    assert fm_doc["spec"]["functionRef"] == "FN-001"
    assert fm_doc["spec"]["effectRefs"] == ["FE-001"]
    assert fm_doc["spec"]["causeRefs"] == ["FC-001"]
    assert fm_doc["spec"]["actionRefs"] == ["ACT-001"]
    assert fe_doc["spec"]["failureModeRef"] == "FM-001"
    assert fc_doc["spec"]["failureModeRef"] == "FM-001"
    assert fc_doc["spec"]["ap"] == "High"
    assert act_doc["spec"]["targetCauseRefs"] == ["FC-001"]

    status = _invoke_dfmea_json(
        [
            "analysis",
            "update-action-status",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--action",
            "ACT-001",
            "--status",
            "in-progress",
        ]
    )
    assert status["data"]["resource"]["id"] == "ACT-001"
    act_doc = _read_yaml(project_root / "dfmea" / "actions" / "ACT-001.yaml")
    assert act_doc["spec"]["status"] == "in-progress"


def test_dfmea_analysis_update_fc_recomputes_ap(tmp_path) -> None:
    project_root = _create_project_with_failure_chain(tmp_path)

    _invoke_dfmea_json(
        [
            "analysis",
            "update-fc",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--failure-cause",
            "FC-001",
            "--occurrence",
            "1",
            "--detection",
            "1",
        ]
    )

    fc_doc = _read_yaml(project_root / "dfmea" / "causes" / "FC-001.yaml")
    assert fc_doc["spec"]["occurrence"] == 1
    assert fc_doc["spec"]["detection"] == 1
    assert fc_doc["spec"]["ap"] == "Medium"
    assert compute_ap(10, 1, 1) == "High"
    assert compute_ap(3, 10, 10) == "Low"
    assert compute_ap(5, 3, 3) == "Medium"


def test_quality_project_renumber_updates_dfmea_references(tmp_path) -> None:
    project_root = _create_project_with_failure_chain(tmp_path)

    result = runner.invoke(
        quality_app,
        [
            "project",
            "id",
            "renumber",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--from",
            "FM-001",
            "--to",
            "FM-002",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["data"]["renumber"]["fromId"] == "FM-001"
    assert payload["data"]["renumber"]["toId"] == "FM-002"
    assert not (project_root / "dfmea" / "failure-modes" / "FM-001.yaml").exists()
    assert (project_root / "dfmea" / "failure-modes" / "FM-002.yaml").exists()

    fm_doc = _read_yaml(project_root / "dfmea" / "failure-modes" / "FM-002.yaml")
    fe_doc = _read_yaml(project_root / "dfmea" / "effects" / "FE-001.yaml")
    fc_doc = _read_yaml(project_root / "dfmea" / "causes" / "FC-001.yaml")
    act_doc = _read_yaml(project_root / "dfmea" / "actions" / "ACT-001.yaml")
    assert fm_doc["metadata"]["id"] == "FM-002"
    assert fe_doc["spec"]["failureModeRef"] == "FM-002"
    assert fc_doc["spec"]["failureModeRef"] == "FM-002"
    assert act_doc["spec"]["failureModeRef"] == "FM-002"
    changed_refs = payload["data"]["renumber"]["changedReferences"]
    assert {item["fieldPath"] for item in changed_refs} >= {
        "spec.failureModeRef",
    }


def test_quality_project_repair_id_conflicts_repairs_path_metadata_mismatch(tmp_path) -> None:
    project_root = _create_project_with_failure_chain(tmp_path)
    original = project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    duplicate = project_root / "dfmea" / "failure-modes" / "FM-002.yaml"
    duplicate.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(
        quality_app,
        [
            "project",
            "repair",
            "id-conflicts",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["renumbers"][0]["fromId"] == "FM-001"
    assert payload["data"]["renumbers"][0]["toId"] == "FM-002"
    repaired = _read_yaml(duplicate)
    assert repaired["metadata"]["id"] == "FM-002"


def _create_initialized_project_with_function(root: Path) -> Path:
    project_root = _create_initialized_project_with_component(root)
    _invoke_dfmea_json(
        [
            "analysis",
            "add-function",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--component",
            "COMP-001",
            "--title",
            "Drive fan motor",
        ]
    )
    return project_root


def _create_project_with_failure_chain(root: Path) -> Path:
    project_root = _create_initialized_project_with_function(root)
    _invoke_dfmea_json(
        [
            "analysis",
            "add-failure-chain",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--function",
            "FN-001",
            "--fm-description",
            "Motor stalls",
            "--severity",
            "8",
            "--fe-description",
            "Airflow lost",
            "--fc-description",
            "Bearing seizure",
            "--occurrence",
            "4",
            "--detection",
            "5",
            "--act-description",
            "Add current spike detection",
            "--status",
            "planned",
            "--target-causes",
            "1",
        ]
    )
    return project_root


def _create_initialized_project_with_component(root: Path) -> Path:
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

    for args in (
        [
            "structure",
            "add-system",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Fan Controller",
        ],
        [
            "structure",
            "add-subsystem",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-001",
            "--title",
            "Motor Control",
        ],
        [
            "structure",
            "add-component",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SUB-001",
            "--title",
            "Motor Driver",
        ],
    ):
        _invoke_dfmea_json(args)
    return root / "projects" / "cooling-fan-controller"


def _invoke_dfmea_json(args: list[str]) -> dict:
    result = runner.invoke(dfmea_app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    return payload


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
