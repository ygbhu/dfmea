# DFMEA WAL Snapshot Semantics Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a focused WAL snapshot test module that proves old readers keep an old canonical snapshot, new readers see committed writes, open readers do not block CLI writers, and the project still returns to a clean CLI-validated state after rebuild.

**Architecture:** Add one small low-level test file, `tests/test_wal_snapshot_semantics.py`, that combines sqlite3 reader connections with real CLI writes. The sqlite layer is used only to observe canonical facts (`projects`, `nodes`, `fm_links` if needed), while the CLI remains responsible for creating projects, performing writes, rebuilding projection, and validating final consistency. This complements `tests/test_realistic_multi_agent_sessions.py`: that file proves CLI-level multi-agent workflows, while the new file proves the underlying WAL snapshot guarantee those workflows rely on.

**Tech Stack:** Python 3.11+, pytest, Typer `CliRunner`, stdlib `sqlite3`, existing `dfmea_cli` CLI commands, existing helper module `tests/helpers_realistic_dfmea.py`.

---

## File Structure

### Tests

- Create: `tests/test_wal_snapshot_semantics.py` - low-level WAL reader snapshot and reader/writer coexistence tests.
- Leave unchanged: `tests/helpers_realistic_dfmea.py` - reuse only existing helpers:
  - `invoke_json`
  - `read_project_data`
  - `seed_realistic_structure_only`
- Leave unchanged: `tests/test_realistic_multi_agent_sessions.py` - still owns CLI-first multi-agent session coverage.

### Runtime Package

- No runtime changes are planned.
- If a WAL snapshot test exposes a real defect, patch only the smallest affected runtime file after reproducing it with the failing test:
  - `src/dfmea_cli/db.py`
  - `src/dfmea_cli/services/analysis.py`
  - `src/dfmea_cli/services/structure.py`
  - `src/dfmea_cli/services/projections.py`
  - `src/dfmea_cli/services/validate.py`

### Design Reference

- Spec: `docs/superpowers/specs/2026-03-28-dfmea-wal-snapshot-semantics-design.md`

## Scope Guardrails

- WAL assertions must be based on sqlite3 direct reads of canonical data, not on CLI query outputs.
- CLI is used only for real writes, project creation, projection rebuild, and final validate.
- Do not add random sleeps or timing windows.
- Do not expand this module into a generic SQLite locking suite.
- Final success condition is: CLI `projection rebuild` succeeds and `validate` shows zero error-level issues.

## Local Helpers To Add In The New Test File

Add only these small file-local helpers inside `tests/test_wal_snapshot_semantics.py`:

```python
from pathlib import Path
import sqlite3

from helpers_realistic_dfmea import invoke_json, read_project_data, seed_realistic_structure_only


def _open_reader(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def _canonical_fn_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM nodes WHERE type = 'FN' ORDER BY rowid"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _canonical_req_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute("SELECT COUNT(*) FROM nodes WHERE type = 'REQ'").fetchone()[0]
    )


def _projection_dirty(db_path: Path) -> bool:
    return bool(read_project_data(db_path)["projection_dirty"])
```

These helpers are file-local on purpose; do not move them into the shared helper module.

## Task 1: Add Reader Snapshot Test

**Files:**
- Create: `tests/test_wal_snapshot_semantics.py`

- [ ] **Step 1: Write the failing test**

