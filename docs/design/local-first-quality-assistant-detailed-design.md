# Local-first Quality Assistant Detailed Design

> Status: implementation design baseline
>
> Requirements reference: `docs/requirements/local-first-quality-assistant-requirements.md`
>
> Architecture reference: `docs/architecture/local-first-quality-assistant-architecture.md`
>
> Scope: V1 file-backed quality workspace, project-scoped DFMEA baseline, plugin contracts, Git version commands, projections, exports, and Agent-facing CLI output.

## 1. Design Goals

This document converts the target architecture into implementation-level contracts.

V1 must provide:

- local Git workspace initialization.
- project directory creation.
- project-local `.quality/` state.
- quality method discovery and built-in schema plugin enablement.
- file-backed resource create/update/delete/query.
- project-scoped readable IDs.
- validation with stable JSON issues.
- projection freshness checks.
- project-scoped Git snapshot/history/diff/restore.
- DFMEA baseline commands.
- extension points for PFMEA and future methods.

V1 must not introduce:

- SQLite, PostgreSQL, or another source-of-truth database.
- service process requirement.
- cross-project links.
- automatic semantic merge.
- external plugin package installation.

## 2. Repository Layout

V1 uses Python 3.11+ and keeps Typer as the CLI framework unless a concrete blocker appears. The existing `dfmea` console script remains, and V1 adds a new `quality` console script for shared workspace/project/plugin/Git operations.

### 2.1 Tooling Repository

The tooling repository contains implementation code, built-in plugins, schemas, skills, tests, and docs.

Target Python package layout:

```text
src/
  quality_core/
    __init__.py
    cli/
      quality.py
      output.py
      errors.py
    workspace/
      discovery.py
      config.py
      project.py
    resources/
      envelope.py
      ids.py
      paths.py
      store.py
      locks.py
      atomic.py
    plugins/
      registry.py
      contracts.py
    methods/
      registry.py
      contracts.py
    validation/
      engine.py
      issues.py
      json_schema.py
    graph/
      loader.py
      index.py
      links.py
    projections/
      builder.py
      manifest.py
      freshness.py
    git/
      status.py
      snapshot.py
      history.py
      diff.py
      restore.py
  quality_methods/
    dfmea/
      plugin.py
      lifecycle.py
      structure_service.py
      analysis_service.py
      schemas/
      validators.py
      projections.py
      exports.py
    pfmea/
      __init__.py  # placeholder only
  quality_adapters/
    cli/
      quality.py
      dfmea.py
      dfmea_commands/
  dfmea_cli/
    cli.py
    commands/
dfmea/
  SKILL.md
pfmea/
  SKILL.md          # placeholder only
tests/
```

The exact package names can be adjusted to fit the current Python project, but the boundaries above are the implementation boundaries.

### 2.2 Quality Workspace

The user/team data repository layout is:

```text
quality-workspace/
  .git/
  .quality/
    workspace.yaml
    plugins.yaml
  projects/
    cooling-fan-controller/
      .quality/
        schemas/
        tombstones/
        locks/
      project.yaml
      dfmea/
      pfmea/
      control-plan/
      links/
      exports/
      reports/
      evidence/
```

Workspace `.quality/` contains workspace-level defaults and plugin availability. Project `.quality/` contains project-specific state.

Project-local managed state:

```text
projects/<project-slug>/.quality/schemas/**
projects/<project-slug>/.quality/tombstones/**
```

Project-local runtime state:

```text
projects/<project-slug>/.quality/locks/**
```

Runtime locks must be ignored by Git.

## 3. Configuration Model

### 3.1 Workspace Config

`.quality/workspace.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: QualityWorkspace
metadata:
  name: default
spec:
  projectsRoot: projects
  defaults:
    generatedOutputs:
      projectionsManaged: false
      exportsManaged: false
      reportsManaged: false
```

Workspace defaults may suggest generated-output behavior, but the effective project decision must be written into `project.yaml`.

### 3.2 Workspace Plugin Config

`.quality/plugins.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: WorkspacePlugins
spec:
  builtins:
    - dfmea
  enabledByDefault:
    - dfmea
```

This file keeps the historical `plugins.yaml` name because it stores active schema/resource plugins
backing implemented methods. Product-level method discovery is exposed through `quality method list`.

V1 supports built-in methods only:

