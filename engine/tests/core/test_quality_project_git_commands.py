from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from typer.testing import CliRunner

from quality_adapters.cli.dfmea import app as dfmea_app
from quality_adapters.cli.quality import app as quality_app

runner = CliRunner()


def test_project_status_reports_dirty_managed_paths_and_stale_projection(tmp_path) -> None:
    project_root = _create_valid_git_project(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "baseline")

    fm_path = project_root / "dfmea" / "failure-modes" / "FM-001.yaml"
    fm_doc = yaml.safe_load(fm_path.read_text(encoding="utf-8"))
    fm_doc["spec"]["severity"] = 9
    fm_path.write_text(yaml.safe_dump(fm_doc, sort_keys=False), encoding="utf-8")

    payload = _invoke_quality_json(
        [
            "project",
            "status",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
        ]
    )

    dirty_paths = {item["path"] for item in payload["data"]["dirtyManagedPaths"]}
    assert "projects/cooling-fan-controller/dfmea/failure-modes/FM-001.yaml" in dirty_paths
    assert payload["data"]["projections"][0]["status"] == "stale"
    assert payload["data"]["validation"]["errors"] == 0


def test_project_snapshot_commits_managed_paths_and_excludes_locks(tmp_path) -> None:
    project_root = _create_valid_git_project(tmp_path, rebuild_projection=False)
    lock_path = project_root / ".quality" / "locks" / "project.lock"
    lock_path.write_text("runtime", encoding="utf-8")

    payload = _invoke_quality_json(
        [
            "project",
            "snapshot",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--message",
            "quality(project): baseline",
        ]
    )

    assert payload["data"]["created"] is True
    committed = set(_git(tmp_path, "show", "--name-only", "--pretty=format:", "HEAD").splitlines())
    assert "projects/cooling-fan-controller/project.yaml" in committed
    assert "projects/cooling-fan-controller/.quality/schemas/dfmea/plugin.yaml" in committed
    assert "projects/cooling-fan-controller/dfmea/dfmea.yaml" in committed
    assert "projects/cooling-fan-controller/dfmea/projections/manifest.json" not in committed
    assert "projects/cooling-fan-controller/.quality/locks/project.lock" not in committed
    lock_path.unlink()

    _invoke_dfmea_json(
        [
            "structure",
            "add-system",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Temporary System",
        ]
    )
    delete_payload = _invoke_dfmea_json(
        [
            "structure",
            "delete",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--node",
            "SYS-002",
        ]
    )
    tombstone_path = Path(delete_payload["data"]["tombstonePath"])
    assert tombstone_path.name == "SYS-002"
    assert tombstone_path.parent.name == "tombstones"
    second = _invoke_quality_json(
        [
            "project",
            "snapshot",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--message",
            "quality(project): delete component",
        ]
    )
    assert second["data"]["created"] is True
    committed_second = set(
        _git(tmp_path, "show", "--name-only", "--pretty=format:", "HEAD").splitlines()
    )
    assert "projects/cooling-fan-controller/.quality/tombstones/SYS-002" in committed_second


def test_project_history_and_diff_filter_managed_paths_with_resource_summaries(tmp_path) -> None:
    _create_valid_git_project(tmp_path)
    _invoke_quality_json(
        [
            "project",
            "snapshot",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--message",
            "quality(project): baseline",
        ]
    )
    baseline = _git(tmp_path, "rev-parse", "HEAD").strip()

    _invoke_dfmea_json(
        [
            "analysis",
            "update-risk",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--failure-mode",
            "FM-001",
            "--severity",
            "9",
        ]
    )
    (tmp_path / "notes.txt").write_text("unmanaged", encoding="utf-8")

    diff_payload = _invoke_quality_json(
        [
            "project",
            "diff",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--from",
            baseline,
        ]
    )
    paths = {item["path"] for item in diff_payload["data"]["changedPaths"]}
    assert "projects/cooling-fan-controller/dfmea/failure-modes/FM-001.yaml" in paths
    assert "notes.txt" not in paths
    resources = {item["id"]: item for item in diff_payload["data"]["resources"]}
    assert resources["FM-001"]["kind"] == "FailureMode"

    _invoke_quality_json(
        [
            "project",
            "snapshot",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--message",
            "quality(project): update severity",
        ]
    )
    history_payload = _invoke_quality_json(
        [
            "project",
            "history",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--limit",
            "5",
        ]
    )
    subjects = [entry["subject"] for entry in history_payload["data"]["history"]]
    assert "quality(project): update severity" in subjects
    assert "quality(project): baseline" in subjects


