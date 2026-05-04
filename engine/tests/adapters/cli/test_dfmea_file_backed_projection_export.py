from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.dfmea import app as dfmea_app
from quality_adapters.cli.quality import app as quality_app

runner = CliRunner()


def test_dfmea_projection_rebuild_writes_manifest_and_projection_files(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)

    payload = _invoke_dfmea_json(
        [
            "projection",
            "rebuild",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )

    assert payload["command"] == "dfmea projection rebuild"
    manifest_path = project_root / "dfmea" / "projections" / "manifest.json"
    assert manifest_path.exists()
    for relative_path in (
        "tree.json",
        "risk-register.json",
        "action-backlog.json",
        "traceability.json",
    ):
        assert (project_root / "dfmea" / "projections" / relative_path).exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "ProjectionManifest"
    assert manifest["schemaVersions"]["dfmea"] == "dfmea.ai/v1"
    assert manifest["sourceHash"].startswith("sha256:")
    assert "project.yaml" in manifest["sources"]
    assert ".quality/schemas/dfmea/plugin.yaml" in manifest["sources"]
    assert "dfmea/failure-modes/FM-001.yaml" in manifest["sources"]
    assert payload["data"]["freshness"]["status"] == "fresh"


def test_dfmea_projection_status_detects_source_and_schema_changes(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)
    _invoke_dfmea_json(
        [
            "projection",
            "rebuild",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )

    clean_status = _invoke_dfmea_json(
        [
            "projection",
            "status",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )
    assert clean_status["data"]["freshness"]["status"] == "fresh"

    fm_path = project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    fm_doc = yaml.safe_load(fm_path.read_text(encoding="utf-8"))
    fm_doc["spec"]["severity"] = 9
    fm_path.write_text(yaml.safe_dump(fm_doc, sort_keys=False), encoding="utf-8")

    stale_status = _invoke_dfmea_json(
        [
            "projection",
            "status",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )
    assert stale_status["data"]["freshness"]["status"] == "stale"
    assert "sources_changed" in stale_status["data"]["freshness"]["reasons"]

    _invoke_dfmea_json(
        [
            "projection",
            "rebuild",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )
    schema_path = project_root / ".quality" / "schemas" / "dfmea" / "plugin.yaml"
    schema_doc = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    schema_doc["metadata"]["note"] = "changed"
    schema_path.write_text(yaml.safe_dump(schema_doc, sort_keys=False), encoding="utf-8")

    schema_stale = _invoke_dfmea_json(
        [
            "projection",
            "status",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )
    assert schema_stale["data"]["freshness"]["status"] == "stale"


def test_dfmea_exports_include_source_ids_and_paths(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)
    out_dir = tmp_path / "out"

    markdown = _invoke_dfmea_json(
        [
            "export",
            "markdown",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--out",
            str(out_dir),
        ]
    )
    markdown_path = Path(markdown["data"]["files"][0]["path"])
    text = markdown_path.read_text(encoding="utf-8")
    assert "`FM-001`" in text
    assert str(project_root / "dfmea" / "failure-modes" / "FM-001.yaml") in text
    assert markdown["data"]["generatedOutputs"]["exportsManaged"] is False

    csv_payload = _invoke_dfmea_json(
        [
            "export",
            "risk-csv",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--out",
            str(out_dir),
        ]
    )
    csv_path = Path(csv_payload["data"]["files"][0]["path"])
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["failureModeId"] == "FM-001"
    assert rows[0]["failureModePath"] == str(
        project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    )


def test_project_generated_output_config_defaults_are_materialized(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)
    project_doc = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))
    generated = project_doc["spec"]["generatedOutputs"]
    assert generated == {
        "projectionsManaged": False,
        "exportsManaged": False,
        "reportsManaged": False,
        "exportProfiles": [],
    }


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
