from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from helpers_realistic_dfmea import parse_json_payload, seed_realistic_structure_only


def _open_reader(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _canonical_fn_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM nodes WHERE type = 'FN' AND id IS NOT NULL ORDER BY id"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _canonical_req_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM nodes WHERE type = 'REQ'").fetchone()
    assert row is not None
    return int(row[0])


def _projection_dirty(db_path: Path, *, project_id: str = "demo") -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return bool(json.loads(row[0])["projection_dirty"])


def test_wal_reader_snapshot_keeps_old_reader_view_and_exposes_commit_to_new_reader(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_structure_only(cli_runner, tmp_path)
    db_path = seeded["db_path"]

    reader_a = _open_reader(db_path)
    try:
        reader_a.execute("BEGIN")
        baseline_fn_ids = _canonical_fn_ids(reader_a)
        baseline_req_count = _canonical_req_count(reader_a)

        add_result = cli_runner.invoke(
            [
                "analysis",
                "add-function",
                "--db",
                str(db_path),
                "--comp",
                seeded["controller_comp_id"],
                "--name",
                "Control fan startup enable logic",
                "--description",
                "Enable controller output when startup conditions are satisfied",
                "--format",
                "json",
            ]
        )
        assert add_result.exit_code == 0, add_result.stdout
        add_payload = parse_json_payload(add_result)
        fn_id = add_payload["data"]["fn_id"]

        assert _canonical_fn_ids(reader_a) == baseline_fn_ids
        assert _canonical_req_count(reader_a) == baseline_req_count
        assert _projection_dirty(db_path) is True

        reader_b = _open_reader(db_path)
        try:
            assert set(_canonical_fn_ids(reader_b)) == set(baseline_fn_ids) | {fn_id}
            assert _canonical_req_count(reader_b) == baseline_req_count
        finally:
            reader_b.close()

        reader_a.commit()
    finally:
        reader_a.close()

    rebuild_result = cli_runner.invoke(
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout
    rebuild_payload = parse_json_payload(rebuild_result)
    assert rebuild_payload["data"]["projection_dirty"] is False
    assert _projection_dirty(db_path) is False

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(db_path), "--format", "json"]
    )
    assert validate_result.exit_code == 0, validate_result.stdout
    validate_payload = parse_json_payload(validate_result)
    assert validate_payload["data"]["summary"]["errors"] == 0


def test_wal_reader_does_not_block_cli_writer_and_system_still_converges(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_structure_only(cli_runner, tmp_path)
    db_path = seeded["db_path"]

    reader = _open_reader(db_path)
    try:
        reader.execute("BEGIN")
        baseline_req_count = _canonical_req_count(reader)

        add_function_result = cli_runner.invoke(
            [
                "analysis",
                "add-function",
                "--db",
                str(db_path),
                "--comp",
                seeded["controller_comp_id"],
                "--name",
                "Control fan startup enable logic",
                "--description",
                "Enable controller output when startup conditions are satisfied",
                "--format",
                "json",
            ]
        )
        assert add_function_result.exit_code == 0, add_function_result.stdout
        add_function_payload = parse_json_payload(add_function_result)
        fn_id = add_function_payload["data"]["fn_id"]

        add_requirement_result = cli_runner.invoke(
            [
                "analysis",
                "add-requirement",
                "--db",
                str(db_path),
                "--fn",
                fn_id,
                "--text",
                "Controller shall enable startup output only when all interlocks are satisfied.",
                "--format",
                "json",
            ]
        )
        assert add_requirement_result.exit_code == 0, add_requirement_result.stdout

        assert _canonical_req_count(reader) == baseline_req_count
        assert _projection_dirty(db_path) is True

        reader.commit()
    finally:
        reader.close()

    projection_status_result = cli_runner.invoke(
        ["projection", "status", "--db", str(db_path), "--format", "json"]
    )
    assert projection_status_result.exit_code == 0, projection_status_result.stdout
    projection_status_payload = parse_json_payload(projection_status_result)
    assert projection_status_payload["data"]["projection_dirty"] is True

    rebuild_result = cli_runner.invoke(
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"]
    )
    assert rebuild_result.exit_code == 0, rebuild_result.stdout

    summary_result = cli_runner.invoke(
        [
            "query",
            "summary",
            "--db",
            str(db_path),
            "--comp",
            seeded["controller_comp_id"],
            "--format",
            "json",
        ]
    )
    assert summary_result.exit_code == 0, summary_result.stdout
    summary_payload = parse_json_payload(summary_result)
    assert summary_payload["data"]["counts"]["functions"] == 1
    assert summary_payload["data"]["counts"]["requirements"] == 1

    validate_result = cli_runner.invoke(
        ["validate", "--db", str(db_path), "--format", "json"]
    )
    assert validate_result.exit_code == 0, validate_result.stdout
    validate_payload = parse_json_payload(validate_result)
    assert validate_payload["data"]["summary"]["errors"] == 0
