# Local-first Quality Assistant Development Plan

> Status: implemented through Phase 10; Phase 11 PFMEA is intentionally deferred as a placeholder.
>
> Requirements: `docs/requirements/local-first-quality-assistant-requirements.md`
>
> Architecture: `docs/architecture/local-first-quality-assistant-architecture.md`
>
> Detailed design: `docs/design/local-first-quality-assistant-detailed-design.md`
>
> Migration map: `docs/design/current-dfmea-cli-migration-map.md`

## 1. Plan Purpose

This plan guides development from the current historical `dfmea-cli` implementation to the new local-first quality assistant.

The plan is intentionally incremental. The current Python CLI should remain the implementation base while storage, project boundaries, and Git workflows are replaced underneath it.

## 2. Development Rules

### 2.1 Non-negotiable Architecture Rules

- Source of truth is project files, not SQLite.
- Project directory is the V1 business and ID namespace.
- Resource IDs are project-local, readable IDs such as `FM-001`.
- Project-specific state lives under `projects/<slug>/.quality/`.
- Runtime locks are not committed.
- Generated projections/exports/reports are not authoritative.
- Git is the version, sync, history, diff, and restore layer.
- `dfmea` owns DFMEA domain commands.
- `quality` owns workspace/project/plugin/Git operations.

### 2.2 Technology Decision

V1 continues to use Python for the CLI and core implementation.

Decision:

- keep Python 3.11+ as the implementation language.
- keep Typer for CLI command registration unless a concrete blocker appears.
- treat the Python implementation as a headless quality engine with CLI as the first stable
  adapter.
- add the shared `quality` console script next to the existing `dfmea` console script.
- use Python modules for workspace, resource store, validation, projection, export, and Git orchestration.
- avoid introducing a second implementation language for the V1 core.

Why Python remains the right V1 choice:

- the current historical project is already a working Python CLI.
- existing DFMEA command and service code can be migrated incrementally.
- Agent-readable business logic matters more than raw CLI execution speed.
- Python has mature libraries for YAML, JSON Schema, Git process integration, Markdown/CSV export, and testing.
- switching to Go/Rust/Node would force a rewrite before the product architecture is proven.

Alternatives rejected for V1:

- Go: good single-binary CLI, but higher rewrite cost and weaker fit for reusing current DFMEA logic.
- Rust: strong correctness and performance, but unnecessary complexity for the current file/CLI workload.
- Node/TypeScript: good for optional UI/adapters, but the project is intentionally moving away from
  the previous TypeScript platform direction.

Future option:

- after the Python CLI stabilizes, performance-critical helpers may be extracted if profiling proves a need. This is not a V1 design assumption.

### 2.3 Project Structure Adjustment

The original project structure must be adjusted before large feature migration.

Target structure:

```text
src/
  dfmea_cli/
    __main__.py
    cli.py
    commands/       # compatibility wrappers
  quality_core/
    cli/
    workspace/
    resources/
    methods/
    plugins/
    validation/
    graph/
    projections/
    git/
    exports/
  quality_methods/
    dfmea/
    pfmea/          # placeholder only until PFMEA phase starts
plugin/
  package.json
  plugin.js
  bin/opencode-quality.js
engine/
  src/
    quality_adapters/
      cli/
        quality.py
        dfmea.py
        dfmea_commands/
      opencode/       # OpenCode templates and installer
```

Rules:

- `dfmea_cli` remains as the compatibility namespace for existing DFMEA command imports.
- `quality_core` owns shared workspace/project/method/resource/Git behavior.
- `quality_core.methods` owns product-level quality method discovery.
- `quality_core.plugins` owns the lower-level schema/resource plugin contract for implemented
  methods.
- `quality_methods.dfmea` owns the active DFMEA method descriptors, schemas, validators,
  projections, and domain services.
- `quality_methods.pfmea` is a reserved method package only; it is discoverable as planned but is
  not registered as an active built-in schema plugin yet.