```python
def test_wal_reader_snapshot_keeps_old_reader_view_and_exposes_commit_to_new_reader(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_structure_only(cli_runner, tmp_path)
    db_path = seeded["db_path"]

    reader_a = _open_reader(db_path)
    try:
        reader_a.execute("BEGIN")
        baseline_fn_ids = _canonical_fn_ids(reader_a)
        assert baseline_fn_ids == []

        writer_payload = invoke_json(
            cli_runner,
            [
                "analysis",
                "add-function",
                "--db",
                str(db_path),
                "--comp",
                seeded["controller_comp_id"],
                "--name",
                "Control fan start and stop",
                "--description",
                "Command fan start and stop according to cooling demand",
                "--format",
                "json",
            ],
        )
        new_fn_id = writer_payload["data"]["fn_id"]

        # Old reader keeps the old canonical snapshot.
        assert _canonical_fn_ids(reader_a) == []

        reader_b = _open_reader(db_path)
        try:
            assert _canonical_fn_ids(reader_b) == [new_fn_id]
        finally:
            reader_b.close()

        reader_a.execute("COMMIT")
    finally:
        reader_a.close()

    assert _projection_dirty(db_path) is True

    rebuild_payload = invoke_json(
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"]["errors"] == 0
```

Create `tests/test_wal_snapshot_semantics.py` and add this first test function before moving to Step 2.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_wal_snapshot_semantics.py::test_wal_reader_snapshot_keeps_old_reader_view_and_exposes_commit_to_new_reader -q`
Expected:

- Preferred TDD path: FAIL because the local helper functions (`_open_reader`, `_canonical_fn_ids`, `_canonical_req_count`, `_projection_dirty`) are not implemented yet.
- Acceptable outcome: PASS if you wrote the local helpers at the same time as the test and the current implementation already satisfies WAL snapshot semantics. In that case, keep the new test and do not invent a runtime change.

- [ ] **Step 3: Write minimal implementation**

- Create `tests/test_wal_snapshot_semantics.py`.
- Add the local helper functions from the “Local Helpers” section.
- Add the snapshot test exactly as shown.
- Do not add product-code changes unless this test reveals an actual defect.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_wal_snapshot_semantics.py::test_wal_reader_snapshot_keeps_old_reader_view_and_exposes_commit_to_new_reader -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wal_snapshot_semantics.py
git commit -m "test: add wal reader snapshot coverage"
```

If this task exposed a real runtime defect and you fixed it, stage the touched runtime file(s) alongside `tests/test_wal_snapshot_semantics.py` before committing.

## Task 2: Add Reader/Writer Coexistence Test

**Files:**
- Modify: `tests/test_wal_snapshot_semantics.py`

- [ ] **Step 1: Write the failing test**

```python
def test_wal_reader_does_not_block_cli_writer_and_system_still_converges(
    cli_runner, tmp_path: Path
):
    seeded = seed_realistic_structure_only(cli_runner, tmp_path)
    db_path = seeded["db_path"]

    reader = _open_reader(db_path)
    try:
        reader.execute("BEGIN")
        baseline_req_count = _canonical_req_count(reader)
        assert baseline_req_count == 0

        writer_payload = invoke_json(
            cli_runner,
            [
                "analysis",
                "add-function",
                "--db",
                str(db_path),
                "--comp",
                seeded["controller_comp_id"],
                "--name",
                "Modulate fan speed",
                "--description",
                "Adjust commanded fan speed to meet heat rejection demand",
                "--format",
                "json",
            ],
        )
        fn_id = writer_payload["data"]["fn_id"]

        req_payload = invoke_json(
            cli_runner,
            [
                "analysis",
                "add-requirement",
                "--db",
                str(db_path),
                "--fn",
                fn_id,
                "--text",
                "Track requested fan speed across operating range",
                "--source",
                "CTRL-REQ-SPEED",
                "--format",
                "json",
            ],
        )
        assert req_payload["data"]["req_rowid"] > 0

        # Open reader still sees its old snapshot.
        assert _canonical_req_count(reader) == 0
        assert _projection_dirty(db_path) is True

        reader.execute("COMMIT")
    finally:
        reader.close()

    status_payload = invoke_json(
        cli_runner,
        ["projection", "status", "--db", str(db_path), "--format", "json"],
    )
    assert status_payload["data"]["projection_dirty"] is True

    rebuild_payload = invoke_json(
        cli_runner,
        ["projection", "rebuild", "--db", str(db_path), "--format", "json"],
    )
    assert rebuild_payload["data"]["projection_dirty"] is False

    summary_payload = invoke_json(
        cli_runner,
        [
            "query",
            "summary",
            "--db",
            str(db_path),
            "--comp",
            seeded["controller_comp_id"],
            "--format",
            "json",
        ],
    )
    assert summary_payload["data"]["counts"]["functions"] == 1
    assert summary_payload["data"]["counts"]["requirements"] == 1

    validate_payload = invoke_json(
        cli_runner,
        ["validate", "--db", str(db_path), "--format", "json"],
    )
    assert validate_payload["data"]["summary"]["errors"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_wal_snapshot_semantics.py::test_wal_reader_does_not_block_cli_writer_and_system_still_converges -q`
