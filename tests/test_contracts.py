from dfmea_cli.contracts import (
    CONTRACT_VERSION,
    failure_result,
    success_result,
    validation_result,
)
from dfmea_cli.errors import CliError, ProjectDbMismatchError


def test_success_result_has_stable_shape():
    payload = success_result(command="init", data={"project_id": "demo"})

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["ok"] is True
    assert payload["command"] == "init"
    assert payload["data"] == {"project_id": "demo"}
    assert payload["warnings"] == []
    assert payload["errors"] == []
    assert payload["meta"] == {}


def test_failure_result_preserves_structured_error_details():
    error = ProjectDbMismatchError(db_project_id="demo", requested_project_id="wrong")
    payload = failure_result(command="validate", errors=[error.to_error()])

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["ok"] is False
    assert payload["command"] == "validate"
    assert payload["data"] is None
    assert payload["errors"] == [
        {
            "code": "PROJECT_DB_MISMATCH",
            "message": "Database project 'demo' does not match requested project 'wrong'.",
            "target": {"project_id": "wrong", "db_project_id": "demo"},
            "suggested_action": "Use --project demo or point --db at the correct project database.",
        }
    ]


def test_cli_error_uses_stable_exit_code_mapping():
    error = CliError(code="DB_BUSY", message="Database is busy.")

    assert error.resolved_exit_code == 3


def test_validation_result_adds_validation_failed_error_for_error_level_issues():
    payload = validation_result(
        issues=[
            {
                "level": "error",
                "kind": "BROKEN_REFERENCE",
                "reason": "Referenced node is missing.",
            }
        ]
    )

    assert payload["ok"] is False
    assert payload["data"]["issues"][0]["kind"] == "BROKEN_REFERENCE"
    assert payload["errors"] == [
        {
            "code": "VALIDATION_FAILED",
            "message": "Validation reported one or more error-level issues.",
            "suggested_action": "Review data.issues and fix the reported validation errors.",
        }
    ]
