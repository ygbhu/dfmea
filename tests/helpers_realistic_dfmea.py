from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RealisticCoolingFanProjectSeed:
    db_path: Path
    project_id: str
    controller_comp_id: str
    motor_comp_id: str
    sensor_comp_id: str
    controller_start_fn_id: str
    controller_speed_fn_id: str
    controller_protect_fn_id: str
    motor_airflow_fn_id: str
    sensor_signal_fn_id: str
    fm_missed_start_id: str
    fm_low_speed_id: str
    fm_no_protection_id: str
    fm_low_airflow_id: str
    fm_temp_signal_biased_id: str
    fc_temp_signal_frozen_rowid: int
    fc_motor_bearing_drag_rowid: int
    fc_driver_output_stuck_rowid: int
    fc_overtemperature_threshold_high_rowid: int
    fc_sensor_pullup_open_circuit_rowid: int
    fe_controller_underestimates_demand_rowid: int
    fe_airflow_not_established_rowid: int
    act_start_id: str
    act_speed_id: str
    act_protect_id: str
    act_motor_id: str
    act_sensor_id: str


def _payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def parse_json_payload(result) -> dict:
    return _payload(result)


def rebuild_projection(cli_runner, db_path: Path) -> dict:
    result = cli_runner.invoke(
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.stdout
    return _payload(result)


def _affected_object(payload: dict, node_type: str, *, ordinal: int = 1) -> dict:
    matches = [
        item
        for item in payload["data"]["affected_objects"]
        if item["type"] == node_type
    ]
    index = ordinal - 1
    if index < 0 or index >= len(matches):
        raise AssertionError(
            "Missing affected object "
            f"type={node_type!r} ordinal={ordinal} in {payload['data']['affected_objects']!r}"
        )
    return matches[index]


def read_node_rowid(db_path: Path, node_ref: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT rowid FROM nodes WHERE id = ?",
            (node_ref,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise AssertionError(f"Missing node rowid for {node_ref!r} in {db_path}")
    return int(row[0])


def read_fm_links(db_path: Path) -> list[dict[str, int]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT from_rowid, to_fm_rowid FROM fm_links ORDER BY from_rowid, to_fm_rowid"
        ).fetchall()
    finally:
        conn.close()

    return [
        {"from_node_rowid": int(from_rowid), "to_fm_rowid": int(to_fm_rowid)}
        for from_rowid, to_fm_rowid in rows
    ]


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "realistic-cooling-fan.db"
    result = cli_runner.invoke(
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
        ]
    )
    assert result.exit_code == 0, result.stdout
    return db_path


def _add_structure(
    cli_runner, db_path: Path, *, node_type: str, name: str, parent: str | None = None
):
    args = [
        "structure",
        "add",
        "--db",
        str(db_path),
        "--type",
        node_type,
        "--name",
        name,
        "--format",
        "json",
    ]
    if parent is not None:
        args.extend(["--parent", parent])
    result = cli_runner.invoke(args)
    assert result.exit_code == 0, result.stdout
    return _payload(result)


def _add_function(cli_runner, db_path: Path, *, comp: str, name: str, description: str):
    result = cli_runner.invoke(
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
        ]
    )
    assert result.exit_code == 0, result.stdout
    return _payload(result)


def _add_requirement(cli_runner, db_path: Path, *, fn: str, text: str, source: str):
    result = cli_runner.invoke(
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
        ]
    )
    assert result.exit_code == 0, result.stdout
    return _payload(result)


def _add_characteristic(
    cli_runner, db_path: Path, *, fn: str, text: str, value: str, unit: str
):
    result = cli_runner.invoke(
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
        ]
    )
    assert result.exit_code == 0, result.stdout
    return _payload(result)


def _add_failure_chain(cli_runner, db_path: Path, *, fn: str, extra_args: list[str]):
    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            fn,
            *extra_args,
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.stdout
    return _payload(result)


def _link_trace(cli_runner, db_path: Path, *, from_ref: str, to_fm: str) -> None:
    result = cli_runner.invoke(
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
        ]
    )
    assert result.exit_code == 0, result.stdout


