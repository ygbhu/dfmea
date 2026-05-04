# Local-first Quality Assistant Requirements

> Status: target product requirements baseline
>
> Scope: local-first personal and small-team quality management assistant for project-scoped DFMEA
> first, with PFMEA, Control Plan, and future quality plugins as deferred extension points.
>
> Architecture reference: `docs/architecture/local-first-quality-assistant-architecture.md`
>
> Historical note: `2026-03-15-dfmea-skill-requirements.md` describes the old DFMEA SQLite direction and remains historical context only.

## 1. Purpose

This document defines what the Local-first Quality Assistant must do and the product constraints it must satisfy.

It is the upstream requirement source for architecture, detailed design, implementation planning, tests, and acceptance review.

This document does not define implementation tasks or schedule.

## 2. Product Goal

Build a personal and small-team headless quality management engine where humans, Agents, local
tools, optional UIs, and CI use the same quality plugin contracts, while project quality data
remains in local Git repositories as structured, reviewable, and mergeable files.

The system must help users:

- create and maintain project-scoped DFMEA data.
- reserve a project boundary that can later connect PFMEA, Control Plan, evidence, exports, and
  reports.
- let Agents safely create, update, query, validate, export, and explain quality data.
- use Git for team synchronization, version history, audit, diff, and restore.
- optionally add OpenCode, UI, IDE, or CI adapters in future phases without creating a second source
  of truth.

## 3. Product Positioning

The product is:

- local-first.
- Git-native.
- Agent-friendly.
- project-scoped.
- plugin-extensible.
- host-adapter friendly.
- file-backed.

The product is not:

- a centralized FMEA platform.
- a web-service-first system.
- an OpenCode-native plugin as its core product form.
- a PostgreSQL or SQLite-backed product in the target architecture.
- an enterprise permission/signoff system.
- a replacement for mature official FMEA release systems.

## 4. Users And Roles

Primary users:

- quality engineer: maintain DFMEA/PFMEA, validate risk data, inspect AP and action status.
- design engineer: maintain design functions, characteristics, failure modes, causes, and design actions.
- manufacturing/process engineer: maintain process flow, process steps, process risks, controls, and PFMEA actions.
- project owner: inspect project progress, risk summary, open actions, and traceability coverage.
- Agent: execute CLI-backed operations, query context, propose changes, validate data, generate exports, and explain results.

Role boundaries:

- Humans own engineering judgment and final review.
- Agents execute repeatable structured operations and produce reviewable changes.
- CLI/plugins enforce domain rules and write safety.
- Git stores version history, team sync state, and reviewable diffs.
- Optional host adapters improve Agent, UI, IDE, or CI ergonomics but do not own data.

## 5. Core Concepts

### 5.1 Workspace

A workspace is a local Git repository containing one or more quality projects.

Requirements:

- A workspace must support multiple projects by default.
- A workspace with exactly one project must be valid.
- Workspace-level commands must explicitly report affected projects.
- Workspace-level batch operations must not silently mutate projects outside the requested scope.
- Workspace-level configuration may define defaults, but project-specific state must live under the project directory.

### 5.2 Project

A project is the business boundary for quality data.

Requirements:

- A project must have stable metadata and a stable project directory name.
- In V1, the project directory name is the project identity and must match `metadata.slug`.
- Project rename is out of V1 scope unless implemented by an explicit migration command.
- A project may enable multiple quality domains.
- Git snapshot, validation, restore, diff, and history must operate on one project by default.
- Cross-domain links are allowed inside one project.
- Cross-project links are out of V1 scope.

### 5.3 Quality Domain Plugin

A quality domain plugin owns a quality method area such as DFMEA, PFMEA, Control Plan, or 8D.

Requirements:

- Each plugin must declare its resource kinds.
- Each plugin must declare schemas for its source files.
- Each plugin must declare path rules and ID prefixes.
- Each plugin must provide validation rules.
- Each plugin must provide query/projection/export capabilities.
- Each plugin must provide Agent skill guidance.

### 5.4 Source Resource

A source resource is a structured file that is part of the canonical project data.

Requirements:

- Source resources must be human-readable and Agent-readable.
- Source resources must be Git-diffable and Git-mergeable.
- Source resources must use a uniform envelope with `apiVersion`, `kind`, `metadata`, and `spec`.
- Source resources must validate against plugin schemas.
- Source resources must not require a running service or database to read.

### 5.5 Generated View

A generated view is a projection, export, or report derived from source resources.

Requirements:

- Generated views must be rebuildable from source resources.
- Generated views must not be treated as source data.
- Generated views must include source references when used for review or traceability.
- Generated views may be committed to Git only when configured as managed outputs.
- Generated views must be unmanaged by default and become managed only through explicit project configuration; source resources remain managed by default.
- Workspace defaults may suggest generated-output behavior, but the effective project decision must be recorded in project configuration.

