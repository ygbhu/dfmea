from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from helpers_realistic_dfmea import (
    parse_json_payload,
    read_fm_links,
    read_node_rowid,
    read_project_data,
    seed_realistic_cooling_fan_project,
)


def _agent_json(agent: str, cli_runner, args: list[str]) -> dict:
    result = cli_runner.invoke(args)
    assert result.exit_code == 0, f"{agent}: {result.stdout}"
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _canonical_revision(db_path: Path, *, project_id: str = "demo") -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return int(json.loads(row[0])["canonical_revision"])


def _projection_dirty(db_path: Path, *, project_id: str = "demo") -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return bool(json.loads(row[0])["projection_dirty"])


def _node_ids(payload: dict) -> list[str | None]:
    return [node.get("id") for node in payload["data"]["nodes"]]


def _node_names(payload: dict) -> list[str | None]:
    return [node.get("name") for node in payload["data"]["nodes"]]


def _agent_a_create_shared_structure(cli_runner, db_path: Path) -> dict:
    init_payload = _agent_json(
        "Agent A",
        cli_runner,
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--name",
            "Passenger Vehicle Electronic Cooling Fan Controller",
            "--format",
            "json",
        ],
    )
    assert init_payload["command"] == "init"
    assert _canonical_revision(db_path) == 0

    sys_payload = _agent_json(
        "Agent A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "SYS",
            "--name",
            "Engine Thermal Management System",
            "--format",
            "json",
        ],
    )
    sys_id = sys_payload["data"]["node_id"]

    sub_payload = _agent_json(
        "Agent A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "SUB",
            "--name",
            "Cooling Fan System",
            "--parent",
            sys_id,
            "--format",
            "json",
        ],
    )
    sub_id = sub_payload["data"]["node_id"]

    controller_payload = _agent_json(
        "Agent A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Electronic Cooling Fan Controller",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    _agent_json(
        "Agent A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Cooling Fan Motor Assembly",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    _agent_json(
        "Agent A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Coolant Temperature Sensing Path",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )

    return {
        "sys_id": sys_id,
        "sub_id": sub_id,
        "controller_comp_id": controller_payload["data"]["node_id"],
    }


def _assert_partial_structure_failure_isolated(
    cli_runner, db_path: Path, *, sys_id: str, sub_id: str
) -> None:
    # Lifecycle checkpoint 1 for the same invariant: failed writes must not leak
    # into shared state visible to other agents during partial structure intake.
    # Test harness snapshots shared state directly from SQLite; only CLI calls count
    # as Agent A/B/C actions in this scenario.
    partial_revision_before_invalid = _canonical_revision(db_path)

    invalid_parent_result = cli_runner.invoke(
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Recovery Candidate Controller Housing",
            "--parent",
            sys_id,
            "--format",
            "json",
        ]
    )
    assert invalid_parent_result.exit_code != 0
    invalid_parent_payload = parse_json_payload(invalid_parent_result)
    assert invalid_parent_payload["errors"][0]["code"] == "INVALID_PARENT"
    invalid_parent_target = invalid_parent_payload["errors"][0]["target"]
    assert invalid_parent_target["node_type"] == "COMP"
    assert invalid_parent_target["parent_ref"] == sys_id
    assert invalid_parent_target["parent_type"] == "SYS"

    component_list_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    assert component_list_payload["data"]["count"] == 3
    assert set(_node_names(component_list_payload)) == {
        "Electronic Cooling Fan Controller",
        "Cooling Fan Motor Assembly",
        "Coolant Temperature Sensing Path",
    }
    assert _canonical_revision(db_path) == partial_revision_before_invalid


def _assert_full_trace_failure_isolated(cli_runner, full_seed) -> None:
    # Lifecycle checkpoint 2 for the same invariant: failed writes must not leak
    # into shared state visible to other agents during full analysis tracing.
    full_db_path = full_seed.db_path

    # Test harness snapshots shared trace graph state directly; agents continue to
    # interact only through explicit CLI commands.
    fm_links_before_invalid_trace = read_fm_links(full_db_path)
    full_revision_before_invalid_trace = read_project_data(full_db_path)[
        "canonical_revision"
    ]

    invalid_trace_result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(full_db_path),
            "--from",
            f"fc:{full_seed.fc_driver_output_stuck_rowid}",
            "--to-fm",
            full_seed.fm_low_speed_id,
            "--format",
            "json",
        ]
    )
    assert invalid_trace_result.exit_code != 0
    invalid_trace_payload = parse_json_payload(invalid_trace_result)
    assert invalid_trace_payload["errors"][0]["code"] == "INVALID_REFERENCE"
    invalid_trace_target = invalid_trace_payload["errors"][0]["target"]
    assert (
        invalid_trace_target["from"] == f"fc:{full_seed.fc_driver_output_stuck_rowid}"
    )
    assert invalid_trace_target["to_fm"] == full_seed.fm_low_speed_id
    assert "source_component" in invalid_trace_target
    assert "target_component" in invalid_trace_target
    assert (
        invalid_trace_target["source_component"]
        == invalid_trace_target["target_component"]
    )
    assert "component" in invalid_trace_payload["errors"][0]["message"]
    assert read_fm_links(full_db_path) == fm_links_before_invalid_trace
    assert (
        read_project_data(full_db_path)["canonical_revision"]
        == full_revision_before_invalid_trace
    )


