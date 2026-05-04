from __future__ import annotations

from quality_core.cli.errors import QualityCliError
from quality_core.methods.contracts import QualityMethod
from quality_methods.dfmea.method import get_method as get_dfmea_method
from quality_methods.pfmea.method import get_method as get_pfmea_method


def list_quality_methods() -> list[QualityMethod]:
    return [get_dfmea_method(), get_pfmea_method()]


def list_active_quality_methods() -> list[QualityMethod]:
    return [method for method in list_quality_methods() if method.implemented]


def quality_methods_by_id() -> dict[str, QualityMethod]:
    return {method.method_id: method for method in list_quality_methods()}


def get_quality_method(method_id: str) -> QualityMethod:
    method = quality_methods_by_id().get(method_id)
    if method is None:
        raise QualityCliError(
            code="METHOD_NOT_FOUND",
            message=f"Quality method '{method_id}' was not found.",
            target={"methodId": method_id},
            suggestion="Run `quality method list` to see available quality methods.",
        )
    return method