## 6. Functional Requirements

### 6.1 Workspace Management

The system must support:

- initializing a quality workspace.
- detecting workspace configuration.
- listing projects.
- validating workspace configuration.
- reporting Git status relevant to managed quality data.

Configuration loading requirements:

- Workspace discovery must support `--workspace <path>` and upward discovery from the current directory.
- Commands must load workspace config, plugin config, project config, project-local schema snapshots, and plugin collection declarations in a deterministic documented order.
- Commands must compare project schema snapshots with tooling schema versions before mutating source files.
- Commands must fail with stable error codes when workspace, project, plugin, or schema configuration cannot be resolved.

### 6.2 Project Management

The system must support:

- creating a project.
- reading project metadata.
- updating project metadata.
- enabling and disabling project quality domains.
- validating a project.
- producing a project status summary.
- snapshotting a project into Git.
- showing project history and diff.
- restoring a project safely from a previous version.

### 6.3 DFMEA Domain

The system must support project-scoped DFMEA.

Required DFMEA concepts:

- DFMEA analysis root.
- system/subsystem/component structure.
- function.
- requirement.
- characteristic.
- failure mode.
- failure effect.
- failure cause.
- action.
- trace links.

The DFMEA plugin must support:

- creating and updating structure nodes.
- creating and updating functions.
- creating and updating requirements and characteristics.
- creating and updating failure chains.
- updating S/O/D/AP and action status fields.
- deleting objects with controlled cleanup.
- querying by component, function, failure mode, AP, severity, action status, and keyword.
- tracing causes and effects.
- validating DFMEA graph and methodology rules.
- exporting review and table views.

### 6.4 PFMEA Domain

PFMEA is deferred from the current implementation baseline. The system must keep PFMEA as a future
project-scoped domain extension point, but it must not expose PFMEA commands or register PFMEA as a
built-in plugin until the PFMEA implementation phase starts.

Required PFMEA concepts:

- PFMEA analysis root.
- process flow.
- process step.
- process function.
- process failure mode.
- process effect.
- process cause.
- prevention control.
- detection control.
- process action.
- links to DFMEA when available.

When implemented, the PFMEA plugin should support:

- creating and updating process flows and steps.
- creating and updating process functions.
- creating and updating process failure chains.
- maintaining prevention and detection controls.
- updating S/O/D/AP and action status fields.
- querying by process step, AP, severity, action status, and keyword.
- validating PFMEA graph and methodology rules.
- exporting review and table views.

PFMEA must not require DFMEA to exist when implemented, but it must be able to link to DFMEA design
characteristics, effects, causes, and actions when both domains are enabled in the same project.

### 6.5 Control Plan Domain

The system should support Control Plan as a project domain after DFMEA/PFMEA foundations are stable.

Control Plan requirements:

- reference DFMEA/PFMEA characteristics and controls.
- track product/process characteristics.
- track control methods, sample size/frequency, reaction plans, and ownership.
- validate coverage from PFMEA controls/actions to Control Plan rows.

Control Plan is not mandatory for the first implementation milestone, but the project/domain model must not block it.

### 6.6 Traceability

The system must support traceability across source resources.

Requirements:

- Same-aggregate references may be embedded in resource `spec`.
- Cross-aggregate references must be represented as link resources unless explicitly declared by plugin schema.
- Cross-domain references must be represented as link resources.
- Links must validate endpoint existence.
- Links must validate allowed relationship type.
- Links must be queryable by source, target, kind, and domain.
- Traceability results must include file paths and resource IDs.
- File-backed link sets must have project-scoped resource IDs.
- Nested link entries may use local IDs that are unique only within their parent link set.

### 6.7 Query And Context Retrieval

The system must support Agent-friendly queries.

Requirements:

- Query output must support stable JSON.
- Query output must include resource ID, kind, title/summary, path, and source references.
- Common focused queries should not require full project file scanning when fresh projections exist.
- The system must support context bundles for Agent work, such as a function with its failure chain, actions, and trace links.
- Context bundle commands must return stable JSON with source paths, included resource IDs, and projection freshness metadata.
- Query commands may read source files directly or use fresh projections.

### 6.8 Validation

The system must support complete validation issue reporting.

Validation must cover:

- schema validity.
- duplicate IDs.
- missing references.
- invalid relationship types.
- invalid hierarchy.
- orphan resources.
- stale or missing projections.
- DFMEA/PFMEA methodology rules.
- cross-domain coverage rules where enabled.

Validation output must:

- return all detected issues, not stop at first error.
- classify issue severity.
- include resource ID, kind, path, field, message, and suggested action.
- support machine-readable JSON.

Severity requirements:

- `error` means the source state is invalid or unsafe for the requested operation.
- `warning` means the operation may complete, but follow-up is recommended.
- `info` means contextual detail for humans or Agents.
- Snapshot and restore operations must fail when validation returns `error` issues.

### 6.9 Projection And Export

The system must support rebuildable projections and generated exports.

Projection requirements:

- build structure trees.
- build risk registers.
- build action backlogs.
- build traceability matrices.
- build AP/severity/status summaries.
- write a projection manifest with source hash, per-plugin schema versions, build time, project slug, and project root.
- write per-source file hashes in the projection manifest.
- refuse to treat stale projection data as authoritative.
- mark a projection stale when any managed source file or project schema snapshot is added, removed, renamed, or hash-mismatched.

Export requirements:

- generate Markdown review views.
- generate CSV/table views where useful.
- preserve source references.
- keep exports separate from source resources.
- support configured managed exports for Git snapshots.
- keep generated projections, exports, and reports out of commits by default unless the project opts them in as managed outputs.

### 6.10 Git Version And Team Sync

The system must use Git for team sync, history, audit, diff, and restore.

Requirements:

- A quality project repository may contain multiple projects.
- Git operations must default to a single project scope.
- Workspace-level Git operations must explicitly list affected projects.
- Project snapshots must stage managed source files, project-local schema snapshots, tombstones, and configured generated outputs.
- Snapshot commit messages must include business context.
- Project history must show project-relevant commits.
- Project diff must summarize source file changes and quality object changes where possible.
- V1 project history may be implemented by Git path filtering over project managed paths.
- V1 project diff must include raw Git file changes and add parsed object summaries when resource files can be parsed.
- Project restore must be safe and create a new forward commit instead of rewriting history.
- Project restore must restore project-managed non-generated paths from the target ref, including source files, project-local schema snapshots, tombstones, links, and evidence references.
- Project restore must exclude runtime locks, rebuild generated files, validate, and commit the restored state.
- Same-object conflicts must be surfaced for human review with Agent assistance.
- Automatic semantic merge of conflicting quality objects is out of V1 scope.

### 6.11 ID Generation

The system must prioritize readable project-scoped IDs.

Requirements:

- IDs must include a resource-type prefix.
- Ordinary object IDs must use a project-local sequence number, such as `FM-001`.
- Singleton project/domain resources may use fixed IDs such as `PRJ`, `DFMEA`, and `PFMEA`.
- IDs are unique inside one project directory; identical IDs may exist in different projects.
- IDs must not be reused.
- ID format must be stable and documented.
- Validation must detect duplicate IDs and mismatches between file path and `metadata.id` for collection resources that use `{id}.yaml` addressing.
- Validation must support fixed-file singleton resources and nested local IDs declared by plugin schemas.
- ID allocation must scan existing source files and tombstones instead of relying on a counter file.
- Deleting an object must record a project-local tombstone so the ID is not reused.
- Same-project ID conflicts from branch merges must be repairable through a CLI renumber command that updates files and references.
- ID allocation and renumbering must run under the project write lock.

### 6.12 Optional Host Adapters

The system may provide OpenCode, UI, IDE, or CI adapters in future phases. No host adapter
implementation is required or bundled for the current V1 CLI-first baseline.

Adapter requirements:

- Adapters must not become a separate source of truth.
- Adapters must read source resources and projections from the quality project repository.
- Adapter writes must call the CLI or a shared plugin core used by the CLI.
- Adapters must not implement independent write rules.
- UI adapters should support project selection, structure tree, resource editor, Agent
  conversation, Git status/diff/history, and export preview.
- CI adapters should support validation, projection freshness checks, and export/report checks.

## 7. Non-functional Requirements

### 7.1 Local-first Operation

- The system must work without a server.
- The system must not require PostgreSQL, SQLite, or any database in the target architecture.
- The system must run on local files.
- The system must support Windows local file operations.

### 7.2 Git-native Data

- Source data must be structured text.
- Source data must be Git-diffable.
- Source data must be Git-mergeable at object-file granularity.
- Generated files must be distinguishable from source files.

### 7.3 Agent Friendliness

- Skills must describe safe workflows.
- CLI output must support stable JSON.
- Source files must be understandable without hidden state.
- Query commands must provide focused context bundles.
- Commands must return enough paths and IDs for follow-up actions.

### 7.4 Safety And Recovery

- CLI writes must be atomic at the file operation level where possible.
- CLI write commands must acquire a project-scoped runtime lock before mutating project files.
- Multi-file writes must either complete safely or report affected files and repair guidance.
- Validation must detect inconsistent states after merge or manual edit.
- Exports and projections must be rebuildable.
- Restore must not rewrite Git history by default.

### 7.5 Scale