- `dfmea` is an active quality method and active built-in schema plugin.
- `pfmea` is discoverable as a planned quality method, but it is not an active schema plugin and
  cannot be enabled until the PFMEA phase starts.

### 3.3 Project Config

`projects/<project-slug>/project.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: QualityProject
metadata:
  id: PRJ
  slug: cooling-fan-controller
  name: Cooling Fan Controller
spec:
  domains:
    dfmea:
      enabled: true
      root: ./dfmea
    pfmea:
      enabled: false
      root: ./pfmea
  generatedOutputs:
    projectionsManaged: false
    exportsManaged: false
    reportsManaged: false
```

Rules:

- project directory name is the V1 project identity.
- `metadata.slug` must equal the project directory name.
- `metadata.id` is always `PRJ`.
- project rename is out of V1 unless implemented by a migration command.

### 3.4 Loading Order

Every CLI command uses the same loading order:

1. Resolve workspace root from `--workspace` or upward discovery.
2. Load `.quality/workspace.yaml`.
3. Load `.quality/plugins.yaml`.
4. Resolve `--project <project-slug-or-directory>` against `projects/*/project.yaml`.
5. Load the selected `project.yaml`.
6. Load project-local schema snapshots from `projects/<slug>/.quality/schemas/<plugin-id>/`.
7. Load canonical tooling schemas from built-in plugins.
8. Compare project snapshot schema versions with tooling schema versions.
9. Load plugin collection declarations and path rules.
10. Load only resource files needed by the command.

## 4. Method And Plugin Contract

`quality_core.methods` is the product-level contract for quality methods such as DFMEA and PFMEA.
It exposes method ID, display name, active/planned status, command namespace, validators, projection
rebuilders, and the underlying schema plugin when implemented.

`quality_core.plugins` remains the lower-level schema/resource contract used by implemented
methods.

Each plugin declares:

- plugin ID.
- schema version.
- resource kinds.
- ID prefix registry.
- collection directories and file addressing.
- singleton resources.
- nested local ID rules.
- validators.
- projection builders.
- exporters.
- CLI command registration.
- Agent skill guidance.

Example plugin declaration:

```yaml
apiVersion: quality.ai/v1
kind: PluginDescriptor
metadata:
  pluginId: dfmea
  version: dfmea.ai/v1
spec:
  singletons:
    - kind: DfmeaAnalysis
      id: DFMEA
      file: dfmea.yaml
      schema: schemas/dfmea-analysis.schema.json
  collections:
    - kind: FailureMode
      directory: failure-modes
      fileName: "{id}.yaml"
      idPrefix: FM
      schema: schemas/failure-mode.schema.json
      titleField: metadata.title
```

Plugin enablement:

1. Validate plugin exists in built-in registry.
2. Create project domain directory if needed.
3. Copy schema snapshot into `projects/<slug>/.quality/schemas/<plugin-id>/`.
4. Update `project.yaml` domain enablement.
5. Initialize singleton resource if requested by command.

Plugin disablement:

- allowed only when the target domain has no source resources that would be orphaned.
- must not delete data silently.

## 5. Resource Model

### 5.1 Envelope

All file-backed resources use:

```yaml
apiVersion: quality.ai/v1
kind: FailureMode
metadata:
  id: FM-001
  title: Fan motor stalls
  labels:
    domain: dfmea
spec:
  functionRef: FN-001
  effectRefs:
    - FE-001
```

Required fields:

- `apiVersion`
- `kind`
- `metadata.id`
- `spec`

Optional fields:

- `metadata.title`
- `metadata.labels`
- `metadata.createdAt`
- `metadata.updatedAt`
- `status`, only when explicitly plugin-managed

### 5.2 Resource Categories

There are three ID/file categories.

| Category | Example | File rule | ID rule |
| --- | --- | --- | --- |
| Singleton resource | `project.yaml`, `dfmea.yaml` | fixed file name | fixed ID such as `PRJ`, `DFMEA` |
| Collection resource | `failure-modes/FM-001.yaml` | `{metadata.id}.yaml` | `<TYPE>-<SEQ>` |
| Nested local resource | `spec.links[].id` | no file path | unique inside parent resource |

Validation must apply the correct rule per plugin declaration.

### 5.3 DFMEA V1 Collections

DFMEA V1 uses:

```text
dfmea/
  dfmea.yaml
  structure/
    SYS-001.yaml
    SUB-001.yaml
    COMP-001.yaml
  functions/
    FN-001.yaml
  requirements/
    REQ-001.yaml
  characteristics/
    CHAR-001.yaml
  failure-modes/
    FM-001.yaml
  effects/
    FE-001.yaml
  causes/
    FC-001.yaml
  actions/
    ACT-001.yaml
  links/
    LINKS-001.yaml
  projections/
```

Cross-domain link sets live under:

```text
projects/<project-slug>/links/LINKS-001.yaml
```

## 6. ID Design

### 6.1 ID Format

V1 ordinary IDs:

```text
<TYPE>-<SEQ>
```

Rules:

- `TYPE` is declared by the plugin.
- `SEQ` is numeric, at least three digits.
- sequence expands after `999`.
- IDs are unique only inside one project.
- identical IDs may exist in different projects.
- deleted IDs are not reused.

Examples:

```text
FN-001
FM-007
ACT-021
STEP-001
PFM-004
```

Singleton IDs:

```text
PRJ
DFMEA
PFMEA
```

### 6.2 Allocation Algorithm

Allocation must run under the project write lock.

Algorithm:

1. Resolve project and plugin collection.
2. Acquire `projects/<slug>/.quality/locks/project.lock`.
3. Scan collection files matching `<TYPE>-*.yaml`.
4. Scan tombstones matching `projects/<slug>/.quality/tombstones/<TYPE>-*`.
5. Parse numeric suffixes.
6. Allocate `max + 1`.
7. Write new file atomically.
8. Validate targeted graph.
9. Release lock.

No V1 counter file is allowed.

### 6.3 Tombstones

Deletion creates a tombstone:

```text
projects/<project-slug>/.quality/tombstones/FM-007
```

Tombstone file content may be empty or minimal YAML:

```yaml
apiVersion: quality.ai/v1
kind: IdTombstone
metadata:
  id: FM-007
spec:
  deletedAt: "2026-05-03T00:00:00Z"
  resourceKind: FailureMode
```

Rules:

- tombstones are managed paths.
- tombstones are committed with project snapshots.
- tombstones are considered by ID allocation.
- tombstones are created for deleted IDs only.
- renumber does not create a tombstone for an ID still used by another object.

### 6.4 Renumber Repair

Commands:

```text
quality project id renumber --project cooling-fan-controller --from FM-008 --to FM-009
quality project repair id-conflicts --project cooling-fan-controller
```

Renumber must:

- acquire the project write lock.
- locate the resource currently using `--from`.
- validate `--to` prefix and availability.
- rename the file.
- update `metadata.id`.
- update references inside the same project.
- rebuild projections.
- validate the project.
- return changed files and references in JSON.

## 7. Storage And Atomic Writes

### 7.1 Resource Store Interface

Core storage API:

```python
class ResourceStore:
    def load(self, ref: ResourceRef) -> Resource: ...
    def list(self, selector: ResourceSelector) -> list[Resource]: ...
    def create(self, resource: Resource) -> WriteResult: ...
    def update(self, resource: Resource) -> WriteResult: ...
    def delete(self, ref: ResourceRef) -> WriteResult: ...
    def rename_id(self, old_id: str, new_id: str) -> WriteResult: ...
```

`ResourceRef` includes:

- workspace root.
- project slug.
- domain.
- kind.
- id.
- path.

### 7.2 Atomic Write Strategy

Write command flow:

1. Acquire project lock.
2. Load current graph.
3. Validate preconditions.
4. Prepare writes in temporary sibling files.
5. Replace files atomically where the platform supports it.
6. Re-read written files.
7. Run targeted validation.
8. Keep or remove rollback manifest.
9. Return stable JSON.

For multi-file operations, keep a rollback manifest until completion:

```text
projects/<slug>/.quality/tmp/<operation-id>/rollback.json
```

Runtime temp files must not be managed paths.

### 7.3 Locks

Project write lock:

```text
projects/<project-slug>/.quality/locks/project.lock
```

Rules:

- all writes acquire the lock.
- reads and queries do not require the lock.
- lock timeout returns `FILE_LOCKED`.
- stale lock may be broken only after process verification or documented timeout.
- lock files are ignored by Git.

## 8. Validation Design

### 8.1 Validation Pipeline