- `quality_adapters.cli` owns the active CLI entrypoints and command wiring.
- `quality_adapters.opencode` owns generated OpenCode commands, skills, and plugin hooks. It is an
  adapter over CLI/shared-core contracts and must not own source data.
- Other `quality_adapters.*` packages are reserved for optional host integration only; adapters must
  call CLI or shared core contracts and must not own source data.
- historical SQLite modules are retired and must not be restored.
- command groups use file-backed services and project-local resource IDs.

`pyproject.toml` target:

```toml
[project.scripts]
dfmea = "quality_adapters.cli.dfmea:main"
quality = "quality_adapters.cli.quality:main"
```

This gives us the new architecture boundary without breaking the existing `dfmea` CLI all at once.

### 2.4 Development Constraints

- Keep changes scoped to one phase at a time.
- Prefer adapting current `dfmea_cli` command UX over inventing new names.
- SQLite removal has completed for migrated V1 behavior; do not restore SQLite-backed source-of-truth code.
- Do not add or keep unintegrated host/UI code in the core repo; any future adapter task must use
  the same CLI/plugin contracts as the Python implementation.
- Do not reintroduce PostgreSQL, SQLite, service-process requirements, or cross-project links.
- Update Agent skills when command behavior changes.

### 2.5 Definition Of Done Per Phase

Each phase is done when:

- behavior is implemented.
- unit/integration tests cover the phase acceptance criteria.
- docs or skill examples are updated if command usage changed.
- `ruff` and `pytest` pass for affected code.
- no new dependency is added without a clear reason.

## 3. Recommended Milestones

## Phase 0: Baseline Guardrails

Goal: make the current repo safe for migration work.

Deliverables:

- Confirm current CLI commands and tests.
- Add a top-level architecture notice in README if needed.
- Add project fixtures for target file layout.
- Add `.gitignore` entries for runtime locks and temp files.

Target files:

- `README.md`
- `.gitignore`
- `tests/fixtures/`
- `docs/`

Acceptance criteria:

- Current `dfmea` CLI still imports.
- `pytest` baseline is known.
- Target fixture contains `projects/demo/.quality/schemas`, `tombstones`, and `project.yaml`.

## Phase 1: Core Workspace And Project Files

Goal: create the shared file-backed workspace/project foundation without changing all DFMEA commands at once.

Deliverables:

- target Python package structure under `src/quality_core/` and `src/quality_methods/`.
- `quality` CLI entrypoint.
- workspace discovery.
- workspace init.
- project create.
- project config loading.
- project-local `.quality/` directory creation.
- stable JSON output contract `quality.ai/v1`.

Target modules:

```text
src/quality_core/cli/
src/quality_core/workspace/
src/quality_core/resources/
```

Current modules affected:

- `pyproject.toml`
- new `src/quality_core/`
- new `src/quality_methods/`
- `dfmea_cli/contracts.py`
- `dfmea_cli/output.py`
- `dfmea_cli/errors.py`

Acceptance criteria:

- `pyproject.toml` exposes both `dfmea` and `quality` console scripts.
- `quality_core` and `quality_methods.dfmea` packages import cleanly.
- `quality workspace init` creates `.quality/workspace.yaml` and `.quality/plugins.yaml`.
- `quality project create cooling-fan-controller` creates `projects/cooling-fan-controller/project.yaml`.
- project `metadata.id` is `PRJ`.
- project `metadata.slug` equals the project directory.
- JSON output includes `contractVersion`, `projectSlug`, and `projectRoot`.

## Phase 2: Plugin Registry And Schema Snapshots

Goal: introduce built-in plugin contracts and project-local schema snapshots.

Deliverables:

- built-in plugin registry.
- DFMEA plugin descriptor.
- DFMEA schema snapshot copy on plugin enable.
- plugin list/enable/disable commands.
- schema version mismatch detection.

Target modules:

```text
src/quality_core/plugins/
src/quality_core/validation/json_schema.py
src/quality_methods/dfmea/
```

Current modules affected:

- `dfmea_cli/schema.py` becomes legacy reference.
- `dfmea/node-schema.md`
- `dfmea/failure-chain-schema.md`

Acceptance criteria:

- `quality plugin list` shows built-in `dfmea`.
- `quality plugin enable dfmea --project <project>` writes `projects/<slug>/.quality/schemas/dfmea/`.
- commands fail with `SCHEMA_VERSION_MISMATCH` when project snapshot and tooling schema do not match.
- project-local schema snapshots are staged by project snapshot later.

## Phase 3: File-backed Resource Store, IDs, Locks

Goal: replace SQLite CRUD foundations with file-backed resources and project-local IDs.

Deliverables:

- resource envelope parser/writer.
- collection path registry.
- project lock.
- atomic write helper.
- ID allocation by scanning source files and tombstones.
- tombstone creation on delete.
- path/ID validation helpers.

Target modules:

```text
src/quality_core/resources/envelope.py
src/quality_core/resources/ids.py
src/quality_core/resources/paths.py
src/quality_core/resources/store.py
src/quality_core/resources/locks.py
src/quality_core/resources/atomic.py
```

Current modules replaced:

- `dfmea_cli/db.py`
- SQL-dependent parts of `dfmea_cli/resolve.py`
- SQL-dependent parts of `dfmea_cli/services/projects.py`

Acceptance criteria:

- new DFMEA resource can be written as YAML.
- collection file basename matches `metadata.id`.
- singleton resources validate fixed ID and fixed file name.
- deleting `FM-001` creates `projects/<slug>/.quality/tombstones/FM-001`.
- allocating after delete skips tombstoned IDs.
- concurrent writes use `projects/<slug>/.quality/locks/project.lock`.

## Phase 4: DFMEA Init And Structure Commands

Goal: move the first real DFMEA command group to file-backed storage.

Deliverables:

- `dfmea init --project <project>` creates `dfmea/dfmea.yaml` and directories.
- `dfmea structure add/update/move/delete` writes YAML resources.
- structure relationships represented by source fields.
- command output uses project-local IDs and paths.

Current modules affected:

- `dfmea_cli/commands/init.py`
- `dfmea_cli/commands/structure.py`
- `dfmea_cli/services/projects.py`
- `dfmea_cli/services/structure.py`
- `dfmea_cli/resolve.py`

Acceptance criteria:

- no `--db` needed for migrated structure commands.
- `SYS-001`, `SUB-001`, `COMP-001` files are created.
- structure delete creates tombstone.
- validation catches missing parent references.

## Phase 5: DFMEA Analysis Commands

Goal: migrate DFMEA business authoring commands while preserving existing UX where useful.

Deliverables:

- function, requirement, characteristic create/update/delete.
- failure chain create/update/delete.
- S/O/D/AP calculation preserved.
- action status update.
- same-aggregate references stored in `spec`.
- link set support for cross-aggregate links where needed.
- renumber repair command updates references.

Current modules affected:

- `dfmea_cli/commands/analysis.py`
- `dfmea_cli/services/analysis.py`

Acceptance criteria:

- `dfmea analysis add-function` creates `FN-001.yaml`.
- `dfmea analysis add-failure-chain` creates FM/FE/FC/ACT resources.
- existing AP calculation behavior is preserved.
- `quality project id renumber --from FM-001 --to FM-002` updates references.
- branch-style same-ID fixture can be repaired by `quality project repair id-conflicts`.

## Phase 6: Validation Engine

Goal: split validation into core engine and DFMEA plugin rules.

Deliverables:

- JSON Schema validation.
- ID/path validation.
- duplicate ID validation.
- reference validation.
- graph validation.
- DFMEA methodology validation.
- stable issue shape and exit codes.

Current modules affected:

- `dfmea_cli/commands/validate.py`
- `dfmea_cli/services/validate.py`
- `dfmea_cli/errors.py`

Acceptance criteria:

- `dfmea validate --project <project>` reports all issues.
- duplicate IDs return `DUPLICATE_ID`.
- missing references return `REFERENCE_NOT_FOUND`.
- collection file/id mismatch is an error.
- singleton fixed filename/id rules pass.
- nested link IDs are validated within the parent link set.

