# DFMEA Projection-Driven Read Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a projection-driven read model layer that preserves canonical SQLite writes while moving summaries, risk views, action backlogs, and review export onto rebuildable derived views without breaking the current V1 JSON contract.

**Architecture:** Keep `projects + nodes + fm_links` as the only canonical source of truth, then add a rebuildable `derived_views` table plus project freshness metadata. Write services only bump canonical revision and mark projections dirty; read/export commands load fresh projections through a shared projection service while preserving existing JSON result shapes for current commands. Exact recursion and raw object inspection continue to read canonical data directly.

**Tech Stack:** Python 3.11+, Typer, stdlib `sqlite3`, pytest, existing `dfmea_cli` package, Markdown skill/docs.

---

## File Structure

### Runtime Package

- Modify: `src/dfmea_cli/schema.py` - add `derived_views` DDL and indexes.
- Modify: `src/dfmea_cli/services/projects.py` - seed projection metadata in `projects.data`.
- Modify: `src/dfmea_cli/services/projects.py` - allow upgraded DBs that include `derived_views` in init safety checks.
- Modify: `src/dfmea_cli/services/structure.py` - bump canonical revision and mark projections dirty after successful writes.
- Modify: `src/dfmea_cli/services/analysis.py` - bump canonical revision and mark projections dirty after successful writes.
- Create: `src/dfmea_cli/services/projections.py` - projection status, rebuild, load, freshness checks, JSON payload builders.
- Modify: `src/dfmea_cli/services/query.py` - move summary/risk/action reads to projections; add map/bundle/dossier loaders.
- Modify: `src/dfmea_cli/services/export_markdown.py` - render review export from projections and keep ledger compatibility mode.
- Modify: `src/dfmea_cli/services/validate.py` - add projection validation scope and issue kinds.
- Modify: `src/dfmea_cli/cli.py` - register projection command group.
- Create: `src/dfmea_cli/commands/projection.py` - `projection status` and `projection rebuild` bindings.
- Modify: `src/dfmea_cli/commands/query.py` - add `query map`, `query bundle`, `query dossier`; annotate projection meta.
- Modify: `src/dfmea_cli/commands/export_markdown.py` - expose export layout/mode and projection meta.

### Tests

- Create: `tests/test_projection_commands.py` - schema bootstrap, dirty tracking, projection status/rebuild behavior.
- Modify: `tests/test_init_command.py` - assert projection metadata exists after init.
- Modify: `tests/test_structure_commands.py` - assert writes mark projections dirty.
- Modify: `tests/test_analysis_function_commands.py` - assert function/REQ/CHAR writes mark projections dirty.
- Modify: `tests/test_analysis_failure_chain_create.py` - assert failure-chain writes mark projections dirty.
- Modify: `tests/test_query_commands.py` - projection-backed summary/by-ap/by-severity/actions and new map/bundle/dossier commands.
- Modify: `tests/test_validate_and_export_commands.py` - projection validation and review export layout.
- Modify: `tests/test_installed_cli.py` - help output and installed command behavior for `projection` group.
- Modify: `tests/test_bootstrap.py` - root help includes `projection`.
- Modify: `tests/test_analysis_failure_chain_update.py` - update commands mark projections dirty.
- Modify: `tests/test_analysis_links_and_delete.py` - link/unlink/delete commands mark projections dirty.

### Docs And Agent Adapters

- Modify: `docs/architecture/2026-03-16-dfmea-skill-architecture.md` - incorporate the projection layer as a formal architecture enhancement.
- Modify: `docs/superpowers/specs/2026-03-25-dfmea-projection-driven-read-model-design.md` - accepted design spec.
- Modify: `dfmea/SKILL.md` - route read-heavy tasks through projection-aware commands.
- Modify: `dfmea/skills/dfmea-query/SKILL.md` - describe `query map` / `bundle` / `dossier` / projection-backed summaries.
- Modify: `dfmea/skills/dfmea-maintenance/SKILL.md` - describe `projection status` / `projection rebuild` and projection-aware validation/export.

