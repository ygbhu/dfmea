from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import dfmea_cli.db as db_helpers
from dfmea_cli.errors import CliError, DbBusyError
from dfmea_cli.resolve import (
    ResolvedNode,
    normalize_retry_policy,
    resolve_node_reference,
)
from dfmea_cli.services.projections import mark_projection_dirty
from dfmea_cli.services.structure import (
    _allocate_business_id,
    _node_identity,
    _utc_now,
)


@dataclass(frozen=True, slots=True)
class AnalysisMutationResult:
    db_path: Path
    project_id: str
    node_type: str
    node_id: str | None
    rowid: int
    parent_type: str
    parent_id: str | None
    parent_rowid: int
    busy_timeout_ms: int
    retry: int
    affected_objects: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class FailureChainCreateResult:
    db_path: Path
    project_id: str
    fn_id: str
    fn_rowid: int
    fm_id: str
    fm_rowid: int
    affected_objects: list[dict[str, Any]]
    busy_timeout_ms: int
    retry: int


@dataclass(frozen=True, slots=True)
class AnalysisLinkResult:
    db_path: Path
    project_id: str
    fn_id: str
    fn_rowid: int
    fm_id: str
    fm_rowid: int
    linked_type: str
    linked_rowid: int
    busy_timeout_ms: int
    retry: int


@dataclass(frozen=True, slots=True)
class TraceLinkResult:
    db_path: Path
    project_id: str
    from_type: str
    from_rowid: int
    to_fm_id: str
    to_fm_rowid: int
    busy_timeout_ms: int
    retry: int


@dataclass(frozen=True, slots=True)
class AnalysisDeleteResult:
    db_path: Path
    project_id: str
    deleted_type: str
    deleted_id: str | None
    deleted_rowid: int
    affected_objects: list[dict[str, Any]]
    busy_timeout_ms: int
    retry: int


ALLOWED_ACTION_KINDS = {"prevention", "detection"}
ALLOWED_ACTION_STATUSES = {"planned", "in-progress", "completed"}
ALLOWED_AP_VALUES = {"High", "Medium", "Low"}


