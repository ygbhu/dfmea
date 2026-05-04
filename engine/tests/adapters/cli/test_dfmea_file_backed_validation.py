from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.dfmea import app as dfmea_app
from quality_adapters.cli.quality import app as quality_app

runner = CliRunner()


def test_dfmea_validate_clean_project_returns_no_error_issues(tmp_path) -> None:
    _create_valid_project(tmp_path)

    result = runner.invoke(
        dfmea_app,
        [
            "validate",
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
    assert payload["command"] == "dfmea validate"
    assert payload["data"]["summary"]["errors"] == 0
    assert payload["meta"]["schemaVersions"] == {"dfmea": "dfmea.ai/v1"}


def test_dfmea_validate_reports_duplicate_ids_and_missing_references(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)
    fm_path = project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    duplicate_path = project_root / "dfmea" / "failure-modes" / "FM-002.yaml"
    duplicate_path.write_text(fm_path.read_text(encoding="utf-8"), encoding="utf-8")

    fc_path = project_root / "dfmea" / "causes" / "FC-001.yaml"
    fc_doc = _read_yaml(fc_path)
    fc_doc["spec"]["failureModeRef"] = "FM-999"
    fc_path.write_text(yaml.safe_dump(fc_doc, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        dfmea_app,
        [
            "validate",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 3, result.output
    payload = json.loads(result.output)
    codes = [issue["code"] for issue in payload["data"]["issues"]]
    assert "DUPLICATE_ID" in codes
    assert "REFERENCE_NOT_FOUND" in codes
    assert payload["errors"][0]["code"] == "VALIDATION_FAILED"


def test_dfmea_validate_reports_path_mismatch_without_stopping(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)
    bad_path = project_root / "dfmea" / "effects" / "FE-999.yaml"
    bad_path.write_text(
        (project_root / "dfmea" / "effects" / "FE-001.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    fm_path = project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    fm_doc = _read_yaml(fm_path)
    fm_doc["spec"]["causeRefs"] = ["FC-999"]
    fm_path.write_text(yaml.safe_dump(fm_doc, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        dfmea_app,
        [
            "validate",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 3, result.output
    payload = json.loads(result.output)
    issues = payload["data"]["issues"]
    assert any(issue["code"] == "ID_PREFIX_MISMATCH" for issue in issues)
    assert any(issue["code"] == "REFERENCE_NOT_FOUND" for issue in issues)


def test_dfmea_validate_reports_nested_link_id_duplicates(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)
    link_path = project_root / "links" / "LINKS-001.yaml"
    link_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "quality.ai/v1",
                "kind": "TraceLinkSet",
                "metadata": {"id": "LINKS-001"},
                "spec": {
                    "links": [
                        {"id": "LINK-001", "from": {"id": "CHAR-001"}, "to": {"id": "FM-001"}},
                        {"id": "LINK-001", "from": {"id": "FC-001"}, "to": {"id": "FM-001"}},
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        dfmea_app,
        [
            "validate",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ],
    )

    assert result.exit_code == 3, result.output
    payload = json.loads(result.output)
    assert any(
        issue["code"] == "DUPLICATE_ID" and issue.get("field") == "spec.links[1].id"
        for issue in payload["data"]["issues"]
    )


def _create_valid_project(root: Path) -> Path:
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
        ],
        [
            "analysis",
            "add-requirement",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--function",
            "FN-001",
            "--text",
            "Provide commanded airflow",
        ],
        [
            "analysis",
            "add-characteristic",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--function",
            "FN-001",
            "--text",
            "Motor current",
            "--value",
            "10",
            "--unit",
            "A",
        ],
        [
            "analysis",
            "add-failure-chain",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--function",
            "FN-001",
            "--requirement",
            "REQ-001",
            "--characteristic",
            "CHAR-001",
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
            "completed",
            "--target-causes",
            "1",
        ],
    ):
        result = runner.invoke(dfmea_app, args)
        assert result.exit_code == 0, result.output
    return root / "projects" / "cooling-fan-controller"


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