## Implementation Constraints

- Follow TDD strictly. Every feature starts with a failing test.
- Keep `projects + nodes + fm_links` as canonical truth; `derived_views` is always rebuildable.
- Never build or mutate partial projections inside a canonical write transaction.
- Preserve `query get`, `query list`, `query search`, `trace causes`, and `trace effects` as canonical reads.
- Add projection freshness metadata to success payload `meta` for projection-backed commands.
- Keep existing `data.count` / `data.nodes` output shapes for `query by-ap`, `query by-severity`, and `query actions`.
- Keep existing `query summary` output shape and enrich only through `meta.projection` in this phase.
- Keep `export markdown` default behavior compatible with the current single-file ledger export; add `--layout review` as an explicit new mode.
- Treat stale projections as warnings in validation, but treat corrupt or untraceable projections as errors.
- Preserve the installed `dfmea` command shape unless the plan explicitly adds a new subcommand.

## Task Ordering

1. Projection schema, metadata, and upgrade foundation
2. Shared projection service skeleton and CLI management commands
3. Dirty tracking on canonical writes
4. Projection-backed existing query commands without contract breakage
5. Projection-backed Markdown review export while keeping ledger default
6. Projection-aware validation
7. Second-phase dossier and bundle commands
8. Architecture and skill doc updates

## Scope Note

This plan is intentionally split into two implementation phases:

- Phase 1: upgrade path, projection infrastructure, projection-backed existing commands, validation, and review export mode
- Phase 2: new `query map` / `query bundle` / `query dossier` commands and broader dossier-oriented UX

Do not start Phase 2 until Phase 1 passes full regression tests.

### Task 1: Projection Schema, Init Metadata, And Upgrade Helpers

**Files:**
- Modify: `src/dfmea_cli/schema.py`
- Modify: `src/dfmea_cli/services/projects.py`
- Modify: `tests/test_init_command.py`
- Create: `tests/test_projection_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_init_bootstraps_derived_views_table(cli_runner, tmp_path):
    db_path = tmp_path / "projection.db"
    result = cli_runner.invoke([
        "init", "--db", str(db_path), "--project", "demo", "--name", "Demo", "--format", "json",
    ])

    assert result.exit_code == 0

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='derived_views'"
        ).fetchone()
        assert row == ("derived_views",)
    finally:
        conn.close()


def test_init_seeds_projection_metadata(cli_runner, tmp_path):
    db_path = tmp_path / "projection.db"
    result = cli_runner.invoke([
        "init", "--db", str(db_path), "--project", "demo", "--name", "Demo", "--format", "json",
    ])
    assert result.exit_code == 0

    import json, sqlite3
    conn = sqlite3.connect(db_path)
    try:
        raw = conn.execute("SELECT data FROM projects WHERE id = ?", ("demo",)).fetchone()[0]
    finally:
        conn.close()

    data = json.loads(raw)
    assert data["canonical_revision"] == 0
    assert data["projection_dirty"] is False
    assert data["last_projection_revision"] == 0


def test_projection_status_upgrades_legacy_db_before_reading(cli_runner, tmp_path):
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)")
        conn.execute("CREATE TABLE nodes (rowid INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, type TEXT NOT NULL, parent_id INTEGER NOT NULL DEFAULT 0, project_id TEXT NOT NULL, name TEXT, data TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL, updated TEXT NOT NULL)")
        conn.execute("CREATE TABLE fm_links (from_rowid INTEGER NOT NULL, to_fm_rowid INTEGER NOT NULL, PRIMARY KEY (from_rowid, to_fm_rowid))")
        conn.execute("INSERT INTO projects (id, name, data, created, updated) VALUES (?, ?, ?, ?, ?)", ("demo", "Demo", "{}", "2026-03-25T00:00:00+00:00", "2026-03-25T00:00:00+00:00"))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(["projection", "status", "--db", str(db_path), "--format", "json"])
    assert result.exit_code == 0, result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_init_command.py tests/test_projection_commands.py -q`
