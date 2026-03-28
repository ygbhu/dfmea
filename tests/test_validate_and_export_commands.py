from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "validate-export.db"
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
    cli_runner,
    db_path: Path,
    *,
    node_type: str,
    name: str,
    parent: str | None = None,
) -> dict:
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


def _add_function(
    cli_runner, db_path: Path, *, comp: str, name: str, description: str
) -> dict:
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


def _add_requirement(
    cli_runner, db_path: Path, *, fn: str, text: str, source: str
) -> dict:
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
) -> dict:
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


def _seed_analysis_db(cli_runner, tmp_path: Path) -> dict:
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
    chain_result = cli_runner.invoke(
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
    assert chain_result.exit_code == 0, chain_result.stdout
    chain_payload = _payload(chain_result)
    return {
        "comp_id": comp_payload["data"]["node_id"],
        "db_path": db_path,
        "fn_id": fn_payload["data"]["fn_id"],
        "fn_rowid": fn_payload["data"]["affected_objects"][0]["rowid"],
        "fm_id": chain_payload["data"]["fm_id"],
        "act_id": _affected_object(chain_payload, "ACT")["id"],
        "act_owner": "Chen",
        "act_due": "2026-06-15",
    }


def test_validate_returns_non_zero_and_report_on_error_issue(
    cli_runner, tmp_path: Path
):
    seeded = _seed_analysis_db(cli_runner, tmp_path)

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute("UPDATE nodes SET data = ? WHERE id = ?", ("{", seeded["fn_id"]))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        ["validate", "--db", str(seeded["db_path"]), "--format", "json"]
    )

    payload = _payload(result)
    assert result.exit_code != 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["command"] == "validate"
    assert any(error["code"] == "VALIDATION_FAILED" for error in payload["errors"])
    assert payload["data"]["summary"]["errors"] >= 1
    assert any(
        issue["scope"] == "schema" and issue["kind"] == "MALFORMED_JSON"
        for issue in payload["data"]["issues"]
    )


def test_validate_returns_zero_for_clean_db(cli_runner, tmp_path: Path):
    db_path = _init_db(cli_runner, tmp_path)

    result = cli_runner.invoke(["validate", "--db", str(db_path), "--format", "json"])

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "validate"
    assert payload["data"]["summary"] == {"errors": 0, "warnings": 0}
    assert payload["data"]["issues"] == []
    assert payload["errors"] == []


def test_validate_reports_stale_projection_as_warning(cli_runner, tmp_path: Path):
    seeded = _seed_analysis_db(cli_runner, tmp_path)

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
            "structure",
            "add",
            "--db",
            str(seeded["db_path"]),
            "--type",
            "SYS",
            "--name",
            "Extra",
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.stdout

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(seeded["db_path"]), "--format", "json"]
    )

    payload = _payload(validate_result)
    assert validate_result.exit_code == 0
    assert payload["ok"] is True
    assert any(
        issue["scope"] == "projection" and issue["kind"] == "STALE_PROJECTION"
        for issue in payload["data"]["issues"]
    )


def test_validate_reports_corrupted_projection_as_error(cli_runner, tmp_path: Path):
    seeded = _seed_analysis_db(cli_runner, tmp_path)

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

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute(
            "UPDATE derived_views SET data = ? WHERE project_id = ?", ("{", "demo")
        )
        conn.commit()
    finally:
        conn.close()

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(seeded["db_path"]), "--format", "json"]
    )

    payload = _payload(validate_result)
    assert validate_result.exit_code != 0
    assert payload["ok"] is False
    assert any(
        issue["scope"] == "projection" and issue["kind"] == "PROJECTION_CORRUPT"
        for issue in payload["data"]["issues"]
    )


