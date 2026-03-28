from __future__ import annotations

from pathlib import Path

from helpers_realistic_dfmea import (
    parse_json_payload,
    rebuild_projection,
    seed_realistic_cooling_fan_project,
)


def test_realistic_query_map_bundle_and_dossier_are_traceable(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    rebuild_projection(cli_runner, seeded.db_path)

    map_result = cli_runner.invoke(
        ["query", "map", "--db", str(seeded.db_path), "--format", "json"]
    )
    map_payload = parse_json_payload(map_result)
    assert map_result.exit_code == 0, map_result.stdout
    assert map_payload["data"]["counts"] == {
        "systems": 1,
        "subsystems": 1,
        "components": 3,
        "functions": 5,
        "failure_modes": 5,
        "open_actions": 5,
    }

    bundle_result = cli_runner.invoke(
        [
            "query",
            "bundle",
            "--db",
            str(seeded.db_path),
            "--comp",
            seeded.controller_comp_id,
            "--format",
            "json",
        ]
    )
    bundle_payload = parse_json_payload(bundle_result)
    assert bundle_result.exit_code == 0, bundle_result.stdout
    assert bundle_payload["data"]["component"]["id"] == seeded.controller_comp_id
    assert bundle_payload["data"]["counts"]["failure_modes"] == 3

    dossier_result = cli_runner.invoke(
        [
            "query",
            "dossier",
            "--db",
            str(seeded.db_path),
            "--fn",
            seeded.controller_start_fn_id,
            "--format",
            "json",
        ]
    )
    dossier_payload = parse_json_payload(dossier_result)
    assert dossier_result.exit_code == 0, dossier_result.stdout
    assert dossier_payload["data"]["function"]["id"] == seeded.controller_start_fn_id
    assert len(dossier_payload["data"]["requirements"]) == 1
    assert len(dossier_payload["data"]["characteristics"]) == 1
    assert [card["fm"]["id"] for card in dossier_payload["data"]["failure_modes"]] == [
        "FM-001"
    ]


def test_realistic_query_by_ap_and_severity_match_realistic_risk_matrix(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    rebuild_projection(cli_runner, seeded.db_path)

    by_ap_result = cli_runner.invoke(
        [
            "query",
            "by-ap",
            "--db",
            str(seeded.db_path),
            "--ap",
            "High",
            "--format",
            "json",
        ]
    )
    by_ap_payload = parse_json_payload(by_ap_result)
    assert by_ap_result.exit_code == 0, by_ap_result.stdout
    assert by_ap_payload["data"]["count"] == 5
    assert {node["rowid"] for node in by_ap_payload["data"]["nodes"]} == {
        seeded.fc_temp_signal_frozen_rowid,
        seeded.fc_driver_output_stuck_rowid,
        seeded.fc_overtemperature_threshold_high_rowid,
        seeded.fc_motor_bearing_drag_rowid,
        seeded.fc_sensor_pullup_open_circuit_rowid,
    }

    by_severity_result = cli_runner.invoke(
        [
            "query",
            "by-severity",
            "--db",
            str(seeded.db_path),
            "--gte",
            "7",
            "--format",
            "json",
        ]
    )
    by_severity_payload = parse_json_payload(by_severity_result)
    assert by_severity_result.exit_code == 0, by_severity_result.stdout
    assert by_severity_payload["data"]["count"] == 5
    assert {node["id"] for node in by_severity_payload["data"]["nodes"]} == {
        "FM-001",
        "FM-002",
        "FM-003",
        "FM-004",
        "FM-005",
    }


def test_realistic_query_actions_planned_then_completed(cli_runner, tmp_path: Path):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    rebuild_projection(cli_runner, seeded.db_path)

    planned_result = cli_runner.invoke(
        [
            "query",
            "actions",
            "--db",
            str(seeded.db_path),
            "--status",
            "planned",
            "--format",
            "json",
        ]
    )
    planned_payload = parse_json_payload(planned_result)
    assert planned_result.exit_code == 0, planned_result.stdout
    assert planned_payload["data"]["count"] == 5

    update_result = cli_runner.invoke(
        [
            "analysis",
            "update-action-status",
            "--db",
            str(seeded.db_path),
            "--act",
            seeded.act_speed_id,
            "--status",
            "completed",
            "--format",
            "json",
        ]
    )
    assert update_result.exit_code == 0, update_result.stdout

    status_result = cli_runner.invoke(
        ["projection", "status", "--db", str(seeded.db_path), "--format", "json"]
    )
    status_payload = parse_json_payload(status_result)
    assert status_result.exit_code == 0, status_result.stdout
    assert status_payload["data"]["projection_dirty"] is True

    rebuild_projection(cli_runner, seeded.db_path)

    completed_result = cli_runner.invoke(
        [
            "query",
            "actions",
            "--db",
            str(seeded.db_path),
            "--status",
            "completed",
            "--format",
            "json",
        ]
    )
    completed_payload = parse_json_payload(completed_result)
    assert completed_result.exit_code == 0, completed_result.stdout
    assert completed_payload["data"]["count"] == 1
    assert [node["id"] for node in completed_payload["data"]["nodes"]] == [
        seeded.act_speed_id
    ]


def test_realistic_validate_warns_when_projection_is_stale_after_write(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    rebuild_projection(cli_runner, seeded.db_path)

    update_result = cli_runner.invoke(
        [
            "analysis",
            "update-action-status",
            "--db",
            str(seeded.db_path),
            "--act",
            seeded.act_speed_id,
            "--status",
            "in-progress",
            "--format",
            "json",
        ]
    )
    assert update_result.exit_code == 0, update_result.stdout

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(seeded.db_path), "--format", "json"]
    )
    validate_payload = parse_json_payload(validate_result)
    assert validate_result.exit_code == 0, validate_result.stdout
    assert validate_payload["ok"] is True
    assert any(
        issue["scope"] == "projection" and issue["kind"] == "STALE_PROJECTION"
        for issue in validate_payload["data"]["issues"]
    )


def test_realistic_review_export_contains_controller_navigation_links(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    rebuild_projection(cli_runner, seeded.db_path)
    out_dir = tmp_path / "review-export"

    export_result = cli_runner.invoke(
        [
            "export",
            "markdown",
            "--db",
            str(seeded.db_path),
            "--out",
            str(out_dir),
            "--layout",
            "review",
            "--format",
            "json",
        ]
    )
    export_payload = parse_json_payload(export_result)
    assert export_result.exit_code == 0, export_result.stdout

    exported_paths = [Path(item["path"]) for item in export_payload["data"]["files"]]
    assert any(
        path.parent.name == "actions" and path.name == "open.md"
        for path in exported_paths
    )

    project_root = out_dir / seeded.project_id
    index_path = project_root / "index.md"
    component_path = project_root / "components" / f"{seeded.controller_comp_id}.md"
    actions_path = project_root / "actions" / "open.md"
    assert actions_path.exists()
    index_content = index_path.read_text(encoding="utf-8")
    component_content = component_path.read_text(encoding="utf-8")

    assert (
        f"[`{seeded.controller_comp_id}`](components/{seeded.controller_comp_id}.md)"
        in index_content
    )
    assert (
        f"[`{seeded.controller_start_fn_id}`](../functions/{seeded.controller_start_fn_id}.md)"
        in component_content
    )


def test_realistic_same_component_trace_target_is_rejected(cli_runner, tmp_path: Path):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(seeded.db_path),
            "--from",
            f"fe:{seeded.fe_airflow_not_established_rowid}",
            "--to-fm",
            seeded.fm_low_speed_id,
            "--format",
            "json",
        ]
    )

    payload = parse_json_payload(result)
    assert result.exit_code != 0
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "from": f"fe:{seeded.fe_airflow_not_established_rowid}",
        "to_fm": seeded.fm_low_speed_id,
        "source_component": seeded.controller_comp_id,
        "target_component": seeded.controller_comp_id,
    }
    assert "different component" in payload["errors"][0]["message"].lower()