Expected: FAIL because `derived_views`, projection metadata, and legacy upgrade helpers are not implemented.

- [ ] **Step 3: Write the minimal implementation**

In `src/dfmea_cli/schema.py`, add the new table and index:

```python
"""
CREATE TABLE IF NOT EXISTS derived_views (
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind                TEXT NOT NULL,
  scope_ref           TEXT NOT NULL,
  canonical_revision  INTEGER NOT NULL,
  built_at            TEXT NOT NULL,
  data                TEXT NOT NULL,
  PRIMARY KEY (project_id, kind, scope_ref)
)
""",
"CREATE INDEX IF NOT EXISTS idx_derived_views_kind ON derived_views(project_id, kind)",
```

In `src/dfmea_cli/services/projects.py`, seed project metadata like:

```python
project_data = {
    "canonical_revision": 0,
    "projection_dirty": False,
    "projection_schema_version": "1.0",
    "last_projection_build_at": None,
    "last_projection_revision": 0,
}
```

Also add an upgrade helper in `src/dfmea_cli/services/projections.py` or a schema utility used by projection entrypoints:

```python
def ensure_projection_schema(conn: sqlite3.Connection, project_id: str) -> None:
    bootstrap_schema(conn)
    # backfill projects.data defaults if missing
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_init_command.py tests/test_projection_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/schema.py src/dfmea_cli/services/projects.py src/dfmea_cli/services/projections.py tests/test_init_command.py tests/test_projection_commands.py
git commit -m "feat: add projection schema bootstrap and legacy upgrade support"
```

### Task 2: Create Projection Service Skeleton And CLI Commands

**Files:**
- Create: `src/dfmea_cli/services/projections.py`
- Create: `src/dfmea_cli/commands/projection.py`
- Modify: `src/dfmea_cli/cli.py`
- Modify: `tests/test_projection_commands.py`
- Modify: `tests/test_installed_cli.py`
- Modify: `tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_projection_status_reports_dirty_state(cli_runner, seeded_projection_db):
    result = cli_runner.invoke([
        "projection", "status", "--db", str(seeded_projection_db), "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["projection_dirty"] is True


def test_root_help_lists_projection_group():
    from typer.testing import CliRunner
    from dfmea_cli.cli import app

    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "projection" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_projection_commands.py tests/test_installed_cli.py tests/test_bootstrap.py -q`
Expected: FAIL because the `projection` command group and service do not exist.

- [ ] **Step 3: Write the minimal implementation**

In `src/dfmea_cli/services/projections.py`, add:

```python
@dataclass(frozen=True, slots=True)
class ProjectionStatus:
    project_id: str
    canonical_revision: int
    last_projection_revision: int
    projection_dirty: bool
    last_projection_build_at: str | None


def get_projection_status(...): ...
def rebuild_projections(...): ...
def ensure_projection_schema(...): ...
```

In `src/dfmea_cli/commands/projection.py`, expose:

```python
projection_app = typer.Typer(help="Projection management commands.")

@projection_app.command("status")
def projection_status_command(...):
    ...

@projection_app.command("rebuild")
def projection_rebuild_command(...):
    ...
```

Register the group in `src/dfmea_cli/cli.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_projection_commands.py tests/test_installed_cli.py tests/test_bootstrap.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/projections.py src/dfmea_cli/commands/projection.py src/dfmea_cli/cli.py tests/test_projection_commands.py tests/test_installed_cli.py tests/test_bootstrap.py
git commit -m "feat: add projection status and rebuild commands"
```

### Task 3: Mark Projections Dirty After Canonical Writes

