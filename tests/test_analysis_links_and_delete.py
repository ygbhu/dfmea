from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _json_payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "analysis-links.db"
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


def _add_requirement(cli_runner, db_path: Path) -> dict:
    result = cli_runner.invoke(
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
    assert result.exit_code == 0, result.stdout
    return _json_payload(result)


def _add_characteristic(cli_runner, db_path: Path) -> dict:
    result = cli_runner.invoke(
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
    assert result.exit_code == 0, result.stdout
    return _json_payload(result)


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


def _add_function(cli_runner, db_path: Path, *, comp: str, name: str) -> dict:
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
            f"{name} description",
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.stdout
    return _json_payload(result)


def _affected_rowids(payload: dict, node_type: str) -> list[int]:
    return [
        obj["rowid"]
        for obj in payload["data"]["affected_objects"]
        if obj["type"] == node_type
    ]


def test_link_and_unlink_requirement_and_characteristic_success(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_payload = _add_requirement(cli_runner, db_path)
    char_payload = _add_characteristic(cli_runner, db_path)
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
    )
    req_rowid = req_payload["data"]["req_rowid"]
    char_rowid = char_payload["data"]["char_rowid"]

    link_req_result = cli_runner.invoke(
        [
            "analysis",
            "link-fm-requirement",
            "--db",
            str(db_path),
            "--fm",
            "FM-001",
            "--req",
            str(req_rowid),
            "--format",
            "json",
        ]
    )
    assert link_req_result.exit_code == 0, link_req_result.stdout
    link_req_payload = _json_payload(link_req_result)
    assert link_req_payload["command"] == "analysis link-fm-requirement"
    assert link_req_payload["data"] == {
        "project_id": "demo",
        "fn_id": "FN-001",
        "fm_id": "FM-001",
        "req_rowid": req_rowid,
        "affected_objects": [
            {"type": "FM", "id": "FM-001", "rowid": 7},
            {"type": "REQ", "rowid": req_rowid},
        ],
    }

    link_char_result = cli_runner.invoke(
        [
            "analysis",
            "link-fm-characteristic",
            "--db",
            str(db_path),
            "--fm",
            "FM-001",
            "--char",
            str(char_rowid),
            "--format",
            "json",
        ]
    )
    assert link_char_result.exit_code == 0, link_char_result.stdout
    link_char_payload = _json_payload(link_char_result)
    assert link_char_payload["command"] == "analysis link-fm-characteristic"
    assert link_char_payload["data"] == {
        "project_id": "demo",
        "fn_id": "FN-001",
        "fm_id": "FM-001",
        "char_rowid": char_rowid,
        "affected_objects": [
            {"type": "FM", "id": "FM-001", "rowid": 7},
            {"type": "CHAR", "rowid": char_rowid},
        ],
    }

    conn = sqlite3.connect(db_path)
    try:
        linked_fm = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert json.loads(linked_fm) == {
        "related_characteristics": [char_rowid],
        "severity": 8,
        "violates_requirements": [req_rowid],
    }

    unlink_req_result = cli_runner.invoke(
        [
            "analysis",
            "unlink-fm-requirement",
            "--db",
            str(db_path),
            "--fm",
            "FM-001",
            "--req",
            str(req_rowid),
            "--format",
            "json",
        ]
    )
    assert unlink_req_result.exit_code == 0, unlink_req_result.stdout
    unlink_req_payload = _json_payload(unlink_req_result)
    assert unlink_req_payload["command"] == "analysis unlink-fm-requirement"

    unlink_char_result = cli_runner.invoke(
        [
            "analysis",
            "unlink-fm-characteristic",
            "--db",
            str(db_path),
            "--fm",
            "FM-001",
            "--char",
            str(char_rowid),
            "--format",
            "json",
        ]
    )
    assert unlink_char_result.exit_code == 0, unlink_char_result.stdout
    unlink_char_payload = _json_payload(unlink_char_result)
    assert unlink_char_payload["command"] == "analysis unlink-fm-characteristic"

    conn = sqlite3.connect(db_path)
    try:
        unlinked_fm = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert json.loads(unlinked_fm) == {"severity": 8}


def test_link_and_unlink_trace_success_via_fm_links(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    _add_structure(
        cli_runner,
        db_path,
        node_type="COMP",
        name="Rotor",
        parent="SUB-001",
    )
    _add_function(cli_runner, db_path, comp="COMP-002", name="Support rotation")
    first_chain = _add_failure_chain(
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
        "--fc-description",
        "Winding short",
        "--occurrence",
        "4",
        "--detection",
        "3",
        "--ap",
        "High",
    )
    second_chain = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            "FN-002",
            "--fm-description",
            "Torque ripple high",
            "--severity",
            "6",
            "--fe-description",
            "Rotor vibration high",
            "--fe-level",
            "component",
            "--fc-description",
            "Bearing wear",
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
    assert second_chain.exit_code == 0, second_chain.stdout
    second_chain_payload = _json_payload(second_chain)
    second_fe_rowid = _affected_rowids(second_chain_payload, "FE")[0]
    first_fc_rowid = _affected_rowids(first_chain, "FC")[0]

    link_fe_result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{second_fe_rowid}",
            "--to-fm",
            "FM-001",
            "--format",
            "json",
        ]
    )
    assert link_fe_result.exit_code == 0, link_fe_result.stdout
    link_fe_payload = _json_payload(link_fe_result)
    assert link_fe_payload["command"] == "analysis link-trace"

    link_fc_result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            f"fc:{first_fc_rowid}",
            "--to-fm",
            "FM-002",
            "--format",
            "json",
        ]
    )
    assert link_fc_result.exit_code == 0, link_fc_result.stdout

    conn = sqlite3.connect(db_path)
    try:
        linked_rows = conn.execute(
            "SELECT from_rowid, to_fm_rowid FROM fm_links ORDER BY from_rowid"
        ).fetchall()
    finally:
        conn.close()

    assert linked_rows == [(first_fc_rowid, 10), (second_fe_rowid, 7)]

    unlink_fe_result = cli_runner.invoke(
        [
            "analysis",
            "unlink-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{second_fe_rowid}",
            "--to-fm",
            "FM-001",
            "--format",
            "json",
        ]
    )
    assert unlink_fe_result.exit_code == 0, unlink_fe_result.stdout

    unlink_fc_result = cli_runner.invoke(
        [
            "analysis",
            "unlink-trace",
            "--db",
            str(db_path),
            "--from",
            f"fc:{first_fc_rowid}",
            "--to-fm",
            "FM-002",
            "--format",
            "json",
        ]
    )
    assert unlink_fc_result.exit_code == 0, unlink_fc_result.stdout

    conn = sqlite3.connect(db_path)
    try:
        remaining_rows = conn.execute(
            "SELECT from_rowid, to_fm_rowid FROM fm_links ORDER BY from_rowid"
        ).fetchall()
    finally:
        conn.close()

    assert remaining_rows == []


