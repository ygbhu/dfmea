# DFMEA Multi-Agent WAL Coverage Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a realistic multi-agent session test suite that proves several agents can share one DFMEA SQLite/WAL database, interleave explicit CLI reads and writes, observe canonical visibility immediately, respect dirty/stale projection semantics, survive failed writes without cross-agent pollution, and still converge to a clean validated state.

**Architecture:** Create one new module, `tests/test_realistic_multi_agent_sessions.py`, and keep the multi-agent orchestration local to that file. Reuse the existing realistic helper module only for low-level DB inspection and full-project seeding where explicitly allowed, but do not hide multi-agent session steps behind large scenario helpers: each Agent A/B/C action in the tests must be an explicit CLI call against the same `db_path`. Use `query list/get/search` plus project metadata reads to prove canonical visibility, use `projection status` and stale-projection validation to prove dirty/stale semantics, and use `projection rebuild` followed by projection-backed queries to prove final convergence.

**Tech Stack:** Python 3.11+, pytest, Typer `CliRunner`, stdlib `sqlite3`, existing `dfmea_cli` CLI commands, existing realistic helper module.

---

## File Structure

### Tests

- Create: `tests/test_realistic_multi_agent_sessions.py` - three multi-agent session tests for shared-DB visibility, projection coordination, and failed-write isolation.
- Leave unchanged: `tests/helpers_realistic_dfmea.py` - already provides what this plan needs:
  - `invoke_json`
  - `parse_json_payload`
  - `read_project_data`
  - `read_fm_links`
  - `read_node_rowid`
  - `seed_realistic_cooling_fan_project`
- Leave unchanged: `tests/test_realistic_dfmea_end_to_end.py`
- Leave unchanged: `tests/test_realistic_dfmea_regression_matrix.py`
- Leave unchanged: `tests/test_realistic_agent_session.py`

### Runtime Package

- No runtime changes are planned.
- If a new test exposes a real defect, patch only the smallest affected runtime file after reproducing it through the failing test:
  - `src/dfmea_cli/services/projections.py`
  - `src/dfmea_cli/services/query.py`
  - `src/dfmea_cli/services/validate.py`
  - `src/dfmea_cli/services/analysis.py`
  - `src/dfmea_cli/services/structure.py`
  - `src/dfmea_cli/services/trace.py`
  - or the smallest affected file under `src/dfmea_cli/commands/`

### Design Reference

- Spec: `docs/superpowers/specs/2026-03-28-dfmea-multi-agent-wal-coverage-design.md`

## Scope Guardrails

- The new module tests multi-agent semantics, not random thread scheduling.
- Every Agent A/B/C step must be a fresh CLI invocation against the same `db_path`.
- Canonical reads are used to prove immediate visibility.
- Projection-backed reads are used only after the test has explicitly acknowledged dirty/stale state.
- Every session must end with `validate` asserting `{errors: 0, warnings: 0}`.
- Do not add export coverage in this round; the multi-agent proof ends with `query` / `trace` evidence plus `validate`.

## Local Helpers To Add In The New Test File

Add only these small local helpers inside `tests/test_realistic_multi_agent_sessions.py`:

```python
from pathlib import Path

from helpers_realistic_dfmea import (
    invoke_json,
    parse_json_payload,
    read_fm_links,
    read_project_data,
    read_node_rowid,
    seed_realistic_cooling_fan_project,
)


def _agent_json(agent: str, cli_runner, args: list[str]) -> dict:
    """Thin wrapper used only to label failures by agent."""
    payload = invoke_json(cli_runner, args)
    assert payload["command"], f"Agent {agent} returned empty command"
    return payload


def _canonical_revision(db_path: Path) -> int:
    return int(read_project_data(db_path)["canonical_revision"])


def _projection_dirty(db_path: Path) -> bool:
    return bool(read_project_data(db_path)["projection_dirty"])


def _node_ids(payload: dict) -> set[str]:
    return {node["id"] for node in payload["data"]["nodes"]}


def _node_names(payload: dict) -> set[str]:
    return {node["name"] for node in payload["data"]["nodes"]}


def _fm_link_pairs(db_path: Path) -> set[tuple[int, int]]:
    return {
        (item["from_node_rowid"], item["to_fm_rowid"])
        for item in read_fm_links(db_path)
    }
```

These helpers exist only to improve readability; they must not hide any agent step.