**Files:**
- Modify: `src/dfmea_cli/services/structure.py`
- Modify: `src/dfmea_cli/services/analysis.py`
- Modify: `tests/test_structure_commands.py`
- Modify: `tests/test_analysis_function_commands.py`
- Modify: `tests/test_analysis_failure_chain_create.py`
- Modify: `tests/test_analysis_failure_chain_update.py`
- Modify: `tests/test_analysis_links_and_delete.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_structure_write_bumps_revision_and_marks_projection_dirty(cli_runner, seeded_db):
    result = cli_runner.invoke([
        "structure", "add", "--db", str(seeded_db), "--type", "SYS", "--name", "Drive", "--format", "json",
    ])
    assert result.exit_code == 0

    import json, sqlite3
    conn = sqlite3.connect(seeded_db)
    try:
        raw = conn.execute("SELECT data FROM projects WHERE id = ?", ("demo",)).fetchone()[0]
    finally:
        conn.close()

    data = json.loads(raw)
    assert data["canonical_revision"] == 1
    assert data["projection_dirty"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_structure_commands.py tests/test_analysis_function_commands.py tests/test_analysis_failure_chain_create.py -q`
Expected: FAIL because write services do not update projection freshness metadata.

- [ ] **Step 3: Write the minimal implementation**

Add a shared helper inside `src/dfmea_cli/services/projections.py` or a small internal helper first:

```python
def mark_projection_dirty(conn: sqlite3.Connection, project_id: str) -> None:
    row = conn.execute("SELECT data FROM projects WHERE id = ?", (project_id,)).fetchone()
    payload = json.loads(row[0])
    payload["canonical_revision"] = int(payload.get("canonical_revision", 0)) + 1
    payload["projection_dirty"] = True
    conn.execute("UPDATE projects SET data = ?, updated = datetime('now') WHERE id = ?", (json.dumps(payload), project_id))
```

Call that helper at the end of every successful structure and analysis write transaction, including:

- structure add/update/move/delete
- analysis add/update/delete
- link/unlink operations
- action status updates

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_structure_commands.py tests/test_analysis_function_commands.py tests/test_analysis_failure_chain_create.py tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/structure.py src/dfmea_cli/services/analysis.py src/dfmea_cli/services/projections.py tests/test_structure_commands.py tests/test_analysis_function_commands.py tests/test_analysis_failure_chain_create.py tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py
git commit -m "feat: mark projections dirty after canonical writes"
```

### Task 4: Build Phase 1 Projections And Move Existing Queries Onto Them Without Breaking Contract

**Files:**
- Modify: `src/dfmea_cli/services/projections.py`
- Modify: `src/dfmea_cli/services/query.py`
- Modify: `tests/test_query_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_summary_reports_projection_meta_without_changing_data_shape(cli_runner, seeded_query_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_query_db), "--format", "json"])
    result = cli_runner.invoke([
        "query", "summary", "--db", str(seeded_query_db), "--comp", "COMP-001", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["component"]["id"] == "COMP-001"
    assert payload["meta"]["projection"]["kind"] == "component_bundle"


def test_query_by_ap_keeps_count_and_nodes_shape_while_using_projection(cli_runner, seeded_query_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_query_db), "--format", "json"])
    result = cli_runner.invoke([
        "query", "by-ap", "--db", str(seeded_query_db), "--ap", "High", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["count"] == 1
    assert payload["data"]["nodes"][0]["data"]["ap"] == "High"
    assert payload["meta"]["projection"]["kind"] == "risk_register"


def test_query_actions_keeps_count_and_nodes_shape_while_using_projection(cli_runner, seeded_query_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_query_db), "--format", "json"])
    result = cli_runner.invoke([
        "query", "actions", "--db", str(seeded_query_db), "--status", "planned", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["count"] == 1
    assert payload["data"]["nodes"][0]["data"]["status"] == "planned"
    assert payload["meta"]["projection"]["kind"] == "action_backlog"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_query_commands.py -q`
Expected: FAIL because the phase-1 projections (`component_bundle`, `risk_register`, `action_backlog`) are not built or consumed yet.

- [ ] **Step 3: Write the minimal implementation**

Refactor `src/dfmea_cli/services/projections.py` to build the phase-1 projections first, then refactor `src/dfmea_cli/services/query.py` to consume them while preserving existing data envelopes:

```python
def rebuild_projections(...):
    project_map = build_project_map(...)
    component_bundles = build_component_bundles(...)
    function_dossiers = build_function_dossiers(...)
    risk_register = build_risk_register(...)
    action_backlog = build_action_backlog(...)
    # persist all rows into derived_views
```

Important phase boundary:

- `project_map` and `function_dossier` are built in Phase 1 because `--layout review` export needs them
- `query map` / `query bundle` / `query dossier` commands are still deferred to Phase 2

Then update `src/dfmea_cli/services/query.py`:

```python
def query_summary(...):
    bundle = load_projection(..., kind="component_bundle", scope_ref=comp_ref)
    return QueryResult(..., data={
        "project_id": project_id,
        "component": bundle["component"],
        "counts": bundle["counts"],
        "functions": bundle["functions"],
    })
```

Keep `query by-ap`, `query by-severity`, and `query actions` returning `count + nodes`, but source those results from `risk_register` / `action_backlog` projections and append projection provenance to `meta`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_query_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/projections.py src/dfmea_cli/services/query.py tests/test_query_commands.py
git commit -m "feat: back existing summary and filter queries with projections"
```

### Task 5: Rebuild Markdown Export Around Review Projections While Keeping Ledger Default

**Files:**
- Modify: `src/dfmea_cli/services/export_markdown.py`
- Modify: `src/dfmea_cli/commands/export_markdown.py`
- Modify: `tests/test_validate_and_export_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_export_markdown_review_layout_creates_index_and_component_files(cli_runner, seeded_projection_db, tmp_path):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_projection_db), "--format", "json"])
    out_dir = tmp_path / "exports"
    result = cli_runner.invoke([
        "export", "markdown", "--db", str(seeded_projection_db), "--out", str(out_dir), "--layout", "review", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    paths = [Path(item["path"]) for item in payload["data"]["files"]]
    assert any(path.name == "index.md" for path in paths)
    assert any(path.parent.name == "components" for path in paths)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_and_export_commands.py -q`
Expected: FAIL because export is still a single ledger-style file and has no `--layout` option.

- [ ] **Step 3: Write the minimal implementation**

In `src/dfmea_cli/commands/export_markdown.py`, add a layout option:

```python
layout: str = typer.Option("ledger", "--layout")
```

In `src/dfmea_cli/services/export_markdown.py`, split rendering:

```python
def export_markdown(..., layout: str):
    if layout == "ledger":
        return _export_ledger(...)
    return _export_review_projection(...)
```

Use `project_map`, `component_bundle`, and `function_dossier` to write:

```python
<out>/<project_id>/index.md
<out>/<project_id>/components/<COMP-id>.md
<out>/<project_id>/functions/<FN-id>.md
<out>/<project_id>/actions/open.md
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_and_export_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/export_markdown.py src/dfmea_cli/commands/export_markdown.py tests/test_validate_and_export_commands.py
git commit -m "feat: add projection-driven markdown review export"
```

### Task 6: Add Projection Validation And Freshness Reporting

**Files:**
- Modify: `src/dfmea_cli/services/validate.py`
- Modify: `src/dfmea_cli/services/projections.py`
- Modify: `tests/test_validate_and_export_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_validate_reports_stale_projection_warning(cli_runner, seeded_projection_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_projection_db), "--format", "json"])
    cli_runner.invoke([
        "structure", "add", "--db", str(seeded_projection_db), "--type", "SYS", "--name", "Extra", "--format", "json"
    ])
    result = cli_runner.invoke(["validate", "--db", str(seeded_projection_db), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert any(issue["scope"] == "projection" and issue["kind"] == "STALE_PROJECTION" for issue in payload["data"]["issues"])


def test_validate_reports_projection_corruption_as_error(cli_runner, seeded_projection_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_projection_db), "--format", "json"])
    import sqlite3
    conn = sqlite3.connect(seeded_projection_db)
    try:
        conn.execute("UPDATE derived_views SET data = ?", ("{",))
        conn.commit()
    finally:
        conn.close()
    result = cli_runner.invoke(["validate", "--db", str(seeded_projection_db), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert any(issue["scope"] == "projection" and issue["kind"] == "PROJECTION_CORRUPT" for issue in payload["data"]["issues"])


def test_query_summary_upgrades_legacy_db_before_projection_read(cli_runner, tmp_path):
    import sqlite3

    db_path = tmp_path / "legacy-query.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)")
        conn.execute("CREATE TABLE nodes (rowid INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, type TEXT NOT NULL, parent_id INTEGER NOT NULL DEFAULT 0, project_id TEXT NOT NULL, name TEXT, data TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL, updated TEXT NOT NULL)")
        conn.execute("CREATE TABLE fm_links (from_rowid INTEGER NOT NULL, to_fm_rowid INTEGER NOT NULL, PRIMARY KEY (from_rowid, to_fm_rowid))")
        conn.execute("INSERT INTO projects (id, name, data, created, updated) VALUES (?, ?, ?, ?, ?)", ("demo", "Demo", "{}", "2026-03-25T00:00:00+00:00", "2026-03-25T00:00:00+00:00"))
        conn.execute("INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("SYS-001", "SYS", 0, "demo", "Drive", '{"description":"Drive"}', "2026-03-25T00:00:00+00:00", "2026-03-25T00:00:00+00:00"))
        conn.execute("INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("SUB-001", "SUB", 1, "demo", "Inverter", '{"description":"Inverter"}', "2026-03-25T00:00:00+00:00", "2026-03-25T00:00:00+00:00"))
        conn.execute("INSERT INTO nodes (id, type, parent_id, project_id, name, data, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("COMP-001", "COMP", 2, "demo", "Stator", '{"description":"Stator"}', "2026-03-25T00:00:00+00:00", "2026-03-25T00:00:00+00:00"))
        conn.commit()
    finally:
        conn.close()

    result = cli_runner.invoke(["query", "summary", "--db", str(db_path), "--comp", "COMP-001", "--format", "json"])
    assert result.exit_code == 0, result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_and_export_commands.py -q`
Expected: FAIL because validation does not inspect `derived_views` or projection freshness.

- [ ] **Step 3: Write the minimal implementation**

In `src/dfmea_cli/services/validate.py`, add:

```python
issues.extend(_validate_projection_state(conn, project_id=project_id, nodes=nodes, node_by_rowid=node_by_rowid))
```

Implement checks for:

```python
def _validate_projection_state(...):
    # stale revision warning
    # malformed projection JSON error
    # missing source id/rowid error
    # schema version mismatch error
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_and_export_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/validate.py src/dfmea_cli/services/projections.py tests/test_validate_and_export_commands.py
git commit -m "feat: validate projection freshness and traceability"
```

### Task 7: Phase 2 - Add Map, Bundle, And Dossier Commands

**Files:**
- Modify: `src/dfmea_cli/services/query.py`
- Modify: `src/dfmea_cli/commands/query.py`
- Modify: `tests/test_query_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_map_returns_project_navigation_view(cli_runner, seeded_query_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_query_db), "--format", "json"])
    result = cli_runner.invoke(["query", "map", "--db", str(seeded_query_db), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["project"]["id"] == "demo"


def test_query_dossier_returns_function_dossier(cli_runner, seeded_query_db):
    cli_runner.invoke(["projection", "rebuild", "--db", str(seeded_query_db), "--format", "json"])
    result = cli_runner.invoke([
        "query", "dossier", "--db", str(seeded_query_db), "--fn", "FN-001", "--format", "json"
    ])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["data"]["function"]["id"] == "FN-001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_query_commands.py -q`
Expected: FAIL because these new read-model commands do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Add `query map`, `query bundle`, and `query dossier` command/service bindings that read from `project_map`, `component_bundle`, and `function_dossier` projections.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_query_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dfmea_cli/services/query.py src/dfmea_cli/commands/query.py tests/test_query_commands.py
git commit -m "feat: add projection-native map bundle and dossier commands"
```

### Task 8: Update Architecture And Skill Routing Docs

**Files:**
- Modify: `docs/architecture/2026-03-16-dfmea-skill-architecture.md`
- Modify: `dfmea/SKILL.md`
- Modify: `dfmea/skills/dfmea-query/SKILL.md`
- Modify: `dfmea/skills/dfmea-maintenance/SKILL.md`
- Modify: `tests/test_installed_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_installed_cli_help_lists_projection_group(cli_runner):
    result = cli_runner.invoke(["--help"])
    assert result.exit_code == 0
    assert "projection" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails or coverage is missing**

Run: `python -m pytest tests/test_installed_cli.py tests/test_bootstrap.py -q`
Expected: FAIL if the command group is absent, or PASS only after runtime changes are complete; then verify the docs are still outdated.

- [ ] **Step 3: Update the docs**

Make the architecture doc reflect the new read-model layer:

```markdown
- Canonical Storage Layer remains the only source of truth.
- Projection Build Layer owns rebuildable derived views.
- Query/export commands prefer projection-backed reads.
```

Update agent adapter docs so they route:

```markdown
- broad navigation -> `dfmea query map`
- component review -> `dfmea query bundle`
- function deep review -> `dfmea query dossier`
- maintenance -> `dfmea projection status` / `dfmea projection rebuild`
```

- [ ] **Step 4: Run the final focused test sweep**

Run: `python -m pytest tests/test_projection_commands.py tests/test_query_commands.py tests/test_validate_and_export_commands.py tests/test_installed_cli.py tests/test_bootstrap.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/2026-03-16-dfmea-skill-architecture.md dfmea/SKILL.md dfmea/skills/dfmea-query/SKILL.md dfmea/skills/dfmea-maintenance/SKILL.md tests/test_installed_cli.py tests/test_bootstrap.py
git commit -m "docs: route dfmea reads through projection-aware workflows"
```

## Final Verification

- [ ] Run: `python -m pytest tests/test_projection_commands.py tests/test_query_commands.py tests/test_validate_and_export_commands.py tests/test_installed_cli.py -q`
- [ ] Run: `python -m pytest tests/test_bootstrap.py tests/test_analysis_failure_chain_update.py tests/test_analysis_links_and_delete.py -q`
- [ ] Run: `python -m pytest tests -q`
- [ ] Manually spot-check:
  - `dfmea projection status --db <db> --format json`
  - `dfmea projection rebuild --db <db> --format json`
  - `dfmea export markdown --db <db> --out <dir> --layout review --format json`

- [ ] Phase 2 spot-check after Phase 1 stabilizes:
  - `dfmea query map --db <db> --format json`
  - `dfmea query bundle --db <db> --comp <COMP-id> --format json`
  - `dfmea query dossier --db <db> --fn <FN-id> --format json`

## Notes For The Implementer

- Do not move trace recursion into projections in this iteration.
- Do not add FTS5 or semantic search in this iteration.
- If review export grows too quickly, prefer more files with narrower scope over one giant markdown file.
- If a projection command needs to auto-rebuild, include that fact in `meta.projection.status` so downstream agents know they consumed rebuilt data.
- If design drift appears during implementation, update `docs/superpowers/specs/2026-03-25-dfmea-projection-driven-read-model-design.md` before continuing.
