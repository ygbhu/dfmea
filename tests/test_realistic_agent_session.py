from __future__ import annotations

from pathlib import Path

from helpers_realistic_dfmea import (
    affected_object,
    invoke_json,
    parse_json_payload,
    read_fm_links,
    read_node_data,
    read_node_rowid,
    read_project_data,
    seed_realistic_cooling_fan_project,
    seed_realistic_controller_core,
    seed_realistic_structure_only,
)


def _add_function(
    cli_runner, db_path: Path, *, comp: str, name: str, description: str
) -> dict:
    return invoke_json(
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            comp,
            "--name",
            name,
            "--description",
            description,
            "--format",
            "json",
        ],
    )


def _add_requirement(
    cli_runner, db_path: Path, *, fn: str, text: str, source: str
) -> dict:
    return invoke_json(
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            fn,
            "--text",
            text,
            "--source",
            source,
            "--format",
            "json",
        ],
    )


def _add_characteristic(
    cli_runner, db_path: Path, *, fn: str, text: str, value: str, unit: str
) -> dict:
    return invoke_json(
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            fn,
            "--text",
            text,
            "--value",
            value,
            "--unit",
            unit,
            "--format",
            "json",
        ],
    )


def _add_failure_chain(
    cli_runner, db_path: Path, *, fn: str, args: list[str], target_causes: str = "1"
) -> dict:
    # `target_causes` uses the command-local creation order of FC entries in this call.
    return invoke_json(
        cli_runner,
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            fn,
            *args,
            "--target-causes",
            target_causes,
            "--format",
            "json",
        ],
    )


def _link_trace(cli_runner, db_path: Path, *, from_ref: str, to_fm: str) -> dict:
    return invoke_json(
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            from_ref,
            "--to-fm",
            to_fm,
            "--format",
            "json",
        ],
    )


def _node_ids(payload: dict) -> set[str]:
    return {node["id"] for node in payload["data"]["nodes"]}


def _controller_chain_args(
    *, req_rowid: int, char_rowid: int, chain: str
) -> tuple[list[str], str]:
    definitions = {
        "start": (
            [
                "--fm-description",
                "Fan not started when cooling requested",
                "--severity",
                "8",
                "--violates-req",
                str(req_rowid),
                "--related-char",
                str(char_rowid),
                "--fe-description",
                "Required airflow not delivered",
                "--fe-level",
                "system",
                "--fc-description",
                "Temperature signal biased low",
                "--occurrence",
                "4",
                "--detection",
                "4",
                "--ap",
                "High",
                "--fc-description",
                "Driver output stage stuck low",
                "--occurrence",
                "3",
                "--detection",
                "3",
                "--ap",
                "High",
                "--act-description",
                "Add sensor plausibility and output-stage feedback diagnostics",
                "--kind",
                "detection",
                "--status",
                "planned",
                "--owner",
                "Controls",
                "--due",
                "2026-07-01",
            ],
            "1,2",
        ),
        "speed": (
            [
                "--fm-description",
                "Fan speed below target",
                "--severity",
                "7",
                "--violates-req",
                str(req_rowid),
                "--related-char",
                str(char_rowid),
                "--fe-description",
                "Heat rejection lower than commanded",
                "--fe-level",
                "system",
                "--fc-description",
                "PWM clamp calibrated too low",
                "--occurrence",
                "4",
                "--detection",
                "5",
                "--ap",
                "Medium",
                "--fc-description",
                "Low-voltage fallback logic incorrect",
                "--occurrence",
                "3",
                "--detection",
                "5",
                "--ap",
                "Medium",
                "--act-description",
                "Tighten PWM calibration and low-voltage fallback test coverage",
                "--kind",
                "prevention",
                "--status",
                "planned",
                "--owner",
                "Controls",
                "--due",
                "2026-07-15",
            ],
            "1,2",
        ),
        "protect": (
            [
                "--fm-description",
                "Overtemperature protection not entered",
                "--severity",
                "9",
                "--violates-req",
                str(req_rowid),
                "--related-char",
                str(char_rowid),
                "--fe-description",
                "Protective high-speed mode unavailable",
                "--fe-level",
                "system",
                "--fc-description",
                "Overtemperature threshold set too high",
                "--occurrence",
                "3",
                "--detection",
                "4",
                "--ap",
                "High",
                "--fc-description",
                "Fault-state machine stalls",
                "--occurrence",
                "2",
                "--detection",
                "5",
                "--ap",
                "Medium",
                "--act-description",
                "Add threshold boundary tests and watchdog coverage",
                "--kind",
                "detection",
                "--status",
                "planned",
                "--owner",
                "Software",
                "--due",
                "2026-07-30",
            ],
            "1,2",
        ),
    }
    return definitions[chain]