def _agent_c_add_controller_core(
    cli_runner, db_path: Path, controller_comp_id: str
) -> dict:
    start_fn_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            controller_comp_id,
            "--name",
            "Control fan start and stop",
            "--description",
            "Command fan start and stop according to cooling demand",
            "--format",
            "json",
        ],
    )
    start_fn_id = start_fn_payload["data"]["fn_id"]

    speed_fn_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            controller_comp_id,
            "--name",
            "Modulate fan speed",
            "--description",
            "Adjust commanded fan speed to meet heat rejection demand",
            "--format",
            "json",
        ],
    )
    speed_fn_id = speed_fn_payload["data"]["fn_id"]

    start_req_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            start_fn_id,
            "--text",
            "Start fan within demanded cooling window",
            "--source",
            "CTRL-REQ-START",
            "--format",
            "json",
        ],
    )
    speed_req_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            speed_fn_id,
            "--text",
            "Track requested fan speed across operating range",
            "--source",
            "CTRL-REQ-SPEED",
            "--format",
            "json",
        ],
    )
    assert start_req_payload["data"]["req_rowid"] > 0
    assert speed_req_payload["data"]["req_rowid"] > 0

    start_char_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            start_fn_id,
            "--text",
            "Fan start response time",
            "--value",
            "500",
            "--unit",
            "ms",
            "--format",
            "json",
        ],
    )
    speed_char_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            speed_fn_id,
            "--text",
            "Fan speed tracking error",
            "--value",
            "10",
            "--unit",
            "pct",
            "--format",
            "json",
        ],
    )
    assert start_char_payload["data"]["char_rowid"] > 0
    assert speed_char_payload["data"]["char_rowid"] > 0

    return {
        "start_fn_id": start_fn_id,
        "speed_fn_id": speed_fn_id,
    }


def _assert_session_a_projection_reads(
    cli_runner, db_path: Path, controller_comp_id: str, start_fn_id: str
):
    summary_payload = _agent_json(
        "Agent A",
        cli_runner,
        [
            "query",
            "summary",
            "--db",
            str(db_path),
            "--comp",
            controller_comp_id,
            "--format",
            "json",
        ],
    )
    assert summary_payload["data"]["component"]["id"] == controller_comp_id
    assert summary_payload["data"]["counts"] == {
        "functions": 2,
        "requirements": 2,
        "characteristics": 2,
        "failure_modes": 0,
        "failure_effects": 0,
        "failure_causes": 0,
        "actions": 0,
    }

    dossier_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(db_path),
            "--fn",
            start_fn_id,
            "--format",
            "json",
        ],
    )
    assert dossier_payload["data"]["function"]["id"] == start_fn_id
    assert len(dossier_payload["data"]["requirements"]) == 1
    assert len(dossier_payload["data"]["characteristics"]) == 1
    assert dossier_payload["data"]["failure_modes"] == []


