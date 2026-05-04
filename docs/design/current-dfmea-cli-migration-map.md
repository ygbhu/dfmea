# Current DFMEA CLI Migration Map

> Status: implementation mapping baseline
>
> Source baseline: current Python `dfmea-cli` project in `src/dfmea_cli/`
>
> Target design: `docs/design/local-first-quality-assistant-detailed-design.md`
>
> Purpose: map the existing historical DFMEA CLI implementation to the new local-first, Git-native, project-scoped architecture.

## 1. Migration Positioning

The current project is the implementation baseline.

We keep:

- Python package and Typer CLI direction.
- `dfmea` command UX where it still matches the product.
- Agent skill-based operation model.
- validation, query, trace, projection, and Markdown export concepts.
- much of the DFMEA business logic and command vocabulary.

We replace:

- SQLite as source of truth.
- rowid-based internal references.
- single-database, single-project assumptions.
- `--db`, `--project-id`, busy timeout, retry, WAL, and SQLite-specific error handling.
- `projects/nodes/fm_links/derived_views` database tables.

We add:

- `quality` shared CLI namespace.
- project directory workspace model.
- project-local `.quality/schemas`, `.quality/tombstones`, `.quality/locks`.
- file-backed resource store.
- project-scoped short IDs such as `FM-001`.
- Git snapshot/history/diff/restore.
- plugin contract for DFMEA, PFMEA, and future quality domains.

## 2. Current Code Inventory

Current code:

```text
src/dfmea_cli/
  __main__.py
  cli.py
  db.py
  schema.py
  resolve.py
  contracts.py
  output.py
  errors.py
  commands/
    init.py
    structure.py
    analysis.py
    query.py
    trace.py
    validate.py
    projection.py
    export_markdown.py
  services/
    projects.py
    structure.py
    analysis.py
    query.py
    trace.py
    validate.py
    projections.py
    export_markdown.py
dfmea/
  SKILL.md
  skills/
  node-schema.md
  failure-chain-schema.md
  storage-spec.md
```

Historical package facts:

- original `pyproject.toml` package name: `dfmea-cli`.
- console entrypoint: `dfmea = "dfmea_cli.__main__:main"`.
- dependency baseline: `typer`.
- dev tools: `pytest`, `ruff`.
- storage baseline: SQLite via `src/dfmea_cli/db.py`.

## 3. Target Package Direction

V1 should evolve without throwing away the working Python CLI shell.

Technology direction:

- keep Python as the V1 implementation language.
- keep Typer unless it blocks the new CLI contract.
- rename the distribution package to `quality-assistant`.
- add a `quality` console script alongside the existing `dfmea` console script.
- introduce new packages for shared core and plugins instead of placing all new code under `dfmea_cli`.
- avoid a Go/Rust/Node rewrite during V1 migration.

Recommended package shape:

```text
plugin/
  package.json
  plugin.js
  bin/opencode-quality.js
engine/
  src/
    dfmea_cli/
      __main__.py
      cli.py
      commands/       # compatibility wrappers
    quality_adapters/
      cli/
        quality.py
        dfmea.py
        dfmea_commands/
      opencode/       # OpenCode templates and installer
    quality_core/
      cli/
      workspace/
      resources/
      plugins/
      validation/
      graph/
      projections/
      git/
      exports/
    quality_methods/
      dfmea/
      pfmea/          # placeholder only
```

Migration rule:

- keep `dfmea_cli` as compatibility namespace for historical DFMEA imports.
- use `quality_adapters.cli` as the active console-script adapter and command wiring layer.
- add `quality_core` for shared project/workspace/storage/Git behavior.
- add `quality_methods.dfmea` for the DFMEA quality method.
- keep `quality_methods.pfmea` as a placeholder until PFMEA is explicitly implemented.
- add `quality` console entrypoint when shared CLI is implemented.

Target entrypoints:

```toml
[project.scripts]
dfmea = "quality_adapters.cli.dfmea:main"
quality = "quality_adapters.cli.quality:main"
```

## 4. Module Mapping