def seed_realistic_cooling_fan_project(
    cli_runner, tmp_path: Path
) -> RealisticCoolingFanProjectSeed:
    db_path = _init_db(cli_runner, tmp_path)

    sys_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="SYS",
        name="Engine Thermal Management System",
    )
    sub_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="SUB",
        name="Cooling Fan System",
        parent=sys_payload["data"]["node_id"],
    )
    controller_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Electronic Cooling Fan Controller",
        parent=sub_payload["data"]["node_id"],
    )
    motor_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Cooling Fan Motor Assembly",
        parent=sub_payload["data"]["node_id"],
    )
    sensor_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Coolant Temperature Sensing Path",
        parent=sub_payload["data"]["node_id"],
    )

    controller_start_fn = _add_function(
        cli_runner,
        db_path,
        comp=controller_payload["data"]["node_id"],
        name="Control fan start and stop",
        description="Command fan start and stop according to cooling demand",
    )
    controller_speed_fn = _add_function(
        cli_runner,
        db_path,
        comp=controller_payload["data"]["node_id"],
        name="Modulate fan speed",
        description="Adjust commanded fan speed to meet heat rejection demand",
    )
    controller_protect_fn = _add_function(
        cli_runner,
        db_path,
        comp=controller_payload["data"]["node_id"],
        name="Enter overtemperature protection and report faults",
        description="Force protection mode and report thermal control faults",
    )
    motor_airflow_fn = _add_function(
        cli_runner,
        db_path,
        comp=motor_payload["data"]["node_id"],
        name="Generate airflow under controller command",
        description="Convert controller command into cooling airflow",
    )
    sensor_signal_fn = _add_function(
        cli_runner,
        db_path,
        comp=sensor_payload["data"]["node_id"],
        name="Provide coolant temperature signal",
        description="Provide coolant temperature feedback to controller logic",
    )

    start_req = _add_requirement(
        cli_runner,
        db_path,
        fn=controller_start_fn["data"]["fn_id"],
        text="Start fan within demanded cooling window",
        source="CTRL-REQ-START",
    )
    start_char = _add_characteristic(
        cli_runner,
        db_path,
        fn=controller_start_fn["data"]["fn_id"],
        text="Fan start response time",
        value="500",
        unit="ms",
    )
    speed_req = _add_requirement(
        cli_runner,
        db_path,
        fn=controller_speed_fn["data"]["fn_id"],
        text="Track requested fan speed across operating range",
        source="CTRL-REQ-SPEED",
    )
    speed_char = _add_characteristic(
        cli_runner,
        db_path,
        fn=controller_speed_fn["data"]["fn_id"],
        text="Fan speed tracking error",
        value="10",
        unit="pct",
    )
    protect_req = _add_requirement(
        cli_runner,
        db_path,
        fn=controller_protect_fn["data"]["fn_id"],
        text="Enter protection mode at calibrated overtemperature threshold",
        source="CTRL-REQ-PROTECT",
    )
    protect_char = _add_characteristic(
        cli_runner,
        db_path,
        fn=controller_protect_fn["data"]["fn_id"],
        text="Protection threshold accuracy",
        value="2",
        unit="degC",
    )

    chain_start = _add_failure_chain(
        cli_runner,
        db_path,
        fn=controller_start_fn["data"]["fn_id"],
        extra_args=[
            "--fm-description",
            "Fan not started when cooling requested",
            "--severity",
            "8",
            "--violates-req",
            str(start_req["data"]["req_rowid"]),
            "--related-char",
            str(start_char["data"]["char_rowid"]),
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
            "--target-causes",
            "1,2",
        ],
    )
    chain_speed = _add_failure_chain(
        cli_runner,
        db_path,
        fn=controller_speed_fn["data"]["fn_id"],
        extra_args=[
            "--fm-description",
            "Fan speed below target",
            "--severity",
            "7",
            "--violates-req",
            str(speed_req["data"]["req_rowid"]),
            "--related-char",
            str(speed_char["data"]["char_rowid"]),
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
            "--target-causes",
            "1,2",
        ],
    )
    chain_protect = _add_failure_chain(
        cli_runner,
        db_path,
        fn=controller_protect_fn["data"]["fn_id"],
        extra_args=[
            "--fm-description",
            "Overtemperature protection not entered",
            "--severity",
            "9",
            "--violates-req",
            str(protect_req["data"]["req_rowid"]),
            "--related-char",
            str(protect_char["data"]["char_rowid"]),
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
            "--target-causes",
            "1,2",
        ],
    )
    chain_motor = _add_failure_chain(
        cli_runner,
        db_path,
        fn=motor_airflow_fn["data"]["fn_id"],
        extra_args=[
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
            "--target-causes",
            "1",
        ],
    )
    chain_sensor = _add_failure_chain(
        cli_runner,
        db_path,
        fn=sensor_signal_fn["data"]["fn_id"],
        extra_args=[
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
            "--target-causes",
            "1",
        ],
    )

    fc_temp_signal_frozen = _affected_object(chain_start, "FC", ordinal=1)
    fc_driver_output_stuck = _affected_object(chain_start, "FC", ordinal=2)
    fc_overtemperature_threshold_high = _affected_object(chain_protect, "FC", ordinal=1)
    fe_airflow_not_established = _affected_object(chain_start, "FE")
    fc_motor_bearing_drag = _affected_object(chain_motor, "FC")
    fc_sensor_pullup_open_circuit = _affected_object(chain_sensor, "FC")
    fe_controller_underestimates_demand = _affected_object(chain_sensor, "FE")

    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fc:{fc_temp_signal_frozen['rowid']}",
        to_fm=chain_sensor["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fe:{fe_controller_underestimates_demand['rowid']}",
        to_fm=chain_start["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fe:{fe_airflow_not_established['rowid']}",
        to_fm=chain_motor["data"]["fm_id"],
    )

    return RealisticCoolingFanProjectSeed(
        db_path=db_path,
        project_id="demo",
        controller_comp_id=controller_payload["data"]["node_id"],
        motor_comp_id=motor_payload["data"]["node_id"],
        sensor_comp_id=sensor_payload["data"]["node_id"],
        controller_start_fn_id=controller_start_fn["data"]["fn_id"],
        controller_speed_fn_id=controller_speed_fn["data"]["fn_id"],
        controller_protect_fn_id=controller_protect_fn["data"]["fn_id"],
        motor_airflow_fn_id=motor_airflow_fn["data"]["fn_id"],
        sensor_signal_fn_id=sensor_signal_fn["data"]["fn_id"],
        fm_missed_start_id=chain_start["data"]["fm_id"],
        fm_low_speed_id=chain_speed["data"]["fm_id"],
        fm_no_protection_id=chain_protect["data"]["fm_id"],
        fm_low_airflow_id=chain_motor["data"]["fm_id"],
        fm_temp_signal_biased_id=chain_sensor["data"]["fm_id"],
        fc_temp_signal_frozen_rowid=fc_temp_signal_frozen["rowid"],
        fc_motor_bearing_drag_rowid=fc_motor_bearing_drag["rowid"],
        fc_driver_output_stuck_rowid=fc_driver_output_stuck["rowid"],
        fc_overtemperature_threshold_high_rowid=(
            fc_overtemperature_threshold_high["rowid"]
        ),
        fc_sensor_pullup_open_circuit_rowid=(fc_sensor_pullup_open_circuit["rowid"]),
        fe_controller_underestimates_demand_rowid=(
            fe_controller_underestimates_demand["rowid"]
        ),
        fe_airflow_not_established_rowid=fe_airflow_not_established["rowid"],
        act_start_id=_affected_object(chain_start, "ACT")["id"],
        act_speed_id=_affected_object(chain_speed, "ACT")["id"],
        act_protect_id=_affected_object(chain_protect, "ACT")["id"],
        act_motor_id=_affected_object(chain_motor, "ACT")["id"],
        act_sensor_id=_affected_object(chain_sensor, "ACT")["id"],
    )