Expected: FAIL if the new coexistence assertion exposes a real WAL/CLI defect. PASS is also acceptable if the current implementation already satisfies the new test once it is added; in that case, keep the new test and do not invent a runtime change.

- [ ] **Step 3: Write minimal implementation**

- Add the second WAL test exactly as shown.
- Keep the reader open while both CLI writes happen.
- Do not add sleeps or timing-based assertions.
- Keep the post-reader closure phase CLI-only: `projection status` -> `projection rebuild` -> `query summary` -> `validate`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_wal_snapshot_semantics.py::test_wal_reader_does_not_block_cli_writer_and_system_still_converges -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wal_snapshot_semantics.py
git commit -m "test: add wal reader writer coexistence coverage"
```

If this task exposed a real runtime defect and you fixed it, stage the touched runtime file(s) alongside `tests/test_wal_snapshot_semantics.py` before committing.

## Task 3: Run The WAL Verification Set

**Files:**
- Verify only; no new files required unless an earlier task exposed a real runtime bug.

- [ ] **Step 1: Run the WAL module only**

Run: `python -m pytest tests/test_wal_snapshot_semantics.py -q`
Expected: PASS.

- [ ] **Step 2: Run the WAL module with multi-agent coverage**

Run: `python -m pytest tests/test_realistic_multi_agent_sessions.py tests/test_wal_snapshot_semantics.py -q`
Expected: PASS.

- [ ] **Step 3: Run the full realistic coverage stack**

Run: `python -m pytest tests/test_realistic_dfmea_end_to_end.py tests/test_realistic_dfmea_regression_matrix.py tests/test_realistic_agent_session.py tests/test_realistic_multi_agent_sessions.py tests/test_wal_snapshot_semantics.py -q`
Expected: PASS.

- [ ] **Step 4: Run the full repository suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit any final cleanup only if needed**

```bash
git add tests/test_wal_snapshot_semantics.py
git commit -m "test: finalize wal snapshot semantics coverage"
```

Only create this final commit if Tasks 1-2 left additional uncommitted cleanup. If there is nothing new after the earlier task commits, skip this step.

If Tasks 1-2 required a real runtime fix, stage the touched runtime files explicitly alongside `tests/test_wal_snapshot_semantics.py` before committing.

## Verification Notes

- Use sqlite3 direct reads only for canonical snapshot assertions.
- Keep CLI writes explicit so the tests still validate the real application path.
- If a test fails because writer commits are actually blocked by an open reader, verify `src/dfmea_cli/db.py` WAL and busy-timeout behavior before changing anything else.
- Final CLI `validate` only needs to prove zero error-level issues; do not over-bind warning counts unless the fixture proves they stay stable.

## Runtime Defect Contingency

If either WAL test fails after the test file and local helpers are present:

1. Record the exact failing assertion and command output.
2. Confirm the failure reflects a real WAL semantic problem, not a bad test setup.
3. Patch only the smallest relevant runtime file, most likely `src/dfmea_cli/db.py` or the specific write service involved.
4. Rerun the single failing WAL test first.
5. Then rerun `projection rebuild` / `validate` through the planned verification commands.

Do not change runtime code merely to force a red-green narrative if the newly added test already passes against the current implementation.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-28-dfmea-wal-snapshot-semantics-tests.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