## Task 1: Add Session A Shared-DB Intake And Visibility Test

**Files:**
- Create: `tests/test_realistic_multi_agent_sessions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_multi_agent_session_interleaves_intake_and_projection_visibility(
    cli_runner, tmp_path: Path
):
    db_path = tmp_path / "multi-agent-a.db"

    # Agent A: explicit shared-db project setup.
    _agent_json(
        "A",
        cli_runner,
        [
            "init",
            "--db",
            str(db_path),
            "--project",
            "demo",
            "--name",
            "Passenger Vehicle Electronic Cooling Fan Controller",
            "--format",
            "json",
        ],
    )
    sys_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "SYS",
            "--name",
            "Engine Thermal Management System",
            "--format",
            "json",
        ],
    )
    sys_id = sys_payload["data"]["node_id"]
    sub_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "SUB",
            "--name",
            "Cooling Fan System",
            "--parent",
            sys_id,
            "--format",
            "json",
        ],
    )
    sub_id = sub_payload["data"]["node_id"]
    controller_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Electronic Cooling Fan Controller",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    motor_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Cooling Fan Motor Assembly",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    sensor_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--name",
            "Coolant Temperature Sensing Path",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    controller_comp_id = controller_payload["data"]["node_id"]
    revision_after_structure = _canonical_revision(db_path)

    # Agent B: canonical reads must see structure immediately.
    component_list = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(db_path),
            "--type",
            "COMP",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    assert component_list["data"]["count"] == 3
    assert _node_names(component_list) == {
        "Electronic Cooling Fan Controller",
        "Cooling Fan Motor Assembly",
        "Coolant Temperature Sensing Path",
    }

    # Agent C: continue intake through explicit CLI writes on the same DB.
    start_fn = _agent_json(
        "C",
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            controller_comp_id,
            "--name",
            "Control fan start and stop",
            "--description",
            "Command fan start and stop according to cooling demand",
            "--format",
            "json",
        ],
    )
    start_fn_id = start_fn["data"]["fn_id"]

    # Agent B: canonical get must see the newly created function immediately.
    function_get = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(db_path),
            "--node",
            start_fn_id,
            "--format",
            "json",
        ],
    )
    assert function_get["data"]["node"]["id"] == start_fn_id

    speed_fn = _agent_json(
        "C",
        cli_runner,
        [
            "analysis",
            "add-function",
            "--db",
            str(db_path),
            "--comp",
            controller_comp_id,
            "--name",
            "Modulate fan speed",
            "--description",
            "Adjust commanded fan speed to meet heat rejection demand",
            "--format",
            "json",
        ],
    )
    speed_fn_id = speed_fn["data"]["fn_id"]

    _agent_json(
        "C",
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            start_fn_id,
            "--text",
            "Start fan within demanded cooling window",
            "--source",
            "CTRL-REQ-START",
            "--format",
            "json",
        ],
    )
    _agent_json(
        "C",
        cli_runner,
        [
            "analysis",
            "add-requirement",
            "--db",
            str(db_path),
            "--fn",
            speed_fn_id,
            "--text",
            "Track requested fan speed across operating range",
            "--source",
            "CTRL-REQ-SPEED",
            "--format",
            "json",
        ],
    )
    _agent_json(
        "C",
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            start_fn_id,
            "--text",
            "Fan start response time",
            "--value",
            "500",
            "--unit",
            "ms",
            "--format",
            "json",
        ],
    )
    _agent_json(
        "C",
        cli_runner,
        [
            "analysis",
            "add-characteristic",
            "--db",
            str(db_path),
            "--fn",
            speed_fn_id,
            "--text",
            "Fan speed tracking error",
            "--value",
            "10",
            "--unit",
            "pct",
            "--format",
            "json",
        ],
    )
    assert _canonical_revision(db_path) > revision_after_structure

    # Agent B: canonical search must see newly inserted text immediately.
    search_payload = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "search",
            "--db",
            str(db_path),
            "--keyword",
            "tracking",
            "--format",
            "json",
        ],
    )
    assert search_payload["data"]["count"] == 1
    assert search_payload["data"]["nodes"][0]["type"] == "CHAR"
    assert search_payload["data"]["nodes"][0]["parent"]["id"] == speed_fn_id

    # Agent A/B: the project must now be dirty/stale until rebuild.
    status_payload = _agent_json(
        "A",
        cli_runner,
        ["projection", "status", "--db", str(db_path), "--format", "json"],
    )
    assert status_payload["data"]["projection_dirty"] is True
    assert _projection_dirty(db_path) is True

    stale_validate = _agent_json(
        "B",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert any(
        issue["scope"] == "projection" and issue["kind"] == "STALE_PROJECTION"
        for issue in stale_validate["data"]["issues"]
    )

    # Agent C: rebuild; Agent A/B now agree on projection-backed reads.
    rebuild_payload = _agent_json(
        "C",
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False

    summary_payload = _agent_json(
        "A",
        cli_runner,
        [
            "query",
            "summary",
            "--db",
            str(db_path),
            "--comp",
            controller_comp_id,
            "--format",
            "json",
        ],
    )
    assert summary_payload["data"]["counts"] == {
        "functions": 2,
        "requirements": 2,
        "characteristics": 2,
        "failure_modes": 0,
        "failure_effects": 0,
        "failure_causes": 0,
        "actions": 0,
    }

    dossier_payload = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(db_path),
            "--fn",
            start_fn_id,
            "--format",
            "json",
        ],
    )
    assert len(dossier_payload["data"]["requirements"]) == 1
    assert len(dossier_payload["data"]["characteristics"]) == 1
    assert dossier_payload["data"]["failure_modes"] == []

    clean_validate = _agent_json(
        "C",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert clean_validate["data"]["summary"] == {"errors": 0, "warnings": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py::test_multi_agent_session_interleaves_intake_and_projection_visibility -q`
