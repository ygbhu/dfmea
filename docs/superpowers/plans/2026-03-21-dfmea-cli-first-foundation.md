# DFMEA CLI-First Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the formal CLI-first DFMEA baseline and implement a tested local `dfmea` command that agents can use for standard writes, reads, validation, and export without writing SQL directly.

**Architecture:** Build a Python CLI with thin command modules, a shared service layer, and SQLite as the single source of truth. Lock the agent-facing contract at the CLI boundary through stable JSON envelopes, explicit exit-code rules, strict DB/project resolution, and centralized transaction, validation, and delete semantics.

**Tech Stack:** Python 3.11+, Typer, stdlib `sqlite3`, pytest, editable package install, Markdown skill files.

---

## File Structure

### Runtime Package

- `pyproject.toml` - package metadata, dependencies, test extras, console script entry point.
- `src/dfmea_cli/__init__.py` - package version and public export surface.
- `src/dfmea_cli/__main__.py` - `python -m dfmea_cli` entry.
- `src/dfmea_cli/cli.py` - root Typer app, root callback, command-group registration.
- `src/dfmea_cli/contracts.py` - stable success/failure/validation envelope helpers.
- `src/dfmea_cli/errors.py` - error codes, domain exceptions, exit-code mapping.
- `src/dfmea_cli/output.py` - JSON/text/markdown rendering.
- `src/dfmea_cli/db.py` - connection factory, WAL setup, busy timeout, retry wrapper.
- `src/dfmea_cli/schema.py` - DDL bootstrap and schema verification.
- `src/dfmea_cli/resolve.py` - project/db resolution and `id|rowid` resolution helpers.
- `src/dfmea_cli/services/projects.py` - project initialization logic.
- `src/dfmea_cli/services/structure.py` - SYS/SUB/COMP add, update, move, delete.
- `src/dfmea_cli/services/analysis.py` - FN/REQ/CHAR/FM/FE/FC/ACT CRUD and link logic.
- `src/dfmea_cli/services/query.py` - query get/list/search/summary/by-ap/by-severity/actions.
- `src/dfmea_cli/services/trace.py` - recursive cause/effect traversal.
- `src/dfmea_cli/services/validate.py` - schema/graph/integrity validation.
- `src/dfmea_cli/services/export_markdown.py` - Markdown export generation.
- `src/dfmea_cli/commands/init.py` - `dfmea init` bindings.
- `src/dfmea_cli/commands/structure.py` - `dfmea structure *` bindings.
- `src/dfmea_cli/commands/analysis.py` - `dfmea analysis *` bindings.
- `src/dfmea_cli/commands/query.py` - `dfmea query *` bindings.
- `src/dfmea_cli/commands/trace.py` - `dfmea trace *` bindings.
- `src/dfmea_cli/commands/validate.py` - `dfmea validate` binding.
- `src/dfmea_cli/commands/export_markdown.py` - `dfmea export markdown` binding.

### Test Package

- `tests/conftest.py` - temp DB helpers, CLI runner, seeded project fixtures.
- `tests/test_bootstrap.py` - package import, root CLI launch, editable install assumptions.
- `tests/test_contracts.py` - JSON envelope shape and exit-code semantics.
- `tests/test_global_options.py` - `--format`, `--quiet`, `--busy-timeout-ms`, `--retry`, DB/project mismatch.
- `tests/test_init_command.py` - DB creation, schema bootstrap, one-project-per-db invariant.
- `tests/test_structure_commands.py` - structure add/update/move/delete behavior.
- `tests/test_analysis_function_commands.py` - FN, REQ, CHAR CRUD.
- `tests/test_analysis_failure_chain_create.py` - FM/FE/FC/ACT chain creation and structured input.
- `tests/test_analysis_failure_chain_update.py` - update-fm/update-fe/update-fc/update-act.
- `tests/test_analysis_links_and_delete.py` - REQ/CHAR link/unlink, trace links, delete-node semantics.
- `tests/test_query_commands.py` - get/list/search/summary/by-ap/by-severity/actions.
- `tests/test_trace_commands.py` - recursive cause/effect traversal.
- `tests/test_validate_and_export_commands.py` - validate output, exit codes, Markdown export.
- `tests/test_installed_cli.py` - subprocess tests against the installed `dfmea` command.

