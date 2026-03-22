from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "structure.db"
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
    assert result.exit_code == 0
    return db_path


def _payload(result) -> dict:
    return json.loads(result.stdout)


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
    return cli_runner.invoke(args)


def _node_rows(
    db_path: Path,
) -> list[tuple[int, str | None, str, int, str, str | None, str]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT rowid, id, type, parent_id, project_id, name, data FROM nodes ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()


def test_add_sys_sub_comp_chain_returns_json(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)

    sys_result = _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    sys_payload = _payload(sys_result)
    sub_result = _add_structure(
        cli_runner,
        db_path,
        node_type="SUB",
        name="Inverter",
        parent=sys_payload["data"]["node_id"],
    )
    sub_payload = _payload(sub_result)
    comp_result = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Stator",
        parent=sub_payload["data"]["node_id"],
    )
    comp_payload = _payload(comp_result)

    assert sys_result.exit_code == 0
    assert sys_payload["contract_version"] == "1.0"
    assert sys_payload["ok"] is True
    assert sys_payload["command"] == "structure add"
    assert sys_payload["data"]["node_id"] == "SYS-001"
    assert sys_payload["data"]["affected_objects"] == [
        {"type": "SYS", "id": "SYS-001", "rowid": 1}
    ]

    assert sub_result.exit_code == 0
    assert sub_payload["contract_version"] == "1.0"
    assert sub_payload["ok"] is True
    assert sub_payload["command"] == "structure add"
    assert sub_payload["data"]["node_id"] == "SUB-001"
    assert sub_payload["data"]["parent_id"] == "SYS-001"

    assert comp_result.exit_code == 0
    assert comp_payload["contract_version"] == "1.0"
    assert comp_payload["ok"] is True
    assert comp_payload["command"] == "structure add"
    assert comp_payload["data"]["node_id"] == "COMP-001"
    assert comp_payload["data"]["parent_id"] == "SUB-001"

    assert _node_rows(db_path) == [
        (1, "SYS-001", "SYS", 0, "demo", "Drive", "{}"),
        (2, "SUB-001", "SUB", 1, "demo", "Inverter", "{}"),
        (3, "COMP-001", "COMP", 2, "demo", "Stator", "{}"),
    ]


def test_update_structure_node_metadata_success(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")

    result = cli_runner.invoke(
        [
            "structure",
            "update",
            "--db",
            str(db_path),
            "--node",
            "SYS-001",
            "--name",
            "E-Drive",
            "--description",
            "Electric drive system",
            "--metadata",
            '{"owner":"platform"}',
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "structure update"
    assert payload["data"]["node_id"] == "SYS-001"
    assert payload["data"]["affected_objects"] == [
        {"type": "SYS", "id": "SYS-001", "rowid": 1}
    ]

    rows = _node_rows(db_path)
    assert rows[0][5] == "E-Drive"
    assert json.loads(rows[0][6]) == {
        "description": "Electric drive system",
        "owner": "platform",
    }


def test_move_structure_node_to_legal_parent_success(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    _add_structure(cli_runner, db_path, node_type="SYS", name="Battery")
    _add_structure(
        cli_runner, db_path, node_type="SUB", name="Inverter", parent="SYS-001"
    )

    result = cli_runner.invoke(
        [
            "structure",
            "move",
            "--db",
            str(db_path),
            "--node",
            "SUB-001",
            "--parent",
            "SYS-002",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "structure move"
    assert payload["data"]["node_id"] == "SUB-001"
    assert payload["data"]["parent_id"] == "SYS-002"

    rows = _node_rows(db_path)
    assert rows[2][3] == 2


def test_illegal_parent_fails_with_structured_error(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")

    result = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Stator",
        parent="SYS-001",
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "structure add"
    assert payload["errors"][0]["code"] == "INVALID_PARENT"
    assert payload["errors"][0]["target"] == {
        "node_type": "COMP",
        "parent_ref": "SYS-001",
        "parent_type": "SYS",
    }


def test_delete_non_empty_component_returns_node_not_empty(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    _add_structure(
        cli_runner, db_path, node_type="SUB", name="Inverter", parent="SYS-001"
    )
    _add_structure(
        cli_runner, db_path, node_type="COMP", name="Stator", parent="SUB-001"
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "FN-001",
                "FN",
                3,
                "demo",
                "Deliver torque",
                '{"description":"Provide rated torque"}',
                "2026-03-21T00:00:00+00:00",
                "2026-03-21T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "structure",
            "delete",
            "--db",
            str(db_path),
            "--node",
            "COMP-001",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "structure delete"
    assert payload["errors"][0]["code"] == "NODE_NOT_EMPTY"
    assert payload["errors"][0]["target"] == {
        "type": "COMP",
        "id": "COMP-001",
        "rowid": 3,
    }


def test_delete_empty_node_succeeds(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    _add_structure(
        cli_runner, db_path, node_type="SUB", name="Inverter", parent="SYS-001"
    )
    _add_structure(
        cli_runner, db_path, node_type="COMP", name="Stator", parent="SUB-001"
    )

    result = cli_runner.invoke(
        [
            "structure",
            "delete",
            "--db",
            str(db_path),
            "--node",
            "COMP-001",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "structure delete"
    assert payload["data"]["node_id"] == "COMP-001"
    assert payload["data"]["affected_objects"] == [
        {"type": "COMP", "id": "COMP-001", "rowid": 3}
    ]
    assert [row[1] for row in _node_rows(db_path)] == ["SYS-001", "SUB-001"]


def test_structure_ids_are_not_reused_after_delete(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)

    first_result = _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    assert first_result.exit_code == 0
    first_payload = _payload(first_result)
    assert first_payload["data"]["node_id"] == "SYS-001"

    delete_result = cli_runner.invoke(
        [
            "structure",
            "delete",
            "--db",
            str(db_path),
            "--node",
            "SYS-001",
            "--format",
            "json",
        ]
    )
    assert delete_result.exit_code == 0

    second_result = _add_structure(cli_runner, db_path, node_type="SYS", name="Battery")

    assert second_result.exit_code == 0
    second_payload = _payload(second_result)
    assert second_payload["data"]["node_id"] == "SYS-002"
    assert _node_rows(db_path) == [(2, "SYS-002", "SYS", 0, "demo", "Battery", "{}")]


def test_malformed_node_json_returns_structured_failure(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE nodes SET data = ? WHERE id = ?", ("{bad-json", "SYS-001"))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "structure",
            "update",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--node",
            "SYS-001",
            "--name",
            "E-Drive",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "structure update"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["meta"]["project_id"] == "demo"


def test_project_resolution_busy_returns_db_busy(
    cli_runner, tmp_path: Path, monkeypatch
):
    db_path = _init_db(cli_runner, tmp_path)

    def busy_connect(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("dfmea_cli.resolve.sqlite3.connect", busy_connect)
    monkeypatch.setattr("dfmea_cli.db.sqlite3.connect", busy_connect)

    result = cli_runner.invoke(
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--type",
            "SYS",
            "--name",
            "Drive",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 3
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "structure add"
    assert payload["errors"][0]["code"] == "DB_BUSY"
    assert payload["meta"]["project_id"] == "demo"


def test_invalid_metadata_returns_structured_json_failure(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)
    _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")

    result = cli_runner.invoke(
        [
            "structure",
            "update",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--node",
            "SYS-001",
            "--metadata",
            "{bad-json",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "structure update"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["meta"] == {
        "db": str(db_path),
        "project_id": "demo",
        "busy_timeout_ms": 5000,
        "retry": 3,
    }