def add_function(
    *,
    db_path: str | Path,
    project_id: str,
    comp_ref: str,
    name: str,
    description: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, rowid, parent_id, parent_rowid = db_helpers.execute_with_retry(
            lambda: _add_function_once(
                db_path=resolved_db_path,
                project_id=project_id,
                comp_ref=comp_ref,
                name=name,
                description=description,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="add function",
        ) from exc

    return AnalysisMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_type="FN",
        node_id=node_id,
        rowid=rowid,
        parent_type="COMP",
        parent_id=parent_id,
        parent_rowid=parent_rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def update_function(
    *,
    db_path: str | Path,
    project_id: str,
    fn_ref: str,
    name: str | None,
    description: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    _ensure_mutable_fields_present(
        fields={"name": name, "description": description},
        entity_label="function",
    )
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, rowid, parent_id, parent_rowid = db_helpers.execute_with_retry(
            lambda: _update_function_once(
                db_path=resolved_db_path,
                project_id=project_id,
                fn_ref=fn_ref,
                name=name,
                description=description,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="update function",
        ) from exc

    return AnalysisMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_type="FN",
        node_id=node_id,
        rowid=rowid,
        parent_type="COMP",
        parent_id=parent_id,
        parent_rowid=parent_rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def add_requirement(
    *,
    db_path: str | Path,
    project_id: str,
    fn_ref: str,
    text: str,
    source: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return _add_child_node(
        db_path=db_path,
        project_id=project_id,
        parent_ref=fn_ref,
        node_type="REQ",
        text=text,
        data={"source": source} if source is not None else {},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def update_requirement(
    *,
    db_path: str | Path,
    project_id: str,
    req_ref: str,
    text: str | None,
    source: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return _update_child_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=req_ref,
        expected_type="REQ",
        text=text,
        updates={"source": source} if source is not None else {},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def delete_requirement(
    *,
    db_path: str | Path,
    project_id: str,
    req_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return _delete_child_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=req_ref,
        expected_type="REQ",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def add_characteristic(
    *,
    db_path: str | Path,
    project_id: str,
    fn_ref: str,
    text: str,
    value: str | None,
    unit: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    data: dict[str, Any] = {}
    if value is not None:
        data["value"] = value
    if unit is not None:
        data["unit"] = unit
    return _add_child_node(
        db_path=db_path,
        project_id=project_id,
        parent_ref=fn_ref,
        node_type="CHAR",
        text=text,
        data=data,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def update_characteristic(
    *,
    db_path: str | Path,
    project_id: str,
    char_ref: str,
    text: str | None,
    value: str | None,
    unit: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    updates: dict[str, Any] = {}
    if value is not None:
        updates["value"] = value
    if unit is not None:
        updates["unit"] = unit
    return _update_child_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=char_ref,
        expected_type="CHAR",
        text=text,
        updates=updates,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def delete_characteristic(
    *,
    db_path: str | Path,
    project_id: str,
    char_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return _delete_child_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=char_ref,
        expected_type="CHAR",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def add_failure_chain(
    *,
    db_path: str | Path,
    project_id: str,
    fn_ref: str,
    chain_spec: dict[str, Any],
    busy_timeout_ms: int,
    retry: int,
) -> FailureChainCreateResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        fn_node, fm_id, fm_rowid, affected_objects = db_helpers.execute_with_retry(
            lambda: _add_failure_chain_once(
                db_path=resolved_db_path,
                project_id=project_id,
                fn_ref=fn_ref,
                chain_spec=chain_spec,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="add failure chain",
        ) from exc

    return FailureChainCreateResult(
        db_path=resolved_db_path,
        project_id=project_id,
        fn_id=_node_identity(fn_node),
        fn_rowid=fn_node.rowid,
        fm_id=cast(str, fm_id),
        fm_rowid=fm_rowid,
        affected_objects=affected_objects,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def update_failure_mode(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    description: str | None,
    severity: int | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return _update_analysis_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=fm_ref,
        expected_type="FM",
        description=description,
        updates={"severity": severity} if severity is not None else {},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def update_failure_effect(
    *,
    db_path: str | Path,
    project_id: str,
    fe_ref: str,
    description: str | None,
    level: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return _update_analysis_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=fe_ref,
        expected_type="FE",
        description=description,
        updates={"level": level} if level is not None else {},
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def update_failure_cause(
    *,
    db_path: str | Path,
    project_id: str,
    fc_ref: str,
    description: str | None,
    occurrence: int | None,
    detection: int | None,
    ap: str | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    updates: dict[str, Any] = {}
    if occurrence is not None:
        updates["occurrence"] = occurrence
    if detection is not None:
        updates["detection"] = detection
    if ap is not None:
        updates["ap"] = ap
    return _update_analysis_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=fc_ref,
        expected_type="FC",
        description=description,
        updates=updates,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def update_action(
    *,
    db_path: str | Path,
    project_id: str,
    act_ref: str,
    description: str | None,
    kind: str | None,
    status: str | None,
    owner: str | None,
    due: str | None,
    target_causes: list[int] | None,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    updates: dict[str, Any] = {}
    if kind is not None:
        updates["kind"] = kind
    if status is not None:
        updates["status"] = status
    if owner is not None:
        updates["owner"] = owner
    if due is not None:
        updates["due"] = due
    if target_causes is not None:
        updates["target_causes"] = target_causes
    return _update_analysis_node(
        db_path=db_path,
        project_id=project_id,
        node_ref=act_ref,
        expected_type="ACT",
        description=description,
        updates=updates,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def update_action_status(
    *,
    db_path: str | Path,
    project_id: str,
    act_ref: str,
    status: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    return update_action(
        db_path=db_path,
        project_id=project_id,
        act_ref=act_ref,
        description=None,
        kind=None,
        status=status,
        owner=None,
        due=None,
        target_causes=None,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def link_fm_requirement(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    req_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisLinkResult:
    return _mutate_fm_local_link(
        db_path=db_path,
        project_id=project_id,
        fm_ref=fm_ref,
        linked_ref=req_ref,
        expected_linked_type="REQ",
        json_field="violates_requirements",
        mode="link",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def unlink_fm_requirement(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    req_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisLinkResult:
    return _mutate_fm_local_link(
        db_path=db_path,
        project_id=project_id,
        fm_ref=fm_ref,
        linked_ref=req_ref,
        expected_linked_type="REQ",
        json_field="violates_requirements",
        mode="unlink",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def link_fm_characteristic(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    char_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisLinkResult:
    return _mutate_fm_local_link(
        db_path=db_path,
        project_id=project_id,
        fm_ref=fm_ref,
        linked_ref=char_ref,
        expected_linked_type="CHAR",
        json_field="related_characteristics",
        mode="link",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def unlink_fm_characteristic(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    char_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisLinkResult:
    return _mutate_fm_local_link(
        db_path=db_path,
        project_id=project_id,
        fm_ref=fm_ref,
        linked_ref=char_ref,
        expected_linked_type="CHAR",
        json_field="related_characteristics",
        mode="unlink",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def link_trace(
    *,
    db_path: str | Path,
    project_id: str,
    from_ref: str,
    to_fm_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> TraceLinkResult:
    return _mutate_trace_link(
        db_path=db_path,
        project_id=project_id,
        from_ref=from_ref,
        to_fm_ref=to_fm_ref,
        mode="link",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def unlink_trace(
    *,
    db_path: str | Path,
    project_id: str,
    from_ref: str,
    to_fm_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> TraceLinkResult:
    return _mutate_trace_link(
        db_path=db_path,
        project_id=project_id,
        from_ref=from_ref,
        to_fm_ref=to_fm_ref,
        mode="unlink",
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )


def delete_analysis_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisDeleteResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        deleted_type, deleted_id, deleted_rowid, affected_objects = (
            db_helpers.execute_with_retry(
                lambda: _delete_analysis_node_once(
                    db_path=resolved_db_path,
                    project_id=project_id,
                    node_ref=node_ref,
                    busy_timeout_ms=retry_policy.busy_timeout_ms,
                ),
                retry=retry_policy.retry,
            )
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation="delete analysis node",
        ) from exc

    return AnalysisDeleteResult(
        db_path=resolved_db_path,
        project_id=project_id,
        deleted_type=deleted_type,
        deleted_id=deleted_id,
        deleted_rowid=deleted_rowid,
        affected_objects=affected_objects,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _add_child_node(
    *,
    db_path: str | Path,
    project_id: str,
    parent_ref: str,
    node_type: str,
    text: str,
    data: dict[str, Any],
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        rowid, parent_id, parent_rowid = db_helpers.execute_with_retry(
            lambda: _add_child_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                parent_ref=parent_ref,
                node_type=node_type,
                text=text,
                data=data,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation=f"add {node_type.lower()}",
        ) from exc

    return AnalysisMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_type=node_type,
        node_id=None,
        rowid=rowid,
        parent_type="FN",
        parent_id=parent_id,
        parent_rowid=parent_rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _update_child_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    expected_type: str,
    text: str | None,
    updates: dict[str, Any],
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    field_values: dict[str, Any] = {"text": text}
    field_values.update(updates)
    _ensure_mutable_fields_present(
        fields=field_values,
        entity_label=_analysis_entity_label(expected_type),
    )
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        rowid, parent_id, parent_rowid = db_helpers.execute_with_retry(
            lambda: _update_child_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                node_ref=node_ref,
                expected_type=expected_type,
                text=text,
                updates=updates,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation=f"update {expected_type.lower()}",
        ) from exc

    return AnalysisMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_type=expected_type,
        node_id=None,
        rowid=rowid,
        parent_type="FN",
        parent_id=parent_id,
        parent_rowid=parent_rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
        affected_objects=[{"type": expected_type, "rowid": rowid}],
    )


def _delete_child_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    expected_type: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        rowid, parent_id, parent_rowid, affected_objects = (
            db_helpers.execute_with_retry(
                lambda: _delete_child_node_once(
                    db_path=resolved_db_path,
                    project_id=project_id,
                    node_ref=node_ref,
                    expected_type=expected_type,
                    busy_timeout_ms=retry_policy.busy_timeout_ms,
                ),
                retry=retry_policy.retry,
            )
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation=f"delete {expected_type.lower()}",
        ) from exc

    return AnalysisMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_type=expected_type,
        node_id=None,
        rowid=rowid,
        parent_type="FN",
        parent_id=parent_id,
        parent_rowid=parent_rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
        affected_objects=affected_objects,
    )


def _update_analysis_node(
    *,
    db_path: str | Path,
    project_id: str,
    node_ref: str,
    expected_type: str,
    description: str | None,
    updates: dict[str, Any],
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisMutationResult:
    field_values: dict[str, Any] = {"description": description}
    field_values.update(updates)
    _ensure_mutable_fields_present(
        fields=field_values,
        entity_label=_analysis_entity_label(expected_type),
    )
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        node_id, rowid, parent_id, parent_rowid = db_helpers.execute_with_retry(
            lambda: _update_analysis_node_once(
                db_path=resolved_db_path,
                project_id=project_id,
                node_ref=node_ref,
                expected_type=expected_type,
                description=description,
                updates=updates,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation=f"update {expected_type.lower()}",
        ) from exc

    return AnalysisMutationResult(
        db_path=resolved_db_path,
        project_id=project_id,
        node_type=expected_type,
        node_id=node_id,
        rowid=rowid,
        parent_type="FM" if expected_type in {"FE", "FC", "ACT"} else "FN",
        parent_id=parent_id,
        parent_rowid=parent_rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _mutate_fm_local_link(
    *,
    db_path: str | Path,
    project_id: str,
    fm_ref: str,
    linked_ref: str,
    expected_linked_type: str,
    json_field: str,
    mode: str,
    busy_timeout_ms: int,
    retry: int,
) -> AnalysisLinkResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        fn_node, fm_node, linked_node = db_helpers.execute_with_retry(
            lambda: _mutate_fm_local_link_once(
                db_path=resolved_db_path,
                project_id=project_id,
                fm_ref=fm_ref,
                linked_ref=linked_ref,
                expected_linked_type=expected_linked_type,
                json_field=json_field,
                mode=mode,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation=f"{mode} fm {expected_linked_type.lower()}",
        ) from exc

    return AnalysisLinkResult(
        db_path=resolved_db_path,
        project_id=project_id,
        fn_id=_node_identity(fn_node),
        fn_rowid=fn_node.rowid,
        fm_id=_node_identity(fm_node),
        fm_rowid=fm_node.rowid,
        linked_type=expected_linked_type,
        linked_rowid=linked_node.rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _mutate_trace_link(
    *,
    db_path: str | Path,
    project_id: str,
    from_ref: str,
    to_fm_ref: str,
    mode: str,
    busy_timeout_ms: int,
    retry: int,
) -> TraceLinkResult:
    resolved_db_path = Path(db_path)
    retry_policy = normalize_retry_policy(
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
    )

    try:
        source_node, to_fm_node = db_helpers.execute_with_retry(
            lambda: _mutate_trace_link_once(
                db_path=resolved_db_path,
                project_id=project_id,
                from_ref=from_ref,
                to_fm_ref=to_fm_ref,
                mode=mode,
                busy_timeout_ms=retry_policy.busy_timeout_ms,
            ),
            retry=retry_policy.retry,
        )
    except db_helpers.RetryableBusyError as exc:
        raise DbBusyError(db_path=resolved_db_path) from exc
    except sqlite3.Error as exc:
        raise _normalize_analysis_storage_error(
            exc=exc,
            db_path=resolved_db_path,
            project_id=project_id,
            operation=f"{mode} trace",
        ) from exc

    return TraceLinkResult(
        db_path=resolved_db_path,
        project_id=project_id,
        from_type=source_node.type,
        from_rowid=source_node.rowid,
        to_fm_id=_node_identity(to_fm_node),
        to_fm_rowid=to_fm_node.rowid,
        busy_timeout_ms=retry_policy.busy_timeout_ms,
        retry=retry_policy.retry,
    )


def _add_function_once(
    *,
    db_path: Path,
    project_id: str,
    comp_ref: str,
    name: str,
    description: str,
    busy_timeout_ms: int,
) -> tuple[str, int, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        parent = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=comp_ref,
            node_type="FN",
            expected_parent_type="COMP",
        )
        node_id = _allocate_business_id(conn, project_id=project_id, node_type="FN")
        timestamp = _utc_now()
        cursor = conn.execute(
            """
            INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                "FN",
                parent.rowid,
                project_id,
                name,
                json.dumps({"description": description}, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        rowid = cursor.lastrowid
        if rowid is None:
            raise CliError(
                code="UNKNOWN",
                message="Function insert did not return a rowid.",
                target={"project_id": project_id, "parent": comp_ref},
                suggested_action="Retry the command. If it persists, inspect SQLite insert behavior.",
            )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return node_id, cast(int, rowid), _node_identity(parent), parent.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_failure_chain_once(
    *,
    db_path: Path,
    project_id: str,
    fn_ref: str,
    chain_spec: dict[str, Any],
    busy_timeout_ms: int,
):
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        fn_node = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=fn_ref,
            node_type="FM",
            expected_parent_type="FN",
        )
        normalized_spec = _normalize_failure_chain_spec(chain_spec)
        validated_req_refs = _validate_linked_analysis_refs(
            conn,
            project_id=project_id,
            fn_node=fn_node,
            refs=normalized_spec["fm"]["violates_requirements"],
            expected_type="REQ",
        )
        validated_char_refs = _validate_linked_analysis_refs(
            conn,
            project_id=project_id,
            fn_node=fn_node,
            refs=normalized_spec["fm"]["related_characteristics"],
            expected_type="CHAR",
        )

        fm_data = {"severity": normalized_spec["fm"]["severity"]}
        if validated_req_refs:
            fm_data["violates_requirements"] = validated_req_refs
        if validated_char_refs:
            fm_data["related_characteristics"] = validated_char_refs

        fm_id, fm_rowid = _insert_analysis_node(
            conn,
            project_id=project_id,
            parent_rowid=fn_node.rowid,
            node_type="FM",
            name=normalized_spec["fm"]["description"],
            data=fm_data,
            allocate_id=True,
        )
        if fm_id is None:
            raise CliError(
                code="UNKNOWN",
                message="FM insert did not return a business id.",
                target={"project_id": project_id, "fn": _node_identity(fn_node)},
                suggested_action="Retry the command. If it persists, inspect failure-chain insert behavior.",
            )
        affected_objects: list[dict[str, Any]] = [
            {"type": "FM", "id": fm_id, "rowid": fm_rowid}
        ]

        for fe_spec in normalized_spec["fe"]:
            fe_data: dict[str, Any] = {}
            if fe_spec["level"] is not None:
                fe_data["level"] = fe_spec["level"]
            _, fe_rowid = _insert_analysis_node(
                conn,
                project_id=project_id,
                parent_rowid=fm_rowid,
                node_type="FE",
                name=fe_spec["description"],
                data=fe_data,
                allocate_id=False,
            )
            affected_objects.append({"type": "FE", "rowid": fe_rowid})

        fc_rowids: list[int] = []
        for fc_spec in normalized_spec["fc"]:
            _, fc_rowid = _insert_analysis_node(
                conn,
                project_id=project_id,
                parent_rowid=fm_rowid,
                node_type="FC",
                name=fc_spec["description"],
                data={
                    "occurrence": fc_spec["occurrence"],
                    "detection": fc_spec["detection"],
                    "ap": fc_spec["ap"],
                },
                allocate_id=False,
            )
            fc_rowids.append(fc_rowid)
            affected_objects.append({"type": "FC", "rowid": fc_rowid})

        for act_spec in normalized_spec["act"]:
            act_target_causes = _resolve_target_causes(
                fc_rowids=fc_rowids,
                target_causes=act_spec["target_causes"],
            )
            act_data: dict[str, Any] = {}
            if act_spec["kind"] is not None:
                act_data["kind"] = act_spec["kind"]
            if act_spec["status"] is not None:
                act_data["status"] = act_spec["status"]
            if act_spec["owner"] is not None:
                act_data["owner"] = act_spec["owner"]
            if act_spec["due"] is not None:
                act_data["due"] = act_spec["due"]
            if act_target_causes:
                act_data["target_causes"] = act_target_causes
            act_id, act_rowid = _insert_analysis_node(
                conn,
                project_id=project_id,
                parent_rowid=fm_rowid,
                node_type="ACT",
                name=act_spec["description"],
                data=act_data,
                allocate_id=True,
            )
            affected_objects.append({"type": "ACT", "id": act_id, "rowid": act_rowid})

        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return fn_node, fm_id, fm_rowid, affected_objects
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_function_once(
    *,
    db_path: Path,
    project_id: str,
    fn_ref: str,
    name: str | None,
    description: str | None,
    busy_timeout_ms: int,
) -> tuple[str, int, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=fn_ref)
        _ensure_analysis_node_type(node.type, expected_type="FN", node_ref=fn_ref)
        parent = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=str(node.parent_id),
            node_type="FN",
            expected_parent_type="COMP",
        )
        data = _decode_analysis_node_data(
            node.data,
            node_ref=_node_identity(node),
            entity_label="function",
        )
        if description is not None:
            data["description"] = description
        update_name = node.name if name is None else name
        conn.execute(
            "UPDATE nodes SET name = ?, data = ?, updated = ? WHERE rowid = ?",
            (
                update_name,
                json.dumps(data, sort_keys=True),
                _utc_now(),
                node.rowid,
            ),
        )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return _node_identity(node), node.rowid, _node_identity(parent), parent.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_child_node_once(
    *,
    db_path: Path,
    project_id: str,
    parent_ref: str,
    node_type: str,
    text: str,
    data: dict[str, Any],
    busy_timeout_ms: int,
) -> tuple[int, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        parent = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=parent_ref,
            node_type=node_type,
            expected_parent_type="FN",
        )
        timestamp = _utc_now()
        cursor = conn.execute(
            """
            INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                None,
                node_type,
                parent.rowid,
                project_id,
                text,
                json.dumps(data, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        rowid = cursor.lastrowid
        if rowid is None:
            raise CliError(
                code="UNKNOWN",
                message=f"{node_type} insert did not return a rowid.",
                target={"project_id": project_id, "parent": parent_ref},
                suggested_action="Retry the command. If it persists, inspect SQLite insert behavior.",
            )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return cast(int, rowid), _node_identity(parent), parent.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_child_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    expected_type: str,
    text: str | None,
    updates: dict[str, Any],
    busy_timeout_ms: int,
) -> tuple[int, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_analysis_node_type(
            node.type, expected_type=expected_type, node_ref=node_ref
        )
        parent = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=str(node.parent_id),
            node_type=expected_type,
            expected_parent_type="FN",
        )
        data = _decode_analysis_node_data(
            node.data,
            node_ref=str(node.rowid),
            entity_label=_analysis_entity_label(expected_type),
        )
        data.update(updates)
        update_name = node.name if text is None else text
        conn.execute(
            "UPDATE nodes SET name = ?, data = ?, updated = ? WHERE rowid = ?",
            (
                update_name,
                json.dumps(data, sort_keys=True),
                _utc_now(),
                node.rowid,
            ),
        )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return node.rowid, _node_identity(parent), parent.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_child_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    expected_type: str,
    busy_timeout_ms: int,
) -> tuple[int, str, int, list[dict[str, Any]]]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_analysis_node_type(
            node.type, expected_type=expected_type, node_ref=node_ref
        )
        parent = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=str(node.parent_id),
            node_type=expected_type,
            expected_parent_type="FN",
        )
        affected_objects = [{"type": expected_type, "rowid": node.rowid}]
        if expected_type == "REQ":
            _cleanup_fm_local_references_for_deleted_node(
                conn,
                fn_rowid=node.parent_id,
                node_rowid=node.rowid,
                json_field="violates_requirements",
                affected_objects=affected_objects,
            )
        elif expected_type == "CHAR":
            _cleanup_fm_local_references_for_deleted_node(
                conn,
                fn_rowid=node.parent_id,
                node_rowid=node.rowid,
                json_field="related_characteristics",
                affected_objects=affected_objects,
            )
        conn.execute("DELETE FROM nodes WHERE rowid = ?", (node.rowid,))
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return node.rowid, _node_identity(parent), parent.rowid, affected_objects
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_analysis_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    expected_type: str,
    description: str | None,
    updates: dict[str, Any],
    busy_timeout_ms: int,
) -> tuple[str | None, int, str, int]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_analysis_node_type(
            node.type, expected_type=expected_type, node_ref=node_ref
        )
        parent = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=str(node.parent_id),
            node_type=expected_type,
            expected_parent_type=_expected_analysis_parent_type(expected_type),
        )
        data = _decode_analysis_node_data(
            node.data,
            node_ref=_node_identity(node),
            entity_label=_analysis_entity_label(expected_type),
        )
        resolved_updates = _validate_analysis_node_updates(
            conn,
            node=node,
            parent=parent,
            expected_type=expected_type,
            updates=updates,
        )
        data.update(resolved_updates)
        update_name = node.name if description is None else description
        conn.execute(
            "UPDATE nodes SET name = ?, data = ?, updated = ? WHERE rowid = ?",
            (
                update_name,
                json.dumps(data, sort_keys=True),
                _utc_now(),
                node.rowid,
            ),
        )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return node.id, node.rowid, _node_identity(parent), parent.rowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _mutate_fm_local_link_once(
    *,
    db_path: Path,
    project_id: str,
    fm_ref: str,
    linked_ref: str,
    expected_linked_type: str,
    json_field: str,
    mode: str,
    busy_timeout_ms: int,
) -> tuple[ResolvedNode, ResolvedNode, ResolvedNode]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        fm_node = resolve_node_reference(conn, project_id=project_id, node_ref=fm_ref)
        _ensure_analysis_node_type(fm_node.type, expected_type="FM", node_ref=fm_ref)
        fn_node = _resolve_parent_node(
            conn,
            project_id=project_id,
            parent_ref=str(fm_node.parent_id),
            node_type="FM",
            expected_parent_type="FN",
        )
        linked_node = resolve_node_reference(
            conn, project_id=project_id, node_ref=linked_ref
        )
        _ensure_analysis_node_type(
            linked_node.type, expected_type=expected_linked_type, node_ref=linked_ref
        )
        if linked_node.parent_id != fn_node.rowid:
            raise CliError(
                code="INVALID_REFERENCE",
                message=(
                    f"{expected_linked_type} reference '{linked_ref}' does not belong to function "
                    f"'{_node_identity(fn_node)}'."
                ),
                target={"node": linked_ref, "fn": _node_identity(fn_node)},
                suggested_action=(
                    f"Use a {expected_linked_type} rowid that belongs to function '{_node_identity(fn_node)}'."
                ),
            )

        data = _decode_analysis_node_data(
            fm_node.data,
            node_ref=_node_identity(fm_node),
            entity_label="failure mode",
        )
        refs = _decode_optional_int_list_field(
            data=data,
            field=json_field,
            node_ref=_node_identity(fm_node),
            entity_label="failure mode",
        )
        if mode == "link":
            if linked_node.rowid not in refs:
                refs.append(linked_node.rowid)
        else:
            refs = [ref for ref in refs if ref != linked_node.rowid]
        if refs:
            data[json_field] = refs
        else:
            data.pop(json_field, None)
        conn.execute(
            "UPDATE nodes SET data = ?, updated = ? WHERE rowid = ?",
            (json.dumps(data, sort_keys=True), _utc_now(), fm_node.rowid),
        )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return fn_node, fm_node, linked_node
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _mutate_trace_link_once(
    *,
    db_path: Path,
    project_id: str,
    from_ref: str,
    to_fm_ref: str,
    mode: str,
    busy_timeout_ms: int,
) -> tuple[ResolvedNode, ResolvedNode]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        source_type, source_rowid = _parse_trace_source_ref(from_ref)
        source_node = resolve_node_reference(
            conn, project_id=project_id, node_ref=str(source_rowid)
        )
        _ensure_analysis_node_type(
            source_node.type, expected_type=source_type, node_ref=str(source_rowid)
        )
        to_fm_node = resolve_node_reference(
            conn, project_id=project_id, node_ref=to_fm_ref
        )
        _ensure_analysis_node_type(
            to_fm_node.type, expected_type="FM", node_ref=to_fm_ref
        )
        _validate_trace_link_directionality(
            conn,
            source_node=source_node,
            to_fm_node=to_fm_node,
            from_ref=from_ref,
            to_fm_ref=to_fm_ref,
        )

        if mode == "link":
            conn.execute(
                "INSERT OR IGNORE INTO fm_links (from_rowid, to_fm_rowid) VALUES (?, ?)",
                (source_node.rowid, to_fm_node.rowid),
            )
        else:
            conn.execute(
                "DELETE FROM fm_links WHERE from_rowid = ? AND to_fm_rowid = ?",
                (source_node.rowid, to_fm_node.rowid),
            )
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return source_node, to_fm_node
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_analysis_node_once(
    *,
    db_path: Path,
    project_id: str,
    node_ref: str,
    busy_timeout_ms: int,
) -> tuple[str, str | None, int, list[dict[str, Any]]]:
    conn = db_helpers.connect(db_path, busy_timeout_ms=busy_timeout_ms)

    try:
        conn.execute("BEGIN")
        node = resolve_node_reference(conn, project_id=project_id, node_ref=node_ref)
        _ensure_analysis_scope_node(node.type, node_ref=node_ref)
        affected_objects: list[dict[str, Any]] = [_affected_object_for_node(node)]

        if node.type == "FC":
            _cleanup_actions_for_deleted_fc(
                conn,
                fc_node=node,
                affected_objects=affected_objects,
            )
        elif node.type == "REQ":
            _cleanup_fm_local_references_for_deleted_node(
                conn,
                fn_rowid=node.parent_id,
                node_rowid=node.rowid,
                json_field="violates_requirements",
                affected_objects=affected_objects,
            )
        elif node.type == "CHAR":
            _cleanup_fm_local_references_for_deleted_node(
                conn,
                fn_rowid=node.parent_id,
                node_rowid=node.rowid,
                json_field="related_characteristics",
                affected_objects=affected_objects,
            )

        conn.execute("DELETE FROM nodes WHERE rowid = ?", (node.rowid,))
        mark_projection_dirty(conn, project_id=project_id)
        conn.commit()
        return node.type, node.id, node.rowid, affected_objects
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _resolve_parent_node(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    parent_ref: str,
    node_type: str,
    expected_parent_type: str,
):
    parent = resolve_node_reference(conn, project_id=project_id, node_ref=parent_ref)
    if parent.type != expected_parent_type:
        raise CliError(
            code="INVALID_PARENT",
            message=f"{node_type} nodes require a {expected_parent_type} parent.",
            target={
                "node_type": node_type,
                "parent_ref": parent_ref,
                "parent_type": parent.type,
            },
            suggested_action=f"Use a {expected_parent_type} parent for {node_type} nodes.",
        )
    return parent


def _insert_analysis_node(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    parent_rowid: int,
    node_type: str,
    name: str,
    data: dict[str, Any],
    allocate_id: bool,
) -> tuple[str | None, int]:
    timestamp = _utc_now()
    node_id = (
        _allocate_business_id(conn, project_id=project_id, node_type=node_type)
        if allocate_id
        else None
    )
    cursor = conn.execute(
        """
        INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id,
            node_type,
            parent_rowid,
            project_id,
            name,
            json.dumps(data, sort_keys=True),
            timestamp,
            timestamp,
        ),
    )
    rowid = cursor.lastrowid
    if rowid is None:
        raise CliError(
            code="UNKNOWN",
            message=f"{node_type} insert did not return a rowid.",
            target={"project_id": project_id, "parent_rowid": parent_rowid},
            suggested_action="Retry the command. If it persists, inspect SQLite insert behavior.",
        )
    return node_id, cast(int, rowid)


def _ensure_analysis_node_type(
    actual_type: str, *, expected_type: str, node_ref: str
) -> None:
    if actual_type == expected_type:
        return
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"Node '{node_ref}' is type '{actual_type}', expected '{expected_type}'.",
        target={
            "node": node_ref,
            "type": actual_type,
            "expected_type": expected_type,
        },
        suggested_action=f"Provide a {expected_type} node reference for this command.",
    )


def _normalize_failure_chain_spec(chain_spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(chain_spec, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message="Failure-chain input must decode to a JSON object.",
            target={"field": "input"},
            suggested_action="Provide an object with fm, fe, fc, and act sections.",
        )

    fm_raw = chain_spec.get("fm")
    if not isinstance(fm_raw, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message="Failure-chain input requires an fm object.",
            target={"field": "fm"},
            suggested_action="Provide fm.description and fm.severity.",
        )

    return {
        "fm": {
            "description": _coerce_required_text(
                fm_raw.get("description"), field="fm.description"
            ),
            "severity": _coerce_int_in_range(
                fm_raw.get("severity"), field="fm.severity", minimum=1, maximum=10
            ),
            "violates_requirements": _coerce_int_list(
                fm_raw.get("violates_requirements", []),
                field="fm.violates_requirements",
                minimum=1,
            ),
            "related_characteristics": _coerce_int_list(
                fm_raw.get("related_characteristics", []),
                field="fm.related_characteristics",
                minimum=1,
            ),
        },
        "fe": _normalize_fe_specs(chain_spec.get("fe", [])),
        "fc": _normalize_fc_specs(chain_spec.get("fc", [])),
        "act": _normalize_act_specs(chain_spec.get("act", [])),
    }


def _normalize_fe_specs(raw_value: Any) -> list[dict[str, Any]]:
    items = _coerce_list(raw_value, field="fe")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise _invalid_field_error(
                field=f"fe[{index}]",
                message="FE entries must be JSON objects.",
                suggested_action="Provide each FE entry as an object with description and optional level.",
            )
        level = item.get("level")
        normalized.append(
            {
                "description": _coerce_required_text(
                    item.get("description"), field=f"fe[{index}].description"
                ),
                "level": None
                if level is None
                else _coerce_required_text(level, field=f"fe[{index}].level"),
            }
        )
    return normalized


def _normalize_fc_specs(raw_value: Any) -> list[dict[str, Any]]:
    items = _coerce_list(raw_value, field="fc")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise _invalid_field_error(
                field=f"fc[{index}]",
                message="FC entries must be JSON objects.",
                suggested_action="Provide each FC entry as an object with description, occurrence, detection, and ap.",
            )
        normalized.append(
            {
                "description": _coerce_required_text(
                    item.get("description"), field=f"fc[{index}].description"
                ),
                "occurrence": _coerce_int_in_range(
                    item.get("occurrence"),
                    field=f"fc[{index}].occurrence",
                    minimum=1,
                    maximum=10,
                ),
                "detection": _coerce_int_in_range(
                    item.get("detection"),
                    field=f"fc[{index}].detection",
                    minimum=1,
                    maximum=10,
                ),
                "ap": _coerce_allowed_text(
                    item.get("ap"),
                    field=f"fc[{index}].ap",
                    allowed=ALLOWED_AP_VALUES,
                ),
            }
        )
    return normalized


def _normalize_act_specs(raw_value: Any) -> list[dict[str, Any]]:
    items = _coerce_list(raw_value, field="act")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise _invalid_field_error(
                field=f"act[{index}]",
                message="ACT entries must be JSON objects.",
                suggested_action="Provide each ACT entry as an object with description and optional metadata.",
            )
        due = item.get("due")
        kind = item.get("kind")
        status = item.get("status")
        owner = item.get("owner")
        normalized.append(
            {
                "description": _coerce_required_text(
                    item.get("description"), field=f"act[{index}].description"
                ),
                "kind": None
                if kind is None
                else _coerce_allowed_text(
                    kind,
                    field=f"act[{index}].kind",
                    allowed=ALLOWED_ACTION_KINDS,
                ),
                "status": None
                if status is None
                else _coerce_allowed_text(
                    status,
                    field=f"act[{index}].status",
                    allowed=ALLOWED_ACTION_STATUSES,
                ),
                "owner": None
                if owner is None
                else _coerce_required_text(owner, field=f"act[{index}].owner"),
                "due": None
                if due is None
                else _coerce_iso_date(due, field=f"act[{index}].due"),
                "target_causes": _coerce_int_list(
                    item.get("target_causes", []),
                    field=f"act[{index}].target_causes",
                    minimum=1,
                ),
            }
        )
    return normalized


def _coerce_list(raw_value: Any, *, field: str) -> list[Any]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return raw_value
    raise _invalid_field_error(
        field=field,
        message=f"Field '{field}' must be a JSON array.",
        suggested_action=f"Provide {field} as an array.",
    )


def _coerce_required_text(raw_value: Any, *, field: str) -> str:
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value
    raise _invalid_field_error(
        field=field,
        message=f"Field '{field}' must be a non-empty string.",
        suggested_action=f"Provide a non-empty string for {field}.",
    )


def _coerce_allowed_text(raw_value: Any, *, field: str, allowed: set[str]) -> str:
    text_value = _coerce_required_text(raw_value, field=field)
    if text_value in allowed:
        return text_value
    raise _invalid_field_error(
        field=field,
        message=f"Field '{field}' must be one of {sorted(allowed)}.",
        suggested_action=f"Use one of {sorted(allowed)} for {field}.",
    )


def _coerce_iso_date(raw_value: Any, *, field: str) -> str:
    text_value = _coerce_required_text(raw_value, field=field)
    try:
        date.fromisoformat(text_value)
    except ValueError as exc:
        raise _invalid_field_error(
            field=field,
            message=f"Field '{field}' must be an ISO date (YYYY-MM-DD).",
            suggested_action=f"Provide {field} in YYYY-MM-DD format.",
        ) from exc
    return text_value


def _coerce_int_in_range(
    raw_value: Any, *, field: str, minimum: int, maximum: int | None = None
) -> int:
    if isinstance(raw_value, bool):
        raise _invalid_field_error(
            field=field,
            message=f"Field '{field}' must be an integer.",
            suggested_action=f"Provide an integer value for {field}.",
        )
    int_value = _coerce_strict_integer(raw_value, field=field)
    if int_value < minimum or (maximum is not None and int_value > maximum):
        range_label = f"{minimum}-{maximum}" if maximum is not None else f">= {minimum}"
        raise _invalid_field_error(
            field=field,
            message=f"Field '{field}' must be in range {range_label}.",
            suggested_action=f"Provide a value in range {range_label} for {field}.",
        )
    return int_value


def _coerce_strict_integer(raw_value: Any, *, field: str) -> int:
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        raise _invalid_field_error(
            field=field,
            message=f"Field '{field}' must be an integer.",
            suggested_action=f"Provide an integer value for {field}.",
        )
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped and (
            stripped.isdigit() or (stripped[0] in "+-" and stripped[1:].isdigit())
        ):
            return int(stripped)
        raise _invalid_field_error(
            field=field,
            message=f"Field '{field}' must be an integer.",
            suggested_action=f"Provide an integer value for {field}.",
        )
    raise _invalid_field_error(
        field=field,
        message=f"Field '{field}' must be an integer.",
        suggested_action=f"Provide an integer value for {field}.",
    )


def _coerce_int_list(raw_value: Any, *, field: str, minimum: int) -> list[int]:
    values = _coerce_list(raw_value, field=field)
    return [
        _coerce_int_in_range(value, field=f"{field}[{index}]", minimum=minimum)
        for index, value in enumerate(values, start=1)
    ]


def _invalid_field_error(
    *, field: str, message: str, suggested_action: str
) -> CliError:
    return CliError(
        code="INVALID_REFERENCE",
        message=message,
        target={"field": field},
        suggested_action=suggested_action,
    )


def _validate_linked_analysis_refs(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    fn_node,
    refs: list[int],
    expected_type: str,
) -> list[int]:
    validated_refs: list[int] = []
    for ref in refs:
        node = resolve_node_reference(conn, project_id=project_id, node_ref=str(ref))
        _ensure_analysis_node_type(
            node.type, expected_type=expected_type, node_ref=str(ref)
        )
        if node.parent_id != fn_node.rowid:
            raise CliError(
                code="INVALID_REFERENCE",
                message=(
                    f"{expected_type} reference '{ref}' does not belong to function "
                    f"'{_node_identity(fn_node)}'."
                ),
                target={"node": str(ref), "fn": _node_identity(fn_node)},
                suggested_action=(
                    f"Use a {expected_type} rowid that belongs to function '{_node_identity(fn_node)}'."
                ),
            )
        validated_refs.append(node.rowid)
    return validated_refs


def _resolve_target_causes(
    *, fc_rowids: list[int], target_causes: list[int]
) -> list[int]:
    resolved_targets: list[int] = []
    for fc_index in target_causes:
        if fc_index < 1 or fc_index > len(fc_rowids):
            raise CliError(
                code="INVALID_REFERENCE",
                message=(
                    f"target_causes reference FC item {fc_index}, but that FC item is not being created in this request."
                ),
                target={"fc_index": fc_index, "fm": "new"},
                suggested_action=(
                    "Use 1-based FC creation-order indexes that exist in this failure-chain request."
                ),
            )
        resolved_targets.append(fc_rowids[fc_index - 1])
    return resolved_targets


def _ensure_mutable_fields_present(
    *, fields: dict[str, Any], entity_label: str
) -> None:
    if any(value is not None for value in fields.values()):
        return
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"{entity_label.capitalize()} update requires at least one mutable field.",
        target={"entity": entity_label, "fields": sorted(fields)},
        suggested_action="Provide at least one update field for this command.",
    )


def _decode_analysis_node_data(
    raw_data: str | None, *, node_ref: str, entity_label: str
) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_data or "{}")
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"{entity_label.capitalize()} '{node_ref}' has malformed JSON data.",
            target={"node": node_ref, "entity": entity_label},
            suggested_action=f"Repair the stored {entity_label} JSON before updating this record.",
        ) from exc
    if not isinstance(decoded, dict):
        raise CliError(
            code="INVALID_REFERENCE",
            message=f"{entity_label.capitalize()} '{node_ref}' data must decode to a JSON object.",
            target={"node": node_ref, "entity": entity_label},
            suggested_action=f"Repair the stored {entity_label} JSON object before updating this record.",
        )
    return decoded


def _analysis_entity_label(node_type: str) -> str:
    return {
        "FN": "function",
        "FM": "failure mode",
        "FE": "failure effect",
        "FC": "failure cause",
        "ACT": "action",
        "REQ": "requirement",
        "CHAR": "characteristic",
    }.get(node_type, "analysis node")


def _expected_analysis_parent_type(node_type: str) -> str:
    return {
        "FM": "FN",
        "FE": "FM",
        "FC": "FM",
        "ACT": "FM",
        "REQ": "FN",
        "CHAR": "FN",
    }.get(node_type, "FN")


def _validate_analysis_node_updates(
    conn: sqlite3.Connection,
    *,
    node: ResolvedNode,
    parent: ResolvedNode,
    expected_type: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    resolved_updates: dict[str, Any] = {}

    if expected_type == "FM":
        if "severity" in updates:
            resolved_updates["severity"] = _coerce_int_in_range(
                updates["severity"], field="severity", minimum=1, maximum=10
            )
        return resolved_updates

    if expected_type == "FE":
        if "level" in updates:
            resolved_updates["level"] = _coerce_required_text(
                updates["level"], field="level"
            )
        return resolved_updates

    if expected_type == "FC":
        if "occurrence" in updates:
            resolved_updates["occurrence"] = _coerce_int_in_range(
                updates["occurrence"], field="occurrence", minimum=1, maximum=10
            )
        if "detection" in updates:
            resolved_updates["detection"] = _coerce_int_in_range(
                updates["detection"], field="detection", minimum=1, maximum=10
            )
        if "ap" in updates:
            resolved_updates["ap"] = _coerce_allowed_text(
                updates["ap"], field="ap", allowed=ALLOWED_AP_VALUES
            )
        return resolved_updates

    if expected_type == "ACT":
        if "kind" in updates:
            resolved_updates["kind"] = _coerce_allowed_text(
                updates["kind"], field="kind", allowed=ALLOWED_ACTION_KINDS
            )
        if "status" in updates:
            resolved_updates["status"] = _coerce_allowed_text(
                updates["status"], field="status", allowed=ALLOWED_ACTION_STATUSES
            )
        if "owner" in updates:
            resolved_updates["owner"] = _coerce_required_text(
                updates["owner"], field="owner"
            )
        if "due" in updates:
            resolved_updates["due"] = _coerce_iso_date(updates["due"], field="due")
        if "target_causes" in updates:
            resolved_updates["target_causes"] = _validate_action_target_causes(
                conn,
                project_id=node.project_id,
                fm_node=parent,
                target_causes=updates["target_causes"],
            )
        return resolved_updates

    return updates


def _validate_action_target_causes(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    fm_node: ResolvedNode,
    target_causes: Any,
) -> list[int]:
    rowids = _coerce_int_list(target_causes, field="target_causes", minimum=1)
    validated: list[int] = []
    for rowid in rowids:
        fc_node = resolve_node_reference(
            conn, project_id=project_id, node_ref=str(rowid)
        )
        _ensure_analysis_node_type(
            fc_node.type, expected_type="FC", node_ref=str(rowid)
        )
        if fc_node.parent_id != fm_node.rowid:
            raise CliError(
                code="INVALID_REFERENCE",
                message=(
                    f"FC reference '{rowid}' does not belong to failure mode "
                    f"'{_node_identity(fm_node)}'."
                ),
                target={"node": str(rowid), "fm": _node_identity(fm_node)},
                suggested_action=(
                    f"Use FC rowids that belong to failure mode '{_node_identity(fm_node)}'."
                ),
            )
        validated.append(fc_node.rowid)
    return validated


def _parse_trace_source_ref(from_ref: str) -> tuple[str, int]:
    prefix, separator, rowid_text = from_ref.partition(":")
    if separator != ":":
        raise CliError(
            code="INVALID_REFERENCE",
            message="Trace source must use the format <fe|fc>:<rowid>.",
            target={"from": from_ref},
            suggested_action="Use --from fe:<rowid> or --from fc:<rowid>.",
        )
    normalized_prefix = prefix.strip().upper()
    if normalized_prefix not in {"FE", "FC"}:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Trace source must start with fe or fc.",
            target={"from": from_ref},
            suggested_action="Use --from fe:<rowid> or --from fc:<rowid>.",
        )
    rowid = _coerce_int_in_range(rowid_text.strip(), field="from", minimum=1)
    return normalized_prefix, rowid


def _ensure_analysis_scope_node(node_type: str, *, node_ref: str) -> None:
    if node_type in {"FN", "FM", "FE", "FC", "ACT", "REQ", "CHAR"}:
        return
    raise CliError(
        code="INVALID_REFERENCE",
        message=(
            f"Node '{node_ref}' is type '{node_type}', which is outside analysis delete-node scope."
        ),
        target={"node": node_ref, "type": node_type},
        suggested_action=(
            "Use analysis delete-node only with FN, FM, FE, FC, ACT, REQ, or CHAR nodes."
        ),
    )


def _affected_object_for_node(node: ResolvedNode) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": node.type, "rowid": node.rowid}
    if node.id is not None:
        payload["id"] = node.id
    return payload


def _cleanup_actions_for_deleted_fc(
    conn: sqlite3.Connection,
    *,
    fc_node: ResolvedNode,
    affected_objects: list[dict[str, Any]],
) -> None:
    act_rows = conn.execute(
        "SELECT rowid, id, type, parent_id, project_id, name, data FROM nodes WHERE type = 'ACT' AND parent_id = ? ORDER BY rowid",
        (fc_node.parent_id,),
    ).fetchall()
    for row in act_rows:
        act_node = ResolvedNode(
            rowid=int(row[0]),
            id=row[1],
            type=row[2],
            parent_id=int(row[3]),
            project_id=row[4],
            name=row[5],
            data=row[6],
        )
        act_data = _decode_analysis_node_data(
            act_node.data,
            node_ref=_node_identity(act_node),
            entity_label="action",
        )
        target_causes = _decode_optional_int_list_field(
            data=act_data,
            field="target_causes",
            node_ref=_node_identity(act_node),
            entity_label="action",
        )
        if fc_node.rowid not in target_causes:
            continue

        remaining = [rowid for rowid in target_causes if rowid != fc_node.rowid]
        affected_objects.append(_affected_object_for_node(act_node))
        if remaining:
            act_data["target_causes"] = remaining
            conn.execute(
                "UPDATE nodes SET data = ?, updated = ? WHERE rowid = ?",
                (json.dumps(act_data, sort_keys=True), _utc_now(), act_node.rowid),
            )
        else:
            conn.execute("DELETE FROM nodes WHERE rowid = ?", (act_node.rowid,))


def _cleanup_fm_local_references_for_deleted_node(
    conn: sqlite3.Connection,
    *,
    fn_rowid: int,
    node_rowid: int,
    json_field: str,
    affected_objects: list[dict[str, Any]] | None = None,
) -> None:
    fm_rows = conn.execute(
        "SELECT rowid, id, type, parent_id, project_id, name, data FROM nodes WHERE type = 'FM' AND parent_id = ? ORDER BY rowid",
        (fn_rowid,),
    ).fetchall()
    for row in fm_rows:
        fm_node = ResolvedNode(
            rowid=int(row[0]),
            id=row[1],
            type=row[2],
            parent_id=int(row[3]),
            project_id=row[4],
            name=row[5],
            data=row[6],
        )
        fm_data = _decode_analysis_node_data(
            fm_node.data,
            node_ref=_node_identity(fm_node),
            entity_label="failure mode",
        )
        refs = _decode_optional_int_list_field(
            data=fm_data,
            field=json_field,
            node_ref=_node_identity(fm_node),
            entity_label="failure mode",
        )
        updated_refs = [ref for ref in refs if ref != node_rowid]
        if updated_refs == refs:
            continue
        if updated_refs:
            fm_data[json_field] = updated_refs
        else:
            fm_data.pop(json_field, None)
        conn.execute(
            "UPDATE nodes SET data = ?, updated = ? WHERE rowid = ?",
            (json.dumps(fm_data, sort_keys=True), _utc_now(), fm_node.rowid),
        )
        if affected_objects is not None:
            affected_objects.append(_affected_object_for_node(fm_node))


def _decode_optional_int_list_field(
    *,
    data: dict[str, Any],
    field: str,
    node_ref: str,
    entity_label: str,
) -> list[int]:
    raw_value = data.get(field)
    if raw_value is None:
        return []
    if not isinstance(raw_value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in raw_value
    ):
        raise CliError(
            code="INVALID_REFERENCE",
            message=(
                f"{entity_label.capitalize()} '{node_ref}' field '{field}' must be an integer list."
            ),
            target={"node": node_ref, "entity": entity_label, "field": field},
            suggested_action=(
                f"Repair the stored {entity_label} JSON so '{field}' is an array of integers."
            ),
        )
    return list(raw_value)


def _validate_trace_link_directionality(
    conn: sqlite3.Connection,
    *,
    source_node: ResolvedNode,
    to_fm_node: ResolvedNode,
    from_ref: str,
    to_fm_ref: str,
) -> None:
    source_component_id = _resolve_component_id_for_analysis_node(conn, source_node)
    target_component_id = _resolve_component_id_for_analysis_node(conn, to_fm_node)
    if source_component_id == target_component_id:
        raise CliError(
            code="INVALID_REFERENCE",
            message=(
                f"{source_node.type} trace links must target an FM in a different component."
            ),
            target={
                "from": from_ref,
                "to_fm": to_fm_ref,
                "source_component": source_component_id,
                "target_component": target_component_id,
            },
            suggested_action="Link trace nodes only to FM nodes in a different component.",
        )


def _resolve_component_id_for_analysis_node(
    conn: sqlite3.Connection, node: ResolvedNode
) -> str:
    current = node
    while True:
        if current.type == "COMP":
            return _node_identity(current)
        if current.parent_id == 0:
            raise CliError(
                code="INVALID_REFERENCE",
                message=f"Node '{_node_identity(node)}' is not attached to a component.",
                target={"node": _node_identity(node), "type": node.type},
                suggested_action="Repair the node hierarchy before creating trace links.",
            )
        current = resolve_node_reference(
            conn, project_id=node.project_id, node_ref=str(current.parent_id)
        )


def _normalize_analysis_storage_error(
    *,
    exc: sqlite3.Error,
    db_path: Path,
    project_id: str,
    operation: str,
) -> CliError:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return DbBusyError(db_path=db_path)
    if "no such table" in message:
        return CliError(
            code="INVALID_REFERENCE",
            message="Database does not expose the expected DFMEA schema.",
            target={"db": str(db_path)},
            suggested_action="Initialize a valid DFMEA database before running analysis commands.",
        )
    return CliError(
        code="UNKNOWN",
        message=f"Failed to {operation} in project '{project_id}'.",
        target={"db": str(db_path), "project_id": project_id},
        suggested_action="Retry the command. If it persists, inspect database integrity and SQLite state.",
    )
