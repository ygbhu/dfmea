from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "trace.db"
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


def _affected_object(payload: dict, node_type: str, *, ordinal: int = 1) -> dict:
    matches = [
        item
        for item in payload["data"]["affected_objects"]
        if item["type"] == node_type
    ]
    return matches[ordinal - 1]


def _seed_trace_db(cli_runner, tmp_path: Path) -> dict:
    db_path = _init_db(cli_runner, tmp_path)
    sys_payload = _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    sub_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="SUB",
        name="Powertrain",
        parent=sys_payload["data"]["node_id"],
    )
    inverter_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Inverter",
        parent=sub_payload["data"]["node_id"],
    )
    rotor_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Rotor",
        parent=sub_payload["data"]["node_id"],
    )
    bearing_payload = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Bearing",
        parent=sub_payload["data"]["node_id"],
    )

    fn_one = _add_function(
        cli_runner,
        db_path,
        comp=inverter_payload["data"]["node_id"],
        name="Deliver torque",
        description="Provide rated torque",
    )
    fn_two = _add_function(
        cli_runner,
        db_path,
        comp=rotor_payload["data"]["node_id"],
        name="Support rotation",
        description="Maintain stable rotor motion",
    )
    fn_three = _add_function(
        cli_runner,
        db_path,
        comp=bearing_payload["data"]["node_id"],
        name="Support shaft",
        description="Maintain bearing lubrication",
    )

    chain_one = _add_failure_chain(
        cli_runner,
        db_path,
        fn=fn_one["data"]["fn_id"],
        extra_args=[
            "--fm-description",
            "Torque too low",
            "--severity",
            "8",
            "--fc-description",
            "Motor drag",
            "--occurrence",
            "4",
            "--detection",
            "3",
            "--ap",
            "High",
        ],
    )
    chain_two = _add_failure_chain(
        cli_runner,
        db_path,
        fn=fn_two["data"]["fn_id"],
        extra_args=[
            "--fm-description",
            "Rotor friction high",
            "--severity",
            "7",
            "--fe-description",
            "Motor drag",
            "--fe-level",
            "component",
            "--fc-description",
            "Bearing wear",
            "--occurrence",
            "5",
            "--detection",
            "4",
            "--ap",
            "High",
        ],
    )
    chain_three = _add_failure_chain(
        cli_runner,
        db_path,
        fn=fn_three["data"]["fn_id"],
        extra_args=[
            "--fm-description",
            "Lubrication loss",
            "--severity",
            "6",
            "--fe-description",
            "Bearing wear",
            "--fe-level",
            "component",
        ],
    )

    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fc:{_affected_object(chain_one, 'FC')['rowid']}",
        to_fm=chain_two["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fc:{_affected_object(chain_two, 'FC')['rowid']}",
        to_fm=chain_three["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fe:{_affected_object(chain_three, 'FE')['rowid']}",
        to_fm=chain_two["data"]["fm_id"],
    )
    _link_trace(
        cli_runner,
        db_path,
        from_ref=f"fe:{_affected_object(chain_two, 'FE')['rowid']}",
        to_fm=chain_one["data"]["fm_id"],
    )

    return {
        "db_path": db_path,
        "fm_one_id": chain_one["data"]["fm_id"],
        "fm_one_rowid": chain_one["data"]["fm_rowid"],
        "fm_two_id": chain_two["data"]["fm_id"],
        "fm_two_rowid": chain_two["data"]["fm_rowid"],
        "fm_three_id": chain_three["data"]["fm_id"],
        "fm_three_rowid": chain_three["data"]["fm_rowid"],
        "fm_one_fc_rowid": _affected_object(chain_one, "FC")["rowid"],
        "fm_two_fc_rowid": _affected_object(chain_two, "FC")["rowid"],
        "fm_two_fe_rowid": _affected_object(chain_two, "FE")["rowid"],
        "fm_three_fe_rowid": _affected_object(chain_three, "FE")["rowid"],
    }


def test_trace_causes_returns_depth_annotated_recursive_chain(
    cli_runner, tmp_path: Path
):
    seeded = _seed_trace_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "trace",
            "causes",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            seeded["fm_one_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "trace causes"
    assert payload["data"]["project_id"] == "demo"
    assert [item["fm"]["id"] for item in payload["data"]["chain"]] == [
        seeded["fm_one_id"],
        seeded["fm_two_id"],
        seeded["fm_three_id"],
    ]
    assert [item["depth"] for item in payload["data"]["chain"]] == [0, 1, 2]
    assert payload["data"]["chain"][0]["via"] is None
    assert payload["data"]["chain"][1]["via"] == {
        "rowid": seeded["fm_one_fc_rowid"],
        "id": None,
        "type": "FC",
        "project_id": "demo",
        "name": "Motor drag",
        "parent": {
            "rowid": seeded["fm_one_rowid"],
            "id": seeded["fm_one_id"],
            "type": "FM",
            "name": "Torque too low",
        },
        "data": {"ap": "High", "detection": 3, "occurrence": 4},
    }
    assert payload["data"]["chain"][2]["via"]["name"] == "Bearing wear"


def test_trace_effects_returns_depth_annotated_recursive_chain(
    cli_runner, tmp_path: Path
):
    seeded = _seed_trace_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "trace",
            "effects",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            seeded["fm_three_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "trace effects"
    assert [item["fm"]["id"] for item in payload["data"]["chain"]] == [
        seeded["fm_three_id"],
        seeded["fm_two_id"],
        seeded["fm_one_id"],
    ]
    assert [item["depth"] for item in payload["data"]["chain"]] == [0, 1, 2]
    assert payload["data"]["chain"][1]["via"]["type"] == "FE"
    assert payload["data"]["chain"][1]["via"]["rowid"] == seeded["fm_three_fe_rowid"]
    assert payload["data"]["chain"][2]["via"]["rowid"] == seeded["fm_two_fe_rowid"]


def test_trace_depth_limit_is_respected(cli_runner, tmp_path: Path):
    seeded = _seed_trace_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "trace",
            "causes",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            seeded["fm_one_id"],
            "--depth",
            "1",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "trace causes"
    assert [item["fm"]["id"] for item in payload["data"]["chain"]] == [
        seeded["fm_one_id"],
        seeded["fm_two_id"],
    ]
    assert [item["depth"] for item in payload["data"]["chain"]] == [0, 1]


def test_trace_missing_fm_target_fails_structurally(cli_runner, tmp_path: Path):
    seeded = _seed_trace_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "trace",
            "causes",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            "FM-999",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "trace causes"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"node": "FM-999", "project_id": "demo"}


def test_trace_causes_malformed_traced_node_json_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    seeded = _seed_trace_db(cli_runner, tmp_path)

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute(
            "UPDATE nodes SET data = ? WHERE id = ?", ("{broken", seeded["fm_two_id"])
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "trace",
            "causes",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            seeded["fm_one_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "trace causes"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "malformed JSON" in payload["errors"][0]["message"]


def test_trace_effects_dangling_trace_link_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    seeded = _seed_trace_db(cli_runner, tmp_path)

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("DELETE FROM nodes WHERE rowid = ?", (seeded["fm_two_rowid"],))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "trace",
            "effects",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            seeded["fm_three_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "trace effects"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "from_rowid": seeded["fm_three_fe_rowid"],
        "to_fm_rowid": seeded["fm_two_rowid"],
        "project_id": "demo",
    }
    assert "dangling" in payload["errors"][0]["message"].lower()