def test_multi_agent_session_interleaves_intake_and_projection_visibility(
    cli_runner, tmp_path: Path
):
    db_path = tmp_path / "realistic-multi-agent.db"
    structure = _agent_a_create_shared_structure(cli_runner, db_path)
    sub_id = structure["sub_id"]
    controller_comp_id = structure["controller_comp_id"]

    structure_revision = _canonical_revision(db_path)
    assert structure_revision > 0

    component_list_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    assert component_list_payload["data"]["count"] == 3
    assert set(_node_names(component_list_payload)) == {
        "Electronic Cooling Fan Controller",
        "Cooling Fan Motor Assembly",
        "Coolant Temperature Sensing Path",
    }

    controller_core = _agent_c_add_controller_core(
        cli_runner, db_path, controller_comp_id
    )
    start_fn_id = controller_core["start_fn_id"]
    speed_fn_id = controller_core["speed_fn_id"]

    get_start_fn_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(db_path),
            "--node",
            start_fn_id,
            "--format",
            "json",
        ],
    )
    assert get_start_fn_payload["data"]["node"]["id"] == start_fn_id
    assert get_start_fn_payload["data"]["node"]["name"] == "Control fan start and stop"

    analysis_revision = _canonical_revision(db_path)
    assert analysis_revision > structure_revision

    search_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "search",
            "--db",
            str(db_path),
            "--keyword",
            "tracking",
            "--format",
            "json",
        ],
    )
    assert any(
        node["type"] == "CHAR" and node["parent"]["id"] == speed_fn_id
        for node in search_payload["data"]["nodes"]
    )

    projection_status_payload = _agent_json(
        "Agent A",
        cli_runner,
        ["projection", "status", "--db", str(db_path), "--format", "json"],
    )
    assert projection_status_payload["data"]["projection_dirty"] is True
    assert _projection_dirty(db_path) is True

    validate_stale_payload = _agent_json(
        "Agent B",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert any(
        issue["kind"] == "STALE_PROJECTION"
        for issue in validate_stale_payload["data"]["issues"]
    )

    rebuild_payload = _agent_json(
        "Agent C",
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False
    _assert_session_a_projection_reads(
        cli_runner, db_path, controller_comp_id, start_fn_id
    )

    validate_clean_payload = _agent_json(
        "Agent C",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert validate_clean_payload["data"]["summary"] == {"errors": 0, "warnings": 0}


def test_multi_agent_session_coordinates_updates_and_projection_rebuild(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    db_path = seeded.db_path

    baseline_rebuild_payload = _agent_json(
        "Agent A",
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert baseline_rebuild_payload["data"]["projection_dirty"] is False

    baseline_revision = _canonical_revision(db_path)
    assert baseline_revision > 0

    _agent_json(
        "Agent A",
        cli_runner,
        [
            "analysis",
            "update-action-status",
            "--db",
            str(db_path),
            "--act",
            seeded.act_speed_id,
            "--status",
            "completed",
            "--format",
            "json",
        ],
    )

    _agent_json(
        "Agent B",
        cli_runner,
        [
            "analysis",
            "update-fm",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_low_speed_id,
            "--severity",
            "8",
            "--format",
            "json",
        ],
    )

    _agent_json(
        "Agent B",
        cli_runner,
        [
            "analysis",
            "unlink-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{seeded.fe_airflow_not_established_rowid}",
            "--to-fm",
            seeded.fm_low_airflow_id,
            "--format",
            "json",
        ],
    )

    low_airflow_rowid = read_node_rowid(db_path, seeded.fm_low_airflow_id)
    removed_link = {
        "from_node_rowid": seeded.fe_airflow_not_established_rowid,
        "to_fm_rowid": low_airflow_rowid,
    }
    assert removed_link not in read_fm_links(db_path)

    updated_revision = _canonical_revision(db_path)
    assert updated_revision > baseline_revision
    assert _projection_dirty(db_path) is True

    stale_validate_payload = _agent_json(
        "Agent C",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert any(
        issue["kind"] == "STALE_PROJECTION"
        for issue in stale_validate_payload["data"]["issues"]
    )

    _agent_json(
        "Agent B",
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{seeded.fe_airflow_not_established_rowid}",
            "--to-fm",
            seeded.fm_low_airflow_id,
            "--format",
            "json",
        ],
    )
    assert removed_link in read_fm_links(db_path)

    _agent_json(
        "Agent A",
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )

    completed_actions_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "query",
            "actions",
            "--db",
            str(db_path),
            "--status",
            "completed",
            "--format",
            "json",
        ],
    )
    assert seeded.act_speed_id in _node_ids(completed_actions_payload)

    by_severity_payload = _agent_json(
        "Agent A",
        cli_runner,
        [
            "query",
            "by-severity",
            "--db",
            str(db_path),
            "--gte",
            "8",
            "--format",
            "json",
        ],
    )
    assert seeded.fm_low_speed_id in _node_ids(by_severity_payload)

    dossier_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(db_path),
            "--fn",
            seeded.controller_speed_fn_id,
            "--format",
            "json",
        ],
    )
    matched_failure_modes = [
        card
        for card in dossier_payload["data"]["failure_modes"]
        if card["fm"]["id"] == seeded.fm_low_speed_id
    ]
    assert matched_failure_modes

    effects_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "trace",
            "effects",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_temp_signal_biased_id,
            "--format",
            "json",
        ],
    )
    assert [item["fm"]["id"] for item in effects_payload["data"]["chain"]] == [
        seeded.fm_temp_signal_biased_id,
        seeded.fm_missed_start_id,
        seeded.fm_low_airflow_id,
    ]

    final_validate_payload = _agent_json(
        "Agent A",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert final_validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}


