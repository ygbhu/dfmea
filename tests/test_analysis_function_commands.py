from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _payload(result) -> dict:
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "analysis.db"
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


def _create_component_tree(cli_runner, tmp_path: Path) -> Path:
    db_path = _init_db(cli_runner, tmp_path)
    sys_result = _add_structure(cli_runner, db_path, node_type="SYS", name="Drive")
    assert sys_result.exit_code == 0
    sub_result = _add_structure(
        cli_runner,
        db_path,
        node_type="SUB",
        name="Inverter",
        parent=_payload(sys_result)["data"]["node_id"],
    )
    assert sub_result.exit_code == 0
    comp_result = _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Stator",
        parent=_payload(sub_result)["data"]["node_id"],
    )
    assert comp_result.exit_code == 0
    return db_path


def _add_function(cli_runner, db_path: Path, *, comp: str = "COMP-001"):
    return cli_runner.invoke(
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            comp,
            "--name",
            "Deliver torque",
            "--description",
            "Provide rated torque",
            "--format",
            "json",
        ]
    )


def _add_requirement(cli_runner, db_path: Path, *, fn: str = "FN-001"):
    return cli_runner.invoke(
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            fn,
            "--text",
            "Meet 300 Nm output",
            "--source",
            "SYS-REQ-1",
            "--format",
            "json",
        ]
    )


def _add_characteristic(cli_runner, db_path: Path, *, fn: str = "FN-001"):
    return cli_runner.invoke(
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            fn,
            "--text",
            "Torque output",
            "--value",
            "300",
            "--unit",
            "Nm",
            "--format",
            "json",
        ]
    )


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


def test_add_function_returns_fn_identity_and_stores_under_component(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)

    result = _add_function(cli_runner, db_path)

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis add-function"
    assert payload["data"]["fn_id"] == "FN-001"
    assert payload["data"]["parent_comp_id"] == "COMP-001"
    assert payload["data"]["affected_objects"] == [
        {"type": "FN", "id": "FN-001", "rowid": 4}
    ]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT rowid, id, type, parent_id, project_id, name, data FROM nodes WHERE id = ?",
            ("FN-001",),
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        4,
        "FN-001",
        "FN",
        3,
        "demo",
        "Deliver torque",
        '{"description": "Provide rated torque"}',
    )
    assert _project_data(db_path)["canonical_revision"] == 4
    assert _project_data(db_path)["projection_dirty"] is True


