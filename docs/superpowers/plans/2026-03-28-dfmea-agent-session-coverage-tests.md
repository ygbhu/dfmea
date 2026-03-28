# DFMEA Agent Session Coverage Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a realistic session-oriented test suite that proves a DFMEA agent can incrementally record a cooling-fan DFMEA, answer follow-up questions while information is still incomplete, repair changed relationships and risk records, recover from invalid actions, and still finish with a valid, queryable, exportable project.

**Architecture:** Keep the existing realistic helper as the canonical full-project seed, then add a small layer of partial-seed and metadata helpers to support same-database incremental workflows. Put the new behavior in one dedicated pytest module, `tests/test_realistic_agent_session.py`, with three focused session tests: incremental intake, maintenance/repair, and failure recovery. Every session must end with `projection rebuild` plus `validate` as the integrity proof, while query/trace/export serve as additional evidence that the project remains usable to agents and humans.

**Tech Stack:** Python 3.11+, pytest, Typer `CliRunner`, stdlib `sqlite3`, existing `dfmea_cli` CLI commands, existing realistic helper module and projection-backed read model commands.

---

## File Structure

### Tests

- Create: `tests/test_realistic_agent_session.py` - three realistic session tests: incremental intake, maintenance/repair, and failure recovery.
- Modify: `tests/helpers_realistic_dfmea.py` - add only the smallest reusable helpers needed by session tests:
  - partial seeds that stop before full analysis is complete
  - project metadata reads
  - tiny JSON command wrapper
  - stable rowids/IDs needed by repair steps
- Leave unchanged: `tests/test_realistic_dfmea_end_to_end.py` - still owns the straight realistic happy path.
- Leave unchanged: `tests/test_realistic_dfmea_regression_matrix.py` - still owns the realistic matrix of query/validate/export/negative coverage.

### Runtime Package

- No runtime changes are planned.
- If the new session tests expose a real product bug, modify only the smallest affected runtime file after reproducing it via a failing test:
  - `src/dfmea_cli/services/structure.py`
  - `src/dfmea_cli/services/analysis.py`
  - `src/dfmea_cli/services/query.py`
  - `src/dfmea_cli/services/trace.py`
  - `src/dfmea_cli/services/projections.py`
  - `src/dfmea_cli/services/validate.py`
  - `src/dfmea_cli/services/export_markdown.py`
  - or the smallest affected file under `src/dfmea_cli/commands/`

### Design Reference

- Spec: `docs/superpowers/specs/2026-03-28-dfmea-agent-session-coverage-design.md`

## Scope Guardrails

- The new module validates continuous agent task chains; it does not replace command-level payload tests.
- Every session test must end with `validate` output proving `errors == 0`.
- Query/trace/export are supporting proofs and cannot replace the final validate check.
- Do not add speculative concurrency tests in this pass.
- Do not use rowid arithmetic. If a rowid is needed, expose it explicitly from helper payloads.

## Helper Additions To Make First

Add only the helpers below if they do not already exist:

```python
def invoke_json(cli_runner, args: list[str]) -> dict:
    result = cli_runner.invoke(args)
    assert result.exit_code == 0, result.stdout
    return parse_json_payload(result)


def read_project_data(db_path: Path, *, project_id: str = "demo") -> dict:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return json.loads(row[0])
```

Add two partial seeds in `tests/helpers_realistic_dfmea.py`:

### `seed_realistic_structure_only(cli_runner, tmp_path)`

This helper must:

1. call `_init_db(cli_runner, tmp_path)`
2. create, in order:
   - `SYS-001` `Engine Thermal Management System`
   - `SUB-001` `Cooling Fan System`
   - `COMP-001` `Electronic Cooling Fan Controller`
   - `COMP-002` `Cooling Fan Motor Assembly`
   - `COMP-003` `Coolant Temperature Sensing Path`
3. return:

```python
{
    "db_path": db_path,
    "project_id": "demo",
    "sys_id": sys_payload["data"]["node_id"],
    "sub_id": sub_payload["data"]["node_id"],
    "controller_comp_id": controller_payload["data"]["node_id"],
    "motor_comp_id": motor_payload["data"]["node_id"],
    "sensor_comp_id": sensor_payload["data"]["node_id"],
}
```

### `seed_realistic_controller_core(cli_runner, tmp_path)`

This helper must build on `seed_realistic_structure_only()` and then add, in the same database:

1. `FN-001` `Control fan start and stop`
2. `FN-002` `Modulate fan speed`
3. requirement for `FN-001`:
   - text: `Start fan within demanded cooling window`
   - source: `CTRL-REQ-START`
4. requirement for `FN-002`:
   - text: `Track requested fan speed across operating range`
   - source: `CTRL-REQ-SPEED`
5. characteristic for `FN-001`:
   - text: `Fan start response time`
   - value: `500`
   - unit: `ms`
6. characteristic for `FN-002`:
   - text: `Fan speed tracking error`
   - value: `10`
   - unit: `pct`

It must return the previous structure data plus:

```python
{
    "fn_ids": [fn_one["data"]["fn_id"], fn_two["data"]["fn_id"]],
    "controller_start_fn_id": fn_one["data"]["fn_id"],
    "controller_speed_fn_id": fn_two["data"]["fn_id"],
    "requirement_rowids": [req_one["data"]["req_rowid"], req_two["data"]["req_rowid"]],
    "characteristic_rowids": [char_one["data"]["char_rowid"], char_two["data"]["char_rowid"]],
}
```

These partial seeds are intentionally smaller than `seed_realistic_cooling_fan_project()` so Session A can continue working in the same DB.

## Task 1: Add Partial Seed And Metadata Helpers

**Files:**
- Modify: `tests/helpers_realistic_dfmea.py`
- Create: `tests/test_realistic_agent_session.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from helpers_realistic_dfmea import (
    read_project_data,
    seed_realistic_controller_core,
    seed_realistic_structure_only,
)


def test_partial_realistic_seeds_support_agent_style_incremental_intake(
    cli_runner, tmp_path: Path
):
    structure_seed = seed_realistic_structure_only(cli_runner, tmp_path / "structure")
    structure_project = read_project_data(structure_seed["db_path"])

    assert structure_seed["project_id"] == "demo"
    assert structure_seed["controller_comp_id"] == "COMP-001"
    assert structure_seed["motor_comp_id"] == "COMP-002"
    assert structure_seed["sensor_comp_id"] == "COMP-003"
    assert structure_project["projection_dirty"] is True

    controller_seed = seed_realistic_controller_core(cli_runner, tmp_path / "controller")
    controller_project = read_project_data(controller_seed["db_path"])

    assert controller_seed["fn_ids"] == ["FN-001", "FN-002"]
    assert len(controller_seed["requirement_rowids"]) == 2
    assert len(controller_seed["characteristic_rowids"]) == 2
    assert controller_project["projection_dirty"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_partial_realistic_seeds_support_agent_style_incremental_intake -q`
Expected: FAIL because `tests/test_realistic_agent_session.py` and the new partial-seed helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

