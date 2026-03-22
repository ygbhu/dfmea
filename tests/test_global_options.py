import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from dfmea_cli.cli import app


def _create_valid_dfmea_db(tmp_path: Path) -> str:
    db_path = tmp_path / "valid.db"
    result = CliRunner().invoke(
        app,
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
        ],
    )
    assert result.exit_code == 0, result.stdout
    return str(db_path)


def _create_project_db(tmp_path: Path, project_ids: list[str]) -> str:
    db_path = tmp_path / "projects.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO projects (id, name) VALUES (?, ?)",
        [(project_id, project_id.title()) for project_id in project_ids],
    )
    conn.commit()
    conn.close()
    return str(db_path)


def test_default_output_format_is_json(tmp_path: Path):
    db_path = _create_valid_dfmea_db(tmp_path)

    result = CliRunner().invoke(app, ["validate", "--db", db_path])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["contract_version"] == "1.0"
    assert payload["command"] == "validate"


def test_project_db_mismatch_error_is_structured(tmp_path: Path):
    db_path = _create_project_db(tmp_path, ["demo"])

    result = CliRunner().invoke(
        app,
        ["validate", "--db", db_path, "--project", "wrong", "--format", "json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "PROJECT_DB_MISMATCH"


def test_missing_db_path_returns_invalid_reference_without_creating_file(
    tmp_path: Path,
):
    db_path = tmp_path / "missing.db"

    result = CliRunner().invoke(
        app, ["validate", "--db", str(db_path), "--format", "json"]
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert (
        payload["errors"][0]["message"]
        == f"Database '{db_path}' does not exist or is not readable."
    )
    assert not db_path.exists()


def test_multi_project_db_fails_even_when_project_is_explicitly_provided(
    tmp_path: Path,
):
    db_path = _create_project_db(tmp_path, ["demo", "other"])

    result = CliRunner().invoke(
        app,
        ["validate", "--db", db_path, "--project", "demo", "--format", "json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert (
        payload["errors"][0]["message"]
        == "Database must contain exactly one project in V1."
    )


def test_db_only_auto_resolves_single_project(tmp_path: Path):
    db_path = _create_valid_dfmea_db(tmp_path)

    result = CliRunner().invoke(app, ["validate", "--db", db_path, "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["meta"]["project_id"] == "demo"


def test_busy_timeout_and_retry_options_flow_into_meta(tmp_path: Path):
    db_path = _create_valid_dfmea_db(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "--db",
            db_path,
            "--busy-timeout-ms",
            "7000",
            "--retry",
            "2",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["meta"]["busy_timeout_ms"] == 7000
    assert payload["meta"]["retry"] == 2


def test_validate_rejects_negative_busy_timeout_with_structured_json(tmp_path: Path):
    db_path = _create_project_db(tmp_path, ["demo"])

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "--db",
            db_path,
            "--busy-timeout-ms",
            "-1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"option": "busy_timeout_ms", "value": -1}
    assert payload["meta"]["busy_timeout_ms"] == -1


def test_validate_rejects_negative_retry_with_structured_json(tmp_path: Path):
    db_path = _create_project_db(tmp_path, ["demo"])

    result = CliRunner().invoke(
        app,
        ["validate", "--db", db_path, "--retry", "-1", "--format", "json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert payload["errors"][0]["target"] == {"option": "retry", "value": -1}
    assert payload["meta"]["retry"] == -1


def test_validate_returns_clean_result_for_initialized_db(tmp_path: Path):
    db_path = _create_valid_dfmea_db(tmp_path)

    result = CliRunner().invoke(app, ["validate", "--db", db_path, "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["warnings"] == []
    assert payload["errors"] == []
    assert payload["data"]["summary"] == {"errors": 0, "warnings": 0}


def test_quiet_suppresses_human_facing_success_output(tmp_path: Path):
    db_path = _create_valid_dfmea_db(tmp_path)

    result = CliRunner().invoke(
        app,
        ["validate", "--db", db_path, "--format", "text", "--quiet"],
    )

    assert result.exit_code == 0
    assert result.stdout == ""


def test_text_format_requires_explicit_human_facing_request(tmp_path: Path):
    db_path = _create_valid_dfmea_db(tmp_path)

    result = CliRunner().invoke(app, ["validate", "--db", db_path, "--format", "text"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "validate ok for project demo"
