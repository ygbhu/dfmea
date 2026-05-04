from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from quality_core.cli.errors import QualityCliError
from quality_core.resources.envelope import Resource, make_resource
from quality_core.resources.paths import ResourceSelector, id_prefix
from quality_core.resources.store import ResourceStore
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.plugin import get_plugin

FUNCTION_KIND = "Function"
REQUIREMENT_KIND = "Requirement"
CHARACTERISTIC_KIND = "Characteristic"
FAILURE_MODE_KIND = "FailureMode"
FAILURE_EFFECT_KIND = "FailureEffect"
FAILURE_CAUSE_KIND = "FailureCause"
ACTION_KIND = "Action"
STRUCTURE_KIND = "StructureNode"

ALLOWED_ACTION_KINDS = {"prevention", "detection"}
ALLOWED_ACTION_STATUSES = {"planned", "in-progress", "completed"}
ALLOWED_AP_VALUES = {"High", "Medium", "Low"}
ALLOWED_EFFECTIVENESS_STATUSES = {"pending", "verified-effective", "verified-ineffective"}

KIND_BY_PREFIX = {
    "FN": FUNCTION_KIND,
    "REQ": REQUIREMENT_KIND,
    "CHAR": CHARACTERISTIC_KIND,
    "FM": FAILURE_MODE_KIND,
    "FE": FAILURE_EFFECT_KIND,
    "FC": FAILURE_CAUSE_KIND,
    "ACT": ACTION_KIND,
}


@dataclass(frozen=True, slots=True)
class AnalysisMutationResult:
    project: ProjectConfig
    resource: Resource | None
    changed_paths: tuple[Path, ...]
    affected_objects: tuple[dict[str, Any], ...]
    tombstone_paths: tuple[Path, ...] = ()


def compute_ap(severity: int, occurrence: int, detection: int) -> str:
    """Compute Action Priority from the historical DFMEA CLI matrix."""
    if severity >= 9:
        return "High"
    if severity >= 7 and occurrence >= 4 and detection >= 4:
        return "High"
    if severity >= 5 and occurrence >= 7 and detection >= 4:
        return "High"
    if severity <= 3:
        return "Low"
    if severity <= 4 and occurrence <= 4 and detection <= 4:
        return "Low"
    return "Medium"


def add_function(
    *,
    project: ProjectConfig,
    component_ref: str,
    title: str,
    description: str | None = None,
) -> AnalysisMutationResult:
    store = _store(project)
    component = _load_structure_component(store=store, component_ref=component_ref)
    spec: dict[str, Any] = {"componentRef": component.resource_id}
    if description is not None:
        spec["description"] = _coerce_text(description, field="description")
    result = store.create_collection_resource(
        kind=FUNCTION_KIND,
        id_prefix="FN",
        metadata={"title": _coerce_text(title, field="title")},
        spec=spec,
    )
    resource = store.load(store.ref(kind=FUNCTION_KIND, resource_id=result.resource_id))
    return _single_result(project=project, resource=resource, path=result.path)


def update_function(
    *,
    project: ProjectConfig,
    function_ref: str,
    title: str | None = None,
    description: str | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="function",
        fields={"title": title, "description": description},
    )
    store = _store(project)
    resource = _load(store=store, kind=FUNCTION_KIND, resource_id=function_ref)
    metadata = dict(resource.metadata)
    if title is not None:
        metadata["title"] = _coerce_text(title, field="title")
    spec = dict(resource.spec)
    if description is not None:
        spec["description"] = _coerce_text(description, field="description")
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def delete_function(*, project: ProjectConfig, function_ref: str) -> AnalysisMutationResult:
    store = _store(project)
    resource = _load(store=store, kind=FUNCTION_KIND, resource_id=function_ref)
    children = _resources_with_spec_ref(
        store=store,
        kinds=(REQUIREMENT_KIND, CHARACTERISTIC_KIND, FAILURE_MODE_KIND),
        field="functionRef",
        target_id=resource.resource_id,
    )
    if children:
        raise QualityCliError(
            code="NODE_NOT_EMPTY",
            message=f"Function '{resource.resource_id}' still has analysis children.",
            target={
                "resourceId": resource.resource_id,
                "children": [child.resource_id for child in children],
            },
            suggestion=(
                "Delete or move requirement, characteristic, and failure mode children first."
            ),
        )
    return _delete_loaded(project=project, store=store, resource=resource)


def add_requirement(
    *,
    project: ProjectConfig,
    function_ref: str,
    text: str,
    source: str | None = None,
) -> AnalysisMutationResult:
    store = _store(project)
    function = _load(store=store, kind=FUNCTION_KIND, resource_id=function_ref)
    spec: dict[str, Any] = {
        "functionRef": function.resource_id,
        "text": _coerce_text(text, field="text"),
    }
    if source is not None:
        spec["source"] = _coerce_text(source, field="source")
    result = store.create_collection_resource(
        kind=REQUIREMENT_KIND,
        id_prefix="REQ",
        metadata={"title": spec["text"]},
        spec=spec,
    )
    resource = store.load(store.ref(kind=REQUIREMENT_KIND, resource_id=result.resource_id))
    return _single_result(project=project, resource=resource, path=result.path)


def update_requirement(
    *,
    project: ProjectConfig,
    requirement_ref: str,
    text: str | None = None,
    source: str | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="requirement",
        fields={"text": text, "source": source},
    )
    store = _store(project)
    resource = _load(store=store, kind=REQUIREMENT_KIND, resource_id=requirement_ref)
    metadata = dict(resource.metadata)
    spec = dict(resource.spec)
    if text is not None:
        spec["text"] = _coerce_text(text, field="text")
        metadata["title"] = spec["text"]
    if source is not None:
        spec["source"] = _coerce_text(source, field="source")
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def delete_requirement(*, project: ProjectConfig, requirement_ref: str) -> AnalysisMutationResult:
    store = _store(project)
    resource = _load(store=store, kind=REQUIREMENT_KIND, resource_id=requirement_ref)
    changed: list[Path] = []
    affected: list[dict[str, Any]] = []
    for fm in store.list(ResourceSelector(kind=FAILURE_MODE_KIND)):
        spec = dict(fm.spec)
        refs = _string_list(spec.get("requirementRefs"), field="requirementRefs")
        if resource.resource_id not in refs:
            continue
        spec["requirementRefs"] = [ref for ref in refs if ref != resource.resource_id]
        updated = _write_updated_resource(
            store=store, resource=fm, metadata=dict(fm.metadata), spec=spec
        )
        changed.append(updated.path)
        affected.append(_affected(updated))
    deleted = _delete_loaded(project=project, store=store, resource=resource)
    return _merge_result(
        project=project, primary=resource, changed=changed, affected=affected, tail=deleted
    )