- Add `invoke_json()` and `read_project_data()` exactly as shown above.
- Add `seed_realistic_structure_only()` and `seed_realistic_controller_core()` with the exact command sequence and return keys defined above.
- In `tests/test_realistic_agent_session.py`, add only this first test and any imports it needs.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_partial_realistic_seeds_support_agent_style_incremental_intake -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers_realistic_dfmea.py tests/test_realistic_agent_session.py
git commit -m "test: add realistic agent session seed helpers"
```

## Task 2: Add Session A Incremental Intake And Follow-Up Questions

**Files:**
- Modify: `tests/test_realistic_agent_session.py`
- Modify: `tests/helpers_realistic_dfmea.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_session_incrementally_records_dfmea_then_answers_follow_up_questions(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_controller_core(cli_runner, tmp_path)

    list_payload = invoke_json(
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(seeded["db_path"]),
            "--type",
            "FN",
            "--parent",
            seeded["controller_comp_id"],
            "--format",
            "json",
        ],
    )
    assert list_payload["data"]["count"] == 2

    get_payload = invoke_json(
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(seeded["db_path"]),
            "--node",
            seeded["controller_start_fn_id"],
            "--format",
            "json",
        ],
    )
    assert get_payload["data"]["node"]["id"] == seeded["controller_start_fn_id"]

    search_payload = invoke_json(
        cli_runner,
        [
            "query",
            "search",
            "--db",
            str(seeded["db_path"]),
            "--keyword",
            "speed",
            "--format",
            "json",
        ],
    )
    assert search_payload["data"]["count"] >= 1

    protect_fn = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(seeded["db_path"]),
            "--comp",
            seeded["controller_comp_id"],
            "--name",
            "Enter overtemperature protection and report faults",
            "--description",
            "Force protection mode and report thermal control faults",
            "--format",
            "json",
        ],
    )
    protect_fn_id = protect_fn["data"]["fn_id"]

    protect_req = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            protect_fn_id,
            "--text",
            "Enter protection mode at calibrated overtemperature threshold",
            "--source",
            "CTRL-REQ-PROTECT",
            "--format",
            "json",
        ],
    )
    protect_char = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            protect_fn_id,
            "--text",
            "Protection threshold accuracy",
            "--value",
            "2",
            "--unit",
            "degC",
            "--format",
            "json",
        ],
    )

    start_chain = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            seeded["controller_start_fn_id"],
            "--fm-description",
            "Fan not started when cooling requested",
            "--severity",
            "8",
            "--violates-req",
            str(seeded["requirement_rowids"][0]),
            "--related-char",
            str(seeded["characteristic_rowids"][0]),
            "--fe-description",
            "Required airflow not delivered",
            "--fe-level",
            "system",
            "--fc-description",
            "Temperature signal biased low",
            "--occurrence",
            "4",
            "--detection",
            "4",
            "--ap",
            "High",
            "--fc-description",
            "Driver output stage stuck low",
            "--occurrence",
            "3",
            "--detection",
            "3",
            "--ap",
            "High",
            "--act-description",
            "Add sensor plausibility and output-stage feedback diagnostics",
            "--kind",
            "detection",
            "--status",
            "planned",
            "--owner",
            "Controls",
            "--due",
            "2026-07-01",
            "--target-causes",
            "1,2",
            "--format",
            "json",
        ],
    )
    speed_chain = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            seeded["controller_speed_fn_id"],
            "--fm-description",
            "Fan speed below target",
            "--severity",
            "7",
            "--violates-req",
            str(seeded["requirement_rowids"][1]),
            "--related-char",
            str(seeded["characteristic_rowids"][1]),
            "--fe-description",
            "Heat rejection lower than commanded",
            "--fe-level",
            "system",
            "--fc-description",
            "PWM clamp calibrated too low",
            "--occurrence",
            "4",
            "--detection",
            "5",
            "--ap",
            "Medium",
            "--fc-description",
            "Low-voltage fallback logic incorrect",
            "--occurrence",
            "3",
            "--detection",
            "5",
            "--ap",
            "Medium",
            "--act-description",
            "Tighten PWM calibration and low-voltage fallback test coverage",
            "--kind",
            "prevention",
            "--status",
            "planned",
            "--owner",
            "Controls",
            "--due",
            "2026-07-15",
            "--target-causes",
            "1,2",
            "--format",
            "json",
        ],
    )
    protect_chain = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            protect_fn_id,
            "--fm-description",
            "Overtemperature protection not entered",
            "--severity",
            "9",
            "--violates-req",
            str(protect_req["data"]["req_rowid"]),
            "--related-char",
            str(protect_char["data"]["char_rowid"]),
            "--fe-description",
            "Protective high-speed mode unavailable",
            "--fe-level",
            "system",
            "--fc-description",
            "Overtemperature threshold set too high",
            "--occurrence",
            "3",
            "--detection",
            "4",
            "--ap",
            "High",
            "--fc-description",
            "Fault-state machine stalls",
            "--occurrence",
            "2",
            "--detection",
            "5",
            "--ap",
            "Medium",
            "--act-description",
            "Add threshold boundary tests and watchdog coverage",
            "--kind",
            "detection",
            "--status",
            "planned",
            "--owner",
            "Software",
            "--due",
            "2026-07-30",
            "--target-causes",
            "1,2",
            "--format",
            "json",
        ],
    )

    sensor_comp = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(seeded["db_path"]),
            "--comp",
            seeded["sensor_comp_id"],
            "--name",
            "Provide coolant temperature signal",
            "--description",
            "Provide coolant temperature feedback to controller logic",
            "--format",
            "json",
        ],
    )
    sensor_chain = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            sensor_comp["data"]["fn_id"],
            "--fm-description",
            "Temperature signal biased low",
            "--severity",
            "8",
            "--fe-description",
            "Fan not started when cooling requested",
            "--fe-level",
            "component",
            "--fc-description",
            "Sensor pull-up open circuit",
            "--occurrence",
            "4",
            "--detection",
            "4",
            "--ap",
            "High",
            "--act-description",
            "Add sensor input plausibility monitor",
            "--kind",
            "detection",
            "--status",
            "planned",
            "--owner",
            "Diagnostics",
            "--due",
            "2026-08-01",
            "--target-causes",
            "1",
            "--format",
            "json",
        ],
    )

    motor_fn = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(seeded["db_path"]),
            "--comp",
            seeded["motor_comp_id"],
            "--name",
            "Generate airflow under controller command",
            "--description",
            "Convert controller command into cooling airflow",
            "--format",
            "json",
        ],
    )
    motor_chain = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-failure-chain",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            motor_fn["data"]["fn_id"],
            "--fm-description",
            "Required airflow not delivered",
            "--severity",
            "7",
            "--fe-description",
            "Engine-bay airflow margin reduced",
            "--fe-level",
            "vehicle",
            "--fc-description",
            "Motor bearing drag high",
            "--occurrence",
            "5",
            "--detection",
            "4",
            "--ap",
            "High",
            "--act-description",
            "Add bearing drag screening",
            "--kind",
            "prevention",
            "--status",
            "planned",
            "--owner",
            "Supplier Quality",
            "--due",
            "2026-08-15",
            "--target-causes",
            "1",
            "--format",
            "json",
        ],
    )

    start_fc_rowid = next(
        obj["rowid"]
        for obj in start_chain["data"]["affected_objects"]
        if obj["type"] == "FC"
    )
    sensor_fe_rowid = next(
        obj["rowid"]
        for obj in sensor_chain["data"]["affected_objects"]
        if obj["type"] == "FE"
    )
    start_fe_rowid = next(
        obj["rowid"]
        for obj in start_chain["data"]["affected_objects"]
        if obj["type"] == "FE"
    )

    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(seeded["db_path"]),
            "--from",
            f"fc:{start_fc_rowid}",
            "--to-fm",
            sensor_chain["data"]["fm_id"],
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(seeded["db_path"]),
            "--from",
            f"fe:{sensor_fe_rowid}",
            "--to-fm",
            start_chain["data"]["fm_id"],
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(seeded["db_path"]),
            "--from",
            f"fe:{start_fe_rowid}",
            "--to-fm",
            motor_chain["data"]["fm_id"],
            "--format",
            "json",
        ],
    )

    status_payload = invoke_json(
        cli_runner,
        ["projection", "status", "--db", str(seeded["db_path"]), "--format", "json"],
    )
    assert status_payload["data"]["projection_dirty"] is True

    rebuild_projection(cli_runner, seeded["db_path"])

    summary_payload = invoke_json(
        cli_runner,
        [
            "query",
            "summary",
            "--db",
            str(seeded["db_path"]),
            "--comp",
            seeded["controller_comp_id"],
            "--format",
            "json",
        ],
    )
    assert summary_payload["data"]["counts"]["functions"] == 3

    dossier_payload = invoke_json(
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(seeded["db_path"]),
            "--fn",
            seeded["controller_start_fn_id"],
            "--format",
            "json",
        ],
    )
    assert dossier_payload["data"]["function"]["id"] == seeded["controller_start_fn_id"]

    by_ap_payload = invoke_json(
        cli_runner,
        [
            "query",
            "by-ap",
            "--db",
            str(seeded["db_path"]),
            "--ap",
            "High",
            "--format",
            "json",
        ],
    )
    assert by_ap_payload["data"]["count"] == 5

    by_severity_payload = invoke_json(
        cli_runner,
        [
            "query",
            "by-severity",
            "--db",
            str(seeded["db_path"]),
            "--gte",
            "8",
            "--format",
            "json",
        ],
    )
    assert {node["id"] for node in by_severity_payload["data"]["nodes"]} == {
        start_chain["data"]["fm_id"],
        protect_chain["data"]["fm_id"],
        sensor_chain["data"]["fm_id"],
    }

    causes_payload = invoke_json(
        cli_runner,
        [
            "trace",
            "causes",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            start_chain["data"]["fm_id"],
            "--format",
            "json",
        ],
    )
    assert [item["fm"]["id"] for item in causes_payload["data"]["chain"]] == [
        start_chain["data"]["fm_id"],
        sensor_chain["data"]["fm_id"],
    ]

    effects_payload = invoke_json(
        cli_runner,
        [
            "trace",
            "effects",
            "--db",
            str(seeded["db_path"]),
            "--fm",
            sensor_chain["data"]["fm_id"],
            "--format",
            "json",
        ],
    )
    assert [item["fm"]["id"] for item in effects_payload["data"]["chain"]] == [
        sensor_chain["data"]["fm_id"],
        start_chain["data"]["fm_id"],
        motor_chain["data"]["fm_id"],
    ]

    export_out = tmp_path / "session-a-export"
    export_payload = invoke_json(
        cli_runner,
        [
            "export",
            "markdown",
            "--db",
            str(seeded["db_path"]),
            "--out",
            str(export_out),
            "--layout",
            "review",
            "--format",
            "json",
        ],
    )
    assert any(Path(item["path"]).name == "index.md" for item in export_payload["data"]["files"])

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(seeded["db_path"]), "--format", "json"],
    )
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_agent_session_incrementally_records_dfmea_then_answers_follow_up_questions -q`
Expected: FAIL until the session test and any small helper additions are implemented.

- [ ] **Step 3: Write minimal implementation**

- Add the test exactly in the same database started by `seed_realistic_controller_core()`.
- If any repeated command sequence becomes noisy, add only tiny wrappers to `tests/helpers_realistic_dfmea.py`; do not move the whole story into helper internals.
- Keep the test shaped like a conversation:
  - partial intake
  - early query/list/get/search answers
  - additional intake
  - risk and trace follow-ups
  - rebuild
  - export
  - validate

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_agent_session_incrementally_records_dfmea_then_answers_follow_up_questions -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers_realistic_dfmea.py tests/test_realistic_agent_session.py
git commit -m "test: add incremental realistic agent intake coverage"
```

