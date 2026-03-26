from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dfmea_cli.db import RetryableBusyError, connect


def _table_names(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def _project_rows(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id, name FROM projects ORDER BY id").fetchall()
    finally:
        conn.close()
    return rows


def _project_data(db_path: Path, project_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return json.loads(row[0])


def test_init_creates_db_schema_and_single_project(cli_runner, tmp_path: Path):
    db_path = tmp_path / "demo.db"

    result = cli_runner.invoke(
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--name",
            "Demo",
            "--busy-timeout-ms",
            "7000",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "init"
    assert payload["meta"]["project_id"] == "demo"
    assert payload["meta"]["busy_timeout_ms"] == 7000
    assert payload["data"]["affected_objects"] == [{"type": "PROJECT", "id": "demo"}]
    assert db_path.exists()
    assert _table_names(db_path) == {"derived_views", "fm_links", "nodes", "projects"}
    assert _project_rows(db_path) == [("demo", "Demo")]


def test_init_seeds_projection_metadata(cli_runner, tmp_path: Path):
    db_path = tmp_path / "projection-meta.db"

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
    assert _project_data(db_path, "demo") == {
        "canonical_revision": 0,
        "last_projection_build_at": None,
        "last_projection_revision": 0,
        "projection_dirty": False,
        "projection_schema_version": "1.0",
    }


def test_connect_applies_required_pragmas_and_busy_timeout(tmp_path: Path):
    db_path = tmp_path / "pragmas.db"

    conn = connect(db_path, busy_timeout_ms=7000)

    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        recursive_triggers = conn.execute("PRAGMA recursive_triggers").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        conn.close()

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1
    assert recursive_triggers == 1
    assert busy_timeout == 7000


def test_retry_exhaustion_returns_db_busy_json(cli_runner, tmp_path: Path, monkeypatch):
    db_path = tmp_path / "busy.db"

    def always_busy(*args, **kwargs):
        raise RetryableBusyError()

    monkeypatch.setattr("dfmea_cli.db.execute_with_retry", always_busy)

    result = cli_runner.invoke(
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--name",
            "Demo",
            "--retry",
            "2",
            "--format",
            "json",
        ]
    )

    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "DB_BUSY"


def test_init_bootstrap_failure_does_not_leave_schema_only_db(
    cli_runner, tmp_path: Path, monkeypatch
):
    db_path = tmp_path / "half-initialized.db"

    from dfmea_cli.schema import bootstrap_schema as real_bootstrap_schema

    def failing_bootstrap(conn):
        real_bootstrap_schema(conn)
        raise sqlite3.OperationalError("simulated bootstrap failure")

    monkeypatch.setattr(
        "dfmea_cli.services.projects.bootstrap_schema", failing_bootstrap
    )

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

    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["ok"] is False
    assert not db_path.exists() or _table_names(db_path) == set()


def test_init_invalid_db_path_returns_structured_json_failure(
    cli_runner, tmp_path: Path
):
    db_path = tmp_path / "missing-parent" / "demo.db"

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

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"db": str(db_path)}
    assert "suggested_action" in payload["errors"][0]


def test_init_rejects_negative_retry_with_structured_json(cli_runner, tmp_path: Path):
    db_path = tmp_path / "demo.db"

    result = cli_runner.invoke(
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--name",
            "Demo",
            "--retry",
            "-1",
            "--format",
            "json",
        ]
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"option": "retry", "value": -1}
    assert payload["meta"]["retry"] == -1


def test_init_rejects_existing_legacy_sqlite_file(cli_runner, tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE legacy (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

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

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "db": str(db_path),
        "unexpected_tables": ["legacy"],
    }


def test_init_rejects_existing_dfmea_tables_with_dirty_rows(cli_runner, tmp_path: Path):
    db_path = tmp_path / "dirty-dfmea.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL, updated TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE nodes (rowid INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, type TEXT NOT NULL, parent_id INTEGER NOT NULL DEFAULT 0, project_id TEXT NOT NULL, name TEXT, data TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL, updated TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE fm_links (from_rowid INTEGER NOT NULL, to_fm_rowid INTEGER NOT NULL, PRIMARY KEY (from_rowid, to_fm_rowid))"
        )
        conn.execute(
            "INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "SYS-001",
                "SYS",
                0,
                "orphan",
                "Legacy",
                "{}",
                "2026-03-21T00:00:00+00:00",
                "2026-03-21T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

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

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {
        "db": str(db_path),
        "non_empty_tables": ["nodes"],
    }