def _support_chain_args(chain: str) -> tuple[list[str], str]:
    definitions = {
        "motor": (
            [
                "--fm-description",
                "Required airflow not delivered",
                "--severity",
                "7",
                "--fe-description",
                "Engine-bay airflow margin reduced",
                "--fe-level",
                "vehicle",
                "--fc-description",
                "Motor bearing drag high",
                "--occurrence",
                "5",
                "--detection",
                "4",
                "--ap",
                "High",
                "--act-description",
                "Add bearing drag screening",
                "--kind",
                "prevention",
                "--status",
                "planned",
                "--owner",
                "Supplier Quality",
                "--due",
                "2026-08-15",
            ],
            "1",
        ),
        "sensor": (
            [
                "--fm-description",
                "Temperature signal biased low",
                "--severity",
                "8",
                "--fe-description",
                "Fan not started when cooling requested",
                "--fe-level",
                "component",
                "--fc-description",
                "Sensor pull-up open circuit",
                "--occurrence",
                "4",
                "--detection",
                "4",
                "--ap",
                "High",
                "--act-description",
                "Add sensor input plausibility monitor",
                "--kind",
                "detection",
                "--status",
                "planned",
                "--owner",
                "Diagnostics",
                "--due",
                "2026-08-01",
            ],
            "1",
        ),
    }
    return definitions[chain]


