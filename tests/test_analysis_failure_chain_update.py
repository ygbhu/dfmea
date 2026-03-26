from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _json_payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "analysis-update.db"
    result = cli_runner.invoke(
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--name",
            "Demo",
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
    return _json_payload(result)


def _create_function_db(cli_runner, tmp_path: Path) -> Path:
    db_path = _init_db(cli_runner, tmp_path)
    sys_payload = _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    sub_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="SUB",
        name="Inverter",
        parent=sys_payload["data"]["node_id"],
    )
    comp_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Stator",
        parent=sub_payload["data"]["node_id"],
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            comp_payload["data"]["node_id"],
            "--name",
            "Deliver torque",
            "--description",
            "Provide rated torque",
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.stdout
    return db_path


def _add_failure_chain(cli_runner, db_path: Path, *extra_args: str) -> dict:
    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            *extra_args,
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.stdout
    return _json_payload(result)


def _update_act(cli_runner, db_path: Path, *extra_args: str):
    return cli_runner.invoke(
        [
            "analysis",
            "update-act",
            "--db",
            str(db_path),
            "--act",
            "ACT-001",
            *extra_args,
            "--format",
            "json",
        ]
    )


def _affected_rowid(payload: dict, node_type: str, *, ordinal: int = 1) -> int:
    matches = [
        obj["rowid"]
        for obj in payload["data"]["affected_objects"]
        if obj["type"] == node_type
    ]
    return matches[ordinal - 1]