Expected: FAIL because the new test module and local helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

- Create `tests/test_realistic_multi_agent_sessions.py`.
- Add the local helper functions from the “Local Helpers” section.
- Add the Session A test exactly as shown.
- Do not move these multi-agent orchestration helpers into `tests/helpers_realistic_dfmea.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py::test_multi_agent_session_interleaves_intake_and_projection_visibility -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_realistic_multi_agent_sessions.py
git commit -m "test: add realistic multi-agent visibility coverage"
```

## Task 2: Add Session B Interleaved Maintenance And Projection Coordination

**Files:**
- Modify: `tests/test_realistic_multi_agent_sessions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_multi_agent_session_coordinates_updates_and_projection_rebuild(
    cli_runner, tmp_path: Path
):
    seed = seed_realistic_cooling_fan_project(cli_runner, tmp_path)
    db_path = seed.db_path

    # Agent A: establish a clean baseline projection.
    baseline_rebuild = _agent_json(
        "A",
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert baseline_rebuild["data"]["projection_dirty"] is False
    baseline_revision = _canonical_revision(db_path)

    # Agent A: update action status.
    _agent_json(
        "A",
        cli_runner,
        [
            "analysis",
            "update-action-status",
            "--db",
            str(db_path),
            "--act",
            seed.act_speed_id,
            "--status",
            "completed",
            "--format",
            "json",
        ],
    )

    # Agent B: update FM severity and temporarily remove then restore a trace.
    _agent_json(
        "B",
        cli_runner,
        [
            "analysis",
            "update-fm",
            "--db",
            str(db_path),
            "--fm",
            seed.fm_low_speed_id,
            "--description",
            "Fan speed below target after shared-agent maintenance",
            "--severity",
            "8",
            "--format",
            "json",
        ],
    )
    _agent_json(
        "B",
        cli_runner,
        [
            "analysis",
            "unlink-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{seed.fe_airflow_not_established_rowid}",
            "--to-fm",
            seed.fm_low_airflow_id,
            "--format",
            "json",
        ],
    )

    low_airflow_rowid = read_node_rowid(db_path, seed.fm_low_airflow_id)
    assert (seed.fe_airflow_not_established_rowid, low_airflow_rowid) not in _fm_link_pairs(db_path)
    assert _canonical_revision(db_path) > baseline_revision
    assert _projection_dirty(db_path) is True

    # Agent C: stale projection must be visible before rebuild.
    stale_validate = _agent_json(
        "C",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert any(
        issue["scope"] == "projection" and issue["kind"] == "STALE_PROJECTION"
        for issue in stale_validate["data"]["issues"]
    )

    # Agent B: restore the trace, then Agent A rebuilds.
    _agent_json(
        "B",
        cli_runner,
        [
            "analysis",
            "link-trace",
            "--db",
            str(db_path),
            "--from",
            f"fe:{seed.fe_airflow_not_established_rowid}",
            "--to-fm",
            seed.fm_low_airflow_id,
            "--format",
            "json",
        ],
    )
    assert (seed.fe_airflow_not_established_rowid, low_airflow_rowid) in _fm_link_pairs(db_path)

    rebuild_payload = _agent_json(
        "A",
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False

    actions_payload = _agent_json(
        "C",
        cli_runner,
        [
            "query",
            "actions",
            "--db",
            str(db_path),
            "--status",
            "completed",
            "--format",
            "json",
        ],
    )
    assert seed.act_speed_id in _node_ids(actions_payload)

    severity_payload = _agent_json(
        "A",
        cli_runner,
        [
            "query",
            "by-severity",
            "--db",
            str(db_path),
            "--gte",
            "8",
            "--format",
            "json",
        ],
    )
    assert seed.fm_low_speed_id in _node_ids(severity_payload)

    dossier_payload = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "dossier",
            "--db",
            str(db_path),
            "--fn",
            seed.controller_speed_fn_id,
            "--format",
            "json",
        ],
    )
    assert dossier_payload["data"]["failure_modes"][0]["fm"]["id"] == seed.fm_low_speed_id

    trace_payload = _agent_json(
        "C",
        cli_runner,
        [
            "trace",
            "effects",
            "--db",
            str(db_path),
            "--fm",
            seed.fm_temp_signal_biased_id,
            "--format",
            "json",
        ],
    )
    assert [item["fm"]["id"] for item in trace_payload["data"]["chain"]] == [
        seed.fm_temp_signal_biased_id,
        seed.fm_missed_start_id,
        seed.fm_low_airflow_id,
    ]

    clean_validate = _agent_json(
        "A",
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert clean_validate["data"]["summary"] == {"errors": 0, "warnings": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py::test_multi_agent_session_coordinates_updates_and_projection_rebuild -q`
Expected: FAIL until the new Session B test is added.

