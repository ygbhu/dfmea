from __future__ import annotations

from quality_core.methods.contracts import QualityMethod


def get_method() -> QualityMethod:
    return QualityMethod(
        method_id="pfmea",
        display_name="PFMEA",
        status="planned",
        enabled_by_default=False,
        domain_key="pfmea",
        command_namespace=None,
        plugin=None,
        commands=(),
    )
