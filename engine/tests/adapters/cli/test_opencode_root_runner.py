from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RUNNER = REPO_ROOT / "scripts" / "quality_cli.py"


def test_root_runner_exposes_quality_and_dfmea_from_repo_root(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = "runner-smoke"

    workspace_payload = _run_json(
        "quality",
        "workspace",
        "init",
        "--workspace",
        str(workspace),
    )
    assert workspace_payload["command"] == "quality workspace init"

    project_payload = _run_json(
        "quality",
        "project",
        "create",
        project,
        "--workspace",
        str(workspace),
    )
    assert project_payload["meta"]["projectSlug"] == project

    dfmea_payload = _run_json(
        "dfmea",
        "init",
        "--workspace",
        str(workspace),
        "--project",
        project,
    )
    assert dfmea_payload["command"] == "dfmea init"
    assert dfmea_payload["meta"]["schemaVersions"] == {"dfmea": "dfmea.ai/v1"}


def test_root_runner_rejects_unknown_entrypoint() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "pfmea", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "Unknown quality assistant entrypoint: pfmea" in completed.stderr


def _run_json(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    return payload