- [ ] **Step 3: Write minimal implementation**

- Add the Session B test exactly as shown.
- Keep all Agent A/B/C actions as fresh CLI invocations.
- Do not add new shared helpers unless you find literal duplication severe enough to justify one tiny local helper inside this file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py::test_multi_agent_session_coordinates_updates_and_projection_rebuild -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_realistic_multi_agent_sessions.py
git commit -m "test: add realistic multi-agent projection coordination coverage"
```

## Task 3: Add Session C Failed-Write Isolation Test

**Files:**
- Modify: `tests/test_realistic_multi_agent_sessions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_multi_agent_session_isolates_failed_writes_from_other_agents(
    cli_runner, tmp_path: Path
):
    partial_db = tmp_path / "partial.db"

    # Agent A: explicit shared partial setup.
    _agent_json(
        "A",
        cli_runner,
        [
            "init",
            "--db",
            str(partial_db),
            "--project",
            "demo",
            "--name",
            "Passenger Vehicle Electronic Cooling Fan Controller",
            "--format",
            "json",
        ],
    )
    sys_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "SYS",
            "--name",
            "Engine Thermal Management System",
            "--format",
            "json",
        ],
    )
    sys_id = sys_payload["data"]["node_id"]
    sub_payload = _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "SUB",
            "--name",
            "Cooling Fan System",
            "--parent",
            sys_id,
            "--format",
            "json",
        ],
    )
    sub_id = sub_payload["data"]["node_id"]
    _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--name",
            "Electronic Cooling Fan Controller",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--name",
            "Cooling Fan Motor Assembly",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    _agent_json(
        "A",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--name",
            "Coolant Temperature Sensing Path",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )

    # Agent A: illegal structure add.
    partial_revision_before = _canonical_revision(partial_db)
    comp_list_before = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )

    invalid_parent_result = cli_runner.invoke(
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--name",
            "Illegal Shared Component",
            "--parent",
            sys_id,
            "--format",
            "json",
        ]
    )
    invalid_parent_payload = parse_json_payload(invalid_parent_result)
    assert invalid_parent_payload["errors"][0]["code"] == "INVALID_PARENT"

    comp_list_after = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "list",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    assert _node_ids(comp_list_after) == _node_ids(comp_list_before)
    assert _canonical_revision(partial_db) == partial_revision_before

    # Agent C: legal recovery write in the same partial DB.
    legal_component = _agent_json(
        "C",
        cli_runner,
        [
            "structure",
            "add",
            "--db",
            str(partial_db),
            "--type",
            "COMP",
            "--name",
            "Shared Recovery Component",
            "--parent",
            sub_id,
            "--format",
            "json",
        ],
    )
    assert legal_component["data"]["parent_id"] == sub_id
    status_after_recovery = _agent_json(
        "A",
        cli_runner,
        ["projection", "status", "--db", str(partial_db), "--format", "json"],
    )
    assert status_after_recovery["data"]["projection_dirty"] is True

    # Shared full project: invalid trace must not pollute links.
    full_seed = seed_realistic_cooling_fan_project(cli_runner, tmp_path / "full")
    full_db = full_seed.db_path
    links_before = _fm_link_pairs(full_db)
    revision_before = _canonical_revision(full_db)

    invalid_trace_result = cli_runner.invoke(
        [
            "analysis",
            "link-trace",
            "--db",
            str(full_db),
            "--from",
            f"fc:{full_seed.fc_driver_output_stuck_rowid}",
            "--to-fm",
            full_seed.fm_low_speed_id,
            "--format",
            "json",
        ]
    )
    invalid_trace_payload = parse_json_payload(invalid_trace_result)
    assert invalid_trace_payload["errors"][0]["code"] == "INVALID_REFERENCE"
    assert _fm_link_pairs(full_db) == links_before
    assert _canonical_revision(full_db) == revision_before

    # Other agents can still read and finish cleanly.
    get_payload = _agent_json(
        "B",
        cli_runner,
        [
            "query",
            "get",
            "--db",
            str(full_db),
            "--node",
            full_seed.fm_missed_start_id,
            "--format",
            "json",
        ],
    )
    assert get_payload["data"]["node"]["id"] == full_seed.fm_missed_start_id

    rebuild_payload = _agent_json(
        "C",
        cli_runner,
        ["projection", "rebuild", "--db", str(full_db), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False

    clean_validate = _agent_json(
        "A",
        cli_runner,
        ["validate", "--db", str(full_db), "--format", "json"],
    )
    assert clean_validate["data"]["summary"] == {"errors": 0, "warnings": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py::test_multi_agent_session_isolates_failed_writes_from_other_agents -q`
Expected: FAIL until the Session C test is added.

- [ ] **Step 3: Write minimal implementation**

- Add the Session C test exactly as shown.
- Keep error assertions recovery-oriented: assert only the error code and the shared-state invariants that matter.
- Do not expand the test into a general transaction contract suite.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py::test_multi_agent_session_isolates_failed_writes_from_other_agents -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_realistic_multi_agent_sessions.py
git commit -m "test: add realistic multi-agent failure isolation coverage"
```

## Task 4: Run The Full Multi-Agent Verification Set

**Files:**
- Verify only; no new files required unless earlier tasks exposed a real runtime bug.

- [ ] **Step 1: Run the new multi-agent module only**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py -q`
Expected: PASS.

- [ ] **Step 2: Run all realistic modules together**

Run: `python -m pytest tests/test_realistic_dfmea_end_to_end.py tests/test_realistic_dfmea_regression_matrix.py tests/test_realistic_agent_session.py tests/test_realistic_multi_agent_sessions.py -q`
Expected: PASS.

- [ ] **Step 3: Run the closest supporting suites**

Run: `python -m pytest tests/test_projection_commands.py tests/test_query_commands.py tests/test_trace_commands.py tests/test_validate_and_export_commands.py tests/test_structure_commands.py tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py -q`
Expected: PASS.

- [ ] **Step 4: Run the full repository suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit any final cleanup only if needed**

```bash
git add tests/test_realistic_multi_agent_sessions.py
git commit -m "test: finalize realistic multi-agent wal coverage"
```

Only create this final commit if Tasks 1-3 left additional uncommitted cleanup. If there is nothing new after the earlier task commits, skip this step.

## Verification Notes

- `read_project_data(db_path)` is the authoritative source for `canonical_revision` and `projection_dirty` in the new tests.
- For pre-rebuild projection semantics, prefer asserting dirty/stale evidence via `projection status` or `validate` warnings, not assumptions about exact pre-rebuild summary counts.
- Use `query list/get/search` for immediate canonical visibility proof.
- Use `query summary/dossier/actions/by-severity` only after the test has explicitly acknowledged dirty/stale and then rebuilt projection.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-28-dfmea-multi-agent-wal-coverage-tests.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
