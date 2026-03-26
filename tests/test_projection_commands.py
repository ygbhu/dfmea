from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _payload(result) -> dict:
    assert result.stdout.strip().startswith("{"), result.stdout
    return json.loads(result.stdout)


def _init_db(cli_runner, tmp_path: Path) -> Path:
    db_path = tmp_path / "projection.db"
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


def _table_names(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def test_projection_status_returns_projection_metadata_for_clean_project(
    cli_runner, tmp_path: Path
):
    db_path = _init_db(cli_runner, tmp_path)

    result = cli_runner.invoke(
        ["projection", "status", "--db", str(db_path), "--format", "json"]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "projection status"
    assert payload["data"] == {
        "project_id": "demo",
        "canonical_revision": 0,
        "last_projection_build_at": None,
        "last_projection_revision": 0,
        "projection_dirty": False,
        "projection_schema_version": "1.0",
    }


def test_projection_status_upgrades_legacy_db_before_reading(
    cli_runner, tmp_path: Path
):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE nodes (rowid INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, type TEXT NOT NULL, parent_id INTEGER NOT NULL DEFAULT 0, project_id TEXT NOT NULL, name TEXT, data TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL, updated TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE fm_links (from_rowid INTEGER NOT NULL, to_fm_rowid INTEGER NOT NULL, PRIMARY KEY (from_rowid, to_fm_rowid))"
        )
        conn.execute(
            "INSERT INTO projects (id, name, data, created, updated) VALUES (?, ?, ?, ?, ?)",
            (
                "demo",
                "Demo",
                "{}",
                "2026-03-25T00:00:00+00:00",
                "2026-03-25T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        ["projection", "status", "--db", str(db_path), "--format", "json"]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["data"]["projection_dirty"] is True
    assert "derived_views" in _table_names(db_path)
    assert _project_data(db_path, "demo") == {
        "canonical_revision": 0,
        "last_projection_build_at": None,
        "last_projection_revision": 0,
        "projection_dirty": True,
        "projection_schema_version": "1.0",
    }


def test_projection_rebuild_persists_derived_views_and_clears_dirty_flag(
    cli_runner, tmp_path: Path
):
    db_path = _init_db(cli_runner, tmp_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE projects SET data = ? WHERE id = ?",
            (
                json.dumps(
                    {
                        "canonical_revision": 0,
                        "last_projection_build_at": None,
                        "last_projection_revision": 0,
                        "projection_dirty": True,
                        "projection_schema_version": "1.0",
                    },
                    sort_keys=True,
                ),
                "demo",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"]
    )

    payload = _payload(result)
    assert result.exit_code == 0
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "projection rebuild"
    assert payload["data"]["project_id"] == "demo"
    assert payload["data"]["projection_dirty"] is False
    assert payload["data"]["last_projection_revision"] == 0
    assert payload["data"]["rebuilt_counts"] == {
        "action_backlog": 1,
        "component_bundle": 0,
        "function_dossier": 0,
        "project_map": 1,
        "risk_register": 1,
    }

    project_data = _project_data(db_path, "demo")
    assert project_data["projection_dirty"] is False
    assert project_data["last_projection_revision"] == 0
    assert project_data["last_projection_build_at"] is not None

    conn = sqlite3.connect(db_path)
    try:
        row_count = conn.execute(
            "SELECT COUNT(*) FROM derived_views WHERE project_id = ?", ("demo",)
        ).fetchone()[0]
    finally:
        conn.close()
    assert row_count == 3