## Phase 7: Graph, Query, Trace, Context

Goal: rebuild read/query workflows on file graph and fresh projections.

Deliverables:

- graph loader.
- in-memory indexes.
- query get/list/search/summary/map.
- query by AP/severity/actions.
- trace causes/effects.
- context bundle command.

Current modules affected:

- `dfmea_cli/commands/query.py`
- `dfmea_cli/commands/trace.py`
- `dfmea_cli/services/query.py`
- `dfmea_cli/services/trace.py`

Acceptance criteria:

- query output includes ID, kind, path, title/summary.
- `dfmea context failure-chain` returns root resource, related resources, links, paths, and freshness metadata.
- trace commands do not need SQLite.
- stale projection behavior follows command mode.

## Phase 8: Projection And Export

Goal: replace database-derived views with file graph projections and generated exports.

Deliverables:

- projection manifest.
- `sourceHash` over source files and project schema snapshots.
- projection freshness check.
- tree/risk/action/traceability projections.
- Markdown and CSV export.
- generated output config in `project.yaml`.

Current modules affected:

- `dfmea_cli/commands/projection.py`
- `dfmea_cli/services/projections.py`
- `dfmea_cli/commands/export_markdown.py`
- `dfmea_cli/services/export_markdown.py`

Acceptance criteria:

- `dfmea projection rebuild` writes projections and manifest.
- schema snapshot change marks projection stale.
- source file change marks projection stale.
- generated exports are not staged unless configured as managed.
- export contains source IDs and paths.

## Phase 9: Git Version Commands

Goal: implement project-scoped Git workflows.

Deliverables:

- `quality project status`.
- `quality project snapshot`.
- `quality project history`.
- `quality project diff`.
- `quality project restore`.
- optional hook installer.

Target modules:

```text
src/quality_core/git/
```

Acceptance criteria:

- status reports dirty managed paths and stale projections.
- snapshot validates, rebuilds, stages managed paths, and commits.
- snapshot includes schema snapshots and tombstones.
- snapshot excludes locks.
- history filters commits by project managed paths.
- diff shows raw paths and parsed resource summaries.
- restore restores managed non-generated paths, excludes locks, rebuilds generated outputs, validates, and creates a forward commit.

## Phase 10: Agent Skills And Docs Update

Goal: make Agent usage match the new CLI and file model.

Deliverables:

- update `dfmea/SKILL.md`.
- update `dfmea/skills/*`.
- document new command examples.
- document forbidden operations.

Acceptance criteria:

- skills use `--project`, not `--db`.
- skills mention `quality project snapshot`.
- skills mention `quality project restore`.
- skills warn not to edit projections/exports as source.
- skills explain `FM-001` IDs, tombstones, and renumber repair.

## Phase 11: PFMEA First Slice

Status: deferred. Keep only placeholders until PFMEA is explicitly restarted.

Reserved future work:

- PFMEA plugin descriptor.
- PFMEA schema snapshots.
- `pfmea init`.
- process flow and process step resources.
- process failure mode resources.
- PFMEA validation baseline.
- project-level link sets remain the shared location for future DFMEA/PFMEA relationships.

Acceptance criteria:

- PFMEA can be enabled per project.
- `pfmea init` creates `pfmea/pfmea.yaml`.
- `STEP-001` and `PFM-001` style IDs work.
- `pfmea analysis add-failure-mode` creates `PFM-*` resources under the PFMEA domain.
- PFMEA validation checks process step and process failure mode references.

Current baseline rule:

- `quality method list` reports DFMEA active and PFMEA planned.
- `quality plugin list` reports active schema plugins for implemented methods; currently DFMEA only.
- There is no active `pfmea` console script.
- `src/quality_methods/pfmea/` and `pfmea/SKILL.md` are placeholders only.

## Phase 10.5: OpenCode-first Adapter

Goal: make OpenCode the first-priority Agent host without moving quality domain logic into
OpenCode.