def test_update_function_updates_name_and_description(cli_runner, tmp_path: Path):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_result = _add_function(cli_runner, db_path)
    assert add_result.exit_code == 0

    result = cli_runner.invoke(
        [
            "analysis",
            "update-function",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--name",
            "Transmit torque",
            "--description",
            "Sustain rated torque output",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis update-function"
    assert payload["data"]["fn_id"] == "FN-001"
    assert payload["data"]["affected_objects"] == [
        {"type": "FN", "id": "FN-001", "rowid": 4}
    ]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name, data FROM nodes WHERE id = ?",
            ("FN-001",),
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        "Transmit torque",
        '{"description": "Sustain rated torque output"}',
    )


def test_add_update_delete_requirement_by_rowid(cli_runner, tmp_path: Path):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_function_result = _add_function(cli_runner, db_path)
    assert add_function_result.exit_code == 0

    add_result = cli_runner.invoke(
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--text",
            "Meet 300 Nm output",
            "--source",
            "SYS-REQ-1",
            "--format",
            "json",
        ]
    )

    assert add_result.exit_code == 0
    add_payload = _payload(add_result)
    req_rowid = add_payload["data"]["req_rowid"]
    assert add_payload["command"] == "analysis add-requirement"
    assert add_payload["data"]["fn_id"] == "FN-001"
    assert add_payload["data"]["affected_objects"] == [
        {"type": "REQ", "rowid": req_rowid}
    ]

    update_result = cli_runner.invoke(
        [
            "analysis",
            "update-requirement",
            "--db",
            str(db_path),
            "--req",
            str(req_rowid),
            "--text",
            "Meet 320 Nm output",
            "--source",
            "SYS-REQ-2",
            "--format",
            "json",
        ]
    )

    assert update_result.exit_code == 0
    update_payload = _payload(update_result)
    assert update_payload["command"] == "analysis update-requirement"
    assert update_payload["data"]["req_rowid"] == req_rowid
    assert update_payload["data"]["affected_objects"] == [
        {"type": "REQ", "rowid": req_rowid}
    ]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, type, parent_id, project_id, name, data FROM nodes WHERE rowid = ?",
            (req_rowid,),
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        None,
        "REQ",
        4,
        "demo",
        "Meet 320 Nm output",
        '{"source": "SYS-REQ-2"}',
    )

    delete_result = cli_runner.invoke(
        [
            "analysis",
            "delete-requirement",
            "--db",
            str(db_path),
            "--req",
            str(req_rowid),
            "--format",
            "json",
        ]
    )

    assert delete_result.exit_code == 0
    delete_payload = _payload(delete_result)
    assert delete_payload["command"] == "analysis delete-requirement"
    assert delete_payload["data"]["req_rowid"] == req_rowid
    assert delete_payload["data"]["affected_objects"] == [
        {"type": "REQ", "rowid": req_rowid}
    ]

    conn = sqlite3.connect(db_path)
    try:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE rowid = ?",
            (req_rowid,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert remaining == 0
    assert _project_data(db_path)["canonical_revision"] == 7
    assert _project_data(db_path)["projection_dirty"] is True


def test_add_update_delete_characteristic_by_rowid(cli_runner, tmp_path: Path):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_function_result = _add_function(cli_runner, db_path)
    assert add_function_result.exit_code == 0

    add_result = cli_runner.invoke(
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--text",
            "Torque output",
            "--value",
            "300",
            "--unit",
            "Nm",
            "--format",
            "json",
        ]
    )

    assert add_result.exit_code == 0
    add_payload = _payload(add_result)
    char_rowid = add_payload["data"]["char_rowid"]
    assert add_payload["command"] == "analysis add-characteristic"
    assert add_payload["data"]["fn_id"] == "FN-001"
    assert add_payload["data"]["affected_objects"] == [
        {"type": "CHAR", "rowid": char_rowid}
    ]

    update_result = cli_runner.invoke(
        [
            "analysis",
            "update-characteristic",
            "--db",
            str(db_path),
            "--char",
            str(char_rowid),
            "--text",
            "Rated torque output",
            "--value",
            "320",
            "--unit",
            "Nm",
            "--format",
            "json",
        ]
    )

    assert update_result.exit_code == 0
    update_payload = _payload(update_result)
    assert update_payload["command"] == "analysis update-characteristic"
    assert update_payload["data"]["char_rowid"] == char_rowid
    assert update_payload["data"]["affected_objects"] == [
        {"type": "CHAR", "rowid": char_rowid}
    ]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, type, parent_id, project_id, name, data FROM nodes WHERE rowid = ?",
            (char_rowid,),
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        None,
        "CHAR",
        4,
        "demo",
        "Rated torque output",
        '{"unit": "Nm", "value": "320"}',
    )

    delete_result = cli_runner.invoke(
        [
            "analysis",
            "delete-characteristic",
            "--db",
            str(db_path),
            "--char",
            str(char_rowid),
            "--format",
            "json",
        ]
    )

    assert delete_result.exit_code == 0
    delete_payload = _payload(delete_result)
    assert delete_payload["command"] == "analysis delete-characteristic"
    assert delete_payload["data"]["char_rowid"] == char_rowid
    assert delete_payload["data"]["affected_objects"] == [
        {"type": "CHAR", "rowid": char_rowid}
    ]

    conn = sqlite3.connect(db_path)
    try:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE rowid = ?",
            (char_rowid,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert remaining == 0


def test_add_function_on_non_component_parent_fails_structurally(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)

    result = _add_function(cli_runner, db_path, comp="SUB-001")

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-function"
    assert payload["errors"][0]["code"] == "INVALID_PARENT"
    assert payload["errors"][0]["target"] == {
        "node_type": "FN",
        "parent_ref": "SUB-001",
        "parent_type": "SUB",
    }


def test_function_ids_are_not_reused_after_delete(cli_runner, tmp_path: Path):
    db_path = _create_component_tree(cli_runner, tmp_path)

    first_result = _add_function(cli_runner, db_path)
    assert first_result.exit_code == 0
    assert _payload(first_result)["data"]["fn_id"] == "FN-001"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM nodes WHERE id = ?", ("FN-001",))
        conn.commit()
    finally:
        conn.close()

    second_result = cli_runner.invoke(
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            "COMP-001",
            "--name",
            "Deliver backup torque",
            "--description",
            "Provide degraded torque",
            "--format",
            "json",
        ]
    )

    assert second_result.exit_code == 0
    second_payload = _payload(second_result)
    assert second_payload["data"]["fn_id"] == "FN-002"


