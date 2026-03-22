from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _payload(result) -> dict:
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "failure-chain.db"
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


def _create_function_db(cli_runner, tmp_path: Path) -> Path:
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

    function_result = cli_runner.invoke(
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            "COMP-001",
            "--name",
            "Deliver torque",
            "--description",
            "Provide rated torque",
            "--format",
            "json",
        ]
    )
    assert function_result.exit_code == 0
    return db_path


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


def _failure_chain_rows(db_path: Path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT rowid, id, type, parent_id, name, data FROM nodes WHERE type IN ('FM', 'FE', 'FC', 'ACT') ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()


def test_add_failure_chain_repeated_flags_creates_fm_and_fc(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_result = _add_requirement(cli_runner, db_path)
    char_result = _add_characteristic(cli_runner, db_path)
    assert req_result.exit_code == 0
    assert char_result.exit_code == 0

    req_rowid = _payload(req_result)["data"]["req_rowid"]
    char_rowid = _payload(char_result)["data"]["char_rowid"]

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--fm-description",
            "Torque output too low",
            "--severity",
            "7",
            "--violates-req",
            str(req_rowid),
            "--related-char",
            str(char_rowid),
            "--fc-description",
            "Winding short",
            "--occurrence",
            "4",
            "--detection",
            "3",
            "--ap",
            "High",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["data"]["fm_id"] == "FM-001"
    assert payload["data"]["fn_id"] == "FN-001"
    assert payload["data"]["affected_objects"] == [
        {"type": "FM", "id": "FM-001", "rowid": 7},
        {"type": "FC", "rowid": 8},
    ]

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT rowid, id, type, parent_id, name, data FROM nodes ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()

    assert rows[6] == (
        7,
        "FM-001",
        "FM",
        4,
        "Torque output too low",
        json.dumps(
            {
                "related_characteristics": [char_rowid],
                "severity": 7,
                "violates_requirements": [req_rowid],
            },
            sort_keys=True,
        ),
    )
    assert rows[7] == (
        8,
        None,
        "FC",
        7,
        "Winding short",
        '{"ap": "High", "detection": 3, "occurrence": 4}',
    )


def test_add_failure_chain_repeated_flags_target_causes_use_fc_creation_indexes(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
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
            "1,2",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis add-failure-chain"

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT rowid, id, type, parent_id, name, data FROM nodes WHERE rowid >= 5 ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (5, "FM-001", "FM", 4, "Torque output unstable", '{"severity": 8}'),
        (
            6,
            None,
            "FC",
            5,
            "Winding short",
            '{"ap": "High", "detection": 3, "occurrence": 4}',
        ),
        (
            7,
            None,
            "FC",
            5,
            "Solder crack",
            '{"ap": "Medium", "detection": 6, "occurrence": 2}',
        ),
        (
            8,
            "ACT-001",
            "ACT",
            5,
            "Add screening",
            '{"due": "2026-06-15", "kind": "detection", "owner": "Chen", "status": "planned", "target_causes": [6, 7]}',
        ),
    ]


def test_add_failure_chain_repeated_flags_reject_invalid_target_cause_index(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
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
            "2",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"fc_index": 2, "fm": "new"}


def test_add_failure_chain_rejects_input_mixed_with_creation_flags(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    input_path = tmp_path / "mixed-chain.json"
    input_path.write_text(
        json.dumps(
            {"fm": {"description": "Torque output unstable", "severity": 8}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--input",
            str(input_path),
            "--fm-description",
            "Should fail",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "input": str(input_path),
        "conflicts": ["--fm-description"],
    }


def test_add_failure_chain_input_json_creates_full_chain_in_one_transaction(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_result = _add_requirement(cli_runner, db_path)
    char_result = _add_characteristic(cli_runner, db_path)
    assert req_result.exit_code == 0
    assert char_result.exit_code == 0

    req_rowid = _payload(req_result)["data"]["req_rowid"]
    char_rowid = _payload(char_result)["data"]["char_rowid"]
    input_path = tmp_path / "chain.json"
    input_path.write_text(
        json.dumps(
            {
                "fm": {
                    "description": "Torque output unstable",
                    "severity": 8,
                    "violates_requirements": [req_rowid],
                    "related_characteristics": [char_rowid],
                },
                "fe": [
                    {
                        "description": "Vehicle acceleration reduced",
                        "level": "vehicle",
                    }
                ],
                "fc": [
                    {
                        "description": "Winding short",
                        "occurrence": 4,
                        "detection": 3,
                        "ap": "High",
                    },
                    {
                        "description": "Solder crack",
                        "occurrence": 2,
                        "detection": 6,
                        "ap": "Medium",
                    },
                ],
                "act": [
                    {
                        "description": "Upgrade insulation",
                        "kind": "prevention",
                        "status": "planned",
                        "owner": "Li",
                        "due": "2026-06-01",
                        "target_causes": [1],
                    },
                    {
                        "description": "Add end-of-line screening",
                        "kind": "detection",
                        "status": "in-progress",
                        "owner": "Chen",
                        "due": "2026-06-15",
                        "target_causes": [1, 2],
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--input",
            str(input_path),
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["data"] == {
        "project_id": "demo",
        "fn_id": "FN-001",
        "fm_id": "FM-001",
        "fm_rowid": 7,
        "affected_objects": [
            {"type": "FM", "id": "FM-001", "rowid": 7},
            {"type": "FE", "rowid": 8},
            {"type": "FC", "rowid": 9},
            {"type": "FC", "rowid": 10},
            {"type": "ACT", "id": "ACT-001", "rowid": 11},
            {"type": "ACT", "id": "ACT-002", "rowid": 12},
        ],
    }

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT rowid, id, type, parent_id, name, data FROM nodes WHERE rowid >= 7 ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (
            7,
            "FM-001",
            "FM",
            4,
            "Torque output unstable",
            json.dumps(
                {
                    "related_characteristics": [char_rowid],
                    "severity": 8,
                    "violates_requirements": [req_rowid],
                },
                sort_keys=True,
            ),
        ),
        (8, None, "FE", 7, "Vehicle acceleration reduced", '{"level": "vehicle"}'),
        (
            9,
            None,
            "FC",
            7,
            "Winding short",
            '{"ap": "High", "detection": 3, "occurrence": 4}',
        ),
        (
            10,
            None,
            "FC",
            7,
            "Solder crack",
            '{"ap": "Medium", "detection": 6, "occurrence": 2}',
        ),
        (
            11,
            "ACT-001",
            "ACT",
            7,
            "Upgrade insulation",
            '{"due": "2026-06-01", "kind": "prevention", "owner": "Li", "status": "planned", "target_causes": [9]}',
        ),
        (
            12,
            "ACT-002",
            "ACT",
            7,
            "Add end-of-line screening",
            '{"due": "2026-06-15", "kind": "detection", "owner": "Chen", "status": "in-progress", "target_causes": [9, 10]}',
        ),
    ]


def test_add_failure_chain_on_non_fn_parent_fails_structurally(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "COMP-001",
            "--fm-description",
            "Torque output too low",
            "--severity",
            "7",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_PARENT"
    assert payload["errors"][0]["target"] == {
        "node_type": "FM",
        "parent_ref": "COMP-001",
        "parent_type": "COMP",
    }


def test_add_failure_chain_rejects_invalid_req_reference(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--fm-description",
            "Torque output too low",
            "--severity",
            "7",
            "--violates-req",
            "999",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"node": "999", "project_id": "demo"}
    assert _failure_chain_rows(db_path) == []


def test_add_failure_chain_input_json_rejects_float_severity(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    input_path = tmp_path / "float-severity.json"
    input_path.write_text(
        json.dumps(
            {"fm": {"description": "Torque output unstable", "severity": 7.9}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--input",
            str(input_path),
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"field": "fm.severity"}
    assert _failure_chain_rows(db_path) == []


def test_add_failure_chain_rejects_invalid_target_cause_reference(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    input_path = tmp_path / "bad-target-causes.json"
    input_path.write_text(
        json.dumps(
            {
                "fm": {"description": "Torque output unstable", "severity": 8},
                "fc": [
                    {
                        "description": "Winding short",
                        "occurrence": 4,
                        "detection": 3,
                        "ap": "High",
                    }
                ],
                "act": [
                    {
                        "description": "Upgrade insulation",
                        "kind": "prevention",
                        "status": "planned",
                        "owner": "Li",
                        "due": "2026-06-01",
                        "target_causes": [2],
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--input",
            str(input_path),
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"fc_index": 2, "fm": "new"}
    assert _failure_chain_rows(db_path) == []


def test_add_failure_chain_input_json_rejects_float_target_cause(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    input_path = tmp_path / "float-target-cause.json"
    input_path.write_text(
        json.dumps(
            {
                "fm": {"description": "Torque output unstable", "severity": 8},
                "fc": [
                    {
                        "description": "Winding short",
                        "occurrence": 4,
                        "detection": 3,
                        "ap": "High",
                    }
                ],
                "act": [
                    {
                        "description": "Upgrade insulation",
                        "kind": "prevention",
                        "status": "planned",
                        "owner": "Li",
                        "due": "2026-06-01",
                        "target_causes": [1.5],
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--input",
            str(input_path),
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"field": "act[1].target_causes[1]"}
    assert _failure_chain_rows(db_path) == []


def test_failure_chain_ids_are_not_reused_after_delete(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)

    first_result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--fm-description",
            "Torque output too low",
            "--severity",
            "7",
            "--act-description",
            "Increase copper fill",
            "--kind",
            "prevention",
            "--status",
            "planned",
            "--owner",
            "Li",
            "--due",
            "2026-07-01",
            "--format",
            "json",
        ]
    )
    assert first_result.exit_code == 0
    first_payload = _payload(first_result)
    assert first_payload["data"]["fm_id"] == "FM-001"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM nodes WHERE id IN (?, ?)", ("ACT-001", "FM-001"))
        conn.commit()
    finally:
        conn.close()

    second_result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--fm-description",
            "Torque output oscillates",
            "--severity",
            "6",
            "--act-description",
            "Tighten process window",
            "--kind",
            "detection",
            "--status",
            "planned",
            "--owner",
            "Chen",
            "--due",
            "2026-08-01",
            "--format",
            "json",
        ]
    )

    assert second_result.exit_code == 0
    second_payload = _payload(second_result)
    assert second_payload["data"]["fm_id"] == "FM-002"

    affected_objects = second_payload["data"]["affected_objects"]
    assert {obj["id"] for obj in affected_objects if "id" in obj} == {
        "FM-002",
        "ACT-002",
    }


def test_add_failure_chain_with_malformed_input_json_returns_structured_failure(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    input_path = tmp_path / "malformed-chain.json"
    input_path.write_text("{bad-json", encoding="utf-8")

    result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-001",
            "--input",
            str(input_path),
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis add-failure-chain"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"input": str(input_path)}


def test_add_failure_chain_help_mentions_input_and_grouping(cli_runner):
    result = cli_runner.invoke(["analysis", "add-failure-chain", "--help"])

    assert result.exit_code == 0
    assert "--input" in result.stdout
    assert "Preferred for" in result.stdout
    assert "complex chains" in result.stdout
    assert "pair by occurrence order" in result.stdout
    assert "1-based FC" in result.stdout
    assert "creation-order indexes" in result.stdout
    assert "not stored FC" in result.stdout
    assert "rowids" in result.stdout