def add_characteristic(
    *,
    project: ProjectConfig,
    function_ref: str,
    text: str,
    value: str | None = None,
    unit: str | None = None,
) -> AnalysisMutationResult:
    store = _store(project)
    function = _load(store=store, kind=FUNCTION_KIND, resource_id=function_ref)
    spec: dict[str, Any] = {
        "functionRef": function.resource_id,
        "text": _coerce_text(text, field="text"),
    }
    if value is not None:
        spec["value"] = _coerce_text(value, field="value")
    if unit is not None:
        spec["unit"] = _coerce_text(unit, field="unit")
    result = store.create_collection_resource(
        kind=CHARACTERISTIC_KIND,
        id_prefix="CHAR",
        metadata={"title": spec["text"]},
        spec=spec,
    )
    resource = store.load(store.ref(kind=CHARACTERISTIC_KIND, resource_id=result.resource_id))
    return _single_result(project=project, resource=resource, path=result.path)


def update_characteristic(
    *,
    project: ProjectConfig,
    characteristic_ref: str,
    text: str | None = None,
    value: str | None = None,
    unit: str | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="characteristic",
        fields={"text": text, "value": value, "unit": unit},
    )
    store = _store(project)
    resource = _load(store=store, kind=CHARACTERISTIC_KIND, resource_id=characteristic_ref)
    metadata = dict(resource.metadata)
    spec = dict(resource.spec)
    if text is not None:
        spec["text"] = _coerce_text(text, field="text")
        metadata["title"] = spec["text"]
    if value is not None:
        spec["value"] = _coerce_text(value, field="value")
    if unit is not None:
        spec["unit"] = _coerce_text(unit, field="unit")
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def delete_characteristic(
    *, project: ProjectConfig, characteristic_ref: str
) -> AnalysisMutationResult:
    store = _store(project)
    resource = _load(store=store, kind=CHARACTERISTIC_KIND, resource_id=characteristic_ref)
    changed: list[Path] = []
    affected: list[dict[str, Any]] = []
    for fm in store.list(ResourceSelector(kind=FAILURE_MODE_KIND)):
        spec = dict(fm.spec)
        refs = _string_list(spec.get("characteristicRefs"), field="characteristicRefs")
        if resource.resource_id not in refs:
            continue
        spec["characteristicRefs"] = [ref for ref in refs if ref != resource.resource_id]
        updated = _write_updated_resource(
            store=store, resource=fm, metadata=dict(fm.metadata), spec=spec
        )
        changed.append(updated.path)
        affected.append(_affected(updated))
    deleted = _delete_loaded(project=project, store=store, resource=resource)
    return _merge_result(
        project=project, primary=resource, changed=changed, affected=affected, tail=deleted
    )


def add_failure_mode(
    *,
    project: ProjectConfig,
    function_ref: str,
    title: str,
    severity: int,
    requirement_refs: list[str] | None = None,
    characteristic_refs: list[str] | None = None,
) -> AnalysisMutationResult:
    store = _store(project)
    function = _load(store=store, kind=FUNCTION_KIND, resource_id=function_ref)
    req_refs = _validate_function_local_refs(
        store=store,
        function_id=function.resource_id,
        refs=requirement_refs or [],
        kind=REQUIREMENT_KIND,
        field="requirementRefs",
    )
    char_refs = _validate_function_local_refs(
        store=store,
        function_id=function.resource_id,
        refs=characteristic_refs or [],
        kind=CHARACTERISTIC_KIND,
        field="characteristicRefs",
    )
    description = _coerce_text(title, field="title")
    spec: dict[str, Any] = {
        "functionRef": function.resource_id,
        "description": description,
        "severity": _coerce_int_in_range(severity, field="severity", minimum=1, maximum=10),
        "requirementRefs": req_refs,
        "characteristicRefs": char_refs,
        "effectRefs": [],
        "causeRefs": [],
        "actionRefs": [],
    }
    result = store.create_collection_resource(
        kind=FAILURE_MODE_KIND,
        id_prefix="FM",
        metadata={"title": description},
        spec=spec,
    )
    resource = store.load(store.ref(kind=FAILURE_MODE_KIND, resource_id=result.resource_id))
    return _single_result(project=project, resource=resource, path=result.path)