def test_multi_agent_session_isolates_failed_writes_from_other_agents(
    cli_runner, tmp_path: Path
):
    """Verify one invariant across two lifecycle checkpoints in the same Session C.

    Failed writes do not leak into shared state for other agents, sampled once in
    partial structure intake and once in full analysis tracing.
    """
    partial_db_path = tmp_path / "partial-shared.db"
    partial_structure = _agent_a_create_shared_structure(cli_runner, partial_db_path)

    _assert_partial_structure_failure_isolated(
        cli_runner,
        partial_db_path,
        sys_id=partial_structure["sys_id"],
        sub_id=partial_structure["sub_id"],
    )

    add_component_payload = _agent_json(
        "Agent C",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db_path),
            "--type",
            "COMP",
            "--name",
            "Recovery Candidate Controller Housing",
            "--parent",
            partial_structure["sub_id"],
            "--format",
            "json",
        ],
    )
    assert add_component_payload["data"]["parent_id"] == partial_structure["sub_id"]

    projection_status_payload = _agent_json(
        "Agent A",
        cli_runner,
        ["projection", "status", "--db", str(partial_db_path), "--format", "json"],
    )
    assert projection_status_payload["data"]["projection_dirty"] is True

    # Same Session C continues into the full realistic shared project checkpoint.
    full_seed = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    full_db_path = full_seed.db_path
    _assert_full_trace_failure_isolated(cli_runner, full_seed)

    get_fm_payload = _agent_json(
        "Agent B",
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(full_db_path),
            "--node",
            full_seed.fm_missed_start_id,
            "--format",
            "json",
        ],
    )
    assert get_fm_payload["data"]["node"]["id"] == full_seed.fm_missed_start_id

    _agent_json(
        "Agent C",
        cli_runner,
        ["projection", "rebuild", "--db", str(full_db_path), "--format", "json"],
    )

    validate_payload = _agent_json(
        "Agent A",
        cli_runner,
        ["validate", "--db", str(full_db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}