| Current module | Current role | Target action | Target module |
| --- | --- | --- | --- |
| `dfmea_cli/__main__.py` | CLI entrypoint | Keep as compatibility entrypoint | `quality_adapters.cli.dfmea` |
| `dfmea_cli/cli.py` | Typer root for `dfmea` | Keep as compatibility wrapper | `quality_adapters.cli.dfmea` |
| `dfmea_cli/db.py` | SQLite connection, WAL, busy retry | Replace | `quality_core.resources.store`, `quality_core.resources.locks`, `quality_core.resources.atomic` |
| `dfmea_cli/schema.py` | SQLite DDL | Replace with JSON Schema/plugin descriptors | `quality_methods.dfmea.schemas`, `quality_core.validation.json_schema` |
| `dfmea_cli/resolve.py` | Resolve DB/project/node refs | Replace with workspace/project/resource resolution | `quality_core.workspace.discovery`, `quality_core.workspace.project`, `quality_core.resources.paths` |
| `dfmea_cli/contracts.py` | JSON result helpers | Keep concept, change contract fields to `quality.ai/v1` and camelCase | `quality_core.cli.output` |
| `dfmea_cli/output.py` | JSON/text/markdown rendering | Keep and adapt meta fields away from `project_id` | `quality_core.cli.output` |
| `dfmea_cli/errors.py` | CLI exceptions and exit mapping | Keep pattern, replace codes | `quality_core.cli.errors` |
| `commands/init.py` | Create SQLite DB/project | Rewrite to create workspace/project/DFMEA files | `quality_adapters.cli.dfmea_commands.init` |
| `commands/structure.py` | Typer structure commands | Keep UX; swap service backend | `quality_adapters.cli.dfmea_commands.structure` |
| `commands/analysis.py` | Typer DFMEA analysis commands | Keep most UX; swap service backend and IDs | `quality_adapters.cli.dfmea_commands.analysis` |
| `commands/query.py` | Query commands | Keep; route through file graph/projections | `quality_adapters.cli.dfmea_commands.query` |
| `commands/trace.py` | Trace commands | Keep; route through graph links | `quality_adapters.cli.dfmea_commands.trace` |
| `commands/validate.py` | Validation command | Keep UX; call new validation engine | `quality_adapters.cli.dfmea_commands.validate` |
| `commands/projection.py` | Projection status/rebuild | Keep; change manifest/freshness model | `quality_adapters.cli.dfmea_commands.projection` |
| `commands/export_markdown.py` | Markdown export command | Keep; consume file graph/projections | `quality_adapters.cli.dfmea_commands.export_markdown` |
| `services/projects.py` | Initialize DB and project row | Rewrite | `quality_core.workspace.project` |
| `services/structure.py` | Structure mutation logic | Preserve business rules; replace SQL CRUD | `quality_methods.dfmea.structure_service` |
| `services/analysis.py` | DFMEA mutation logic | Preserve business rules; replace SQL CRUD/link storage | `quality_methods.dfmea.analysis_service` |
| `services/query.py` | Read/query logic | Preserve query semantics; replace SQL reads with graph/projection reads | `quality_methods.dfmea.query_service` |
| `services/trace.py` | Cause/effect tracing | Preserve semantics; use graph index | `quality_methods.dfmea.trace_service` |
| `services/validate.py` | Schema/graph/projection validation | Split into generic engine plus DFMEA validators | `quality_core.validation`, `quality_methods.dfmea.validators` |
| `services/projections.py` | DB-derived views | Preserve projection shapes where useful; rebuild from file graph | `quality_core.projections`, `quality_methods.dfmea.projections` |
| `services/export_markdown.py` | Markdown rendering | Keep rendering logic where possible; replace row loading | `quality_methods.dfmea.exports` |
| `dfmea/SKILL.md` | Agent guidance | Keep and update for project files/Git commands | `dfmea/SKILL.md` |
| `dfmea/skills/*` | Subskill guidance | Keep and update commands/options | `dfmea/skills/*` |

## 5. Data Model Mapping

### 5.1 SQLite Tables To Files

| Current SQLite model | Target file model |
| --- | --- |
| `projects` row | `projects/<slug>/project.yaml` |
| `nodes` rows with `type=system/subsystem/component` | `dfmea/structure/SYS-001.yaml`, `SUB-001.yaml`, `COMP-001.yaml` |
| `nodes` rows with `type=function` | `dfmea/functions/FN-001.yaml` |
| `nodes` rows with `type=requirement` | `dfmea/requirements/REQ-001.yaml` |
| `nodes` rows with `type=characteristic` | `dfmea/characteristics/CHAR-001.yaml` |
| `nodes` rows with `type=failure_mode` | `dfmea/failure-modes/FM-001.yaml` |
| `nodes` rows with `type=failure_effect` | `dfmea/effects/FE-001.yaml` |
| `nodes` rows with `type=failure_cause` | `dfmea/causes/FC-001.yaml` |
| `nodes` rows with `type=action` | `dfmea/actions/ACT-001.yaml` |
| `fm_links` | inline same-aggregate refs or `links/LINKS-001.yaml` depending on relationship scope |
| `derived_views` | `dfmea/projections/*.json` plus `manifest.json` |
| `project.data.projection_dirty` | projection manifest freshness |
| `project.data.canonical_revision` | Git commit history |

### 5.2 Reference Mapping

Current code accepts rowids and optional business IDs. Target V1 should standardize on project-local IDs.

| Current reference | Target reference |
| --- | --- |
| SQLite `rowid` | not part of public contract |
| `node.id` | `metadata.id` |
| `parent_id` rowid | `spec.parentRef` or plugin-declared relationship field |
| `project_id` | project path/slug context |
| `fm_links.from_rowid/to_fm_rowid` | resource IDs in `spec` or `TraceLinkSet` |

During migration, command options should stop exposing rowid after file-backed storage is introduced.

## 6. Command Mapping

### 6.1 Shared `quality` Commands

New commands:

| Target command | Purpose | Current source |
| --- | --- | --- |
| `quality workspace init` | create `.quality/workspace.yaml`, `.quality/plugins.yaml` | new |
| `quality project create` | create `projects/<slug>/project.yaml` and project `.quality/` | rewrite `services/projects.py` |
| `quality project status` | Git/config/projection status | new |
| `quality project validate` | cross-domain validation | extend `commands/validate.py` logic |
| `quality project snapshot` | validate/rebuild/export/stage/commit | new |
| `quality project history` | Git history by managed paths | new |
| `quality project diff` | Git diff plus object summaries | new |
| `quality project restore` | forward restore commit | new |
| `quality plugin list/enable/disable` | built-in plugin management | new |

### 6.2 Existing `dfmea` Commands

| Current command | Target status |
| --- | --- |
| `dfmea init` | keep; initialize DFMEA domain inside an existing project or create project when explicitly requested |
| `dfmea structure add/update/move/delete` | keep; write YAML resources |
| `dfmea analysis add-function/update-function/...` | keep; write YAML resources |
| `dfmea analysis add-failure-chain` | keep; create FM/FE/FC/ACT resources and refs |
| `dfmea analysis link-*` | keep if same-aggregate; cross-domain links move to `TraceLinkSet` |
| `dfmea query get/list/search/summary/map/bundle/dossier/by-ap/by-severity/actions` | keep; use graph/projections |
| `dfmea trace causes/effects` | keep; use graph index |
| `dfmea validate` | keep; domain validation |
| `dfmea projection status/rebuild` | keep; domain projection command |
| `dfmea export markdown` | keep; export generated view |

### 6.3 Options To Remove Or Replace

| Current option/concept | Target |
| --- | --- |
| `--db` | `--workspace` plus `--project` |
| `--project-id` | `--project <project-slug-or-directory>` |
| `--busy-timeout-ms` | optional lock timeout if needed |
| `--retry` | remove or replace with lock retry policy |
| rowid args | project-local resource IDs |

## 7. Service Migration Strategy

### 7.1 Keep Business Logic, Replace Persistence

Services such as `analysis.py`, `structure.py`, `query.py`, and `trace.py` contain useful DFMEA behavior. The migration should avoid rewriting all business rules at once.

Recommended strategy:

1. Create file-backed `ResourceStore`.
2. Create graph loader that returns structures similar enough for current service logic.
3. Extract pure business helpers from current services.
4. Replace SQL sections one command group at a time.
5. Keep command output shape stable under the new JSON contract.

### 7.2 SQL Removal Boundary

All direct `sqlite3` usage should be removed from:

- services.
- commands.
- resolution.
- validation.
- projections.
- exports.

Allowed transitional state:

- `db.py` and `schema.py` may remain temporarily as unused legacy modules during early phases.
- final V1 implementation must remove or archive SQLite source-of-truth code.

### 7.3 Projection Migration

Current `services/projections.py` has useful output concepts:

- project map.
- component bundles.
- risk register.
- action backlog.
- function dossiers.

Target keeps these view concepts but rebuilds them from the file graph and writes projection JSON files plus a manifest.

### 7.4 Validation Migration

Current `services/validate.py` mixes:

- storage/schema checks.
- graph checks.
- duplicate business ID checks.
- projection state checks.
- reference checks.

Target split:

```text
quality_core.validation.engine
  -> schema validation
  -> ID/path validation
  -> graph validation
  -> projection freshness

quality_methods.dfmea.validators
  -> DFMEA methodology and graph rules
```

## 8. Agent Skill Migration

Update skill guidance from database commands to project commands.

Current skill concepts to keep:

- use CLI as official interface.
- validate after changes.
- query before editing.
- export review markdown.

Skill changes:

- replace `--db` examples with `--project`.
- add `quality project snapshot`.
- add `quality project restore`.
- warn against editing projections/exports as source.
- explain `FM-001` style IDs.
- explain tombstones and renumber repair.

## 9. Migration Risks

| Risk | Mitigation |
| --- | --- |
| Big-bang rewrite loses working DFMEA behavior | migrate command group by command group |
| SQL business logic is tangled with persistence | extract pure helpers before replacing all service code |
| Rowid assumptions leak into CLI | add tests that command outputs use project-local IDs only |
| Projection behavior regresses | preserve projection fixture outputs where possible |
| Agent skills become stale | update skills in the same phase as command option changes |
| Restore/snapshot bugs can affect Git history | test with temporary Git repos before enabling commit creation |

## 10. Migration Completion Criteria

Migration is complete when:

- `dfmea` commands no longer require `--db`.
- `quality` CLI exists for workspace/project/plugin/Git operations.
- no target workflow depends on `sqlite3`.
- project data is stored under `projects/<slug>/`.
- project-local schema snapshots and tombstones are managed.
- projections are generated files with manifests.
- Git snapshot/history/diff/restore work against managed paths.
- existing DFMEA workflows are covered by file-backed tests.
- Agent skills document the new file/Git workflows.
