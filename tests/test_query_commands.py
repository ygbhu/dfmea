from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "query.db"
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


def _affected_object(payload: dict, node_type: str) -> dict:
    for item in payload["data"]["affected_objects"]:
        if item["type"] == node_type:
            return item
    raise AssertionError(f"Missing affected object for type {node_type}: {payload}")


def _seed_query_db(cli_runner, tmp_path: Path) -> dict:
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
    fn_payload = _add_function(
        cli_runner,
        db_path,
        comp=comp_payload["data"]["node_id"],
        name="Deliver torque",
        description="Provide rated torque",
    )
    req_payload = _add_requirement(
        cli_runner,
        db_path,
        fn=fn_payload["data"]["fn_id"],
        text="Meet 300 Nm output",
        source="SYS-REQ-1",
    )
    char_payload = _add_characteristic(
        cli_runner,
        db_path,
        fn=fn_payload["data"]["fn_id"],
        text="Torque output",
        value="300",
        unit="Nm",
    )

    chain_one_result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            fn_payload["data"]["fn_id"],
            "--fm-description",
            "Torque output too low",
            "--severity",
            "8",
            "--violates-req",
            str(req_payload["data"]["req_rowid"]),
            "--related-char",
            str(char_payload["data"]["char_rowid"]),
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
            "--format",
            "json",
        ]
    )
    assert chain_one_result.exit_code == 0, chain_one_result.stdout
    chain_one_payload = _payload(chain_one_result)

    chain_two_result = cli_runner.invoke(
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(db_path),
            "--fn",
            fn_payload["data"]["fn_id"],
            "--fm-description",
            "Torque ripple high",
            "--severity",
            "6",
            "--fc-description",
            "Resolver offset drift",
            "--occurrence",
            "2",
            "--detection",
            "6",
            "--ap",
            "Low",
            "--act-description",
            "Tighten calibration window",
            "--kind",
            "prevention",
            "--status",
            "completed",
            "--owner",
            "Li",
            "--due",
            "2026-07-01",
            "--target-causes",
            "1",
            "--format",
            "json",
        ]
    )
    assert chain_two_result.exit_code == 0, chain_two_result.stdout
    chain_two_payload = _payload(chain_two_result)

    return {
        "db_path": db_path,
        "project_id": "demo",
        "comp_id": comp_payload["data"]["node_id"],
        "fn_id": fn_payload["data"]["fn_id"],
        "req_rowid": req_payload["data"]["req_rowid"],
        "char_rowid": char_payload["data"]["char_rowid"],
        "fm_one_id": chain_one_payload["data"]["fm_id"],
        "fm_two_id": chain_two_payload["data"]["fm_id"],
        "fc_high_rowid": _affected_object(chain_one_payload, "FC")["rowid"],
        "act_planned_id": _affected_object(chain_one_payload, "ACT")["id"],
        "act_completed_id": _affected_object(chain_two_payload, "ACT")["id"],
    }