## Task 3: Add Session B Maintenance And Integrity Repair Chain

**Files:**
- Modify: `tests/test_realistic_agent_session.py`
- Modify: `tests/helpers_realistic_dfmea.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_session_repairs_realistic_dfmea_after_user_requested_changes(
    cli_runner, tmp_path: Path
):
    scenario = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    rebuild_projection(cli_runner, scenario.db_path)

    invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fm",
            "--db",
            str(scenario.db_path),
            "--fm",
            scenario.fm_low_speed_id,
            "--description",
            "Fan speed below thermal demand after low-voltage event",
            "--severity",
            "8",
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fe",
            "--db",
            str(scenario.db_path),
            "--fe",
            str(scenario.fe_low_speed_heat_rejection_rowid),
            "--description",
            "Heat rejection reduced during sustained load",
            "--level",
            "system",
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "update-fc",
            "--db",
            str(scenario.db_path),
            "--fc",
            str(scenario.fc_driver_output_stuck_rowid),
            "--description",
            "Driver output stage intermittently stuck low",
            "--occurrence",
            "4",
            "--detection",
            "4",
            "--ap",
            "High",
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "update-act",
            "--db",
            str(scenario.db_path),
            "--act",
            scenario.act_speed_id,
            "--description",
            "Expand PWM calibration and low-voltage fallback verification",
            "--kind",
            "prevention",
            "--status",
            "in-progress",
            "--owner",
            "Controls Validation",
            "--due",
            "2026-08-30",
            "--target-causes",
            f"{scenario.fc_pwm_clamp_low_rowid},{scenario.fc_low_voltage_logic_rowid}",
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "update-action-status",
            "--db",
            str(scenario.db_path),
            "--act",
            scenario.act_speed_id,
            "--status",
            "completed",
            "--format",
            "json",
        ],
    )

    invoke_json(
        cli_runner,
        [
            "analysis",
            "unlink-fm-requirement",
            "--db",
            str(scenario.db_path),
            "--fm",
            scenario.fm_low_speed_id,
            "--req",
            str(scenario.req_speed_rowid),
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-fm-requirement",
            "--db",
            str(scenario.db_path),
            "--fm",
            scenario.fm_low_speed_id,
            "--req",
            str(scenario.req_speed_rowid),
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "unlink-fm-characteristic",
            "--db",
            str(scenario.db_path),
            "--fm",
            scenario.fm_low_speed_id,
            "--char",
            str(scenario.char_speed_rowid),
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-fm-characteristic",
            "--db",
            str(scenario.db_path),
            "--fm",
            scenario.fm_low_speed_id,
            "--char",
            str(scenario.char_speed_rowid),
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "unlink-trace",
            "--db",
            str(scenario.db_path),
            "--from",
            f"fe:{scenario.fe_airflow_not_established_rowid}",
            "--to-fm",
            scenario.fm_low_airflow_id,
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(scenario.db_path),
            "--from",
            f"fe:{scenario.fe_airflow_not_established_rowid}",
            "--to-fm",
            scenario.fm_low_airflow_id,
            "--format",
            "json",
        ],
    )

    temp_req = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(scenario.db_path),
            "--fn",
            scenario.controller_speed_fn_id,
            "--text",
            "Temporary verification requirement",
            "--source",
            "TEMP-REQ-1",
            "--format",
            "json",
        ],
    )
    temp_char = invoke_json(
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(scenario.db_path),
            "--fn",
            scenario.controller_speed_fn_id,
            "--text",
            "Temporary verification characteristic",
            "--value",
            "1",
            "--unit",
            "flag",
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "delete-requirement",
            "--db",
            str(scenario.db_path),
            "--req",
            str(temp_req["data"]["req_rowid"]),
            "--format",
            "json",
        ],
    )
    invoke_json(
        cli_runner,
        [
            "analysis",
            "delete-characteristic",
            "--db",
            str(scenario.db_path),
            "--char",
            str(temp_char["data"]["char_rowid"]),
            "--format",
            "json",
        ],
    )

    status_payload = invoke_json(
        cli_runner,
        ["projection", "status", "--db", str(scenario.db_path), "--format", "json"],
    )
    assert status_payload["data"]["projection_dirty"] is True

    rebuild_projection(cli_runner, scenario.db_path)

    dossier_payload = invoke_json(
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(scenario.db_path),
            "--fn",
            scenario.controller_speed_fn_id,
            "--format",
            "json",
        ],
    )
    assert dossier_payload["data"]["function"]["id"] == scenario.controller_speed_fn_id

    actions_payload = invoke_json(
        cli_runner,
        [
            "query",
            "actions",
            "--db",
            str(scenario.db_path),
            "--status",
            "completed",
            "--format",
            "json",
        ],
    )
    assert scenario.act_speed_id in {node["id"] for node in actions_payload["data"]["nodes"]}

    severity_payload = invoke_json(
        cli_runner,
        [
            "query",
            "by-severity",
            "--db",
            str(scenario.db_path),
            "--gte",
            "8",
            "--format",
            "json",
        ],
    )
    assert scenario.fm_low_speed_id in {node["id"] for node in severity_payload["data"]["nodes"]}

    export_payload = invoke_json(
        cli_runner,
        [
            "export",
            "markdown",
            "--db",
            str(scenario.db_path),
            "--out",
            str(tmp_path / "repair-export"),
            "--layout",
            "review",
            "--format",
            "json",
        ],
    )
    assert export_payload["data"]["files"]

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(scenario.db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"]["errors"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_agent_session_repairs_realistic_dfmea_after_user_requested_changes -q`
Expected: FAIL because the helper does not yet expose every stable rowid and relationship needed by the repair session.