Deliverables:

- `quality opencode init`.
- generated `.opencode/commands/*.md`.
- generated `.opencode/skills/*/SKILL.md`.
- generated `.opencode/plugins/quality-assistant.js` session context hook.
- generated OpenCode context points Agents at `quality method list` before assuming method
  capabilities.
- adapter templates packaged under `quality_adapters.opencode`.
- tests for template installation, idempotency, and conflict handling.

Acceptance criteria:

- `quality opencode init --workspace .` installs OpenCode commands, skills, and plugin files.
- re-running init skips unchanged generated files.
- local modifications are preserved unless `--force` is used.
- OpenCode plugin hook injects context only; it does not implement resource writes, ID allocation,
  schema validation, projection rebuilds, or Git restore behavior.
- PFMEA remains placeholder-only.

## 4. Suggested Commit Slices

Use small commits or PRs in this order:

1. `docs`: architecture/design/development docs.
2. `chore`: package entrypoint for `quality` CLI and empty core modules.
3. `feat(core)`: workspace/project config loading.
4. `feat(plugins)`: built-in plugin registry and schema snapshots.
5. `feat(storage)`: resource store, IDs, tombstones, locks.
6. `feat(dfmea)`: init and structure file-backed commands.
7. `feat(dfmea)`: analysis file-backed commands.
8. `feat(validation)`: validation engine and DFMEA rules.
9. `feat(query)`: graph, query, trace, context.
10. `feat(projection)`: manifest, freshness, projections.
11. `feat(git)`: status, snapshot, history, diff, restore.
12. `docs(skills)`: Agent skill updates.
13. `feat(pfmea)`: future PFMEA plugin, init, process flow, process failure modes, and validation.

## 5. Test Plan By Layer

### Core Tests

- workspace discovery.
- project creation.
- project config validation.
- plugin enablement.
- schema snapshot version mismatch.
- lock acquire/release/stale behavior.
- ID allocation and tombstones.
- atomic write rollback behavior.

### DFMEA Tests

- init.
- structure add/update/move/delete.
- analysis add/update/delete.
- failure chain creation.
- AP calculation.
- reference validation.
- query and context bundle.
- trace causes/effects.

### Projection/Export Tests

- projection build.
- projection freshness after source change.
- projection freshness after schema snapshot change.
- Markdown export source references.
- generated output opt-in.

### Git Tests

Use temporary Git repos.

- snapshot creates commit.
- snapshot stages managed source paths.
- snapshot includes tombstones/schema snapshots.
- snapshot excludes locks.
- history filters by project path.
- diff parses changed resources.
- restore creates forward commit.
- restore excludes generated target files and rebuilds generated outputs.

## 6. Work That Should Not Start Yet

Do not start these until DFMEA file-backed baseline and OpenCode-first adapter are stable:

- full OpenCodeUI productization.
- UI/IDE/CI adapter implementation.
- external plugin package installation.
- cross-project links.
- automatic semantic merge.
- Control Plan implementation.
- enterprise approval/permission workflows.

## 7. Implementation Status

Phases 1 through 10 are implemented in the Python local-first architecture. Phase 11 is deferred.

Current baseline:

- workspace and project file foundation exists.
- the built-in DFMEA plugin is available.
- shared resource store, project-local IDs, tombstones, locks, and atomic writes exist.
- DFMEA init, structure, analysis, validation, query, trace, context, projection, export, and Git
  project commands use file-backed project resources.
- `quality method list` exposes DFMEA as active and PFMEA as a planned placeholder.
- PFMEA is kept as a future placeholder only and is not registered as an active built-in schema
  plugin.
- OpenCode-first adapter installation exists through `quality opencode init`; it generates host
  commands, skills, and a lightweight plugin hook while preserving Python core ownership.
- old TypeScript platform code, PostgreSQL infrastructure, and SQLite-backed DFMEA service modules
  are no longer part of the target project.

Next implementation work should be defined as a new phase only when it extends the current
requirements and architecture.