def test_link_trace_rejects_fe_target_in_same_component(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    first_chain = _add_failure_chain(
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
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque ripple high",
        "--severity",
        "6",
    )
    fe_rowid = _affected_rowids(first_chain, "FE")[0]

    result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{fe_rowid}",
            "--to-fm",
            "FM-002",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _json_payload(result)
    assert payload["command"] == "analysis link-trace"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "from": f"fe:{fe_rowid}",
        "to_fm": "FM-002",
        "source_component": "COMP-001",
        "target_component": "COMP-001",
    }
    assert "different component" in payload["errors"][0]["message"].lower()


def test_link_trace_rejects_fc_target_in_same_component(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    first_chain = _add_failure_chain(
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
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque ripple high",
        "--severity",
        "6",
    )
    fc_rowid = _affected_rowids(first_chain, "FC")[0]

    result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            f"fc:{fc_rowid}",
            "--to-fm",
            "FM-002",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _json_payload(result)
    assert payload["command"] == "analysis link-trace"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "from": f"fc:{fc_rowid}",
        "to_fm": "FM-002",
        "source_component": "COMP-001",
        "target_component": "COMP-001",
    }
    assert "different component" in payload["errors"][0]["message"].lower()


def test_delete_requirement_reports_modified_fm_objects(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_payload = _add_requirement(cli_runner, db_path)
    char_payload = _add_characteristic(cli_runner, db_path)
    req_rowid = req_payload["data"]["req_rowid"]
    char_rowid = char_payload["data"]["char_rowid"]
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--violates-req",
        str(req_rowid),
        "--related-char",
        str(char_rowid),
    )

    result = cli_runner.invoke(
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

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis delete-requirement"
    assert payload["data"]["affected_objects"] == [
        {"type": "REQ", "rowid": req_rowid},
        {"type": "FM", "id": "FM-001", "rowid": 7},
    ]

    conn = sqlite3.connect(db_path)
    try:
        fm_data = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert json.loads(fm_data) == {
        "related_characteristics": [char_rowid],
        "severity": 8,
    }


def test_delete_characteristic_reports_modified_fm_objects(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_payload = _add_requirement(cli_runner, db_path)
    char_payload = _add_characteristic(cli_runner, db_path)
    req_rowid = req_payload["data"]["req_rowid"]
    char_rowid = char_payload["data"]["char_rowid"]
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--violates-req",
        str(req_rowid),
        "--related-char",
        str(char_rowid),
    )

    result = cli_runner.invoke(
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

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis delete-characteristic"
    assert payload["data"]["affected_objects"] == [
        {"type": "CHAR", "rowid": char_rowid},
        {"type": "FM", "id": "FM-001", "rowid": 7},
    ]

    conn = sqlite3.connect(db_path)
    try:
        fm_data = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert json.loads(fm_data) == {
        "severity": 8,
        "violates_requirements": [req_rowid],
    }


def test_delete_node_requirement_reports_modified_fm_objects(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_payload = _add_requirement(cli_runner, db_path)
    char_payload = _add_characteristic(cli_runner, db_path)
    req_rowid = req_payload["data"]["req_rowid"]
    char_rowid = char_payload["data"]["char_rowid"]
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--violates-req",
        str(req_rowid),
        "--related-char",
        str(char_rowid),
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "delete-node",
            "--db",
            str(db_path),
            "--node",
            str(req_rowid),
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis delete-node"
    assert payload["data"] == {
        "project_id": "demo",
        "deleted_node": {"type": "REQ", "rowid": req_rowid},
        "affected_objects": [
            {"type": "REQ", "rowid": req_rowid},
            {"type": "FM", "id": "FM-001", "rowid": 7},
        ],
    }

    conn = sqlite3.connect(db_path)
    try:
        fm_data = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert json.loads(fm_data) == {
        "related_characteristics": [char_rowid],
        "severity": 8,
    }


def test_delete_node_characteristic_reports_modified_fm_objects(
    cli_runner, tmp_path: Path
):
    db_path = _create_function_db(cli_runner, tmp_path)
    req_payload = _add_requirement(cli_runner, db_path)
    char_payload = _add_characteristic(cli_runner, db_path)
    req_rowid = req_payload["data"]["req_rowid"]
    char_rowid = char_payload["data"]["char_rowid"]
    _add_failure_chain(
        cli_runner,
        db_path,
        "--fm-description",
        "Torque output unstable",
        "--severity",
        "8",
        "--violates-req",
        str(req_rowid),
        "--related-char",
        str(char_rowid),
    )

    result = cli_runner.invoke(
        [
            "analysis",
            "delete-node",
            "--db",
            str(db_path),
            "--node",
            str(char_rowid),
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["command"] == "analysis delete-node"
    assert payload["data"] == {
        "project_id": "demo",
        "deleted_node": {"type": "CHAR", "rowid": char_rowid},
        "affected_objects": [
            {"type": "CHAR", "rowid": char_rowid},
            {"type": "FM", "id": "FM-001", "rowid": 7},
        ],
    }

    conn = sqlite3.connect(db_path)
    try:
        fm_data = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", ("FM-001",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert json.loads(fm_data) == {
        "severity": 8,
        "violates_requirements": [req_rowid],
    }


def test_delete_fc_cleans_target_causes_and_deletes_orphaned_acts(
    cli_runner, tmp_path: Path
):
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
        "--act-description",
        "Tighten solder process",
        "--kind",
        "prevention",
        "--status",
        "in-progress",
        "--owner",
        "Li",
        "--due",
        "2026-07-01",
        "--target-causes",
        "1,2",
    )
    fc_first, fc_second = _affected_rowids(create_payload, "FC")

    result = cli_runner.invoke(
        [
            "analysis",
            "delete-node",
            "--db",
            str(db_path),
            "--node",
            str(fc_first),
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "analysis delete-node"
    assert payload["data"] == {
        "project_id": "demo",
        "deleted_node": {"type": "FC", "rowid": fc_first},
        "affected_objects": [
            {"type": "FC", "rowid": fc_first},
            {"type": "ACT", "id": "ACT-001", "rowid": 8},
            {"type": "ACT", "id": "ACT-002", "rowid": 9},
        ],
    }

    conn = sqlite3.connect(db_path)
    try:
        remaining_nodes = conn.execute(
            "SELECT rowid, id, type, name, data FROM nodes WHERE rowid >= 5 ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()

    assert remaining_nodes == [
        (5, "FM-001", "FM", "Torque output unstable", '{"severity": 8}'),
        (
            fc_second,
            None,
            "FC",
            "Solder crack",
            '{"ap": "Medium", "detection": 6, "occurrence": 2}',
        ),
        (
            9,
            "ACT-002",
            "ACT",
            "Tighten solder process",
            f'{{"due": "2026-07-01", "kind": "prevention", "owner": "Li", "status": "in-progress", "target_causes": [{fc_second}]}}',
        ),
    ]


def test_delete_non_analysis_node_fails_structurally(cli_runner, tmp_path: Path):
    db_path = _create_function_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "analysis",
            "delete-node",
            "--db",
            str(db_path),
            "--node",
            "COMP-001",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = _json_payload(result)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "analysis delete-node"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "analysis" in payload["errors"][0]["message"].lower()
