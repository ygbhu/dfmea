from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from quality_adapters.cli.quality import app
from quality_core.cli.errors import QualityCliError, exit_code_for_error
from quality_core.resources.atomic import atomic_write_text
from quality_core.resources.envelope import make_resource
from quality_core.resources.locks import ProjectWriteLock, project_lock_path
from quality_core.resources.paths import ResourceSelector, validate_resource_path
from quality_core.resources.store import ResourceStore
from quality_core.workspace.project import ProjectConfig, load_project_config
from quality_methods.dfmea import get_plugin

runner = CliRunner()


def test_store_creates_loads_lists_and_updates_dfmea_collection_resource(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    store = ResourceStore(project=project, plugin=get_plugin())

    result = store.create_collection_resource(
        kind="FailureMode",
        id_prefix="FM",
        metadata={"title": "Motor stalls"},
        spec={"functionRef": "FN-001"},
    )

    assert result.resource_id == "FM-001"
    assert result.path == project.root / "dfmea" / "failure-modes" / "FM-001.yaml"
    assert result.path.exists()
    assert not result.lock_path.exists()

    document = yaml.safe_load(result.path.read_text(encoding="utf-8"))
    assert document["apiVersion"] == "quality.ai/v1"
    assert document["kind"] == "FailureMode"
    assert document["metadata"]["id"] == "FM-001"
    assert document["metadata"]["title"] == "Motor stalls"
    assert document["spec"]["functionRef"] == "FN-001"

    loaded = store.load(store.ref(kind="FailureMode", resource_id="FM-001"))
    assert loaded.resource_id == "FM-001"
    assert loaded.path == result.path

    updated = make_resource(
        kind="FailureMode",
        resource_id="FM-001",
        metadata={"title": "Motor intermittent stall"},
        spec={"functionRef": "FN-001", "severity": 8},
    )
    update_result = store.update(updated)
    assert update_result.path == result.path
    assert store.load(store.ref(kind="FailureMode", resource_id="FM-001")).spec["severity"] == 8

    listed = store.list(ResourceSelector(kind="FailureMode"))
    assert [resource.resource_id for resource in listed] == ["FM-001"]
    assert store.list(ResourceSelector(kind="FailureMode", id_prefix="F")) == []
    assert [
        resource.resource_id
        for resource in store.list(ResourceSelector(kind="FailureMode", id_prefix="FM"))
    ] == ["FM-001"]


def test_store_writes_singleton_with_fixed_id_and_file_name(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    store = ResourceStore(project=project, plugin=get_plugin())
    resource = make_resource(
        kind="DfmeaAnalysis",
        resource_id="DFMEA",
        metadata={"name": "Cooling Fan DFMEA"},
        spec={"methodology": "AIAG-VDA"},
    )

    result = store.create(resource)

    assert result.path == project.root / "dfmea" / "dfmea.yaml"
    loaded = store.load(store.ref(kind="DfmeaAnalysis", resource_id="DFMEA"))
    assert loaded.resource_id == "DFMEA"

    with pytest.raises(QualityCliError) as exc_info:
        validate_resource_path(
            plugin=get_plugin(),
            resource=resource,
            path=project.root / "dfmea" / "wrong.yaml",
        )
    assert exc_info.value.code == "ID_PREFIX_MISMATCH"

    wrong_id = make_resource(
        kind="DfmeaAnalysis",
        resource_id="DFMEA-ALT",
        spec={"methodology": "AIAG-VDA"},
    )
    with pytest.raises(QualityCliError) as wrong_id_exc:
        store.create(wrong_id)
    assert wrong_id_exc.value.code == "ID_PREFIX_MISMATCH"


def test_store_create_rejects_existing_resource_id(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    store = ResourceStore(project=project, plugin=get_plugin())
    store.create_collection_resource(
        kind="FailureMode",
        id_prefix="FM",
        metadata={"title": "Motor stalls"},
        spec={},
    )
    duplicate = make_resource(
        kind="FailureMode",
        resource_id="FM-001",
        metadata={"title": "Duplicate"},
        spec={},
    )

    with pytest.raises(QualityCliError) as exc_info:
        store.create(duplicate)

    assert exc_info.value.code == "ID_CONFLICT"


def test_collection_path_validation_rejects_filename_id_mismatch(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    resource = make_resource(
        kind="FailureMode",
        resource_id="FM-001",
        metadata={"title": "Motor stalls"},
        spec={},
    )

    with pytest.raises(QualityCliError) as exc_info:
        validate_resource_path(
            plugin=get_plugin(),
            resource=resource,
            path=project.root / "dfmea" / "failure-modes" / "FM-999.yaml",
        )
    assert exc_info.value.code == "ID_PREFIX_MISMATCH"


def test_store_list_validates_collection_filename_against_metadata_id(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    store = ResourceStore(project=project, plugin=get_plugin())
    resource = make_resource(
        kind="FailureMode",
        resource_id="FM-001",
        metadata={"title": "Motor stalls"},
        spec={},
    )
    bad_path = project.root / "dfmea" / "failure-modes" / "FM-999.yaml"
    atomic_write_text(bad_path, yaml.safe_dump(resource.to_document(), sort_keys=False))

    with pytest.raises(QualityCliError) as exc_info:
        store.list(ResourceSelector(kind="FailureMode"))

    assert exc_info.value.code == "ID_PREFIX_MISMATCH"


def test_delete_creates_tombstone_and_next_allocation_skips_deleted_id(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    store = ResourceStore(project=project, plugin=get_plugin())
    first = store.create_collection_resource(
        kind="FailureMode",
        id_prefix="FM",
        metadata={"title": "Motor stalls"},
        spec={},
    )

    delete_result = store.delete(store.ref(kind="FailureMode", resource_id="FM-001"))

    assert not first.path.exists()
    assert delete_result.tombstone_path == project.root / ".quality" / "tombstones" / "FM-001"
    assert delete_result.tombstone_path.exists()
    tombstone = yaml.safe_load(delete_result.tombstone_path.read_text(encoding="utf-8"))
    assert tombstone["kind"] == "IdTombstone"
    assert tombstone["metadata"]["id"] == "FM-001"
    assert tombstone["spec"]["resourceKind"] == "FailureMode"

    second = store.create_collection_resource(
        kind="FailureMode",
        id_prefix="FM",
        metadata={"title": "Motor blocked"},
        spec={},
    )
    assert second.resource_id == "FM-002"
    assert second.path.name == "FM-002.yaml"


def test_project_write_lock_blocks_concurrent_writes(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)
    store = ResourceStore(project=project, plugin=get_plugin(), lock_timeout_seconds=0)

    with ProjectWriteLock(project.root):
        assert project_lock_path(project.root).exists()
        with pytest.raises(QualityCliError) as exc_info:
            store.create_collection_resource(
                kind="FailureMode",
                id_prefix="FM",
                metadata={"title": "Motor stalls"},
                spec={},
            )

    assert exc_info.value.code == "FILE_LOCKED"
    assert not project_lock_path(project.root).exists()


def test_unacquired_project_write_lock_does_not_remove_existing_lock(tmp_path) -> None:
    project = _create_enabled_project(tmp_path)

    with ProjectWriteLock(project.root):
        ProjectWriteLock(project.root).release()
        assert project_lock_path(project.root).exists()

    assert not project_lock_path(project.root).exists()


def test_atomic_write_text_replaces_file_without_temp_leftovers(tmp_path) -> None:
    target = tmp_path / "resource.yaml"

    atomic_write_text(target, "first")
    atomic_write_text(target, "second")

    assert target.read_text(encoding="utf-8") == "second"
    assert list(tmp_path.glob(".resource.yaml.*.tmp")) == []


def test_resource_store_errors_have_expected_exit_codes() -> None:
    assert exit_code_for_error("RESOURCE_NOT_FOUND") == 4
    assert exit_code_for_error("ID_CONFLICT") == 4
    assert exit_code_for_error("ID_PREFIX_MISMATCH") == 4
    assert exit_code_for_error("INVALID_PARENT") == 4
    assert exit_code_for_error("NODE_NOT_EMPTY") == 4
    assert exit_code_for_error("FILE_LOCKED") == 6
    assert exit_code_for_error("ATOMIC_WRITE_FAILED") == 6


def _create_enabled_project(root: Path) -> ProjectConfig:
    workspace_result = runner.invoke(app, ["workspace", "init", "--workspace", str(root)])
    assert workspace_result.exit_code == 0, workspace_result.output
    project_result = runner.invoke(
        app,
        [
            "project",
            "create",
            "cooling-fan-controller",
            "--workspace",
            str(root),
        ],
    )
    assert project_result.exit_code == 0, project_result.output
    enable_result = runner.invoke(
        app,
        [
            "plugin",
            "enable",
            "dfmea",
            "--workspace",
            str(root),
            "--project",
            "cooling-fan-controller",
        ],
    )
    assert enable_result.exit_code == 0, enable_result.output
    payload = json.loads(enable_result.output)
    return load_project_config(Path(payload["meta"]["projectRoot"]))