Validation pipeline:

```text
load config
  -> load schema snapshots
  -> scan resources
  -> schema validation
  -> ID/path validation
  -> graph validation
  -> methodology validation
  -> projection freshness checks
```

Validation returns all issues.

### 8.2 Issue Shape

```json
{
  "code": "REFERENCE_NOT_FOUND",
  "severity": "error",
  "message": "Referenced failure cause does not exist.",
  "path": "projects/cooling-fan-controller/dfmea/failure-modes/FM-001.yaml",
  "resourceId": "FM-001",
  "kind": "FailureMode",
  "field": "spec.causeRefs[0]",
  "suggestion": "Run dfmea query search or remove the invalid reference."
}
```

Severity:

- `error`: invalid or unsafe state.
- `warning`: operation can complete but follow-up is recommended.
- `info`: contextual detail.

### 8.3 Core Error Codes

V1 reserves:

```text
WORKSPACE_NOT_FOUND
PROJECT_NOT_FOUND
PROJECT_AMBIGUOUS
PROJECT_ADDRESS_MISMATCH
PLUGIN_NOT_FOUND
PLUGIN_NOT_ENABLED
SCHEMA_VERSION_MISMATCH
MIGRATION_REQUIRED
DUPLICATE_ID
ID_CONFLICT
ID_PREFIX_MISMATCH
RESOURCE_NOT_FOUND
REFERENCE_NOT_FOUND
INVALID_LINK_ENDPOINT
INVALID_RELATIONSHIP
VALIDATION_FAILED
PROJECTION_STALE
GIT_DIRTY
GIT_CONFLICT
RESTORE_PRECONDITION_FAILED
FILE_LOCKED
ATOMIC_WRITE_FAILED
```

### 8.4 ID And Path Validation

Rules:

- collection resources using `{id}.yaml` must have file basename equal to `metadata.id`.
- singleton resources must have the declared fixed file name and fixed ID.
- nested local IDs must be unique within parent resource.
- ID prefix must match kind declaration.
- duplicate IDs are errors within one project.

## 9. Traceability And Graph Design

### 9.1 Graph Inputs

The graph loader reads:

- project singleton.
- enabled domain singletons.
- enabled domain collection resources.
- domain-local link sets.
- project-level cross-domain link sets.
- project-local schema snapshots for validation context.

### 9.2 Link Rules

Same-aggregate references may live in `spec`:

```yaml
spec:
  functionRef: FN-001
  causeRefs:
    - FC-001
```

Cross-aggregate and cross-domain relationships use `TraceLinkSet`.

`TraceLinkSet` file:

```text
projects/<project-slug>/links/LINKS-001.yaml
```

Nested `LINK-<SEQ>` IDs are unique only inside the parent link set.

V1 does not support cross-project links.

### 9.3 Graph Index

In-memory indexes:

- `resourcesById`
- `resourcesByKind`
- `resourcesByPath`
- `linksBySource`
- `linksByTarget`
- `referencesById`
- `actionsByStatus`
- `risksByAP`

The graph index is rebuilt from source files and may be cached only as a projection.

## 10. Projection Design

### 10.1 Manifest

Each projection build writes:

```json
{
  "apiVersion": "quality.ai/v1",
  "kind": "ProjectionManifest",
  "projectSlug": "cooling-fan-controller",
  "projectRoot": "projects/cooling-fan-controller",
  "builtAt": "2026-05-02T13:00:00Z",
  "schemaVersions": {
    "core": "quality.ai/v1",
    "dfmea": "dfmea.ai/v1"
  },
  "sourceHash": "sha256:...",
  "sources": {
    "project.yaml": "sha256:...",
    ".quality/schemas/dfmea/plugin.yaml": "sha256:...",
    "dfmea/failure-modes/FM-001.yaml": "sha256:..."
  },
  "projections": {
    "dfmea/tree.json": "sha256:...",
    "dfmea/risk-register.json": "sha256:..."
  }
}
```

`sourceHash` covers all managed source inputs used by the projection, including schema snapshots.

### 10.2 Freshness Algorithm

A projection is stale when:

- a managed source file is added.
- a managed source file is removed.
- a managed source file is renamed.
- a managed source file hash differs.
- a project schema snapshot hash differs.
- schema version in manifest differs from loaded schema snapshots.

