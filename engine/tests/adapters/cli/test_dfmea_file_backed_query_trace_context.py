from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.dfmea import app as dfmea_app
from quality_adapters.cli.quality import app as quality_app

runner = CliRunner()


def test_dfmea_query_reads_file_backed_resources(tmp_path) -> None:
    project_root = _create_valid_project(tmp_path)

    get_payload = _invoke_dfmea_json(
        [
            "query",
            "get",
            "FM-001",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )
    assert get_payload["command"] == "dfmea query get"
    assert get_payload["data"]["resource"]["id"] == "FM-001"
    assert get_payload["data"]["resource"]["kind"] == "FailureMode"
    assert get_payload["data"]["resource"]["path"] == str(
        project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    )
    assert get_payload["meta"]["freshness"]["mode"] == "source-scan"

    list_payload = _invoke_dfmea_json(
        [
            "query",
            "list",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--type",
            "FM",
            "--parent",
            "FN-001",
        ]
    )
    assert list_payload["data"]["count"] == 1
    assert list_payload["data"]["resources"][0]["summary"] == "S8: Motor stalls"

    search_payload = _invoke_dfmea_json(
        [
            "query",
            "search",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--keyword",
            "current spike",
        ]
    )
    assert [item["id"] for item in search_payload["data"]["resources"]] == ["ACT-001"]


def test_dfmea_query_summary_map_risk_and_actions(tmp_path) -> None:
    _create_valid_project(tmp_path)

    summary = _invoke_dfmea_json(
        [
            "query",
            "summary",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--comp",
            "COMP-001",
        ]
    )
    assert summary["data"]["counts"]["functions"] == 1
    assert summary["data"]["counts"]["failureModes"] == 1
    assert summary["data"]["counts"]["actions"] == 1

    project_map = _invoke_dfmea_json(
        [
            "query",
            "map",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )
    assert project_map["data"]["counts"]["structureNodes"] == 3
    assert project_map["data"]["counts"]["failureModes"] == 1

    by_ap = _invoke_dfmea_json(
        [
            "query",
            "by-ap",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--ap",
            "High",
        ]
    )
    assert by_ap["data"]["resources"][0]["id"] == "FC-001"

    by_severity = _invoke_dfmea_json(
        [
            "query",
            "by-severity",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--gte",
            "7",
        ]
    )
    assert by_severity["data"]["resources"][0]["id"] == "FM-001"

    actions = _invoke_dfmea_json(
        [
            "query",
            "actions",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--status",
            "completed",
        ]
    )
    assert actions["data"]["resources"][0]["id"] == "ACT-001"


def test_dfmea_trace_and_context_use_file_graph(tmp_path) -> None:
    project_root = _create_project_with_trace_link(tmp_path)

    causes = _invoke_dfmea_json(
        [
            "trace",
            "causes",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--fm",
            "FM-001",
        ]
    )
    assert causes["command"] == "dfmea trace causes"
    assert [item["failureMode"]["id"] for item in causes["data"]["chain"]] == [
        "FM-001",
        "FM-002",
    ]
    assert causes["data"]["chain"][1]["via"]["id"] == "FC-001"

    effects = _invoke_dfmea_json(
        [
            "trace",
            "effects",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--fm",
            "FM-001",
        ]
    )
    assert [item["failureMode"]["id"] for item in effects["data"]["chain"]] == [
        "FM-001",
        "FM-002",
    ]
    assert effects["data"]["chain"][1]["via"]["id"] == "FE-001"

    context = _invoke_dfmea_json(
        [
            "context",
            "failure-chain",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--failure-mode",
            "FM-001",
        ]
    )
    assert context["command"] == "dfmea context failure-chain"
    assert context["data"]["root"]["id"] == "FM-001"
    related_ids = {item["id"] for item in context["data"]["relatedResources"]}
    assert {"FN-001", "FE-001", "FC-001", "ACT-001"} <= related_ids
    assert context["data"]["links"][0]["id"] == "LINK-001"
    assert str(project_root / "dfmea" / "failure-modes" / "FM-001.yaml") in context["data"]["paths"]
    assert context["data"]["freshness"]["mode"] == "source-scan"


def _create_project_with_trace_link(root: Path) -> Path:
    project_root = _create_valid_project(root)
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
            "Motor overheats",
            "--severity",
            "7",
            "--fe-description",
            "Thermal shutdown",
            "--fc-description",
            "Blocked airflow",
            "--occurrence",
            "3",
            "--detection",
            "4",
        ]
    )
    link_path = project_root / "links" / "LINKS-001.yaml"
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "quality.ai/v1",
                "kind": "TraceLinkSet",
                "metadata": {"id": "LINKS-001"},
                "spec": {
                    "links": [
                        {
                            "id": "LINK-001",
                            "from": {"domain": "dfmea", "kind": "FailureCause", "id": "FC-001"},
                            "to": {"domain": "dfmea", "kind": "FailureMode", "id": "FM-002"},
                            "relationship": "causes",
                        },
                        {
                            "id": "LINK-002",
                            "from": {
                                "domain": "dfmea",
                                "kind": "FailureEffect",
                                "id": "FE-001",
                            },
                            "to": {"domain": "dfmea", "kind": "FailureMode", "id": "FM-002"},
                            "relationship": "effects",
                        },
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return project_root


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
        _invoke_dfmea_json(args)
    return root / "projects" / "cooling-fan-controller"


def _invoke_dfmea_json(args: list[str]) -> dict:
    result = runner.invoke(dfmea_app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    return payload