- [ ] **Step 3: Write minimal implementation**

Extend `RealisticCoolingFanProjectSeed` only with fields this test needs, such as:

```python
req_start_rowid: int
req_speed_rowid: int
req_protect_rowid: int
char_start_rowid: int
char_speed_rowid: int
char_protect_rowid: int
fe_low_speed_heat_rejection_rowid: int
fc_pwm_clamp_low_rowid: int
fc_low_voltage_logic_rowid: int
```

Capture these from the existing realistic seeding payloads instead of computing them indirectly.

Then implement the session test exactly as a maintenance chain:

1. update FM/FE/FC/ACT/action-status
2. unlink + relink requirement/characteristic
3. unlink + relink trace
4. create and delete a temporary requirement/characteristic
5. assert dirty projection
6. rebuild
7. query repaired dossier/actions/severity view
8. export review layout
9. validate with zero errors

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_agent_session_repairs_realistic_dfmea_after_user_requested_changes -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers_realistic_dfmea.py tests/test_realistic_agent_session.py
git commit -m "test: add realistic agent repair session coverage"
```

## Task 4: Add Session C Failure-Recovery Chain

**Files:**
- Modify: `tests/test_realistic_agent_session.py`
- Modify: `tests/helpers_realistic_dfmea.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_session_recovers_from_invalid_actions_and_finishes_cleanly(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_structure_only(cli_runner, tmp_path / "partial")

    invalid_parent_result = cli_runner.invoke(
        [
            "structure",
            "add",
            "--db",
            str(seeded["db_path"]),
            "--type",
            "COMP",
            "--name",
            "Illegal Component",
            "--parent",
            seeded["sys_id"],
            "--format",
            "json",
        ]
    )
    invalid_parent_payload = parse_json_payload(invalid_parent_result)
    assert invalid_parent_payload["ok"] is False
    assert invalid_parent_payload["errors"][0]["code"] == "INVALID_PARENT"

    legal_comp = invoke_json(
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(seeded["db_path"]),
            "--type",
            "COMP",
            "--name",
            "Cooling Fan Relay Interface",
            "--parent",
            seeded["sub_id"],
            "--format",
            "json",
        ],
    )
    assert legal_comp["data"]["parent_id"] == seeded["sub_id"]

    full = seed_realistic_cooling_fan_project(cli_runner, tmp_path / "full")

    delete_result = cli_runner.invoke(
        [
            "structure",
            "delete",
            "--db",
            str(full.db_path),
            "--node",
            full.controller_comp_id,
            "--format",
            "json",
        ]
    )
    delete_payload = parse_json_payload(delete_result)
    assert delete_payload["ok"] is False
    assert delete_payload["errors"][0]["code"] == "NODE_NOT_EMPTY"

    invalid_trace_result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(full.db_path),
            "--from",
            f"fe:{full.fe_airflow_not_established_rowid}",
            "--to-fm",
            full.fm_low_speed_id,
            "--format",
            "json",
        ]
    )
    invalid_trace_payload = parse_json_payload(invalid_trace_result)
    assert invalid_trace_payload["ok"] is False
    assert invalid_trace_payload["errors"][0]["code"] == "INVALID_REFERENCE"

    get_payload = invoke_json(
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(full.db_path),
            "--node",
            full.fm_missed_start_id,
            "--format",
            "json",
        ],
    )
    assert get_payload["data"]["node"]["id"] == full.fm_missed_start_id

    export_payload = invoke_json(
        cli_runner,
        [
            "export",
            "markdown",
            "--db",
            str(full.db_path),
            "--out",
            str(tmp_path / "recovery-export"),
            "--layout",
            "review",
            "--format",
            "json",
        ],
    )
    assert export_payload["data"]["files"]

    rebuild_projection(cli_runner, full.db_path)
    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(full.db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"] == {"errors": 0, "warnings": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_agent_session_recovers_from_invalid_actions_and_finishes_cleanly -q`
Expected: FAIL until the session test is added and any missing helper support is in place.

- [ ] **Step 3: Write minimal implementation**

- Add the failure-recovery test exactly as shown.
- Keep error assertions recovery-oriented and minimal:
  - invalid parent -> `INVALID_PARENT`
  - non-empty structure delete -> `NODE_NOT_EMPTY`
  - same-component trace -> `INVALID_REFERENCE`
- Do not repeat full `target` payload contracts already covered elsewhere.
- Ensure the session actually continues after the failures by performing:
  - one legal structure add
  - one successful `query get`
  - one successful review export
  - `projection rebuild`
  - `validate` with zero errors

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_agent_session.py::test_agent_session_recovers_from_invalid_actions_and_finishes_cleanly -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers_realistic_dfmea.py tests/test_realistic_agent_session.py
git commit -m "test: add realistic agent failure recovery coverage"
```

## Task 5: Run The Full Verification Set

**Files:**
- Verify only; no new files required unless an earlier task exposed a real runtime bug.

- [ ] **Step 1: Run the new session module only**

Run: `python -m pytest tests/test_realistic_agent_session.py -q`
Expected: PASS.

- [ ] **Step 2: Run all realistic modules together**

Run: `python -m pytest tests/test_realistic_dfmea_end_to_end.py tests/test_realistic_dfmea_regression_matrix.py tests/test_realistic_agent_session.py -q`
Expected: PASS.

- [ ] **Step 3: Run the closest supporting command suites**

Run: `python -m pytest tests/test_structure_commands.py tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py tests/test_query_commands.py tests/test_trace_commands.py tests/test_validate_and_export_commands.py -q`
Expected: PASS.

- [ ] **Step 4: Run the full repository suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit any final cleanup only if needed**

```bash
git add tests/helpers_realistic_dfmea.py tests/test_realistic_agent_session.py
git commit -m "test: finalize realistic agent session coverage"
```

Only create this final commit if Tasks 1-4 left additional uncommitted cleanup. If there is nothing new after the earlier task commits, skip this step.

## Verification Notes

- Current worktree uses the real Python package layout from `pyproject.toml`, so `python -m pytest -q` is the authoritative verification command despite the older baseline comments in root `CLAUDE.md`.
- If a session test fails because an existing command behaves differently from this plan, verify the real contract in the existing command tests before changing either the session test or runtime.
- If runtime fixes become necessary, add the narrow failing session test first, patch the smallest runtime file, rerun the narrow session test, then rerun the broader verification set.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-28-dfmea-agent-session-coverage-tests.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
