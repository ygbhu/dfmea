from __future__ import annotations

from pathlib import Path

from helpers_realistic_dfmea import (
    parse_json_payload,
    read_fm_links,
    read_node_rowid,
    rebuild_projection,
    seed_realistic_cooling_fan_project,
)


def test_seed_realistic_cooling_fan_project_returns_expected_identity(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)

    assert seeded.project_id == "demo"
    assert seeded.controller_comp_id == "COMP-001"
    assert seeded.motor_comp_id == "COMP-002"
    assert seeded.sensor_comp_id == "COMP-003"

    assert seeded.controller_start_fn_id == "FN-001"
    assert seeded.controller_speed_fn_id == "FN-002"
    assert seeded.controller_protect_fn_id == "FN-003"
    assert seeded.motor_airflow_fn_id == "FN-004"
    assert seeded.sensor_signal_fn_id == "FN-005"

    assert seeded.fm_missed_start_id == "FM-001"
    assert seeded.fm_low_speed_id == "FM-002"
    assert seeded.fm_no_protection_id == "FM-003"
    assert seeded.fm_low_airflow_id == "FM-004"
    assert seeded.fm_temp_signal_biased_id == "FM-005"

    assert seeded.fc_temp_signal_frozen_rowid > 0
    assert seeded.fc_motor_bearing_drag_rowid > 0
    assert seeded.fc_driver_output_stuck_rowid > 0
    assert seeded.fe_controller_underestimates_demand_rowid > 0
    assert seeded.fe_airflow_not_established_rowid > 0


def test_seed_realistic_cooling_fan_project_persists_expected_trace_links(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    fm_links = read_fm_links(seeded.db_path)
    sensor_fm_rowid = read_node_rowid(seeded.db_path, seeded.fm_temp_signal_biased_id)
    start_fm_rowid = read_node_rowid(seeded.db_path, seeded.fm_missed_start_id)
    motor_fm_rowid = read_node_rowid(seeded.db_path, seeded.fm_low_airflow_id)

    assert fm_links == sorted(
        [
            {
                "from_node_rowid": seeded.fc_temp_signal_frozen_rowid,
                "to_fm_rowid": sensor_fm_rowid,
            },
            {
                "from_node_rowid": seeded.fe_controller_underestimates_demand_rowid,
                "to_fm_rowid": start_fm_rowid,
            },
            {
                "from_node_rowid": seeded.fe_airflow_not_established_rowid,
                "to_fm_rowid": motor_fm_rowid,
            },
        ],
        key=lambda item: (item["from_node_rowid"], item["to_fm_rowid"]),
    )


def test_realistic_happy_path_end_to_end_acceptance(cli_runner, tmp_path: Path):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)

    status_result = cli_runner.invoke(
        ["projection", "status", "--db", str(seeded.db_path), "--format", "json"]
    )
    status_payload = parse_json_payload(status_result)
    assert status_result.exit_code == 0, status_result.stdout
    assert status_payload["ok"] is True
    assert status_payload["command"] == "projection status"
    assert status_payload["data"]["projection_dirty"] is True

    rebuild_payload = rebuild_projection(cli_runner, seeded.db_path)
    assert rebuild_payload["ok"] is True
    assert rebuild_payload["command"] == "projection rebuild"
    assert rebuild_payload["data"]["projection_dirty"] is False

    summary_result = cli_runner.invoke(
        [
            "query",
            "summary",
            "--db",
            str(seeded.db_path),
            "--comp",
            seeded.controller_comp_id,
            "--format",
            "json",
        ]
    )
    summary_payload = parse_json_payload(summary_result)
    assert summary_result.exit_code == 0, summary_result.stdout
    assert summary_payload["ok"] is True
    assert summary_payload["command"] == "query summary"
    assert summary_payload["data"]["counts"] == {
        "functions": 3,
        "requirements": 3,
        "characteristics": 3,
        "failure_modes": 3,
        "failure_effects": 3,
        "failure_causes": 6,
        "actions": 3,
    }

    causes_result = cli_runner.invoke(
        [
            "trace",
            "causes",
            "--db",
            str(seeded.db_path),
            "--fm",
            seeded.fm_missed_start_id,
            "--format",
            "json",
        ]
    )
    causes_payload = parse_json_payload(causes_result)
    assert causes_result.exit_code == 0, causes_result.stdout
    assert [item["fm"]["id"] for item in causes_payload["data"]["chain"]] == [
        seeded.fm_missed_start_id,
        seeded.fm_temp_signal_biased_id,
    ]

    effects_result = cli_runner.invoke(
        [
            "trace",
            "effects",
            "--db",
            str(seeded.db_path),
            "--fm",
            seeded.fm_temp_signal_biased_id,
            "--format",
            "json",
        ]
    )
    effects_payload = parse_json_payload(effects_result)
    assert effects_result.exit_code == 0, effects_result.stdout
    assert [item["fm"]["id"] for item in effects_payload["data"]["chain"]] == [
        seeded.fm_temp_signal_biased_id,
        seeded.fm_missed_start_id,
        seeded.fm_low_airflow_id,
    ]

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(seeded.db_path), "--format", "json"]
    )
    validate_payload = parse_json_payload(validate_result)
    assert validate_result.exit_code == 0, validate_result.stdout
    assert validate_payload["ok"] is True
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}

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
    exported_paths = {
        Path(item["path"]).relative_to(out_dir)
        for item in export_payload["data"]["files"]
    }
    assert Path("demo/index.md") in exported_paths
    assert Path("demo/components/COMP-001.md") in exported_paths
    assert Path("demo/functions/FN-001.md") in exported_paths
    assert Path("demo/actions/open.md") in exported_paths