### Agent Adapter Files

- `dfmea/SKILL.md` - main routing skill that instructs agents to call the CLI.
- `dfmea/node-schema.md` - CLI-era node model reference retained as supporting docs.
- `dfmea/storage-spec.md` - CLI-era storage and export notes retained as supporting docs.
- `dfmea/skills/dfmea-init/SKILL.md` - maps init tasks to `dfmea init`.
- `dfmea/skills/dfmea-structure/SKILL.md` - maps structure tasks to `dfmea structure *`.
- `dfmea/skills/dfmea-analysis/SKILL.md` - maps analysis tasks to `dfmea analysis *`.
- `dfmea/skills/dfmea-query/SKILL.md` - maps read tasks to `dfmea query *` and `dfmea trace *`.
- `dfmea/skills/dfmea-maintenance/SKILL.md` - maps maintenance tasks to `dfmea validate` and `dfmea export markdown`.

### Modified Formal Docs

- `docs/architecture/2026-03-16-dfmea-skill-architecture.md` - rewrite as the CLI-first formal baseline before runtime implementation progresses.

## Plan Constraints

- Follow TDD strictly: write failing test, run it, implement the minimum code, rerun tests.
- Every command-level test that targets agent consumption must parse JSON and assert `contract_version`, `ok`, `command`, and the relevant `data/errors` fields.
- Every write path must go through services and transaction helpers, never directly from command modules.
- Default command output should be JSON unless a human-facing format is explicitly requested.
- `--format json` is the only stable machine contract in V1.
- `validate` must return a full report in all cases; exit code reflects validity.
- If a task reveals missing design decisions, update the accepted spec before continuing.

## Phase Ordering

Implementation order is deliberate:

1. Environment bootstrap
2. Formal architecture baseline update
3. CLI contract foundation
4. DB bootstrap and `init`
5. Structure commands
6. Function/REQ/CHAR commands
7. Failure-chain create/update/link/delete
8. Query and trace
9. Validate and export
10. Skill adapters and installed-command verification

### Task 0: Environment And Packaging Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `src/dfmea_cli/__init__.py`
- Create: `src/dfmea_cli/__main__.py`
- Create: `tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
def test_package_version_is_importable():
    from dfmea_cli import __version__

    assert __version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bootstrap.py -q`
Expected: FAIL with import error because the package does not exist.

- [ ] **Step 3: Create the package skeleton and dependency metadata**

```toml
[project]
name = "dfmea-cli"
version = "0.1.0"
dependencies = ["typer>=0.12,<1"]

[project.scripts]
dfmea = "dfmea_cli.cli:main"
```

- [ ] **Step 4: Install dev dependencies and rerun the bootstrap test**

Run:

```bash
python -m pip install -e .[dev]
python -m pytest tests/test_bootstrap.py -q
```

Expected: PASS and editable install succeeds.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/dfmea_cli/__init__.py src/dfmea_cli/__main__.py tests/test_bootstrap.py
git commit -m "feat: bootstrap dfmea cli package"
```

### Task 1: Update The Formal Architecture Baseline First

**Files:**
- Modify: `docs/architecture/2026-03-16-dfmea-skill-architecture.md`

- [ ] **Step 1: Write the architecture acceptance checklist into the task notes**

```text
- CLI is the official portable write interface.
- Read-only SQL diagnostics remain allowed but non-portable.
- Skills are command routers, not SQL operators.
- Output contract is formalized around stable JSON.
```

- [ ] **Step 2: Rewrite the architecture baseline to match the accepted spec**

Update the architecture doc so it:

- adds CLI interface layer and domain service layer
- promotes `dfmea` as the official write contract
- rewrites operation semantics around CLI contracts
- reframes query architecture as CLI capability backed by SQL
- redefines skills as CLI adapters

- [ ] **Step 3: Read the updated architecture doc and accepted spec side by side**

Read:

- `docs/architecture/2026-03-16-dfmea-skill-architecture.md`
- `docs/superpowers/specs/2026-03-21-dfmea-cli-first-architecture-design.md`

Expected: no contradiction on CLI boundary, SQL boundary, or skill responsibility.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/2026-03-16-dfmea-skill-architecture.md
git commit -m "docs: adopt cli-first dfmea architecture baseline"
```