def add_failure_chain(
    *,
    project: ProjectConfig,
    function_ref: str,
    chain_spec: dict[str, Any],
) -> AnalysisMutationResult:
    store = _store(project)
    function = _load(store=store, kind=FUNCTION_KIND, resource_id=function_ref)
    normalized = _normalize_failure_chain_spec(chain_spec)
    _validate_target_cause_indexes(normalized)
    req_refs = _validate_function_local_refs(
        store=store,
        function_id=function.resource_id,
        refs=normalized["fm"]["requirementRefs"],
        kind=REQUIREMENT_KIND,
        field="requirementRefs",
    )
    char_refs = _validate_function_local_refs(
        store=store,
        function_id=function.resource_id,
        refs=normalized["fm"]["characteristicRefs"],
        kind=CHARACTERISTIC_KIND,
        field="characteristicRefs",
    )

    fm_result = add_failure_mode(
        project=project,
        function_ref=function.resource_id,
        title=normalized["fm"]["description"],
        severity=normalized["fm"]["severity"],
        requirement_refs=req_refs,
        characteristic_refs=char_refs,
    )
    fm = fm_result.resource
    assert fm is not None
    changed = list(fm_result.changed_paths)
    affected = list(fm_result.affected_objects)

    effect_refs: list[str] = []
    for spec in normalized["fe"]:
        created = _create_failure_effect(store=store, fm=fm, spec=spec)
        effect_refs.append(created.resource_id)
        changed.append(_resource_path(created))
        affected.append(_affected(created))

    cause_refs: list[str] = []
    for spec in normalized["fc"]:
        created = _create_failure_cause(store=store, fm=fm, spec=spec)
        cause_refs.append(created.resource_id)
        changed.append(_resource_path(created))
        affected.append(_affected(created))

    action_refs: list[str] = []
    for spec in normalized["act"]:
        target_refs = [cause_refs[index - 1] for index in spec["targetCauseIndexes"]]
        created = _create_action(store=store, fm=fm, spec=spec, target_cause_refs=target_refs)
        action_refs.append(created.resource_id)
        changed.append(_resource_path(created))
        affected.append(_affected(created))

    fm_spec = dict(fm.spec)
    fm_spec["effectRefs"] = effect_refs
    fm_spec["causeRefs"] = cause_refs
    fm_spec["actionRefs"] = action_refs
    fm = _write_updated_resource(
        store=store,
        resource=fm,
        metadata=dict(fm.metadata),
        spec=fm_spec,
    )
    changed.append(_resource_path(fm))
    affected[0] = _affected(fm)
    return AnalysisMutationResult(
        project=project,
        resource=fm,
        changed_paths=_unique_paths(changed),
        affected_objects=tuple(affected),
    )


def update_failure_mode(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    title: str | None = None,
    severity: int | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="failure mode", fields={"title": title, "severity": severity}
    )
    store = _store(project)
    resource = _load(store=store, kind=FAILURE_MODE_KIND, resource_id=failure_mode_ref)
    metadata = dict(resource.metadata)
    spec = dict(resource.spec)
    if title is not None:
        metadata["title"] = _coerce_text(title, field="title")
        spec["description"] = metadata["title"]
    if severity is not None:
        spec["severity"] = _coerce_int_in_range(severity, field="severity", minimum=1, maximum=10)
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def update_failure_effect(
    *,
    project: ProjectConfig,
    failure_effect_ref: str,
    title: str | None = None,
    level: str | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(entity_label="failure effect", fields={"title": title, "level": level})
    store = _store(project)
    resource = _load(store=store, kind=FAILURE_EFFECT_KIND, resource_id=failure_effect_ref)
    metadata = dict(resource.metadata)
    spec = dict(resource.spec)
    if title is not None:
        metadata["title"] = _coerce_text(title, field="title")
        spec["description"] = metadata["title"]
    if level is not None:
        spec["level"] = _coerce_text(level, field="level")
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def update_failure_cause(
    *,
    project: ProjectConfig,
    failure_cause_ref: str,
    title: str | None = None,
    occurrence: int | None = None,
    detection: int | None = None,
    ap: str | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="failure cause",
        fields={"title": title, "occurrence": occurrence, "detection": detection, "ap": ap},
    )
    store = _store(project)
    resource = _load(store=store, kind=FAILURE_CAUSE_KIND, resource_id=failure_cause_ref)
    fm = _load(
        store=store, kind=FAILURE_MODE_KIND, resource_id=_required_ref(resource, "failureModeRef")
    )
    metadata = dict(resource.metadata)
    spec = dict(resource.spec)
    if title is not None:
        metadata["title"] = _coerce_text(title, field="title")
        spec["description"] = metadata["title"]
    if occurrence is not None:
        spec["occurrence"] = _coerce_int_in_range(
            occurrence, field="occurrence", minimum=1, maximum=10
        )
    if detection is not None:
        spec["detection"] = _coerce_int_in_range(
            detection, field="detection", minimum=1, maximum=10
        )
    if ap is not None:
        spec["ap"] = _coerce_allowed_text(ap, field="ap", allowed=ALLOWED_AP_VALUES)
    elif occurrence is not None or detection is not None:
        spec["ap"] = compute_ap(
            _coerce_int_in_range(
                fm.spec.get("severity", 1), field="severity", minimum=1, maximum=10
            ),
            _coerce_int_in_range(
                spec.get("occurrence", 1), field="occurrence", minimum=1, maximum=10
            ),
            _coerce_int_in_range(
                spec.get("detection", 1), field="detection", minimum=1, maximum=10
            ),
        )
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def update_action(
    *,
    project: ProjectConfig,
    action_ref: str,
    title: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    due: str | None = None,
    target_cause_refs: list[str] | None = None,
    effectiveness_status: str | None = None,
    revised_severity: int | None = None,
    revised_occurrence: int | None = None,
    revised_detection: int | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="action",
        fields={
            "title": title,
            "kind": kind,
            "status": status,
            "owner": owner,
            "due": due,
            "target_cause_refs": target_cause_refs,
            "effectiveness_status": effectiveness_status,
            "revised_severity": revised_severity,
            "revised_occurrence": revised_occurrence,
            "revised_detection": revised_detection,
        },
    )
    store = _store(project)
    resource = _load(store=store, kind=ACTION_KIND, resource_id=action_ref)
    fm = _load(
        store=store, kind=FAILURE_MODE_KIND, resource_id=_required_ref(resource, "failureModeRef")
    )
    metadata = dict(resource.metadata)
    spec = dict(resource.spec)
    if title is not None:
        spec["description"] = _coerce_text(title, field="title")
    if kind is not None:
        spec["kind"] = _coerce_allowed_text(kind, field="kind", allowed=ALLOWED_ACTION_KINDS)
    if status is not None:
        spec["status"] = _coerce_allowed_text(
            status, field="status", allowed=ALLOWED_ACTION_STATUSES
        )
    if owner is not None:
        spec["owner"] = _coerce_text(owner, field="owner")
    if due is not None:
        spec["due"] = _coerce_iso_date(due, field="due")
    if target_cause_refs is not None:
        spec["targetCauseRefs"] = _validate_fm_local_cause_refs(
            store=store,
            failure_mode_id=fm.resource_id,
            refs=target_cause_refs,
        )
    if effectiveness_status is not None:
        spec["effectivenessStatus"] = _coerce_allowed_text(
            effectiveness_status,
            field="effectivenessStatus",
            allowed=ALLOWED_EFFECTIVENESS_STATUSES,
        )
    if revised_severity is not None:
        spec["revisedSeverity"] = _coerce_int_in_range(
            revised_severity,
            field="revisedSeverity",
            minimum=1,
            maximum=10,
        )
    if revised_occurrence is not None:
        spec["revisedOccurrence"] = _coerce_int_in_range(
            revised_occurrence,
            field="revisedOccurrence",
            minimum=1,
            maximum=10,
        )
    if revised_detection is not None:
        spec["revisedDetection"] = _coerce_int_in_range(
            revised_detection,
            field="revisedDetection",
            minimum=1,
            maximum=10,
        )
    return _update_single(
        project=project, store=store, resource=resource, metadata=metadata, spec=spec
    )


def update_action_status(
    *,
    project: ProjectConfig,
    action_ref: str,
    status: str,
) -> AnalysisMutationResult:
    return update_action(project=project, action_ref=action_ref, status=status)


def update_risk(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    severity: int | None = None,
    failure_cause_ref: str | None = None,
    occurrence: int | None = None,
    detection: int | None = None,
    ap: str | None = None,
) -> AnalysisMutationResult:
    _ensure_update_fields(
        entity_label="risk",
        fields={"severity": severity, "occurrence": occurrence, "detection": detection, "ap": ap},
    )
    changed: list[Path] = []
    affected: list[dict[str, Any]] = []
    primary: Resource | None = None
    if severity is not None:
        fm_result = update_failure_mode(
            project=project,
            failure_mode_ref=failure_mode_ref,
            severity=severity,
        )
        changed.extend(fm_result.changed_paths)
        affected.extend(fm_result.affected_objects)
        primary = fm_result.resource

    if occurrence is None and detection is None and ap is None:
        assert primary is not None
        return AnalysisMutationResult(
            project=project,
            resource=primary,
            changed_paths=_unique_paths(changed),
            affected_objects=tuple(affected),
        )

    store = _store(project)
    cause_id = failure_cause_ref or _single_cause_for_failure_mode(
        store=store,
        failure_mode_ref=failure_mode_ref,
    )
    fc_result = update_failure_cause(
        project=project,
        failure_cause_ref=cause_id,
        occurrence=occurrence,
        detection=detection,
        ap=ap,
    )
    changed.extend(fc_result.changed_paths)
    affected.extend(fc_result.affected_objects)
    return AnalysisMutationResult(
        project=project,
        resource=fc_result.resource,
        changed_paths=_unique_paths(changed),
        affected_objects=tuple(affected),
    )


def link_fm_requirement(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    requirement_ref: str,
) -> AnalysisMutationResult:
    return _mutate_fm_ref_list(
        project=project,
        failure_mode_ref=failure_mode_ref,
        linked_ref=requirement_ref,
        linked_kind=REQUIREMENT_KIND,
        spec_field="requirementRefs",
        mode="link",
    )


def unlink_fm_requirement(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    requirement_ref: str,
) -> AnalysisMutationResult:
    return _mutate_fm_ref_list(
        project=project,
        failure_mode_ref=failure_mode_ref,
        linked_ref=requirement_ref,
        linked_kind=REQUIREMENT_KIND,
        spec_field="requirementRefs",
        mode="unlink",
    )


def link_fm_characteristic(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    characteristic_ref: str,
) -> AnalysisMutationResult:
    return _mutate_fm_ref_list(
        project=project,
        failure_mode_ref=failure_mode_ref,
        linked_ref=characteristic_ref,
        linked_kind=CHARACTERISTIC_KIND,
        spec_field="characteristicRefs",
        mode="link",
    )


def unlink_fm_characteristic(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    characteristic_ref: str,
) -> AnalysisMutationResult:
    return _mutate_fm_ref_list(
        project=project,
        failure_mode_ref=failure_mode_ref,
        linked_ref=characteristic_ref,
        linked_kind=CHARACTERISTIC_KIND,
        spec_field="characteristicRefs",
        mode="unlink",
    )


def delete_analysis_node(*, project: ProjectConfig, node_ref: str) -> AnalysisMutationResult:
    prefix = id_prefix(node_ref).upper()
    kind = KIND_BY_PREFIX.get(prefix)
    if kind is None:
        raise QualityCliError(
            code="ID_PREFIX_MISMATCH",
            message=f"Analysis node '{node_ref}' has an unsupported ID prefix.",
            target={"nodeRef": node_ref},
            suggestion="Use FN, REQ, CHAR, FM, FE, FC, or ACT resource IDs.",
        )
    if kind == FUNCTION_KIND:
        return delete_function(project=project, function_ref=node_ref)
    if kind == REQUIREMENT_KIND:
        return delete_requirement(project=project, requirement_ref=node_ref)
    if kind == CHARACTERISTIC_KIND:
        return delete_characteristic(project=project, characteristic_ref=node_ref)
    return _delete_failure_chain_resource(project=project, kind=kind, node_ref=node_ref)


def _create_failure_effect(*, store: ResourceStore, fm: Resource, spec: dict[str, Any]) -> Resource:
    resolved_spec: dict[str, Any] = {
        "failureModeRef": fm.resource_id,
        "description": spec["description"],
    }
    if spec["level"] is not None:
        resolved_spec["level"] = spec["level"]
    result = store.create_collection_resource(
        kind=FAILURE_EFFECT_KIND,
        id_prefix="FE",
        metadata={"title": spec["description"]},
        spec=resolved_spec,
    )
    return store.load(store.ref(kind=FAILURE_EFFECT_KIND, resource_id=result.resource_id))


def _create_failure_cause(*, store: ResourceStore, fm: Resource, spec: dict[str, Any]) -> Resource:
    ap = spec["ap"]
    if ap is None:
        ap = compute_ap(
            _coerce_int_in_range(fm.spec.get("severity"), field="severity", minimum=1, maximum=10),
            spec["occurrence"],
            spec["detection"],
        )
    result = store.create_collection_resource(
        kind=FAILURE_CAUSE_KIND,
        id_prefix="FC",
        metadata={"title": spec["description"]},
        spec={
            "failureModeRef": fm.resource_id,
            "description": spec["description"],
            "occurrence": spec["occurrence"],
            "detection": spec["detection"],
            "ap": ap,
        },
    )
    return store.load(store.ref(kind=FAILURE_CAUSE_KIND, resource_id=result.resource_id))


def _create_action(
    *,
    store: ResourceStore,
    fm: Resource,
    spec: dict[str, Any],
    target_cause_refs: list[str],
) -> Resource:
    resolved_spec: dict[str, Any] = {
        "failureModeRef": fm.resource_id,
        "description": spec["description"],
        "targetCauseRefs": target_cause_refs,
    }
    for source_field, target_field in (
        ("kind", "kind"),
        ("status", "status"),
        ("owner", "owner"),
        ("due", "due"),
        ("effectivenessStatus", "effectivenessStatus"),
        ("revisedSeverity", "revisedSeverity"),
        ("revisedOccurrence", "revisedOccurrence"),
        ("revisedDetection", "revisedDetection"),
    ):
        if spec[source_field] is not None:
            resolved_spec[target_field] = spec[source_field]
    result = store.create_collection_resource(
        kind=ACTION_KIND,
        id_prefix="ACT",
        metadata={},
        spec=resolved_spec,
    )
    return store.load(store.ref(kind=ACTION_KIND, resource_id=result.resource_id))


def _mutate_fm_ref_list(
    *,
    project: ProjectConfig,
    failure_mode_ref: str,
    linked_ref: str,
    linked_kind: str,
    spec_field: str,
    mode: str,
) -> AnalysisMutationResult:
    store = _store(project)
    fm = _load(store=store, kind=FAILURE_MODE_KIND, resource_id=failure_mode_ref)
    linked = _load(store=store, kind=linked_kind, resource_id=linked_ref)
    if linked.spec.get("functionRef") != fm.spec.get("functionRef"):
        raise QualityCliError(
            code="INVALID_PARENT",
            message=f"{linked.resource_id} does not belong to failure mode function scope.",
            target={
                "failureMode": fm.resource_id,
                "linkedResource": linked.resource_id,
                "expectedFunctionRef": fm.spec.get("functionRef"),
                "actualFunctionRef": linked.spec.get("functionRef"),
            },
            suggestion="Link only resources that belong to the same function.",
        )
    refs = _string_list(fm.spec.get(spec_field), field=spec_field)
    if mode == "link" and linked.resource_id not in refs:
        refs.append(linked.resource_id)
    if mode == "unlink":
        refs = [ref for ref in refs if ref != linked.resource_id]
    spec = dict(fm.spec)
    spec[spec_field] = refs
    updated = _write_updated_resource(
        store=store, resource=fm, metadata=dict(fm.metadata), spec=spec
    )
    return _single_result(project=project, resource=updated, path=_resource_path(updated))


def _delete_failure_chain_resource(
    *, project: ProjectConfig, kind: str, node_ref: str
) -> AnalysisMutationResult:
    store = _store(project)
    resource = _load(store=store, kind=kind, resource_id=node_ref)
    if kind == FAILURE_MODE_KIND:
        return _delete_failure_mode(project=project, store=store, fm=resource)
    if kind == FAILURE_EFFECT_KIND:
        return _delete_child_from_fm(
            project=project,
            store=store,
            resource=resource,
            fm_field="effectRefs",
        )
    if kind == FAILURE_CAUSE_KIND:
        return _delete_failure_cause(project=project, store=store, cause=resource)
    if kind == ACTION_KIND:
        return _delete_child_from_fm(
            project=project,
            store=store,
            resource=resource,
            fm_field="actionRefs",
        )
    raise AssertionError(f"Unhandled analysis kind: {kind}")


def _delete_failure_mode(
    *, project: ProjectConfig, store: ResourceStore, fm: Resource
) -> AnalysisMutationResult:
    changed: list[Path] = []
    affected: list[dict[str, Any]] = []
    tombstones: list[Path] = []
    for kind in (FAILURE_EFFECT_KIND, FAILURE_CAUSE_KIND, ACTION_KIND):
        for child in store.list(ResourceSelector(kind=kind)):
            if child.spec.get("failureModeRef") != fm.resource_id:
                continue
            deleted = _delete_loaded(project=project, store=store, resource=child)
            changed.extend(deleted.changed_paths)
            affected.extend(deleted.affected_objects)
            tombstones.extend(deleted.tombstone_paths)
    deleted_fm = _delete_loaded(project=project, store=store, resource=fm)
    changed.extend(deleted_fm.changed_paths)
    affected.extend(deleted_fm.affected_objects)
    tombstones.extend(deleted_fm.tombstone_paths)
    return AnalysisMutationResult(
        project=project,
        resource=fm,
        changed_paths=_unique_paths(changed),
        affected_objects=tuple(affected),
        tombstone_paths=tuple(tombstones),
    )


def _delete_child_from_fm(
    *,
    project: ProjectConfig,
    store: ResourceStore,
    resource: Resource,
    fm_field: str,
) -> AnalysisMutationResult:
    fm = _load(
        store=store, kind=FAILURE_MODE_KIND, resource_id=_required_ref(resource, "failureModeRef")
    )
    refs = _string_list(fm.spec.get(fm_field), field=fm_field)
    changed: list[Path] = []
    affected: list[dict[str, Any]] = []
    if resource.resource_id in refs:
        fm_spec = dict(fm.spec)
        fm_spec[fm_field] = [ref for ref in refs if ref != resource.resource_id]
        fm = _write_updated_resource(
            store=store, resource=fm, metadata=dict(fm.metadata), spec=fm_spec
        )
        changed.append(_resource_path(fm))
        affected.append(_affected(fm))
    deleted = _delete_loaded(project=project, store=store, resource=resource)
    return _merge_result(
        project=project, primary=resource, changed=changed, affected=affected, tail=deleted
    )


def _delete_failure_cause(
    *, project: ProjectConfig, store: ResourceStore, cause: Resource
) -> AnalysisMutationResult:
    fm = _load(
        store=store, kind=FAILURE_MODE_KIND, resource_id=_required_ref(cause, "failureModeRef")
    )
    changed: list[Path] = []
    affected: list[dict[str, Any]] = []
    tombstones: list[Path] = []
    fm_spec = dict(fm.spec)
    fm_spec["causeRefs"] = [
        ref
        for ref in _string_list(fm.spec.get("causeRefs"), field="causeRefs")
        if ref != cause.resource_id
    ]
    fm = _write_updated_resource(store=store, resource=fm, metadata=dict(fm.metadata), spec=fm_spec)
    changed.append(_resource_path(fm))
    affected.append(_affected(fm))

    for action in store.list(ResourceSelector(kind=ACTION_KIND)):
        if action.spec.get("failureModeRef") != fm.resource_id:
            continue
        refs = _string_list(action.spec.get("targetCauseRefs"), field="targetCauseRefs")
        if cause.resource_id not in refs:
            continue
        remaining = [ref for ref in refs if ref != cause.resource_id]
        if remaining:
            spec = dict(action.spec)
            spec["targetCauseRefs"] = remaining
            updated = _write_updated_resource(
                store=store, resource=action, metadata=dict(action.metadata), spec=spec
            )
            changed.append(_resource_path(updated))
            affected.append(_affected(updated))
        else:
            fm_spec = dict(fm.spec)
            fm_spec["actionRefs"] = [
                ref
                for ref in _string_list(fm.spec.get("actionRefs"), field="actionRefs")
                if ref != action.resource_id
            ]
            fm = _write_updated_resource(
                store=store, resource=fm, metadata=dict(fm.metadata), spec=fm_spec
            )
            changed.append(_resource_path(fm))
            affected.append(_affected(fm))
            deleted_action = _delete_loaded(project=project, store=store, resource=action)
            changed.extend(deleted_action.changed_paths)
            affected.extend(deleted_action.affected_objects)
            tombstones.extend(deleted_action.tombstone_paths)

    deleted = _delete_loaded(project=project, store=store, resource=cause)
    changed.extend(deleted.changed_paths)
    affected.extend(deleted.affected_objects)
    tombstones.extend(deleted.tombstone_paths)
    return AnalysisMutationResult(
        project=project,
        resource=cause,
        changed_paths=_unique_paths(changed),
        affected_objects=tuple(affected),
        tombstone_paths=tuple(tombstones),
    )


def _normalize_failure_chain_spec(chain_spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(chain_spec, dict):
        raise _invalid_field(
            field="input",
            message="Failure-chain input must be a JSON object.",
            suggestion="Provide an object with fm, fe, fc, and act sections.",
        )
    fm_raw = chain_spec.get("fm")
    if not isinstance(fm_raw, dict):
        raise _invalid_field(
            field="fm",
            message="Failure-chain input requires an fm object.",
            suggestion="Provide fm.description and fm.severity.",
        )
    return {
        "fm": {
            "description": _coerce_text(fm_raw.get("description"), field="fm.description"),
            "severity": _coerce_int_in_range(
                fm_raw.get("severity"),
                field="fm.severity",
                minimum=1,
                maximum=10,
            ),
            "requirementRefs": _coerce_ref_list(
                fm_raw.get("requirementRefs", fm_raw.get("violates_requirements", [])),
                field="fm.requirementRefs",
            ),
            "characteristicRefs": _coerce_ref_list(
                fm_raw.get("characteristicRefs", fm_raw.get("related_characteristics", [])),
                field="fm.characteristicRefs",
            ),
        },
        "fe": _normalize_fe_specs(chain_spec.get("fe")),
        "fc": _normalize_fc_specs(chain_spec.get("fc")),
        "act": _normalize_act_specs(chain_spec.get("act")),
    }


def _normalize_fe_specs(raw_value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(_coerce_list(raw_value, field="fe"), start=1):
        if not isinstance(item, dict):
            raise _invalid_field(
                field=f"fe[{index}]",
                message="Failure effect entries must be JSON objects.",
                suggestion="Use objects with description and optional level fields.",
            )
        level = item.get("level")
        normalized.append(
            {
                "description": _coerce_text(
                    item.get("description"), field=f"fe[{index}].description"
                ),
                "level": None if level is None else _coerce_text(level, field=f"fe[{index}].level"),
            }
        )
    return normalized


def _normalize_fc_specs(raw_value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(_coerce_list(raw_value, field="fc"), start=1):
        if not isinstance(item, dict):
            raise _invalid_field(
                field=f"fc[{index}]",
                message="Failure cause entries must be JSON objects.",
                suggestion=(
                    "Use objects with description, occurrence, detection, and optional ap fields."
                ),
            )
        ap = item.get("ap")
        normalized.append(
            {
                "description": _coerce_text(
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
                "ap": None
                if ap is None
                else _coerce_allowed_text(ap, field=f"fc[{index}].ap", allowed=ALLOWED_AP_VALUES),
            }
        )
    return normalized


def _normalize_act_specs(raw_value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(_coerce_list(raw_value, field="act"), start=1):
        if not isinstance(item, dict):
            raise _invalid_field(
                field=f"act[{index}]",
                message="Action entries must be JSON objects.",
                suggestion="Use objects with description and optional metadata fields.",
            )
        due = item.get("due")
        normalized.append(
            {
                "description": _coerce_text(
                    item.get("description"), field=f"act[{index}].description"
                ),
                "kind": _optional_allowed(
                    item.get("kind"), field=f"act[{index}].kind", allowed=ALLOWED_ACTION_KINDS
                ),
                "status": _optional_allowed(
                    item.get("status"),
                    field=f"act[{index}].status",
                    allowed=ALLOWED_ACTION_STATUSES,
                ),
                "owner": _optional_text(item.get("owner"), field=f"act[{index}].owner"),
                "due": None if due is None else _coerce_iso_date(due, field=f"act[{index}].due"),
                "targetCauseIndexes": _coerce_int_list(
                    item.get("targetCauseIndexes", item.get("target_causes", [])),
                    field=f"act[{index}].targetCauseIndexes",
                    minimum=1,
                ),
                "effectivenessStatus": _optional_allowed(
                    item.get("effectivenessStatus", item.get("effectiveness_status")),
                    field=f"act[{index}].effectivenessStatus",
                    allowed=ALLOWED_EFFECTIVENESS_STATUSES,
                ),
                "revisedSeverity": _optional_int_in_range(
                    item.get("revisedSeverity", item.get("revised_severity")),
                    field=f"act[{index}].revisedSeverity",
                    minimum=1,
                    maximum=10,
                ),
                "revisedOccurrence": _optional_int_in_range(
                    item.get("revisedOccurrence", item.get("revised_occurrence")),
                    field=f"act[{index}].revisedOccurrence",
                    minimum=1,
                    maximum=10,
                ),
                "revisedDetection": _optional_int_in_range(
                    item.get("revisedDetection", item.get("revised_detection")),
                    field=f"act[{index}].revisedDetection",
                    minimum=1,
                    maximum=10,
                ),
            }
        )
    return normalized


def _validate_target_cause_indexes(normalized: dict[str, Any]) -> None:
    fc_count = len(normalized["fc"])
    for act_index, act in enumerate(normalized["act"], start=1):
        for target_index in act["targetCauseIndexes"]:
            if target_index > fc_count:
                raise _invalid_field(
                    field=f"act[{act_index}].targetCauseIndexes",
                    message=(
                        f"Action target references FC item {target_index}, "
                        f"but only {fc_count} FC item(s) are being created."
                    ),
                    suggestion=(
                        "Use 1-based FC creation-order indexes within the same "
                        "failure-chain request."
                    ),
                )


def _store(project: ProjectConfig) -> ResourceStore:
    return ResourceStore(project=project, plugin=get_plugin())


def _load(*, store: ResourceStore, kind: str, resource_id: str) -> Resource:
    return store.load(store.ref(kind=kind, resource_id=resource_id))


def _load_structure_component(*, store: ResourceStore, component_ref: str) -> Resource:
    resource = _load(store=store, kind=STRUCTURE_KIND, resource_id=component_ref)
    if resource.spec.get("nodeType") != "component":
        raise QualityCliError(
            code="INVALID_PARENT",
            message=f"Structure node '{component_ref}' is not a component.",
            target={"componentRef": component_ref, "nodeType": resource.spec.get("nodeType")},
            suggestion="Use an existing COMP structure node.",
        )
    return resource


def _validate_function_local_refs(
    *,
    store: ResourceStore,
    function_id: str,
    refs: list[str],
    kind: str,
    field: str,
) -> list[str]:
    validated: list[str] = []
    for ref in refs:
        resource = _load(store=store, kind=kind, resource_id=ref)
        if resource.spec.get("functionRef") != function_id:
            raise QualityCliError(
                code="INVALID_PARENT",
                message=f"{ref} does not belong to function '{function_id}'.",
                target={"field": field, "resourceId": ref, "functionRef": function_id},
                suggestion="Use references that belong to the same function.",
            )
        validated.append(resource.resource_id)
    return _dedupe(validated)


def _validate_fm_local_cause_refs(
    *, store: ResourceStore, failure_mode_id: str, refs: list[str]
) -> list[str]:
    validated: list[str] = []
    for ref in refs:
        resource = _load(store=store, kind=FAILURE_CAUSE_KIND, resource_id=ref)
        if resource.spec.get("failureModeRef") != failure_mode_id:
            raise QualityCliError(
                code="INVALID_PARENT",
                message=f"{ref} does not belong to failure mode '{failure_mode_id}'.",
                target={"resourceId": ref, "failureModeRef": failure_mode_id},
                suggestion="Use FC references that belong to the same failure mode.",
            )
        validated.append(resource.resource_id)
    return _dedupe(validated)


def _single_cause_for_failure_mode(*, store: ResourceStore, failure_mode_ref: str) -> str:
    causes = [
        resource.resource_id
        for resource in store.list(ResourceSelector(kind=FAILURE_CAUSE_KIND))
        if resource.spec.get("failureModeRef") == failure_mode_ref
    ]
    if len(causes) == 1:
        return causes[0]
    raise QualityCliError(
        code="VALIDATION_FAILED",
        message=(
            "Risk update requires --failure-cause when the failure mode does not have "
            "exactly one cause."
        ),
        target={"failureModeRef": failure_mode_ref, "causeRefs": causes},
        suggestion="Provide --failure-cause with the FC resource ID to update.",
    )


def _resources_with_spec_ref(
    *,
    store: ResourceStore,
    kinds: tuple[str, ...],
    field: str,
    target_id: str,
) -> list[Resource]:
    matches: list[Resource] = []
    for kind in kinds:
        for resource in store.list(ResourceSelector(kind=kind)):
            if resource.spec.get(field) == target_id:
                matches.append(resource)
    return matches


def _write_updated_resource(
    *,
    store: ResourceStore,
    resource: Resource,
    metadata: dict[str, Any],
    spec: dict[str, Any],
) -> Resource:
    updated = make_resource(
        kind=resource.kind,
        resource_id=resource.resource_id,
        metadata=metadata,
        spec=spec,
    )
    store.update(updated)
    return store.load(store.ref(kind=resource.kind, resource_id=resource.resource_id))


def _update_single(
    *,
    project: ProjectConfig,
    store: ResourceStore,
    resource: Resource,
    metadata: dict[str, Any],
    spec: dict[str, Any],
) -> AnalysisMutationResult:
    updated = _write_updated_resource(
        store=store,
        resource=resource,
        metadata=metadata,
        spec=spec,
    )
    return _single_result(project=project, resource=updated, path=_resource_path(updated))


def _delete_loaded(
    *, project: ProjectConfig, store: ResourceStore, resource: Resource
) -> AnalysisMutationResult:
    result = store.delete(store.ref(kind=resource.kind, resource_id=resource.resource_id))
    return AnalysisMutationResult(
        project=project,
        resource=resource,
        changed_paths=result.changed_paths,
        affected_objects=(_affected(resource),),
        tombstone_paths=(result.tombstone_path,) if result.tombstone_path is not None else (),
    )


def _single_result(
    *, project: ProjectConfig, resource: Resource, path: Path
) -> AnalysisMutationResult:
    return AnalysisMutationResult(
        project=project,
        resource=resource,
        changed_paths=(path,),
        affected_objects=(_affected(resource),),
    )


def _merge_result(
    *,
    project: ProjectConfig,
    primary: Resource,
    changed: list[Path],
    affected: list[dict[str, Any]],
    tail: AnalysisMutationResult,
) -> AnalysisMutationResult:
    return AnalysisMutationResult(
        project=project,
        resource=primary,
        changed_paths=_unique_paths([*changed, *tail.changed_paths]),
        affected_objects=tuple([*affected, *tail.affected_objects]),
        tombstone_paths=tail.tombstone_paths,
    )


def _affected(resource: Resource) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": resource.kind,
        "id": resource.resource_id,
    }
    if resource.path is not None:
        payload["path"] = str(resource.path)
    return payload


def _resource_path(resource: Resource) -> Path:
    if resource.path is None:
        raise QualityCliError(
            code="INVALID_PROJECT_CONFIG",
            message=f"Resource '{resource.resource_id}' has no resolved path.",
            target={"kind": resource.kind, "resourceId": resource.resource_id},
            suggestion="Reload the resource through ResourceStore before returning it.",
        )
    return resource.path


def _required_ref(resource: Resource, field: str) -> str:
    value = resource.spec.get(field)
    if isinstance(value, str) and value:
        return value
    raise QualityCliError(
        code="INVALID_PROJECT_CONFIG",
        message=f"Resource '{resource.resource_id}' is missing spec.{field}.",
        path=str(resource.path) if resource.path is not None else None,
        field=f"spec.{field}",
        suggestion="Repair the resource before mutating it.",
    )


def _coerce_list(raw_value: Any, *, field: str) -> list[Any]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return raw_value
    raise _invalid_field(
        field=field,
        message=f"Field '{field}' must be a list.",
        suggestion=f"Provide {field} as a JSON array.",
    )


def _coerce_ref_list(raw_value: Any, *, field: str) -> list[str]:
    values = _coerce_list(raw_value, field=field)
    refs: list[str] = []
    for index, value in enumerate(values, start=1):
        refs.append(_coerce_text(value, field=f"{field}[{index}]"))
    return _dedupe(refs)


def _string_list(raw_value: Any, *, field: str) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list) and all(isinstance(item, str) for item in raw_value):
        return list(raw_value)
    raise QualityCliError(
        code="INVALID_PROJECT_CONFIG",
        message=f"Field '{field}' must be a string list.",
        field=field,
        suggestion="Repair the resource reference list before retrying.",
    )


def _coerce_int_list(raw_value: Any, *, field: str, minimum: int) -> list[int]:
    values = _coerce_list(raw_value, field=field)
    return [
        _coerce_int_in_range(value, field=f"{field}[{index}]", minimum=minimum)
        for index, value in enumerate(values, start=1)
    ]


def _optional_text(raw_value: Any, *, field: str) -> str | None:
    if raw_value is None:
        return None
    return _coerce_text(raw_value, field=field)


def _coerce_text(raw_value: Any, *, field: str) -> str:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise _invalid_field(
            field=field,
            message=f"Field '{field}' must be a non-empty string.",
            suggestion=f"Provide a non-empty value for {field}.",
        )
    return raw_value.strip()


def _optional_allowed(raw_value: Any, *, field: str, allowed: set[str]) -> str | None:
    if raw_value is None:
        return None
    return _coerce_allowed_text(raw_value, field=field, allowed=allowed)


def _coerce_allowed_text(raw_value: Any, *, field: str, allowed: set[str]) -> str:
    value = _coerce_text(raw_value, field=field)
    if value not in allowed:
        raise _invalid_field(
            field=field,
            message=f"Field '{field}' must be one of {sorted(allowed)}.",
            suggestion=f"Use one of: {', '.join(sorted(allowed))}.",
        )
    return value


def _optional_int_in_range(
    raw_value: Any, *, field: str, minimum: int, maximum: int | None = None
) -> int | None:
    if raw_value is None:
        return None
    return _coerce_int_in_range(raw_value, field=field, minimum=minimum, maximum=maximum)


def _coerce_int_in_range(
    raw_value: Any, *, field: str, minimum: int, maximum: int | None = None
) -> int:
    if isinstance(raw_value, bool):
        raise _int_error(field)
    if isinstance(raw_value, int):
        value = raw_value
    elif isinstance(raw_value, str) and raw_value.strip().isdigit():
        value = int(raw_value.strip())
    else:
        raise _int_error(field)
    if value < minimum or (maximum is not None and value > maximum):
        range_label = f"{minimum}-{maximum}" if maximum is not None else f">= {minimum}"
        raise _invalid_field(
            field=field,
            message=f"Field '{field}' must be in range {range_label}.",
            suggestion=f"Provide {field} in range {range_label}.",
        )
    return value


def _coerce_iso_date(raw_value: Any, *, field: str) -> str:
    value = _coerce_text(raw_value, field=field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise _invalid_field(
            field=field,
            message=f"Field '{field}' must be an ISO date (YYYY-MM-DD).",
            suggestion=f"Provide {field} in YYYY-MM-DD format.",
        ) from exc
    return value


def _int_error(field: str) -> QualityCliError:
    return _invalid_field(
        field=field,
        message=f"Field '{field}' must be an integer.",
        suggestion=f"Provide an integer value for {field}.",
    )


def _invalid_field(*, field: str, message: str, suggestion: str) -> QualityCliError:
    return QualityCliError(
        code="VALIDATION_FAILED",
        message=message,
        field=field,
        target={"field": field},
        suggestion=suggestion,
    )


def _ensure_update_fields(*, entity_label: str, fields: dict[str, Any]) -> None:
    if any(value is not None for value in fields.values()):
        return
    raise QualityCliError(
        code="VALIDATION_FAILED",
        message=f"{entity_label.capitalize()} update requires at least one mutable field.",
        target={"entity": entity_label, "fields": sorted(fields)},
        suggestion="Provide at least one update field for this command.",
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return tuple(result)
