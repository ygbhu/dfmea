from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _dfmea_executable() -> str:
    executable = shutil.which("dfmea")
    assert executable is not None, (
        "Installed 'dfmea' console script is not on PATH. "
        "Refresh the editable install with `python -m pip install -e .`."
    )
    return executable


def _run_dfmea(
    args: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_dfmea_executable(), *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installed_dfmea_help_lists_command_tree() -> None:
    result = _run_dfmea(["--help"])

    assert result.returncode == 0, result.stderr or result.stdout
    for name in [
        "init",
        "structure",
        "analysis",
        "query",
        "trace",
        "validate",
        "export",
    ]:
        assert name in result.stdout


def test_installed_dfmea_init_returns_json_and_creates_db(tmp_path: Path) -> None:
    db_path = tmp_path / "installed-demo.db"

    result = _run_dfmea(
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "installed-demo",
            "--name",
            "Installed Demo",
            "--format",
            "json",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "init"
    assert payload["data"]["project_id"] == "installed-demo"
    assert payload["errors"] == []
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id, name FROM projects ORDER BY id").fetchall()
    finally:
        conn.close()

    assert rows == [("installed-demo", "Installed Demo")]


def test_skill_adapter_docs_exist_and_enforce_cli_boundaries() -> None:
    expected_files = {
        ROOT_DIR / "dfmea" / "SKILL.md": [
            "dfmea",
            "sqlite",
            "markdown",
            "source of truth",
        ],
        ROOT_DIR / "dfmea" / "node-schema.md": [
            "FN",
            "REQ",
            "CHAR",
            "ACT",
        ],
        ROOT_DIR / "dfmea" / "storage-spec.md": [
            "SQLite",
            "Markdown",
            "source of truth",
            "export-only",
        ],
        ROOT_DIR / "dfmea" / "skills" / "dfmea-init" / "SKILL.md": [
            "dfmea init",
        ],
        ROOT_DIR / "dfmea" / "skills" / "dfmea-structure" / "SKILL.md": [
            "dfmea structure",
        ],
        ROOT_DIR / "dfmea" / "skills" / "dfmea-analysis" / "SKILL.md": [
            "dfmea analysis",
        ],
        ROOT_DIR / "dfmea" / "skills" / "dfmea-query" / "SKILL.md": [
            "dfmea query",
            "dfmea trace",
        ],
        ROOT_DIR / "dfmea" / "skills" / "dfmea-maintenance" / "SKILL.md": [
            "dfmea validate",
            "dfmea export markdown",
        ],
    }

    for file_path, snippets in expected_files.items():
        assert file_path.exists(), f"Missing adapter doc: {file_path}"
        content = file_path.read_text(encoding="utf-8")
        lowered = content.lower()
        assert "do not write sqlite directly" in lowered
        assert "do not treat exported markdown as source data" in lowered
        for snippet in snippets:
            assert snippet in content