### Task 2: Root CLI And Empty Command Groups

**Files:**
- Create: `src/dfmea_cli/cli.py`
- Test: `tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing root-help test**

```python
from typer.testing import CliRunner

from dfmea_cli.cli import app


def test_root_help_lists_major_command_groups():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ["init", "structure", "analysis", "query", "trace", "validate", "export"]:
        assert name in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bootstrap.py::test_root_help_lists_major_command_groups -q`
Expected: FAIL because the root app and command groups are not registered.

- [ ] **Step 3: Implement the root Typer app with empty registered groups**

```python
app = typer.Typer(no_args_is_help=True)
structure_app = typer.Typer()
analysis_app = typer.Typer()
query_app = typer.Typer()
trace_app = typer.Typer()
export_app = typer.Typer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bootstrap.py::test_root_help_lists_major_command_groups -q`
Expected: PASS with all top-level groups visible.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/cli.py tests/test_bootstrap.py
git commit -m "feat: add root dfmea cli and command groups"
```

### Task 3: CLI Contract Foundation And Global Options

**Files:**
- Create: `src/dfmea_cli/contracts.py`
- Create: `src/dfmea_cli/errors.py`
- Create: `src/dfmea_cli/output.py`
- Create: `src/dfmea_cli/resolve.py`
- Test: `tests/test_contracts.py`
- Test: `tests/test_global_options.py`

- [ ] **Step 1: Write the failing contract and global-option tests**

```python
def test_success_result_has_stable_shape():
    payload = success_result(command="init", data={"project_id": "demo"})
    assert payload["contract_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_default_output_format_is_json(cli_runner, seeded_db):
    result = cli_runner.invoke(["validate", "--db", seeded_db])
    payload = json.loads(result.stdout)
    assert payload["contract_version"] == "1.0"


def test_project_db_mismatch_error_is_structured(cli_runner, mismatched_db):
    result = cli_runner.invoke(["validate", "--db", mismatched_db, "--project", "wrong", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["errors"][0]["code"] == "PROJECT_DB_MISMATCH"


def test_db_only_auto_resolves_single_project(cli_runner, seeded_db):
    result = cli_runner.invoke(["validate", "--db", seeded_db, "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["meta"]["project_id"] == "demo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contracts.py tests/test_global_options.py -q`
Expected: FAIL because contract helpers and global resolution do not exist.

- [ ] **Step 3: Implement JSON envelopes, error codes, renderers, and global resolution helpers**

```python
CONTRACT_VERSION = "1.0"

class CliError(Exception):
    code = "UNKNOWN"

def render_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
```

- [ ] **Step 4: Add explicit tests for `--quiet`, `--format`, and target structure**