Query commands may use projections only when fresh. Otherwise they must rebuild or return `PROJECTION_STALE`, depending on command mode.

### 10.3 V1 Projections

DFMEA V1 projections:

- `dfmea/projections/tree.json`
- `dfmea/projections/risk-register.json`
- `dfmea/projections/action-backlog.json`
- `dfmea/projections/traceability.json`
- `dfmea/projections/manifest.json`

PFMEA may follow the same pattern when implemented.

## 11. Export Design

V1 export formats:

- Markdown review view.
- CSV table view.

Export rules:

- exports are generated views.
- exports are not source data.
- exports must include source IDs and paths.
- exports are not committed by default.
- project configuration can mark export profiles as managed.

Example config:

```yaml
spec:
  generatedOutputs:
    exportsManaged: true
    exportProfiles:
      - dfmea-review-md
      - dfmea-risk-csv
```

## 12. Git Command Design

### 12.1 Status

`quality project status --project <project>`

Returns:

- workspace root.
- project root.
- Git branch.
- dirty managed paths.
- stale projection state.
- validation summary.
- enabled plugins.
- configured generated outputs.

### 12.2 Snapshot

`quality project snapshot --project <project> --message <message>`

Flow:

1. Resolve project.
2. Require no unresolved Git conflicts.
3. Validate project.
4. Rebuild projections.
5. Regenerate configured exports/reports.
6. Stage managed source paths.
7. Stage project-local schema snapshots and tombstones.
8. Stage configured generated outputs.
9. Create commit.
10. Return commit hash and staged paths.

Snapshot must not stage runtime locks.

### 12.3 History

`quality project history --project <project>`

V1 implementation:

- filter Git commits by project managed paths.
- include commit hash, author, date, subject.
- list changed managed paths.
- parse changed resources when possible for object summaries.

### 12.4 Diff

`quality project diff --project <project> [--from <ref>] [--to <ref>]`

V1 implementation:

- use Git file diff as authoritative.
- add parsed object summaries when files are parseable resources.
- report raw paths for unparsable files.
- never hide Git conflicts.

### 12.5 Restore

`quality project restore --project <project> --ref <ref>`

Flow:

1. Resolve project.
2. Require no unresolved Git conflicts.
3. Require managed paths clean unless `--force-with-backup`.
4. Extract project managed non-generated paths from target ref:
   - `project.yaml`
   - `.quality/schemas/**`
   - `.quality/tombstones/**`
   - domain source YAML files
   - `links/**`
   - `evidence/**`
5. Do not restore `.quality/locks/**`.
6. Rebuild projections and configured exports.
7. Validate restored project.
8. Create forward restore commit.

Restore must never run `git reset --hard`.

## 13. CLI JSON Contract

All commands support JSON output.

Success:

```json
{
  "contractVersion": "quality.ai/v1",
  "ok": true,
  "command": "quality project validate",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "workspaceRoot": "...",
    "projectSlug": "cooling-fan-controller",
    "projectRoot": "projects/cooling-fan-controller",
    "schemaVersions": {
      "core": "quality.ai/v1",
      "dfmea": "dfmea.ai/v1"
    }
  }
}
```

Failure:

```json
{
  "contractVersion": "quality.ai/v1",
  "ok": false,
  "command": "dfmea analysis update",
  "data": null,
  "warnings": [],
  "errors": [
    {
      "code": "REFERENCE_NOT_FOUND",
      "severity": "error",
      "message": "Referenced failure cause does not exist.",
      "path": "projects/cooling-fan-controller/dfmea/failure-modes/FM-001.yaml",
      "field": "spec.causeRefs[0]",
      "suggestion": "Run dfmea query search or remove the invalid reference."
    }
  ],
  "meta": {
    "workspaceRoot": "...",
    "projectSlug": "cooling-fan-controller",
    "projectRoot": "projects/cooling-fan-controller"
  }
}
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success; warnings may exist. |
| `1` | Unexpected internal error. |
| `2` | Usage or argument error. |
| `3` | Validation failed with errors. |
| `4` | Workspace/project/config resolution error. |
| `5` | Git state error. |
| `6` | File write, lock, or atomicity error. |
| `7` | Schema/plugin version mismatch or migration required. |

## 14. DFMEA V1 Command Design

### 14.1 Init

```text
dfmea init --project <project>
```

Creates:

- `dfmea/dfmea.yaml`
- initial domain directories.
- project-local schema snapshot if plugin was not enabled.

### 14.2 Structure

Examples:

```text
dfmea structure add-system --project <project> --title "Fan Controller"
dfmea structure add-component --project <project> --parent SYS-001 --title "Motor Driver"
```

Writes `SYS-<SEQ>`, `SUB-<SEQ>`, or `COMP-<SEQ>` resources.

### 14.3 Analysis

Examples:

```text
dfmea analysis add-function --project <project> --component COMP-001 --title "Drive fan motor"
dfmea analysis add-failure-mode --project <project> --function FN-001 --title "Motor stalls"
dfmea analysis update-risk --project <project> --failure-mode FM-001 --severity 8 --occurrence 4 --detection 5
```

Writes functions, requirements, characteristics, failure modes, effects, causes, and actions.

### 14.4 Query And Context

Examples:

```text
dfmea query search --project <project> --keyword "motor"
dfmea context failure-chain --project <project> --failure-mode FM-001
```

Context output includes:

- requested root resource.
- related resources.
- links.
- source paths.
- projection freshness metadata.

### 14.5 Validate, Projection, Export

```text
dfmea validate --project <project>
dfmea projection rebuild --project <project>
dfmea export markdown --project <project> --profile review
```

Domain commands call shared core services for config, store, validation, projection, and output.

## 15. Agent Skill Contract

Skills must tell Agents:

- use CLI commands when available.
- prefer JSON output.
- do not edit projections or exports as source.
- do not rewrite Git history.
- inspect source files and validation output before proposing changes.
- use `quality project snapshot` for commits.
- use `quality project restore` instead of `git reset --hard`.
- use renumber repair commands for same-ID conflicts.

## 16. Testing Strategy

### 16.1 Unit Tests

Unit tests cover:

- workspace discovery.
- project config loading.
- plugin registry.
- schema snapshot comparison.
- ID allocation.
- tombstone behavior.
- path rule validation.
- atomic write helpers.
- projection freshness.
- CLI JSON output shapes.

### 16.2 Integration Tests

Integration tests use temporary Git repositories.

Required cases:

- workspace init.
- project create.
- plugin enable.
- DFMEA init.
- resource create/update/delete.
- tombstone committed by snapshot.
- duplicate ID detection.
- renumber updates references.
- projection stale after source edit.
- projection stale after schema snapshot edit.
- snapshot stages correct managed paths.
- restore restores source, schemas, tombstones, links, evidence.
- restore excludes locks and rebuilds generated outputs.

### 16.3 Golden Fixtures

Keep small fixture projects:

```text
tests/fixtures/projects/dfmea-minimal/
tests/fixtures/projects/dfmea-with-links/
tests/fixtures/projects/dfmea-stale-projection/
tests/fixtures/projects/dfmea-id-conflict/
```

Golden JSON outputs should be stable for Agent consumption.

## 17. Implementation Phases

### Phase A: Core Workspace And File Store

- workspace discovery.
- project create/load.
- project-local `.quality/` directories.
- plugin registry.
- resource envelope parsing.
- atomic write and lock helpers.
- stable JSON output.

### Phase B: ID And Validation Foundation

- prefix registry.
- ID allocation and tombstones.
- path rule validation.
- JSON Schema validation.
- issue model and exit codes.

### Phase C: DFMEA Baseline

- DFMEA plugin descriptor.
- schemas for DFMEA core resources.
- DFMEA init.
- structure/function/failure-chain commands.
- DFMEA query/context.
- DFMEA validation.

### Phase D: Projection And Export

- graph loader.
- projection manifest.
- freshness checks.
- risk register/action backlog/tree projections.
- Markdown and CSV exports.

### Phase E: Git Version Commands

- status.
- snapshot.
- history.
- diff.
- restore.
- hook installer.

### Phase F: PFMEA Initial Slice

- PFMEA plugin descriptor.
- PFMEA source model.
- PFMEA validation baseline.
- DFMEA to PFMEA link support.

## 18. Open Implementation Decisions

Only one product-scope question remains:

- first PFMEA milestone depth.

Implementation-level decisions to settle during Phase A:

- exact YAML parser and formatting policy.
- exact JSON Schema library.
- lock timeout default.

These decisions must not change the architecture contracts in this document.