def _complete_session_a_remaining_model(cli_runner, seeded: dict) -> dict:
    db_path = seeded["db_path"]

    protect_fn = _add_function(
        cli_runner,
        db_path,
        comp=seeded["controller_comp_id"],
        name="Enter overtemperature protection and report faults",
        description="Force protection mode and report thermal control faults",
    )
    protect_req = _add_requirement(
        cli_runner,
        db_path,
        fn=protect_fn["data"]["fn_id"],
        text="Enter protection mode at calibrated overtemperature threshold",
        source="CTRL-REQ-PROTECT",
    )
    protect_char = _add_characteristic(
        cli_runner,
        db_path,
        fn=protect_fn["data"]["fn_id"],
        text="Protection threshold accuracy",
        value="2",
        unit="degC",
    )

    start_args, start_targets = _controller_chain_args(
        req_rowid=seeded["requirement_rowids"][0],
        char_rowid=seeded["characteristic_rowids"][0],
        chain="start",
    )
    speed_args, speed_targets = _controller_chain_args(
        req_rowid=seeded["requirement_rowids"][1],
        char_rowid=seeded["characteristic_rowids"][1],
        chain="speed",
    )
    protect_args, protect_targets = _controller_chain_args(
        req_rowid=protect_req["data"]["req_rowid"],
        char_rowid=protect_char["data"]["char_rowid"],
        chain="protect",
    )
    motor_args, motor_targets = _support_chain_args("motor")
    sensor_args, sensor_targets = _support_chain_args("sensor")

    controller_start_chain = _add_failure_chain(
        cli_runner,
        db_path,
        fn=seeded["controller_start_fn_id"],
        args=start_args,
        target_causes=start_targets,
    )
    controller_speed_chain = _add_failure_chain(
        cli_runner,
        db_path,
        fn=seeded["controller_speed_fn_id"],
        args=speed_args,
        target_causes=speed_targets,
    )
    controller_protect_chain = _add_failure_chain(
        cli_runner,
        db_path,
        fn=protect_fn["data"]["fn_id"],
        args=protect_args,
        target_causes=protect_targets,
    )

    motor_fn = _add_function(
        cli_runner,
        db_path,
        comp=seeded["motor_comp_id"],
        name="Generate airflow under controller command",
        description="Convert controller command into cooling airflow",
    )
    motor_chain = _add_failure_chain(
        cli_runner,
        db_path,
        fn=motor_fn["data"]["fn_id"],
        args=motor_args,
        target_causes=motor_targets,
    )

    sensor_fn = _add_function(
        cli_runner,
        db_path,
        comp=seeded["sensor_comp_id"],
        name="Provide coolant temperature signal",
        description="Provide coolant temperature feedback to controller logic",
    )
    sensor_chain = _add_failure_chain(
        cli_runner,
        db_path,
        fn=sensor_fn["data"]["fn_id"],
        args=sensor_args,
        target_causes=sensor_targets,
    )

    start_fc_temp_signal = affected_object(controller_start_chain, "FC", ordinal=1)
    start_fe_airflow = affected_object(controller_start_chain, "FE")
    sensor_fe_fan_not_started = affected_object(sensor_chain, "FE")

    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fc:{start_fc_temp_signal['rowid']}",
        to_fm=sensor_chain["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fe:{sensor_fe_fan_not_started['rowid']}",
        to_fm=controller_start_chain["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fe:{start_fe_airflow['rowid']}",
        to_fm=motor_chain["data"]["fm_id"],
    )

    return {
        "protect_fn_id": protect_fn["data"]["fn_id"],
        "controller_start_fm_id": controller_start_chain["data"]["fm_id"],
        "controller_protect_fm_id": controller_protect_chain["data"]["fm_id"],
        "motor_fm_id": motor_chain["data"]["fm_id"],
        "sensor_fm_id": sensor_chain["data"]["fm_id"],
    }


def _assert_session_a_follow_up_answers(
    cli_runner, tmp_path: Path, seeded: dict, completed: dict
):
    db_path = seeded["db_path"]

    projection_status = invoke_json(
        cli_runner,
        ["projection", "status", "--db", str(db_path), "--format", "json"],
    )
    assert projection_status["data"]["projection_dirty"] is True

    projection_rebuild = invoke_json(
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert projection_rebuild["data"]["projection_dirty"] is False

    summary_payload = invoke_json(
        cli_runner,
        [
            "query",
            "summary",
            "--db",
            str(db_path),
            "--comp",
            seeded["controller_comp_id"],
            "--format",
            "json",
        ],
    )
    assert summary_payload["data"]["component"]["id"] == seeded["controller_comp_id"]
    assert summary_payload["data"]["counts"]["functions"] == 3
    assert summary_payload["data"]["counts"]["failure_modes"] == 3
    assert summary_payload["data"]["counts"]["actions"] == 3

    dossier_payload = invoke_json(
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(db_path),
            "--fn",
            completed["protect_fn_id"],
            "--format",
            "json",
        ],
    )
    assert dossier_payload["data"]["function"]["id"] == completed["protect_fn_id"]
    assert len(dossier_payload["data"]["requirements"]) == 1
    assert len(dossier_payload["data"]["characteristics"]) == 1
    assert len(dossier_payload["data"]["failure_modes"]) == 1

    by_ap_payload = invoke_json(
        cli_runner,
        [
            "query",
            "by-ap",
            "--db",
            str(db_path),
            "--ap",
            "High",
            "--format",
            "json",
        ],
    )
    assert by_ap_payload["data"]["count"] >= 3
    assert all(node["type"] == "FC" for node in by_ap_payload["data"]["nodes"])

    by_severity_payload = invoke_json(
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
    assert _node_ids(by_severity_payload) == {
        completed["controller_start_fm_id"],
        completed["controller_protect_fm_id"],
        completed["sensor_fm_id"],
    }

    causes_payload = invoke_json(
        cli_runner,
        [
            "trace",
            "causes",
            "--db",
            str(db_path),
            "--fm",
            completed["controller_start_fm_id"],
            "--format",
            "json",
        ],
    )
    assert [item["fm"]["id"] for item in causes_payload["data"]["chain"]] == [
        completed["controller_start_fm_id"],
        completed["sensor_fm_id"],
    ]

    effects_payload = invoke_json(
        cli_runner,
        [
            "trace",
            "effects",
            "--db",
            str(db_path),
            "--fm",
            completed["sensor_fm_id"],
            "--format",
            "json",
        ],
    )
    assert [item["fm"]["id"] for item in effects_payload["data"]["chain"]] == [
        completed["sensor_fm_id"],
        completed["controller_start_fm_id"],
        completed["motor_fm_id"],
    ]

    export_payload = invoke_json(
        cli_runner,
        [
            "export",
            "markdown",
            "--db",
            str(db_path),
            "--out",
            str(tmp_path / "review-export"),
            "--layout",
            "review",
            "--format",
            "json",
        ],
    )
    exported_paths = {
        Path(item["path"]).name for item in export_payload["data"]["files"]
    }
    assert "index.md" in exported_paths
    assert f"{seeded['controller_comp_id']}.md" in exported_paths

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}


def test_partial_realistic_seeds_support_agent_style_incremental_intake(
    cli_runner, tmp_path: Path
):
    structure_seed = seed_realistic_structure_only(cli_runner, tmp_path)

    assert structure_seed["project_id"] == "demo"
    assert structure_seed["db_path"].name == "realistic-cooling-fan.db"
    assert structure_seed["sys_id"] == "SYS-001"
    assert structure_seed["sub_id"] == "SUB-001"
    assert structure_seed["controller_comp_id"] == "COMP-001"
    assert structure_seed["motor_comp_id"] == "COMP-002"
    assert structure_seed["sensor_comp_id"] == "COMP-003"
    assert structure_seed["counts"] == {
        "systems": 1,
        "subsystems": 1,
        "components": 3,
    }
    assert "component_ids" not in structure_seed
    assert read_project_data(structure_seed["db_path"])["projection_dirty"] is True

    core_seed = seed_realistic_controller_core(cli_runner, tmp_path)

    assert core_seed["project_id"] == "demo"
    assert core_seed["db_path"] == structure_seed["db_path"]
    assert core_seed["controller_comp_id"] == structure_seed["controller_comp_id"]
    assert core_seed["motor_comp_id"] == structure_seed["motor_comp_id"]
    assert core_seed["sensor_comp_id"] == structure_seed["sensor_comp_id"]
    assert core_seed["controller_start_fn_id"].startswith("FN-")
    assert core_seed["controller_speed_fn_id"].startswith("FN-")
    assert len(core_seed["fn_ids"]) == 2
    assert core_seed["fn_ids"] == [
        core_seed["controller_start_fn_id"],
        core_seed["controller_speed_fn_id"],
    ]
    assert "component_id" not in core_seed
    assert "function_ids" not in core_seed
    assert len(core_seed["requirement_rowids"]) == 2
    assert len(core_seed["characteristic_rowids"]) == 2
    assert all(
        isinstance(rowid, int) and rowid > 0
        for rowid in core_seed["requirement_rowids"]
    )
    assert all(
        isinstance(rowid, int) and rowid > 0
        for rowid in core_seed["characteristic_rowids"]
    )
    assert core_seed["requirement_rowids"] == sorted(core_seed["requirement_rowids"])
    assert core_seed["characteristic_rowids"] == sorted(
        core_seed["characteristic_rowids"]
    )
    assert core_seed["counts"] == {
        "functions": 2,
        "requirements": 2,
        "characteristics": 2,
    }
    assert read_project_data(core_seed["db_path"])["projection_dirty"] is True


def test_agent_session_incrementally_records_dfmea_then_answers_follow_up_questions(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_controller_core(cli_runner, tmp_path)
    db_path = seeded["db_path"]

    early_list = invoke_json(
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(db_path),
            "--type",
            "FN",
            "--parent",
            seeded["controller_comp_id"],
            "--format",
            "json",
        ],
    )
    assert _node_ids(early_list) == set(seeded["fn_ids"])

    early_get = invoke_json(
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(db_path),
            "--node",
            seeded["controller_start_fn_id"],
            "--format",
            "json",
        ],
    )
    assert early_get["data"]["node"]["name"] == "Control fan start and stop"
    assert early_get["data"]["node"]["data"]["description"] == (
        "Command fan start and stop according to cooling demand"
    )

    early_search = invoke_json(
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
    assert early_search["data"]["count"] == 1
    assert early_search["data"]["nodes"][0]["type"] == "CHAR"
    assert (
        early_search["data"]["nodes"][0]["parent"]["id"]
        == seeded["controller_speed_fn_id"]
    )
    completed = _complete_session_a_remaining_model(cli_runner, seeded)
    _assert_session_a_follow_up_answers(cli_runner, tmp_path, seeded, completed)


def test_agent_session_repairs_realistic_dfmea_after_user_requested_changes(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    db_path = seeded.db_path
    low_airflow_fm_rowid = read_node_rowid(db_path, seeded.fm_low_airflow_id)

    # Business maintenance updates.
    update_fm_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fm",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_low_speed_id,
            "--description",
            "Fan speed below target after limp-home clamp",
            "--severity",
            "8",
            "--format",
            "json",
        ],
    )
    assert update_fm_payload["data"]["fm_id"] == seeded.fm_low_speed_id

    update_fe_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fe",
            "--db",
            str(db_path),
            "--fe",
            str(seeded.fe_low_speed_heat_rejection_rowid),
            "--description",
            "Heat rejection remains below commanded level during degraded mode",
            "--level",
            "vehicle",
            "--format",
            "json",
        ],
    )
    assert (
        update_fe_payload["data"]["fe_rowid"]
        == seeded.fe_low_speed_heat_rejection_rowid
    )

    update_fc_pwm_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fc",
            "--db",
            str(db_path),
            "--fc",
            str(seeded.fc_pwm_clamp_low_rowid),
            "--description",
            "PWM limp-home clamp calibrated too low",
            "--occurrence",
            "2",
            "--detection",
            "4",
            "--ap",
            "Low",
            "--format",
            "json",
        ],
    )
    assert update_fc_pwm_payload["data"]["fc_rowid"] == seeded.fc_pwm_clamp_low_rowid

    update_fc_logic_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fc",
            "--db",
            str(db_path),
            "--fc",
            str(seeded.fc_low_voltage_logic_rowid),
            "--description",
            "Low-voltage fallback branch latches reduced-speed request",
            "--occurrence",
            "4",
            "--detection",
            "5",
            "--ap",
            "High",
            "--format",
            "json",
        ],
    )
    assert (
        update_fc_logic_payload["data"]["fc_rowid"] == seeded.fc_low_voltage_logic_rowid
    )

    update_act_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "update-act",
            "--db",
            str(db_path),
            "--act",
            seeded.act_speed_id,
            "--description",
            "Retune limp-home PWM floor and expand low-voltage regression coverage",
            "--kind",
            "prevention",
            "--status",
            "in-progress",
            "--owner",
            "Controls Calibration",
            "--due",
            "2026-07-20",
            "--target-causes",
            str(seeded.fc_low_voltage_logic_rowid),
            "--format",
            "json",
        ],
    )
    assert update_act_payload["data"]["act_id"] == seeded.act_speed_id

    update_status_payload = invoke_json(
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
    assert update_status_payload["data"]["act_id"] == seeded.act_speed_id

    # Relationship repairs.
    invoke_json(
        cli_runner,
        [
            "analysis",
            "unlink-fm-requirement",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_low_speed_id,
            "--req",
            str(seeded.req_speed_rowid),
            "--format",
            "json",
        ],
    )
    low_speed_fm_data = read_node_data(db_path, seeded.fm_low_speed_id)
    assert seeded.req_speed_rowid not in low_speed_fm_data.get(
        "violates_requirements", []
    )

    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-fm-requirement",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_low_speed_id,
            "--req",
            str(seeded.req_speed_rowid),
            "--format",
            "json",
        ],
    )
    low_speed_fm_data = read_node_data(db_path, seeded.fm_low_speed_id)
    assert low_speed_fm_data.get("violates_requirements") == [seeded.req_speed_rowid]

    invoke_json(
        cli_runner,
        [
            "analysis",
            "unlink-fm-characteristic",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_low_speed_id,
            "--char",
            str(seeded.char_speed_rowid),
            "--format",
            "json",
        ],
    )
    low_speed_fm_data = read_node_data(db_path, seeded.fm_low_speed_id)
    assert seeded.char_speed_rowid not in low_speed_fm_data.get(
        "related_characteristics", []
    )

    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-fm-characteristic",
            "--db",
            str(db_path),
            "--fm",
            seeded.fm_low_speed_id,
            "--char",
            str(seeded.char_speed_rowid),
            "--format",
            "json",
        ],
    )
    low_speed_fm_data = read_node_data(db_path, seeded.fm_low_speed_id)
    assert low_speed_fm_data.get("related_characteristics") == [seeded.char_speed_rowid]

    invoke_json(
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
    assert {
        (item["from_node_rowid"], item["to_fm_rowid"])
        for item in read_fm_links(db_path)
    }.isdisjoint({(seeded.fe_airflow_not_established_rowid, low_airflow_fm_rowid)})

    invoke_json(
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
    assert (seeded.fe_airflow_not_established_rowid, low_airflow_fm_rowid) in {
        (item["from_node_rowid"], item["to_fm_rowid"])
        for item in read_fm_links(db_path)
    }

    deleted_req_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "delete-requirement",
            "--db",
            str(db_path),
            "--req",
            str(seeded.req_start_rowid),
            "--format",
            "json",
        ],
    )
    assert deleted_req_payload["command"] == "analysis delete-requirement"

    deleted_char_payload = invoke_json(
        cli_runner,
        [
            "analysis",
            "delete-characteristic",
            "--db",
            str(db_path),
            "--char",
            str(seeded.char_start_rowid),
            "--format",
            "json",
        ],
    )
    assert deleted_char_payload["command"] == "analysis delete-characteristic"

    projection_status = invoke_json(
        cli_runner,
        ["projection", "status", "--db", str(db_path), "--format", "json"],
    )
    assert projection_status["data"]["projection_dirty"] is True

    projection_rebuild = invoke_json(
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert projection_rebuild["data"]["projection_dirty"] is False

    # Rebuild + result verification.
    dossier_payload = invoke_json(
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
    assert dossier_payload["command"] == "query dossier"
    assert dossier_payload["data"]["function"]["id"] == seeded.controller_speed_fn_id
    assert len(dossier_payload["data"]["requirements"]) == 1
    assert len(dossier_payload["data"]["characteristics"]) == 1
    assert len(dossier_payload["data"]["failure_modes"]) == 1
    assert [item["rowid"] for item in dossier_payload["data"]["requirements"]] == [
        seeded.req_speed_rowid
    ]
    assert [item["rowid"] for item in dossier_payload["data"]["characteristics"]] == [
        seeded.char_speed_rowid
    ]
    assert [card["fm"]["id"] for card in dossier_payload["data"]["failure_modes"]] == [
        seeded.fm_low_speed_id
    ]
    low_speed_card = dossier_payload["data"]["failure_modes"][0]
    assert (
        low_speed_card["fm"]["name"] == "Fan speed below target after limp-home clamp"
    )
    assert [effect["rowid"] for effect in low_speed_card["effects"]] == [
        seeded.fe_low_speed_heat_rejection_rowid
    ]
    assert {cause["rowid"] for cause in low_speed_card["causes"]} == {
        seeded.fc_pwm_clamp_low_rowid,
        seeded.fc_low_voltage_logic_rowid,
    }
    assert low_speed_card["actions"][0]["id"] == seeded.act_speed_id
    assert low_speed_card["actions"][0]["data"]["status"] == "completed"
    assert low_speed_card["actions"][0]["data"]["owner"] == "Controls Calibration"
    assert low_speed_card["actions"][0]["data"]["kind"] == "prevention"
    assert low_speed_card["actions"][0]["data"]["target_causes"] == [
        seeded.fc_low_voltage_logic_rowid
    ]

    start_dossier_payload = invoke_json(
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(db_path),
            "--fn",
            seeded.controller_start_fn_id,
            "--format",
            "json",
        ],
    )
    assert start_dossier_payload["data"]["requirements"] == []
    assert start_dossier_payload["data"]["characteristics"] == []

    trace_effects_payload = invoke_json(
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
    assert [item["fm"]["id"] for item in trace_effects_payload["data"]["chain"]] == [
        seeded.fm_temp_signal_biased_id,
        seeded.fm_missed_start_id,
        seeded.fm_low_airflow_id,
    ]

    completed_actions_payload = invoke_json(
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
    assert completed_actions_payload["command"] == "query actions"
    assert [node["id"] for node in completed_actions_payload["data"]["nodes"]] == [
        seeded.act_speed_id
    ]

    by_severity_payload = invoke_json(
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
    assert {node["id"] for node in by_severity_payload["data"]["nodes"]} == {
        seeded.fm_missed_start_id,
        seeded.fm_low_speed_id,
        seeded.fm_no_protection_id,
        seeded.fm_temp_signal_biased_id,
    }

    export_payload = invoke_json(
        cli_runner,
        [
            "export",
            "markdown",
            "--db",
            str(db_path),
            "--out",
            str(tmp_path / "review-export-session-b"),
            "--layout",
            "review",
            "--format",
            "json",
        ],
    )
    exported_paths = {
        Path(item["path"]).name for item in export_payload["data"]["files"]
    }
    assert "index.md" in exported_paths
    assert f"{seeded.controller_speed_fn_id}.md" in exported_paths

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}


def test_agent_session_recovers_from_invalid_actions_and_finishes_cleanly(
    cli_runner, tmp_path: Path
):
    partial_tmp_path = tmp_path / "partial"
    full_tmp_path = tmp_path / "full"
    partial_tmp_path.mkdir()
    full_tmp_path.mkdir()

    partial_seed = seed_realistic_structure_only(cli_runner, partial_tmp_path)
    partial_db_path = partial_seed["db_path"]
    partial_project_before_invalid = read_project_data(partial_db_path)
    partial_components_before_invalid = invoke_json(
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(partial_db_path),
            "--type",
            "COMP",
            "--parent",
            partial_seed["sub_id"],
            "--format",
            "json",
        ],
    )
    partial_component_names_before_invalid = {
        node["name"] for node in partial_components_before_invalid["data"]["nodes"]
    }

    invalid_parent_result = cli_runner.invoke(
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
            partial_seed["sys_id"],
            "--format",
            "json",
        ]
    )
    assert invalid_parent_result.exit_code != 0
    invalid_parent_payload = parse_json_payload(invalid_parent_result)
    assert invalid_parent_payload["errors"][0]["code"] == "INVALID_PARENT"
    partial_project_after_invalid = read_project_data(partial_db_path)
    partial_components_after_invalid = invoke_json(
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(partial_db_path),
            "--type",
            "COMP",
            "--parent",
            partial_seed["sub_id"],
            "--format",
            "json",
        ],
    )
    assert (
        partial_components_after_invalid["data"]["count"]
        == partial_components_before_invalid["data"]["count"]
    )
    assert {
        node["name"] for node in partial_components_after_invalid["data"]["nodes"]
    } == partial_component_names_before_invalid
    assert "Recovery Candidate Controller Housing" not in {
        node["name"] for node in partial_components_after_invalid["data"]["nodes"]
    }
    assert (
        partial_project_after_invalid["canonical_revision"]
        == partial_project_before_invalid["canonical_revision"]
    )

    valid_component_payload = invoke_json(
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
            partial_seed["sub_id"],
            "--format",
            "json",
        ],
    )
    assert valid_component_payload["data"]["parent_id"] == partial_seed["sub_id"]

    full_seed = seed_realistic_cooling_fan_project(cli_runner, full_tmp_path)
    full_db_path = full_seed.db_path
    full_project_before_delete = read_project_data(full_db_path)
    controller_functions_before_delete = invoke_json(
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(full_db_path),
            "--type",
            "FN",
            "--parent",
            full_seed.controller_comp_id,
            "--format",
            "json",
        ],
    )

    delete_non_empty_result = cli_runner.invoke(
        [
            "structure",
            "delete",
            "--db",
            str(full_db_path),
            "--node",
            full_seed.controller_comp_id,
            "--format",
            "json",
        ]
    )
    assert delete_non_empty_result.exit_code != 0
    delete_non_empty_payload = parse_json_payload(delete_non_empty_result)
    assert delete_non_empty_payload["errors"][0]["code"] == "NODE_NOT_EMPTY"
    full_project_after_delete = read_project_data(full_db_path)
    controller_get_after_delete = invoke_json(
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(full_db_path),
            "--node",
            full_seed.controller_comp_id,
            "--format",
            "json",
        ],
    )
    controller_functions_after_delete = invoke_json(
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(full_db_path),
            "--type",
            "FN",
            "--parent",
            full_seed.controller_comp_id,
            "--format",
            "json",
        ],
    )
    assert (
        controller_get_after_delete["data"]["node"]["id"]
        == full_seed.controller_comp_id
    )
    assert (
        controller_functions_after_delete["data"]["count"]
        == controller_functions_before_delete["data"]["count"]
    )
    assert {
        node["id"] for node in controller_functions_after_delete["data"]["nodes"]
    } == {node["id"] for node in controller_functions_before_delete["data"]["nodes"]}
    assert (
        full_project_after_delete["canonical_revision"]
        == full_project_before_delete["canonical_revision"]
    )

    fm_links_before_invalid_trace = read_fm_links(full_db_path)
    full_project_before_invalid_trace = read_project_data(full_db_path)

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
    assert read_fm_links(full_db_path) == fm_links_before_invalid_trace
    assert (
        read_project_data(full_db_path)["canonical_revision"]
        == full_project_before_invalid_trace["canonical_revision"]
    )

    query_payload = invoke_json(
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
    assert query_payload["data"]["node"]["id"] == full_seed.fm_missed_start_id

    rebuild_payload = invoke_json(
        cli_runner,
        ["projection", "rebuild", "--db", str(full_db_path), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(full_db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}