def test_update_function_with_malformed_json_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_result = _add_function(cli_runner, db_path)
    assert add_result.exit_code == 0

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE nodes SET data = ? WHERE id = ?", ("{bad-json", "FN-001"))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "analysis",
            "update-function",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--name",
            "Transmit torque",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-function"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["meta"]["project_id"] == "demo"


def test_update_function_without_mutable_fields_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_result = _add_function(cli_runner, db_path)
    assert add_result.exit_code == 0

    result = cli_runner.invoke(
        [
            "analysis",
            "update-function",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-function"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "at least one" in payload["errors"][0]["message"].lower()


def test_update_requirement_without_mutable_fields_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_function_result = _add_function(cli_runner, db_path)
    assert add_function_result.exit_code == 0
    add_requirement_result = _add_requirement(cli_runner, db_path)
    assert add_requirement_result.exit_code == 0
    req_rowid = _payload(add_requirement_result)["data"]["req_rowid"]

    result = cli_runner.invoke(
        [
            "analysis",
            "update-requirement",
            "--db",
            str(db_path),
            "--req",
            str(req_rowid),
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-requirement"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "at least one" in payload["errors"][0]["message"].lower()


def test_update_characteristic_without_mutable_fields_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_function_result = _add_function(cli_runner, db_path)
    assert add_function_result.exit_code == 0
    add_characteristic_result = _add_characteristic(cli_runner, db_path)
    assert add_characteristic_result.exit_code == 0
    char_rowid = _payload(add_characteristic_result)["data"]["char_rowid"]

    result = cli_runner.invoke(
        [
            "analysis",
            "update-characteristic",
            "--db",
            str(db_path),
            "--char",
            str(char_rowid),
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-characteristic"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "at least one" in payload["errors"][0]["message"].lower()


def test_update_requirement_with_malformed_json_uses_analysis_wording(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_function_result = _add_function(cli_runner, db_path)
    assert add_function_result.exit_code == 0
    add_requirement_result = _add_requirement(cli_runner, db_path)
    assert add_requirement_result.exit_code == 0
    req_rowid = _payload(add_requirement_result)["data"]["req_rowid"]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE nodes SET data = ? WHERE rowid = ?", ("{bad-json", req_rowid)
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "analysis",
            "update-requirement",
            "--db",
            str(db_path),
            "--req",
            str(req_rowid),
            "--text",
            "Meet 320 Nm output",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-requirement"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "requirement" in payload["errors"][0]["message"].lower()
    assert "structure" not in payload["errors"][0]["message"].lower()


def test_update_characteristic_with_malformed_json_uses_analysis_wording(
    cli_runner, tmp_path: Path
):
    db_path = _create_component_tree(cli_runner, tmp_path)
    add_function_result = _add_function(cli_runner, db_path)
    assert add_function_result.exit_code == 0
    add_characteristic_result = _add_characteristic(cli_runner, db_path)
    assert add_characteristic_result.exit_code == 0
    char_rowid = _payload(add_characteristic_result)["data"]["char_rowid"]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE nodes SET data = ? WHERE rowid = ?", ("{bad-json", char_rowid)
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "analysis",
            "update-characteristic",
            "--db",
            str(db_path),
            "--char",
            str(char_rowid),
            "--text",
            "Rated torque output",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["command"] == "analysis update-characteristic"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "characteristic" in payload["errors"][0]["message"].lower()
    assert "structure" not in payload["errors"][0]["message"].lower()