Run: `python -m pytest tests/test_contracts.py tests/test_global_options.py -q`
Expected: PASS for success/failure envelopes, default JSON output, `PROJECT_DB_MISMATCH`, DB-only project auto-resolution, `json` output, and quiet-mode behavior.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/contracts.py src/dfmea_cli/errors.py src/dfmea_cli/output.py src/dfmea_cli/resolve.py tests/test_contracts.py tests/test_global_options.py
git commit -m "feat: add cli contract foundation"
```

### Task 4: SQLite Connection, Busy Handling, Schema Bootstrap, And `init`

**Files:**
- Create: `src/dfmea_cli/db.py`
- Create: `src/dfmea_cli/schema.py`
- Create: `src/dfmea_cli/services/projects.py`
- Create: `src/dfmea_cli/commands/init.py`
- Modify: `src/dfmea_cli/cli.py`
- Create: `tests/conftest.py`
- Test: `tests/test_init_command.py`
- Test: `tests/test_global_options.py`

- [ ] **Step 1: Write the failing init and busy-setting tests**

```python
def test_init_creates_single_project_db(cli_runner, tmp_path):
    db_path = tmp_path / "demo.db"
    result = cli_runner.invoke(["init", "--db", str(db_path), "--project", "demo", "--name", "Demo", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert db_path.exists()


def test_busy_timeout_option_is_accepted(cli_runner, tmp_path):
    db_path = tmp_path / "timeout.db"
    result = cli_runner.invoke(["init", "--db", str(db_path), "--project", "demo", "--name", "Demo", "--busy-timeout-ms", "7000"])
    assert result.exit_code == 0


def test_retry_exhaustion_returns_db_busy_json(cli_runner, tmp_path, monkeypatch):
    db_path = tmp_path / "busy.db"

    def always_busy(*args, **kwargs):
        raise RetryableBusyError()

    monkeypatch.setattr("dfmea_cli.db.execute_with_retry", always_busy)
    result = cli_runner.invoke([
        "init", "--db", str(db_path), "--project", "demo", "--name", "Demo", "--retry", "2", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["errors"][0]["code"] == "DB_BUSY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_init_command.py tests/test_global_options.py -q`
Expected: FAIL because DB bootstrap and init command are not implemented.

- [ ] **Step 3: Implement connection helper, WAL schema bootstrap, and init command**

```python
def connect(db_path: Path, *, busy_timeout_ms: int) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")
    return conn

def execute_with_retry(fn, *, retry: int):
    for attempt in range(retry + 1):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == retry:
                raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_init_command.py tests/test_global_options.py -q`
Expected: PASS and DB contains exactly one project record, while retry exhaustion returns stable `DB_BUSY` JSON.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/db.py src/dfmea_cli/schema.py src/dfmea_cli/services/projects.py src/dfmea_cli/commands/init.py src/dfmea_cli/cli.py tests/conftest.py tests/test_init_command.py tests/test_global_options.py
git commit -m "feat: add sqlite bootstrap and init command"
```

### Task 5: Structure Commands

**Files:**
- Create: `src/dfmea_cli/services/structure.py`
- Create: `src/dfmea_cli/commands/structure.py`
- Modify: `src/dfmea_cli/cli.py`
- Test: `tests/test_structure_commands.py`

- [ ] **Step 1: Write failing tests for add/update/move/delete**

```python
def test_add_sys_sub_comp_chain_returns_json(cli_runner, initialized_db):
    result = cli_runner.invoke(["structure", "add", "--db", initialized_db, "--type", "SYS", "--name", "Drive", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["command"] == "structure add"


def test_delete_non_empty_component_returns_node_not_empty(cli_runner, populated_structure_db):
    result = cli_runner.invoke(["structure", "delete", "--db", populated_structure_db, "--node", "COMP-001", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["errors"][0]["code"] == "NODE_NOT_EMPTY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structure_commands.py -q`
Expected: FAIL because structure service methods and command bindings do not exist.

- [ ] **Step 3: Implement structure service methods and command bindings**

```python
def move_structure_node(conn, node_ref, parent_ref):
    # resolve node and parent
    # validate legal hierarchy
    # update parent_id in a transaction
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_structure_commands.py -q`
Expected: PASS with JSON envelopes asserted for both success and failure.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/structure.py src/dfmea_cli/commands/structure.py src/dfmea_cli/cli.py tests/test_structure_commands.py
git commit -m "feat: implement structure commands"
```

### Task 6: Function, Requirement, And Characteristic Commands

**Files:**
- Create: `src/dfmea_cli/services/analysis.py`
- Create: `src/dfmea_cli/commands/analysis.py`
- Modify: `src/dfmea_cli/cli.py`
- Test: `tests/test_analysis_function_commands.py`

- [ ] **Step 1: Write failing FN/REQ/CHAR CRUD tests**

```python
def test_add_function_returns_fn_identity(cli_runner, component_db):
    result = cli_runner.invoke([
        "analysis", "add-function", "--db", component_db,
        "--comp", "COMP-001", "--name", "Deliver torque", "--description", "Provide rated torque", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["affected_objects"][0]["type"] == "FN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analysis_function_commands.py -q`
Expected: FAIL because analysis function commands are not implemented.

- [ ] **Step 3: Implement FN/REQ/CHAR CRUD**

```python
def add_requirement(conn, fn_ref, text, source=None):
    # insert REQ row under FN
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_analysis_function_commands.py -q`
Expected: PASS with JSON identity assertions for FN, REQ, and CHAR objects.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/analysis.py src/dfmea_cli/commands/analysis.py src/dfmea_cli/cli.py tests/test_analysis_function_commands.py
git commit -m "feat: implement function requirement and characteristic commands"
```

### Task 7: Failure-Chain Creation And Structured Input

**Files:**
- Modify: `src/dfmea_cli/services/analysis.py`
- Modify: `src/dfmea_cli/commands/analysis.py`
- Test: `tests/test_analysis_failure_chain_create.py`

- [ ] **Step 1: Write failing create tests for repeated flags and `--input`**

```python
def test_add_failure_chain_creates_fm_and_children(cli_runner, function_db):
    result = cli_runner.invoke([
        "analysis", "add-failure-chain", "--db", function_db,
        "--fn", "FN-001", "--fm-description", "Torque low", "--severity", "7",
        "--fc-description", "Winding short", "--occurrence", "4", "--detection", "3", "--ap", "High",
        "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert any(obj["type"] == "FM" for obj in payload["data"]["affected_objects"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analysis_failure_chain_create.py -q`
Expected: FAIL because failure-chain creation is not implemented.

- [ ] **Step 3: Implement failure-chain creation and documented structured-input mode**

```python
def add_failure_chain(conn, fn_ref, chain_spec: dict):
    # create FM, FE, FC, ACT rows in one transaction
    # validate target_causes and REQ/CHAR references
```

- [ ] **Step 4: Document repeated-flag grouping rules in command help**

Add help text in `src/dfmea_cli/commands/analysis.py` that explicitly states:

- repeated FE flags pair by occurrence order
- repeated FC flags pair by occurrence order
- repeated ACT flags pair by occurrence order
- `--input <json-file>` is the preferred mode for complex chains

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_analysis_failure_chain_create.py -q`
Expected: PASS for repeated flags and `--input <json-file>` modes.

- [ ] **Step 6: Commit**

```bash
git add src/dfmea_cli/services/analysis.py src/dfmea_cli/commands/analysis.py tests/test_analysis_failure_chain_create.py
git commit -m "feat: implement failure chain creation"
```

### Task 8: Failure-Chain Updates, Links, And Delete Semantics

**Files:**
- Modify: `src/dfmea_cli/services/analysis.py`
- Modify: `src/dfmea_cli/commands/analysis.py`
- Test: `tests/test_analysis_failure_chain_update.py`
- Test: `tests/test_analysis_links_and_delete.py`

- [ ] **Step 1: Write failing tests for typed updates, link/unlink, `update-action-status`, and `delete-node`**

```python
def test_update_action_status_returns_completed(cli_runner, chain_db):
    result = cli_runner.invoke(["analysis", "update-action-status", "--db", chain_db, "--act", "ACT-001", "--status", "completed", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["ok"] is True


def test_delete_fc_cleans_target_causes(cli_runner, chain_db):
    result = cli_runner.invoke(["analysis", "delete-node", "--db", chain_db, "--node", "12", "--format", "json"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py -q`
Expected: FAIL because update/link/delete semantics are not implemented.

- [ ] **Step 3: Implement typed update commands, REQ/CHAR links, trace links, and delete cleanup**

```python
def delete_analysis_node(conn, node_ref):
    # if FC: clean ACT.target_causes and delete empty ACTs
    # otherwise enforce allowed analysis node deletion semantics
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py -q`
Expected: PASS for updates, links, `update-action-status`, and FC cleanup semantics.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/analysis.py src/dfmea_cli/commands/analysis.py tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py
git commit -m "feat: implement failure chain updates and delete semantics"
```

### Task 9: Query Commands

**Files:**
- Create: `src/dfmea_cli/services/query.py`
- Create: `src/dfmea_cli/commands/query.py`
- Modify: `src/dfmea_cli/cli.py`
- Test: `tests/test_query_commands.py`

- [ ] **Step 1: Write failing tests for `get`, `list`, `search`, `summary`, `by-ap`, `by-severity`, and `actions`**

```python
def test_query_get_returns_structured_node(cli_runner, populated_analysis_db):
    result = cli_runner.invoke(["query", "get", "--db", populated_analysis_db, "--node", "FM-001", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["node"]["type"] == "FM"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_query_commands.py -q`
Expected: FAIL because query services and commands do not exist.

- [ ] **Step 3: Implement the query service and bindings**

```python
def query_actions(conn, status: str):
    return conn.execute(...).fetchall()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_query_commands.py -q`
Expected: PASS with JSON assertions for every command variant.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/query.py src/dfmea_cli/commands/query.py src/dfmea_cli/cli.py tests/test_query_commands.py
git commit -m "feat: implement query commands"
```

### Task 10: Recursive Trace Commands

**Files:**
- Create: `src/dfmea_cli/services/trace.py`
- Create: `src/dfmea_cli/commands/trace.py`
- Modify: `src/dfmea_cli/cli.py`
- Test: `tests/test_trace_commands.py`

- [ ] **Step 1: Write failing recursive trace tests**

```python
def test_trace_causes_returns_depth_annotated_chain(cli_runner, linked_trace_db):
    result = cli_runner.invoke(["trace", "causes", "--db", linked_trace_db, "--fm", "FM-001", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["chain"][0]["depth"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trace_commands.py -q`
Expected: FAIL because recursive trace commands are not implemented.

- [ ] **Step 3: Implement `WITH RECURSIVE` trace traversal**

```sql
WITH RECURSIVE cause_chain AS (
  SELECT rowid, id, type, data, 0 AS depth FROM nodes WHERE rowid = ?
  UNION ALL
  ...
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trace_commands.py -q`
Expected: PASS for both `causes` and `effects` chains.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/trace.py src/dfmea_cli/commands/trace.py src/dfmea_cli/cli.py tests/test_trace_commands.py
git commit -m "feat: implement recursive trace commands"
```

### Task 11: Validation And Export

**Files:**
- Create: `src/dfmea_cli/services/validate.py`
- Create: `src/dfmea_cli/services/export_markdown.py`
- Create: `src/dfmea_cli/commands/validate.py`
- Create: `src/dfmea_cli/commands/export_markdown.py`
- Modify: `src/dfmea_cli/cli.py`
- Test: `tests/test_validate_and_export_commands.py`

- [ ] **Step 1: Write failing validation/export tests**

```python
def test_validate_returns_non_zero_and_report_on_error_issue(cli_runner, invalid_db):
    result = cli_runner.invoke(["validate", "--db", invalid_db, "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_FAILED"


def test_export_markdown_creates_files_with_traceable_ids(cli_runner, populated_analysis_db, tmp_path):
    out_dir = tmp_path / "exports"
    result = cli_runner.invoke(["export", "markdown", "--db", populated_analysis_db, "--out", str(out_dir), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert any(out_dir.iterdir())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validate_and_export_commands.py -q`
Expected: FAIL because validate and export commands do not exist.

- [ ] **Step 3: Implement validation categories, exit-code logic, and export generation**

```python
def run_validation(...):
    issues = ...
    has_error = any(issue["level"] == "error" for issue in issues)
    return has_error, issues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validate_and_export_commands.py -q`
Expected: PASS and exported Markdown includes IDs or rowids for source mapping.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/validate.py src/dfmea_cli/services/export_markdown.py src/dfmea_cli/commands/validate.py src/dfmea_cli/commands/export_markdown.py src/dfmea_cli/cli.py tests/test_validate_and_export_commands.py
git commit -m "feat: implement validation and markdown export"
```

### Task 12: Skill Adapters, Supporting Docs, And Installed CLI Verification

**Files:**
- Create: `dfmea/SKILL.md`
- Create: `dfmea/node-schema.md`
- Create: `dfmea/storage-spec.md`
- Create: `dfmea/skills/dfmea-init/SKILL.md`
- Create: `dfmea/skills/dfmea-structure/SKILL.md`
- Create: `dfmea/skills/dfmea-analysis/SKILL.md`
- Create: `dfmea/skills/dfmea-query/SKILL.md`
- Create: `dfmea/skills/dfmea-maintenance/SKILL.md`
- Test: `tests/test_installed_cli.py`
- Modify: `tests/test_bootstrap.py`

- [ ] **Step 1: Write failing installed-command subprocess tests**

```python
def test_installed_dfmea_help_lists_command_tree():
    result = subprocess.run(["dfmea", "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "structure" in result.stdout
```

- [ ] **Step 2: Refresh editable install before subprocess verification**

Run: `python -m pip install -e .`
Expected: the local `dfmea` console script points to the current package state.

- [ ] **Step 3: Write the skill files and supporting docs as CLI adapters**

```markdown
Use `dfmea structure add` for structure creation.
Do not write SQLite directly.
Do not modify exported Markdown as source data.
```

- [ ] **Step 4: Run installed-command tests**

Run:

```bash
python -m pytest tests/test_installed_cli.py -q
```

Expected: PASS and installed `dfmea` matches package behavior.

- [ ] **Step 5: Commit**

```bash
git add dfmea/SKILL.md dfmea/node-schema.md dfmea/storage-spec.md dfmea/skills/dfmea-init/SKILL.md dfmea/skills/dfmea-structure/SKILL.md dfmea/skills/dfmea-analysis/SKILL.md dfmea/skills/dfmea-query/SKILL.md dfmea/skills/dfmea-maintenance/SKILL.md tests/test_installed_cli.py tests/test_bootstrap.py
git commit -m "feat: add dfmea skill adapters and installed cli checks"
```

### Task 13: Full Verification Pass

**Files:**
- Modify as needed based on verification findings.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests -q`
Expected: PASS across all unit and subprocess CLI tests.

- [ ] **Step 2: Run manual command verification**

Run:

```bash
python -m dfmea_cli --help
dfmea --help
```

Expected: both commands show the same top-level command tree.

- [ ] **Step 3: Run a minimal end-to-end smoke flow**

Run:

```bash
dfmea init --db smoke.db --project smoke --name Smoke --format json
dfmea structure add --db smoke.db --type SYS --name Drive --format json
dfmea validate --db smoke.db --format json
```

Expected: commands return valid JSON envelopes and `validate` exits zero for the healthy DB.

- [ ] **Step 4: Review formal docs and skill files one last time**

Inspect:

- `docs/architecture/2026-03-16-dfmea-skill-architecture.md`
- `dfmea/SKILL.md`
- `docs/superpowers/specs/2026-03-21-dfmea-cli-first-architecture-design.md`

Expected: no contradiction on CLI boundary, SQL diagnostics, or output contract.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: verify dfmea cli-first foundation"
```

## Final Verification Checklist

- [ ] `python -m pip install -e .[dev]` works.
- [ ] `dfmea --help` shows the full command tree.
- [ ] Global options `--format`, `--quiet`, `--busy-timeout-ms`, and `--retry` are implemented and tested.
- [ ] `PROJECT_DB_MISMATCH` and `DB_BUSY` are represented by stable JSON failures.
- [ ] `dfmea init` creates a one-project SQLite DB with WAL enabled.
- [ ] Structure, analysis, query, trace, validate, and export commands all return stable JSON envelopes.
- [ ] `validate` returns full issue reports and non-zero exit code on error-level issues.
- [ ] `analysis update-action-status`, `analysis delete-node`, `query get`, `query list`, REQ/CHAR link/unlink, and `--input <json-file>` for failure-chain creation are covered by tests.
- [ ] Skill files route standard writes through `dfmea` commands instead of direct SQL.
- [ ] `docs/architecture/2026-03-16-dfmea-skill-architecture.md` matches the accepted CLI-first spec.

## Notes For The Implementer

- Keep command modules thin; they should mostly parse options, call services, and render outputs.
- Do not expose public generic patch commands in V1.
- Treat read-only SQL access as a diagnostic capability, not the product interface.
- If a command becomes too awkward with repeated flags, prefer documented structured input over implicit positional coupling.