def test_project_restore_restores_non_generated_paths_rebuilds_and_commits(tmp_path) -> None:
    project_root = _create_valid_git_project(tmp_path)
    _invoke_quality_json(
        [
            "project",
            "snapshot",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--message",
            "quality(project): baseline",
        ]
    )
    baseline = _git(tmp_path, "rev-parse", "HEAD").strip()
    old_manifest = (project_root / "dfmea" / "projections" / "manifest.json").read_text(
        encoding="utf-8"
    )

    _invoke_dfmea_json(
        [
            "analysis",
            "update-risk",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--failure-mode",
            "FM-001",
            "--severity",
            "9",
        ]
    )
    (project_root / ".quality" / "locks" / "project.lock").write_text("runtime", encoding="utf-8")
    _invoke_quality_json(
        [
            "project",
            "snapshot",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--message",
            "quality(project): changed",
        ]
    )

    payload = _invoke_quality_json(
        [
            "project",
            "restore",
            "--workspace",
            str(tmp_path),
            "--project",
            "cooling-fan-controller",
            "--ref",
            baseline,
            "--message",
            "quality(restore): restore baseline",
        ]
    )

    assert payload["data"]["created"] is True
    fm_doc = yaml.safe_load(
        (project_root / "dfmea" / "failure-modes" / "FM-001.yaml").read_text(encoding="utf-8")
    )
    assert fm_doc["spec"]["severity"] == 8
    assert (project_root / ".quality" / "locks" / "project.lock").exists()
    new_manifest = (project_root / "dfmea" / "projections" / "manifest.json").read_text(
        encoding="utf-8"
    )
    assert new_manifest != old_manifest
    assert _git(tmp_path, "log", "-1", "--pretty=%s").strip() == (
        "quality(restore): restore baseline"
    )


def _create_valid_git_project(root: Path, *, rebuild_projection: bool = True) -> Path:
    _git(root, "init")
    _git(root, "config", "user.email", "tester@example.com")
    _git(root, "config", "user.name", "Tester")
    workspace_result = runner.invoke(
        quality_app,
        ["workspace", "init", "--workspace", str(root)],
    )
    assert workspace_result.exit_code == 0, workspace_result.output
    project_result = runner.invoke(
        quality_app,
        [
            "project",
            "create",
            "cooling-fan-controller",
            "--workspace",
            str(root),
        ],
    )
    assert project_result.exit_code == 0, project_result.output
    init_result = runner.invoke(
        dfmea_app,
        [
            "init",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert init_result.exit_code == 0, init_result.output

    for args in (
        [
            "structure",
            "add-system",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--title",
            "Fan Controller",
        ],
        [
            "structure",
            "add-subsystem",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SYS-001",
            "--title",
            "Motor Control",
        ],
        [
            "structure",
            "add-component",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--parent",
            "SUB-001",
            "--title",
            "Motor Driver",
        ],
        [
            "analysis",
            "add-function",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--component",
            "COMP-001",
            "--title",
            "Drive fan motor",
        ],
        [
            "analysis",
            "add-failure-chain",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
            "--function",
            "FN-001",
            "--fm-description",
            "Motor stalls",
            "--severity",
            "8",
            "--fe-description",
            "Airflow lost",
            "--fc-description",
            "Bearing seizure",
            "--occurrence",
            "4",
            "--detection",
            "5",
            "--act-description",
            "Add current spike detection",
            "--status",
            "completed",
            "--target-causes",
            "1",
        ],
    ):
        _invoke_dfmea_json(args)
    if rebuild_projection:
        _invoke_dfmea_json(
            [
                "projection",
                "rebuild",
                "--workspace",
                str(root),
                "--project",
                "cooling-fan-controller",
            ]
        )
    return root / "projects" / "cooling-fan-controller"


def _invoke_quality_json(args: list[str]) -> dict:
    result = runner.invoke(quality_app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    return payload


def _invoke_dfmea_json(args: list[str]) -> dict:
    result = runner.invoke(dfmea_app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["contractVersion"] == "quality.ai/v1"
    assert payload["ok"] is True
    return payload


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout
