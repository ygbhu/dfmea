from __future__ import annotations

from collections import defaultdict
from typing import Any

from quality_core.resources.envelope import Resource
from quality_core.validation.issue import ValidationIssue, error_issue, warning_issue
from quality_core.workspace.project import ProjectConfig
from quality_methods.dfmea.analysis_service import (
    ACTION_KIND,
    ALLOWED_ACTION_STATUSES,
    ALLOWED_AP_VALUES,
    CHARACTERISTIC_KIND,
    FAILURE_CAUSE_KIND,
    FAILURE_EFFECT_KIND,
    FAILURE_MODE_KIND,
    FUNCTION_KIND,
    REQUIREMENT_KIND,
    STRUCTURE_KIND,
    compute_ap,
)


def validate_dfmea_project(
    *,
    project: ProjectConfig,
    resources: tuple[Resource, ...],
) -> list[ValidationIssue]:
    del project
    index = _ResourceIndex(resources)
    issues: list[ValidationIssue] = []
    issues.extend(_validate_structure_graph(index))
    issues.extend(_validate_function_graph(index))
    issues.extend(_validate_failure_chain_refs(index))
    issues.extend(_validate_methodology(index))
    return issues


class _ResourceIndex:
    def __init__(self, resources: tuple[Resource, ...]) -> None:
        self.by_id = {
            resource.metadata["id"]: resource
            for resource in resources
            if isinstance(resource.metadata.get("id"), str)
        }
        self.by_kind: dict[str, list[Resource]] = defaultdict(list)
        for resource in resources:
            self.by_kind[resource.kind].append(resource)

    def get(self, resource_id: str) -> Resource | None:
        return self.by_id.get(resource_id)

    def kind(self, kind: str) -> list[Resource]:
        return self.by_kind.get(kind, [])


def _validate_structure_graph(index: _ResourceIndex) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected_parent_type = {"system": None, "subsystem": "system", "component": "subsystem"}
    expected_parent_prefix = {"subsystem": "SYS", "component": "SUB"}
    for resource in index.kind(STRUCTURE_KIND):
        node_type = resource.spec.get("nodeType")
        if node_type not in expected_parent_type:
            issues.append(
                _resource_issue(
                    resource,
                    code="VALIDATION_FAILED",
                    message="Structure node has an unsupported nodeType.",
                    field="spec.nodeType",
                    suggestion="Use system, subsystem, or component.",
                )
            )
            continue
        parent_ref = resource.spec.get("parentRef")
        if expected_parent_type[node_type] is None:
            if parent_ref is not None:
                issues.append(
                    _resource_issue(
                        resource,
                        code="INVALID_PARENT",
                        message="System structure nodes must not specify parentRef.",
                        field="spec.parentRef",
                        suggestion="Remove spec.parentRef from system resources.",
                    )
                )
            continue
        if not isinstance(parent_ref, str) or not parent_ref:
            issues.append(
                _resource_issue(
                    resource,
                    code="REFERENCE_NOT_FOUND",
                    message=f"{node_type} structure nodes require parentRef.",
                    field="spec.parentRef",
                    suggestion=(
                        "Set spec.parentRef to an existing "
                        f"{expected_parent_prefix[node_type]} node."
                    ),
                )
            )
            continue
        parent = index.get(parent_ref)
        if parent is None:
            issues.append(
                _missing_ref_issue(
                    resource,
                    field="spec.parentRef",
                    ref=parent_ref,
                    expected_kind=STRUCTURE_KIND,
                )
            )
            continue
        if (
            parent.kind != STRUCTURE_KIND
            or parent.spec.get("nodeType") != expected_parent_type[node_type]
        ):
            issues.append(
                _resource_issue(
                    resource,
                    code="INVALID_PARENT",
                    message=f"{node_type} structure nodes have an invalid parent type.",
                    field="spec.parentRef",
                    target={
                        "parentRef": parent_ref,
                        "expectedNodeType": expected_parent_type[node_type],
                        "actualKind": parent.kind,
                        "actualNodeType": parent.spec.get("nodeType"),
                    },
                    suggestion="Move the structure node under a valid parent.",
                )
            )
    return issues


def _validate_function_graph(index: _ResourceIndex) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for function in index.kind(FUNCTION_KIND):
        component_ref = _string_field(function, "componentRef")
        if component_ref is None:
            issues.append(
                _resource_issue(
                    function,
                    code="REFERENCE_NOT_FOUND",
                    message="Function must reference a component.",
                    field="spec.componentRef",
                    suggestion="Set spec.componentRef to an existing component structure node.",
                )
            )
            continue
        component = index.get(component_ref)
        if component is None:
            issues.append(
                _missing_ref_issue(
                    function,
                    field="spec.componentRef",
                    ref=component_ref,
                    expected_kind=STRUCTURE_KIND,
                )
            )
        elif component.kind != STRUCTURE_KIND or component.spec.get("nodeType") != "component":
            issues.append(
                _resource_issue(
                    function,
                    code="INVALID_PARENT",
                    message="Function componentRef must point to a component structure node.",
                    field="spec.componentRef",
                    target={"componentRef": component_ref, "actualKind": component.kind},
                    suggestion="Attach the function to a COMP structure node.",
                )
            )

    for kind in (REQUIREMENT_KIND, CHARACTERISTIC_KIND, FAILURE_MODE_KIND):
        for resource in index.kind(kind):
            function_ref = _string_field(resource, "functionRef")
            if function_ref is None:
                issues.append(
                    _resource_issue(
                        resource,
                        code="REFERENCE_NOT_FOUND",
                        message=f"{kind} must reference a function.",
                        field="spec.functionRef",
                        suggestion="Set spec.functionRef to an existing Function resource.",
                    )
                )
                continue
            function = index.get(function_ref)
            if function is None:
                issues.append(
                    _missing_ref_issue(
                        resource,
                        field="spec.functionRef",
                        ref=function_ref,
                        expected_kind=FUNCTION_KIND,
                    )
                )
            elif function.kind != FUNCTION_KIND:
                issues.append(
                    _resource_issue(
                        resource,
                        code="INVALID_PARENT",
                        message=f"{kind} functionRef must point to a Function resource.",
                        field="spec.functionRef",
                        target={"functionRef": function_ref, "actualKind": function.kind},
                        suggestion="Repair spec.functionRef to point at an FN resource.",
                    )
                )
    return issues


def _validate_failure_chain_refs(index: _ResourceIndex) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for fm in index.kind(FAILURE_MODE_KIND):
        issues.extend(
            _validate_same_function_refs(
                index=index,
                resource=fm,
                field="requirementRefs",
                expected_kind=REQUIREMENT_KIND,
            )
        )
        issues.extend(
            _validate_same_function_refs(
                index=index,
                resource=fm,
                field="characteristicRefs",
                expected_kind=CHARACTERISTIC_KIND,
            )
        )
        for field, expected_kind in (
            ("effectRefs", FAILURE_EFFECT_KIND),
            ("causeRefs", FAILURE_CAUSE_KIND),
            ("actionRefs", ACTION_KIND),
        ):
            for ref_index, ref in enumerate(_string_list(fm.spec.get(field))):
                child = index.get(ref)
                if child is None:
                    issues.append(
                        _missing_ref_issue(
                            fm,
                            field=f"spec.{field}[{ref_index}]",
                            ref=ref,
                            expected_kind=expected_kind,
                        )
                    )
                    continue
                if child.kind != expected_kind or child.spec.get(
                    "failureModeRef"
                ) != fm.metadata.get("id"):
                    issues.append(
                        _resource_issue(
                            fm,
                            code="INVALID_PARENT",
                            message=f"{field} must reference {expected_kind} children of this FM.",
                            field=f"spec.{field}[{ref_index}]",
                            target={
                                "ref": ref,
                                "expectedKind": expected_kind,
                                "actualKind": child.kind,
                            },
                            suggestion="Repair the same-chain child reference list.",
                        )
                    )

    for kind in (FAILURE_EFFECT_KIND, FAILURE_CAUSE_KIND, ACTION_KIND):
        for resource in index.kind(kind):
            fm_ref = _string_field(resource, "failureModeRef")
            if fm_ref is None:
                issues.append(
                    _resource_issue(
                        resource,
                        code="REFERENCE_NOT_FOUND",
                        message=f"{kind} must reference a failure mode.",
                        field="spec.failureModeRef",
                        suggestion="Set spec.failureModeRef to an existing FM resource.",
                    )
                )
                continue
            fm = index.get(fm_ref)
            if fm is None:
                issues.append(
                    _missing_ref_issue(
                        resource,
                        field="spec.failureModeRef",
                        ref=fm_ref,
                        expected_kind=FAILURE_MODE_KIND,
                    )
                )
            elif fm.kind != FAILURE_MODE_KIND:
                issues.append(
                    _resource_issue(
                        resource,
                        code="INVALID_PARENT",
                        message=f"{kind} failureModeRef must point to a FailureMode.",
                        field="spec.failureModeRef",
                        target={"failureModeRef": fm_ref, "actualKind": fm.kind},
                        suggestion="Repair spec.failureModeRef to point at an FM resource.",
                    )
                )

    for action in index.kind(ACTION_KIND):
        fm_ref = _string_field(action, "failureModeRef")
        for ref_index, cause_ref in enumerate(_string_list(action.spec.get("targetCauseRefs"))):
            cause = index.get(cause_ref)
            if cause is None:
                issues.append(
                    _missing_ref_issue(
                        action,
                        field=f"spec.targetCauseRefs[{ref_index}]",
                        ref=cause_ref,
                        expected_kind=FAILURE_CAUSE_KIND,
                    )
                )
                continue
            if cause.kind != FAILURE_CAUSE_KIND or cause.spec.get("failureModeRef") != fm_ref:
                issues.append(
                    _resource_issue(
                        action,
                        code="INVALID_PARENT",
                        message=(
                            "Action targetCauseRefs must point to FC resources under the same FM."
                        ),
                        field=f"spec.targetCauseRefs[{ref_index}]",
                        target={"targetCauseRef": cause_ref, "failureModeRef": fm_ref},
                        suggestion="Repair action target cause references.",
                    )
                )
    return issues


def _validate_methodology(index: _ResourceIndex) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for fm in index.kind(FAILURE_MODE_KIND):
        severity = _int_field(fm, "severity")
        if severity is None:
            issues.append(
                _resource_issue(
                    fm,
                    code="VALIDATION_FAILED",
                    message="Failure mode severity is required.",
                    field="spec.severity",
                    suggestion="Set severity to an integer from 1 to 10.",
                )
            )
        elif severity < 1 or severity > 10:
            issues.append(
                _resource_issue(
                    fm,
                    code="VALIDATION_FAILED",
                    message="Failure mode severity must be in range 1-10.",
                    field="spec.severity",
                    suggestion="Set severity to an integer from 1 to 10.",
                )
            )

    for fc in index.kind(FAILURE_CAUSE_KIND):
        occurrence = _int_field(fc, "occurrence")
        detection = _int_field(fc, "detection")
        ap = _string_field(fc, "ap")
        for field, value in (("occurrence", occurrence), ("detection", detection)):
            if value is None:
                issues.append(
                    _resource_issue(
                        fc,
                        code="VALIDATION_FAILED",
                        message=f"Failure cause {field} is required.",
                        field=f"spec.{field}",
                        suggestion=f"Set {field} to an integer from 1 to 10.",
                    )
                )
            elif value < 1 or value > 10:
                issues.append(
                    _resource_issue(
                        fc,
                        code="VALIDATION_FAILED",
                        message=f"Failure cause {field} must be in range 1-10.",
                        field=f"spec.{field}",
                        suggestion=f"Set {field} to an integer from 1 to 10.",
                    )
                )
        if ap is None or ap not in ALLOWED_AP_VALUES:
            issues.append(
                _resource_issue(
                    fc,
                    code="VALIDATION_FAILED",
                    message="Failure cause AP must be High, Medium, or Low.",
                    field="spec.ap",
                    suggestion="Set AP to the value computed from S/O/D or an allowed override.",
                )
            )
            continue
        fm_ref = _string_field(fc, "failureModeRef")
        fm = index.get(fm_ref) if fm_ref is not None else None
        severity = _int_field(fm, "severity") if fm is not None else None
        if severity is None or occurrence is None or detection is None:
            continue
        expected_ap = compute_ap(severity, occurrence, detection)
        if ap != expected_ap:
            issues.append(
                _resource_issue(
                    fc,
                    code="AP_MISMATCH",
                    message=f"Failure cause AP is '{ap}', expected '{expected_ap}' from S/O/D.",
                    field="spec.ap",
                    target={
                        "severity": severity,
                        "occurrence": occurrence,
                        "detection": detection,
                        "expectedAp": expected_ap,
                        "actualAp": ap,
                    },
                    suggestion="Update AP or review whether a documented override is needed.",
                    severity="warning",
                )
            )

    for action in index.kind(ACTION_KIND):
        status = _string_field(action, "status")
        if status is not None and status not in ALLOWED_ACTION_STATUSES:
            issues.append(
                _resource_issue(
                    action,
                    code="VALIDATION_FAILED",
                    message="Action status is not allowed.",
                    field="spec.status",
                    suggestion="Use planned, in-progress, or completed.",
                )
            )
        if status in {"planned", "in-progress"} and _string_field(action, "owner") is None:
            issues.append(
                _resource_issue(
                    action,
                    code="ACTION_OWNER_MISSING",
                    message="Open actions should have an owner.",
                    field="spec.owner",
                    suggestion="Assign an owner or mark the action completed if appropriate.",
                    severity="warning",
                )
            )
    return issues


def _validate_same_function_refs(
    *,
    index: _ResourceIndex,
    resource: Resource,
    field: str,
    expected_kind: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    function_ref = resource.spec.get("functionRef")
    for ref_index, ref in enumerate(_string_list(resource.spec.get(field))):
        referenced = index.get(ref)
        if referenced is None:
            issues.append(
                _missing_ref_issue(
                    resource,
                    field=f"spec.{field}[{ref_index}]",
                    ref=ref,
                    expected_kind=expected_kind,
                )
            )
            continue
        if referenced.kind != expected_kind or referenced.spec.get("functionRef") != function_ref:
            issues.append(
                _resource_issue(
                    resource,
                    code="INVALID_PARENT",
                    message=(
                        f"{field} must reference {expected_kind} resources in the same function."
                    ),
                    field=f"spec.{field}[{ref_index}]",
                    target={
                        "ref": ref,
                        "expectedKind": expected_kind,
                        "actualKind": referenced.kind,
                    },
                    suggestion="Repair the function-local reference list.",
                )
            )
    return issues


def _missing_ref_issue(
    resource: Resource,
    *,
    field: str,
    ref: str,
    expected_kind: str,
) -> ValidationIssue:
    return _resource_issue(
        resource,
        code="REFERENCE_NOT_FOUND",
        message=f"Referenced {expected_kind} '{ref}' does not exist.",
        field=field,
        target={"ref": ref, "expectedKind": expected_kind},
        suggestion="Create the referenced resource, restore it, or remove the reference.",
    )


def _resource_issue(
    resource: Resource,
    *,
    code: str,
    message: str,
    field: str,
    suggestion: str,
    target: dict[str, Any] | None = None,
    severity: str = "error",
) -> ValidationIssue:
    factory = warning_issue if severity == "warning" else error_issue
    return factory(
        code=code,
        message=message,
        path=resource.path,
        resource_id=resource.metadata.get("id")
        if isinstance(resource.metadata.get("id"), str)
        else None,
        kind=resource.kind,
        field=field,
        target=target,
        suggestion=suggestion,
        plugin_id="dfmea",
    )


def _string_field(resource: Resource | None, field: str) -> str | None:
    if resource is None:
        return None
    value = resource.spec.get(field)
    return value if isinstance(value, str) and value else None


def _int_field(resource: Resource | None, field: str) -> int | None:
    if resource is None:
        return None
    value = resource.spec.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _string_list(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [item for item in raw_value if isinstance(item, str)]
    return []