def test_query_get_returns_structured_fm_node(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "query",
            "get",
            "--db",
            str(seeded["db_path"]),
            "--node",
            seeded["fm_one_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query get"
    assert payload["data"]["node"]["type"] == "FM"
    assert payload["data"]["node"]["id"] == seeded["fm_one_id"]
    assert payload["data"]["node"]["parent"]["id"] == seeded["fn_id"]
    assert payload["data"]["node"]["data"]["severity"] == 8


def test_query_list_filters_by_type_and_parent(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "query",
            "list",
            "--db",
            str(seeded["db_path"]),
            "--type",
            "FM",
            "--parent",
            seeded["fn_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query list"
    assert payload["data"]["count"] == 2
    assert [node["id"] for node in payload["data"]["nodes"]] == [
        seeded["fm_one_id"],
        seeded["fm_two_id"],
    ]


def test_query_search_finds_keyword_in_json_fields(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "query",
            "search",
            "--db",
            str(seeded["db_path"]),
            "--keyword",
            "Chen",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query search"
    assert payload["data"]["count"] == 1
    assert payload["data"]["nodes"][0]["type"] == "ACT"
    assert payload["data"]["nodes"][0]["id"] == seeded["act_planned_id"]


def test_query_summary_returns_component_counts(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "summary",
            "--db",
            str(seeded["db_path"]),
            "--comp",
            seeded["comp_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query summary"
    assert payload["data"]["component"]["id"] == seeded["comp_id"]
    assert payload["data"]["counts"] == {
        "functions": 1,
        "requirements": 1,
        "characteristics": 1,
        "failure_modes": 2,
        "failure_effects": 1,
        "failure_causes": 2,
        "actions": 2,
    }
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "component_bundle",
        "scope_ref": seeded["comp_id"],
        "status": "fresh",
    }


def test_query_by_ap_returns_high_risk_failure_causes(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "by-ap",
            "--db",
            str(seeded["db_path"]),
            "--ap",
            "High",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query by-ap"
    assert payload["data"]["count"] == 1
    assert payload["data"]["nodes"][0]["type"] == "FC"
    assert payload["data"]["nodes"][0]["rowid"] == seeded["fc_high_rowid"]
    assert payload["data"]["nodes"][0]["data"]["ap"] == "High"
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "risk_register",
        "scope_ref": "project",
        "status": "fresh",
    }


def test_query_by_severity_returns_failure_modes_at_or_above_threshold(
    cli_runner, tmp_path: Path
):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "by-severity",
            "--db",
            str(seeded["db_path"]),
            "--gte",
            "7",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query by-severity"
    assert payload["data"]["count"] == 1
    assert payload["data"]["nodes"][0]["id"] == seeded["fm_one_id"]
    assert payload["data"]["nodes"][0]["data"]["severity"] == 8
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "risk_register",
        "scope_ref": "project",
        "status": "fresh",
    }


def test_query_actions_returns_actions_by_status(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "actions",
            "--db",
            str(seeded["db_path"]),
            "--status",
            "planned",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "query actions"
    assert payload["data"]["count"] == 1
    assert payload["data"]["nodes"][0]["type"] == "ACT"
    assert payload["data"]["nodes"][0]["id"] == seeded["act_planned_id"]
    assert payload["data"]["nodes"][0]["data"]["status"] == "planned"
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "action_backlog",
        "scope_ref": "project",
        "status": "fresh",
    }


def test_query_map_returns_project_navigation_view(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "map",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["command"] == "query map"
    assert payload["data"]["project"]["id"] == "demo"
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "project_map",
        "scope_ref": "project",
        "status": "fresh",
    }


def test_query_bundle_returns_component_bundle(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "bundle",
            "--db",
            str(seeded["db_path"]),
            "--comp",
            seeded["comp_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["command"] == "query bundle"
    assert payload["data"]["component"]["id"] == seeded["comp_id"]
    assert payload["data"]["counts"]["failure_modes"] == 2
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "component_bundle",
        "scope_ref": seeded["comp_id"],
        "status": "fresh",
    }


def test_query_dossier_returns_function_dossier(cli_runner, tmp_path: Path):
    seeded = _seed_query_db(cli_runner, tmp_path)

    rebuild_result = cli_runner.invoke(
        [
            "projection",
            "rebuild",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    result = cli_runner.invoke(
        [
            "query",
            "dossier",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            seeded["fn_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["command"] == "query dossier"
    assert payload["data"]["function"]["id"] == seeded["fn_id"]
    assert len(payload["data"]["requirements"]) == 1
    assert len(payload["data"]["characteristics"]) == 1
    assert len(payload["data"]["failure_modes"]) == 2
    assert payload["meta"]["projection"] == {
        "canonical_revision": 8,
        "kind": "function_dossier",
        "scope_ref": seeded["fn_id"],
        "status": "fresh",
    }


def test_query_get_returns_structured_failure_for_malformed_node_json(
    cli_runner, tmp_path: Path
):
    seeded = _seed_query_db(cli_runner, tmp_path)

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute(
            "UPDATE nodes SET data = ? WHERE id = ?", ("{broken", seeded["fm_one_id"])
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "query",
            "get",
            "--db",
            str(seeded["db_path"]),
            "--node",
            seeded["fm_one_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "query get"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "malformed JSON" in payload["errors"][0]["message"]


def test_query_by_severity_returns_structured_failure_for_malformed_stored_severity(
    cli_runner, tmp_path: Path
):
    seeded = _seed_query_db(cli_runner, tmp_path)

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute(
            "UPDATE nodes SET data = ? WHERE id = ?",
            (json.dumps({"severity": "bad"}, sort_keys=True), seeded["fm_one_id"]),
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "query",
            "by-severity",
            "--db",
            str(seeded["db_path"]),
            "--gte",
            "7",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "query by-severity"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "severity" in payload["errors"][0]["message"]


def test_query_get_missing_required_option_returns_json_failure_contract(
    cli_runner, tmp_path: Path
):
    seeded = _seed_query_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "query",
            "get",
            "--db",
            str(seeded["db_path"]),
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "query get"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "--node" in payload["errors"][0]["message"]


def test_query_by_severity_invalid_option_type_returns_json_failure_contract(
    cli_runner, tmp_path: Path
):
    seeded = _seed_query_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        [
            "query",
            "by-severity",
            "--db",
            str(seeded["db_path"]),
            "--gte",
            "not-a-number",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "query by-severity"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "--gte" in payload["errors"][0]["message"]


def test_query_get_returns_structured_failure_for_dangling_parent_reference(
    cli_runner, tmp_path: Path
):
    seeded = _seed_query_db(cli_runner, tmp_path)

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute(
            "UPDATE nodes SET parent_id = ? WHERE id = ?",
            (999999, seeded["fm_one_id"]),
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        [
            "query",
            "get",
            "--db",
            str(seeded["db_path"]),
            "--node",
            seeded["fm_one_id"],
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 2
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "query get"
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert "parent" in payload["errors"][0]["message"].lower()