- The design must support small projects and larger projects with tens of thousands of quality objects.
- Common focused queries should use projections or indexes when available.
- Full rebuilds may be more expensive but must be repeatable.
- Large projects must avoid monolithic source files for high-churn objects.

### 7.6 Extensibility

- New quality domains must be added as plugins.
- Plugins must declare resource kinds, schemas, path rules, validators, projections, exports, and Agent skill guidance.
- Shared project/workspace/Git behavior must not be duplicated inside every plugin.

## 8. Constraints

### 8.1 Source-of-truth Constraints

- Structured source files are the only quality data source of truth.
- Markdown/CSV/HTML/PDF exports are generated views, not source data.
- Projections are generated indexes, not source data.
- Git is the version/sync/audit layer.

### 8.2 Project Boundary Constraints

- Project is the default business boundary.
- DFMEA/PFMEA/Control Plan are project domains.
- Cross-domain links are allowed inside a project.
- Cross-project links are out of V1 scope.

### 8.3 Write Path Constraints

- CLI or shared plugin core is the official write path.
- Manual file edits are allowed only if validation passes.
- Agent skills must prefer CLI commands when commands exist.
- UI must not bypass CLI/shared plugin rules.

### 8.4 Conflict Constraints

- Same-object Git conflicts are expected and must be visible.
- Same-object conflicts require human review with Agent assistance.
- V1 does not require automatic semantic conflict merge.

## 9. V1 Scope

V1 must include:

- workspace initialization.
- deterministic workspace/project/plugin/schema configuration loading.
- project creation.
- structured source file format.
- ID generation with type prefix and project-local sequence number.
- project-local ID tombstones for deleted objects.
- project-local schema snapshots for enabled plugins.
- CLI-assisted ID renumber repair for same-project conflicts.
- DFMEA project-domain source model.
- DFMEA create/update/query/validate/export baseline.
- project-scoped Git snapshot/status/history/diff baseline.
- projection manifest baseline.
- stale projection detection based on per-source file hashes and project schema snapshot hashes.
- opt-in managed generated outputs for snapshots.
- context bundle query baseline for Agent workflows.
- Agent skill routing for DFMEA.
- tests for file-backed source operations.

Deferred extension work:

- PFMEA initial source model.
- PFMEA validate/export baseline.
- DFMEA to PFMEA link model.
- optional pre-commit validation hook.

V1 does not include:

- central server.
- database-backed storage.
- enterprise permission/signoff.
- automatic same-object semantic merge.
- official Control Plan implementation.
- full OpenCodeUI productization.

## 10. Acceptance Criteria

The product direction is accepted when:

- A new workspace can be initialized as a Git repository.
- CLI commands resolve workspace, project, plugin, and schema configuration through the documented loading order.
- A project can be created under `projects/<project-slug>/`.
- DFMEA source resources are written as structured text files.
- New IDs use type prefixes and project-local sequence numbers.
- Deleted IDs are not reused because project-local tombstones are considered during allocation.
- Same-project ID conflicts can be repaired by renumbering one object and updating its references.
- `dfmea validate` can detect schema, graph, duplicate ID, and methodology issues.
- `dfmea query` can return focused context with IDs and paths.
- a context bundle command can return a focused resource graph with source paths and freshness metadata.
- projections can be rebuilt and include a manifest with total source hash, per-source file hashes, and per-plugin schema versions.
- stale projections are not treated as authoritative when source files or project schema snapshots change, and trigger rebuild or a `PROJECTION_STALE` error/warning according to command type.
- Markdown or CSV exports can be regenerated from source.
- generated outputs are not committed by default unless configured as managed outputs.
- `quality project snapshot` can create a project-scoped Git commit.
- `quality project snapshot` includes project-local schema snapshots and tombstones when changed.
- `quality project history` can list commits affecting the selected project by managed paths.
- `quality project diff` can show raw file changes and parsed object summaries where possible.
- `quality project restore` can restore one project by creating a new forward commit without rewriting Git history.
- Git diff shows meaningful source file changes.
- Same-object conflict resolution remains visible and reviewable.
- No target architecture requirement depends on SQLite or PostgreSQL.

## 11. Decisions And Remaining Planning Questions

Decided:

- V1 schema language is JSON Schema for structural validation, with graph/methodology checks in plugin validators.
- V1 CLI uses split namespaces: shared `quality` project/workspace/plugin commands plus active
  domain CLIs such as `dfmea`. `pfmea` is deferred.
- V1 Git operations belong to `quality project ...`; domain-specific snapshots use `--domain`.
- V1 generated projections, exports, and reports are opt-in managed outputs; source resources are managed by default.
- V1 project history starts with Git path filtering and parsed object summaries; richer semantic history is later scope.

Remaining planning question:

- First PFMEA milestone depth when that phase restarts.