def test_export_markdown_creates_files_with_traceable_ids(cli_runner, tmp_path: Path):
    seeded = _seed_analysis_db(cli_runner, tmp_path)
    out_dir = tmp_path / "exports"

    result = cli_runner.invoke(
        [
            "export",
            "markdown",
            "--db",
            str(seeded["db_path"]),
            "--out",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "export markdown"
    assert payload["errors"] == []
    assert payload["data"]["files"]

    exported_paths = [Path(item["path"]) for item in payload["data"]["files"]]
    assert all(path.exists() for path in exported_paths)

    content = exported_paths[0].read_text(encoding="utf-8")
    assert seeded["fn_id"] in content
    assert f"rowid {seeded['fn_rowid']}" in content


def test_export_markdown_review_layout_creates_index_and_component_files(
    cli_runner, tmp_path: Path
):
    seeded = _seed_analysis_db(cli_runner, tmp_path)
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

    out_dir = tmp_path / "review-exports"
    result = cli_runner.invoke(
        [
            "export",
            "markdown",
            "--db",
            str(seeded["db_path"]),
            "--out",
            str(out_dir),
            "--layout",
            "review",
            "--format",
            "json",
        ]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["data"]["files"]

    exported_paths = [Path(item["path"]) for item in payload["data"]["files"]]
    assert any(path.name == "index.md" for path in exported_paths)
    assert any(path.parent.name == "components" for path in exported_paths)
    assert any(path.parent.name == "functions" for path in exported_paths)
    assert any(
        path.parent.name == "actions" and path.name == "open.md"
        for path in exported_paths
    )

    index_path = next(path for path in exported_paths if path.name == "index.md")
    component_path = next(
        path for path in exported_paths if path.parent.name == "components"
    )
    function_path = next(
        path for path in exported_paths if path.parent.name == "functions"
    )
    actions_path = next(
        path
        for path in exported_paths
        if path.parent.name == "actions" and path.name == "open.md"
    )
    index_content = index_path.read_text(encoding="utf-8")
    component_content = component_path.read_text(encoding="utf-8")
    function_content = function_path.read_text(encoding="utf-8")
    actions_content = actions_path.read_text(encoding="utf-8")

    assert "demo" in index_content
    assert "COMP-001" in component_content
    assert seeded["fn_id"] in function_content
    assert (
        f"[`{seeded['comp_id']}`](components/{seeded['comp_id']}.md)" in index_content
    )
    assert f"[`{seeded['fn_id']}`](functions/{seeded['fn_id']}.md)" in index_content
    assert "[Open Actions](actions/open.md)" in index_content
    assert (
        f"[`{seeded['fn_id']}`](../functions/{seeded['fn_id']}.md)" in component_content
    )
    assert (
        f"[`{seeded['comp_id']}`](../components/{seeded['comp_id']}.md)"
        in function_content
    )
    assert "[Back to index](../index.md)" in component_content
    assert "[Back to index](../index.md)" in function_content
    assert "[Back to index](../index.md)" in actions_content
    assert "# Open Actions" in actions_content
    assert seeded["act_owner"] in actions_content
    assert seeded["act_due"] in actions_content
    assert seeded["act_id"] in actions_content
    assert seeded["fm_id"] in actions_content or seeded["fn_id"] in actions_content
    assert "- high_ap: 1" in component_content
    assert "- severity_gte_7: 1" in component_content
    assert f"- open_action_ids: {seeded['act_id']}" in component_content
    assert "- open_actions: 1" in function_content
    assert "Torque output too low" in function_content
    assert seeded["act_id"] in function_content


def test_validate_reports_missing_projection_as_warning(cli_runner, tmp_path: Path):
    seeded = _seed_analysis_db(cli_runner, tmp_path)

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

    conn = sqlite3.connect(seeded["db_path"])
    try:
        conn.execute(
            "DELETE FROM derived_views WHERE project_id = ? AND kind = ?",
            ("demo", "project_map"),
        )
        conn.commit()
    finally:
        conn.close()

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(seeded["db_path"]), "--format", "json"]
    )

    payload = _payload(validate_result)
    assert validate_result.exit_code == 0
    assert any(
        issue["scope"] == "projection" and issue["kind"] == "MISSING_PROJECTION"
        for issue in payload["data"]["issues"]
    )