def _project_data(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?", ("demo",)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return json.loads(row[0])


def test_update_action_status_returns_completed(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--fc-description",
        "Winding short",
        "--occurrence",
        "4",
        "--detection",
        "3",
        "--ap",
        "High",
        "--act-description",
        "Add screening",
        "--kind",
        "detection",
        "--status",
        "planned",
        "--owner",
        "Chen",
        "--due",
        "2026-06-15",
        "--target-causes",
        "1",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "update-action-status",
            "--db",
            str(db_path),
            "--act",
            "ACT-001",
            "--status",
            "completed",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis update-action-status"
    assert payload["data"] == {
        "project_id": "demo",
        "fm_id": "FM-001",
        "act_id": "ACT-001",
        "act_rowid": 7,
        "affected_objects": [{"type": "ACT", "id": "ACT-001", "rowid": 7}],
    }

    conn = sqlite3.connect(db_path)
    try:
        act_row = conn.execute(
            "SELECT name, data FROM nodes WHERE id = ?", ("ACT-001",)
        ).fetchone()
    finally:
        conn.close()

    assert act_row == (
        "Add screening",
        '{"due": "2026-06-15", "kind": "detection", "owner": "Chen", "status": "completed", "target_causes": [6]}',
    )
    assert _project_data(db_path)["canonical_revision"] == 6
    assert _project_data(db_path)["projection_dirty"] is True


def test_update_fm_updates_description_and_severity(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    create_payload = _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "update-fm",
            "--db",
            str(db_path),
            "--fm",
            create_payload["data"]["fm_id"],
            "--description",
            "Torque output too low",
            "--severity",
            "6",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis update-fm"
    assert payload["data"] == {
        "project_id": "demo",
        "fn_id": "FN-001",
        "fm_id": "FM-001",
        "fm_rowid": 5,
        "affected_objects": [{"type": "FM", "id": "FM-001", "rowid": 5}],
    }

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name, data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()
    finally:
        conn.close()

    assert row == ("Torque output too low", '{"severity": 6}')


def test_update_fe_updates_description_and_level(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    create_payload = _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--fe-description",
        "Vehicle acceleration reduced",
        "--fe-level",
        "vehicle",
    )
    fe_rowid = _affected_rowid(create_payload, "FE")

    result = cli_runner.invoke(
        [
            "analysis",
            "update-fe",
            "--db",
            str(db_path),
            "--fe",
            str(fe_rowid),
            "--description",
            "Vehicle launch delayed",
            "--level",
            "system",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis update-fe"
    assert payload["data"] == {
        "project_id": "demo",
        "fm_id": "FM-001",
        "fe_rowid": fe_rowid,
        "affected_objects": [{"type": "FE", "rowid": fe_rowid}],
    }

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name, data FROM nodes WHERE rowid = ?", (fe_rowid,)
        ).fetchone()
    finally:
        conn.close()

    assert row == ("Vehicle launch delayed", '{"level": "system"}')


def test_update_fc_updates_description_and_rankings(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    create_payload = _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--fc-description",
        "Winding short",
        "--occurrence",
        "4",
        "--detection",
        "3",
        "--ap",
        "High",
    )
    fc_rowid = _affected_rowid(create_payload, "FC")

    result = cli_runner.invoke(
        [
            "analysis",
            "update-fc",
            "--db",
            str(db_path),
            "--fc",
            str(fc_rowid),
            "--description",
            "Solder crack",
            "--occurrence",
            "2",
            "--detection",
            "6",
            "--ap",
            "Medium",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis update-fc"
    assert payload["data"] == {
        "project_id": "demo",
        "fm_id": "FM-001",
        "fc_rowid": fc_rowid,
        "affected_objects": [{"type": "FC", "rowid": fc_rowid}],
    }

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name, data FROM nodes WHERE rowid = ?", (fc_rowid,)
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        "Solder crack",
        '{"ap": "Medium", "detection": 6, "occurrence": 2}',
    )


def test_update_act_updates_metadata_and_target_causes(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    create_payload = _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--fc-description",
        "Winding short",
        "--occurrence",
        "4",
        "--detection",
        "3",
        "--ap",
        "High",
        "--fc-description",
        "Solder crack",
        "--occurrence",
        "2",
        "--detection",
        "6",
        "--ap",
        "Medium",
        "--act-description",
        "Add screening",
        "--kind",
        "detection",
        "--status",
        "planned",
        "--owner",
        "Chen",
        "--due",
        "2026-06-15",
        "--target-causes",
        "1",
    )
    fc_first = _affected_rowid(create_payload, "FC", ordinal=1)
    fc_second = _affected_rowid(create_payload, "FC", ordinal=2)

    result = cli_runner.invoke(
        [
            "analysis",
            "update-act",
            "--db",
            str(db_path),
            "--act",
            "ACT-001",
            "--description",
            "Tighten screening window",
            "--kind",
            "prevention",
            "--status",
            "in-progress",
            "--owner",
            "Li",
            "--due",
            "2026-07-01",
            "--target-causes",
            f"{fc_first},{fc_second}",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis update-act"
    assert payload["data"] == {
        "project_id": "demo",
        "fm_id": "FM-001",
        "act_id": "ACT-001",
        "act_rowid": 8,
        "affected_objects": [{"type": "ACT", "id": "ACT-001", "rowid": 8}],
    }

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name, data FROM nodes WHERE id = ?", ("ACT-001",)
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        "Tighten screening window",
        (
            '{"due": "2026-07-01", "kind": "prevention", "owner": "Li", '
            f'"status": "in-progress", "target_causes": [{fc_first}, {fc_second}]}}'
        ),
    )


def test_update_fm_with_malformed_json_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE nodes SET data = ? WHERE id = ?", ("{bad-json", "FM-001"))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "analysis",
            "update-fm",
            "--db",
            str(db_path),
            "--fm",
            "FM-001",
            "--severity",
            "6",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _json_payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-fm"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["meta"]["project_id"] == "demo"


def test_update_act_target_causes_parse_errors_use_rowid_wording(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--fc-description",
        "Winding short",
        "--occurrence",
        "4",
        "--detection",
        "3",
        "--ap",
        "High",
        "--act-description",
        "Add screening",
        "--kind",
        "detection",
        "--status",
        "planned",
        "--owner",
        "Chen",
        "--due",
        "2026-06-15",
        "--target-causes",
        "1",
    )

    result = _update_act(cli_runner, db_path, "--target-causes", "6,not-a-rowid")

    assert result.exit_code != 0
    payload = _json_payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-act"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "field": "--target-causes",
        "value": "6,not-a-rowid",
    }
    assert "rowid" in payload["errors"][0]["message"].lower()
    assert "creation-order" not in payload["errors"][0]["message"].lower()
