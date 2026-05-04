# Local-first Quality Assistant Architecture

> Status: target architecture baseline
>
> Scope: OpenCode-bound quality management assistant built around quality methods, Git-native
> structured files, stable Python CLI contracts, and OpenCode/OpenCode UI as the required host.
>
> Supersedes the previous platform-service direction. The old DFMEA CLI-first architecture remains useful historical context, but this document is the new product architecture target.

## 1. Architecture Positioning

This product is an OpenCode-bound, local-first quality management assistant.

It is not a centralized FMEA platform, not a server-first workflow system, not an OpenCode-core
business runtime, and not a database-backed web application. OpenCode is intentionally the product
host, while Python remains the quality engine:

```text
Human quality work
  -> OpenCode / OpenCode UI host
  -> OpenCode plugin, commands, and skills
  -> quality CLI contract
  -> quality engine and quality domain plugins
  -> Git-native quality project files
  -> validation / projection / exports
  -> Git history / team sync / restore
```

The architecture is built from these mechanisms:

- Repository-native source model: quality data lives as structured files in a Git repository, not in an opaque database.
- Schema-defined collections: each quality plugin declares its object kinds, fields, path rules, validation rules, and editor hints.
- Resource envelope: every source object uses the same `apiVersion / kind / metadata / spec` shape for versioning, discovery, and validation.
- Declarative state plus reconciliation: source files describe quality facts; CLI commands validate them and regenerate projections, exports, and reports.
- Local graph index: traceability is rebuilt from readable files, so Agent workflows can navigate the quality graph without scanning every file manually.
- Reviewable changes: Agent or UI edits should be converted into small file changes, stable CLI
  results, and Git commits that humans can review and restore.
- OpenCode boundary: OpenCode is the required Agent host, but OpenCode plugin/UI code must not own
  quality source data or domain write rules.

The resulting product architecture is:

```text
Git repository as quality workspace
  + project-scoped quality domains
  + plugin-owned resource schemas
  + headless Python quality engine
  + CLI as the stable engine/write interface
  + OpenCode plugin and UI host
  + generated views as disposable projections
```

## 2. Core Product Decisions

| Decision | Target |
| --- | --- |
| Product shape | OpenCode-bound personal and small-team quality assistant |
| Primary user entry | OpenCode / OpenCode UI |
| UI | OpenCode UI host now; future second-stage UI should still use engine contracts |
| Business boundary | `Project` |
| Domain model | DFMEA, PFMEA, Control Plan, 8D, and future quality plugins under a project |
| Source of truth | Git-friendly structured text files |
| Preferred source format | YAML for human/Agent readability; JSON allowed for generated or strict machine payloads |
| Export formats | Markdown, CSV, HTML, PDF as generated views |
| Version and sync | Git |
| Quality project repository | One Git repository can contain multiple projects by default; one-project repositories are a valid subset |
| Snapshot boundary | Project by default; workspace-level snapshot is an explicit batch operation |
| ID strategy | Project-scoped readable IDs with node-type prefixes |
| Conflict strategy | Same-object conflicts are resolved by human review with Agent assistance |
| Database | No SQLite in the target architecture |
| Standard write path | CLI commands, not manual file editing |
| Standard read path | CLI query/projection plus direct file reads for Agent context |
| Host integration | OpenCode plugin over the stable CLI/shared-core contract |

SQLite is intentionally removed. It solved local concurrent writes, but it conflicts with the new Git-native direction because it is binary, hard to diff, hard to merge, and not naturally understandable to Agents during history review.

## 3. Repository Boundary

There are two different repository types.

### 3.1 Tooling Repository

The tooling repository is where this project is developed. It produces the OpenCode plugin, Python
engine, CLI entrypoints, quality domain methods, skills, schemas, tests, and UI host.

```text
opencode-quality-assistant/
  plugin/                    # OpenCode npm plugin and opencode-quality CLI
  engine/
    src/
      quality_core/
      quality_methods/
        dfmea/
        pfmea/               # placeholder for future method
      quality_adapters/
        cli/                 # active CLI adapter entrypoints and command wiring
          dfmea_commands/
        opencode/            # generated OpenCode templates and installer
    plugins/
      dfmea/
      pfmea/                 # placeholder only
  ui/                         # checked-in OpenCode UI host for testing and future UI work
  docs/
  engine/tests/
```

It contains:

- CLI implementation.
- quality plugin code.
- OpenCode plugin and adapter code.
- Agent skill documents.
- schema definitions.
- tests.
- architecture and design docs.

This repository is for product development.

### 3.2 Quality Project Repository

A quality project repository is where real user/team quality data lives.

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

It contains:

- project metadata.
- DFMEA / PFMEA / Control Plan source files.
- evidence references.
- generated exports and reports.
- Git history.

This repository is the user's working asset and the team synchronization boundary. By default, a quality project repository may contain multiple projects. A repository containing exactly one project is a valid special case, not a separate architecture.

## 4. Workspace And Project Model

The workspace is only a local collection of projects. The project is the business boundary.

```text
Workspace
  -> Project
      -> Quality Domains
          -> DFMEA
          -> PFMEA
          -> Control Plan
          -> 8D
          -> Evidence
          -> Reports
```

Default workspace layout:

```text
quality-workspace/
  .quality/
    workspace.yaml
    plugins.yaml
  projects/
    <project-slug>/
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

Example `project.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: QualityProject
metadata:
  id: PRJ
  slug: cooling-fan-controller
  name: Cooling Fan Controller
spec:
  customer: Example OEM
  productLine: Thermal Management
  partNumber: CF-CTRL-001
  phase: design
  owners:
    - quality
    - design
  domains:
    dfmea:
      enabled: true
      root: ./dfmea
    pfmea:
      enabled: true
      root: ./pfmea
    controlPlan:
      enabled: false
      root: ./control-plan
```

Project rules:

- Git snapshot default boundary is one project directory.
- One Git repository may contain multiple project directories under `projects/`.
- Workspace-level Git operations must make the affected project set explicit.
- Cross-domain links are allowed inside the same project.
- Workspace-level commands may batch across projects, but project commands must never silently mutate another project.
- Project `metadata.id` is the singleton ID `PRJ` inside that project directory.
- Project directory name is the stable V1 project identity and namespace for contained resource IDs.
- `metadata.slug` must match the project directory name in V1.
- Project rename is out of V1 scope unless implemented by an explicit migration command.
- Resource IDs inside one project do not embed project identity.

## 5. Quality Method Model

DFMEA, PFMEA, Control Plan, and future quality modules are independent quality methods.

Each method owns:

- CLI namespace.
- Agent skill.
- resource kinds.
- schemas.
- validators.
- query adapters.
- projections.
- export layouts.

Example:

```text
quality-method-dfmea
  CLI: dfmea ...
  Skill: dfmea/SKILL.md
  Kinds:
    DfmeaAnalysis
    StructureNode
    Function
    Requirement
    Characteristic
    FailureMode
    FailureEffect
    FailureCause
    Action

quality-method-pfmea
  CLI: pfmea ...
  Skill: pfmea/SKILL.md
  Kinds:
    PfmeaAnalysis
    ProcessFlow
    ProcessStep
    ProcessFunction
    ProcessFailureMode
    ProcessEffect
    ProcessCause
    PreventionControl
    DetectionControl
    Action
```

OpenCode is one possible Agent host. Quality methods provide domain intelligence and safe file
operations through the headless engine. Any future OpenCode, OpenCodeUI, IDE, or CI integration is
an adapter over the same CLI/shared-core contracts.

Implementation note: `quality_core.methods` is the product-level discovery registry. The lower-level
`quality_core.plugins` contract remains responsible for method schema snapshots, resource
collections, path rules, and project enable/disable semantics.

### 5.1 Host Adapter Boundary

Host adapters are optional integration layers. They translate a host environment into the stable
quality engine contract, but they do not own quality data or implement independent write rules.

Adapter examples:

- `quality_adapters.cli`: active console-script adapter and Typer command wiring for `quality` and
  `dfmea`; PFMEA command wiring is deferred.
- `quality_adapters.opencode`: installs project-local OpenCode commands, skills, and plugin hooks
  that orchestrate the Python CLI/shared-core contract.
- `quality_adapters.opencode_ui`: connects a local UI to schema-driven read/edit workflows.
- `quality_adapters.ci`: runs validation, projection freshness checks, and export checks in CI.
- future IDE or web-shell adapters.

Adapter rules:

- Adapters may call active CLI commands such as `quality` and `dfmea` and parse `quality.ai/v1`
  JSON. Future PFMEA adapters must follow the same contract after PFMEA is implemented.
- Adapters may import shared Python core only when they preserve the same validation, locking,
  resource path, and Git contracts as the CLI.
- Adapters must not directly invent resource paths, allocate IDs, write YAML, or bypass project
  locks.
- Adapters must not make OpenCode, OpenCodeUI, or any other host a required runtime dependency for
  the core engine.
- OpenCode plugin hooks may inject session context and convenience command/tool wrappers, but those
  hooks must call `quality`, active method CLIs such as `dfmea`, or shared Python core. They must
  not implement DFMEA/PFMEA resource writes, ID allocation, schema validation, projection rebuilds,
  or Git restore semantics.

### 5.2 Method Discovery And Schema Plugin Enablement

V1 uses built-in quality methods shipped with the tooling repository.

Method discovery rules:

- `quality method list` reports implemented and planned quality methods.
- `dfmea` is active for V1.
- `pfmea` is discoverable as a planned placeholder but is not an active schema plugin or CLI
  namespace until its implementation phase starts.
- `quality plugin list` reports active built-in schema plugins and project-enabled state for those
  implemented methods.
- `quality plugin enable <plugin-id> --project <project>` enables the underlying schema/resource
  plugin for an implemented method.
- `quality plugin disable <plugin-id> --project <project>` disables an implemented method only when
  no source resources would be orphaned.
- External third-party plugin installation is out of V1 scope.

Future versions may support Python package entry points or method directories, but V1 must not
require that mechanism to start implementation.

### 5.3 Schema Source And Project Schema Snapshots

The tooling repository owns canonical plugin schemas.

Each project stores schema snapshots under `projects/<project-slug>/.quality/schemas/` for reproducibility:

```text
projects/<project-slug>/.quality/
  schemas/
    dfmea/
      plugin.yaml
      failure-mode.schema.json
      action.schema.json
    pfmea/
      plugin.yaml
```

Schema rules:

- Tooling schemas are the implementation source of truth.
- Project schema snapshots are pinned copies used to validate historical project data consistently.
- Project schema snapshots are read-only from normal user workflows.
- V1 does not allow project-local schema overrides.
- If tooling schema version and project schema snapshot version differ, commands must report `SCHEMA_VERSION_MISMATCH` unless a migration command is explicitly invoked.
- Plugin enable copies the plugin schema snapshot into `projects/<project-slug>/.quality/schemas/<plugin-id>/`.
- Plugin migration updates source files and the project schema snapshot together.

### 5.4 Configuration Loading Order

All CLI and adapter write paths must load configuration in the same order. There must be no hidden
database state and no plugin-specific alternate resolution path.

Loading order:

1. Resolve workspace root from `--workspace <path>` or upward discovery from the current directory.
2. Load and validate `.quality/workspace.yaml`.
3. Load `.quality/plugins.yaml` to determine workspace-known plugins and defaults.
4. Resolve `--project <project-slug-or-directory>` against `projects/*/project.yaml`.
5. Load the selected project's `project.yaml`, including `spec.domains`.
6. Load enabled plugin schema snapshots from `projects/<project-slug>/.quality/schemas/<plugin-id>/`.
7. Load canonical tooling schemas for the running CLI version.
8. Compare project schema snapshot versions with tooling schema versions.
9. Load plugin collection declarations and path rules.
10. Scan only managed project paths required by the command.

Failure rules:

- Missing workspace config fails with `WORKSPACE_NOT_FOUND`.
- Missing or ambiguous project identity fails with `PROJECT_NOT_FOUND` or `PROJECT_AMBIGUOUS`.
- Enabled plugin without a schema snapshot fails with `PLUGIN_NOT_ENABLED` or `SCHEMA_VERSION_MISMATCH`, depending on the state.
- Schema version drift fails with `SCHEMA_VERSION_MISMATCH` unless the invoked command is an explicit migration command.
- Commands must include the resolved workspace root, project slug, project root, and schema versions in JSON `meta` when relevant.

## 6. Resource File Model

All source data uses a uniform resource envelope:

```yaml
apiVersion: quality.ai/v1
kind: FailureMode
metadata:
  id: FM-007
  title: Fan motor stalls
  labels:
    domain: dfmea
spec:
  functionRef: FN-012
  effectRefs:
    - FE-003
  causeRefs:
    - FC-005
  severity: 8
  occurrence: 4
  detection: 5
  ap: H
```

Envelope fields:

- `apiVersion`: schema family and version.
- `kind`: resource type.
- `metadata`: identity, title, ownership, labels, timestamps if needed.
- `spec`: domain-specific desired/source data.
- `status`: optional generated status. Source files should avoid committed `status` unless the plugin explicitly marks it as managed.

Resource rules:

- `metadata.id` is the stable object identity.
- Object IDs are unique within the project directory, not globally across all projects.
- File path is an address, not the identity.
- Collection resources use `{metadata.id}.yaml` as the default file name.
- Singleton resources such as `project.yaml`, `dfmea.yaml`, and `pfmea.yaml` use plugin-declared fixed file names and fixed singleton IDs.
- Nested resources such as entries inside a `TraceLinkSet` may have local IDs that are unique only within their parent resource.
- Resource content must validate against its plugin schema.
- Generated fields must either live in projections/exports or be clearly marked as managed.
- Manual edits are allowed only if they pass validation, but CLI remains the recommended write path.

## 7. DFMEA Project Layout

DFMEA is project-scoped.

```text
projects/<project-slug>/dfmea/
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
    tree.json
    risk-register.json
    action-backlog.json
```

Example `dfmea.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: DfmeaAnalysis
metadata:
  id: DFMEA
  name: Cooling Fan Controller DFMEA
spec:
  methodology: AIAG-VDA
  scope: Design failure analysis for fan controller
  structureRoot: ./structure
```

DFMEA source objects are split by object kind to reduce Git conflict size and improve Agent navigation.

## 8. PFMEA Project Layout

PFMEA is also project-scoped and can reference DFMEA objects in the same project.

```text
projects/<project-slug>/pfmea/
  pfmea.yaml
  process-flow/
    FLOW-001.yaml
  process-steps/
    STEP-001.yaml
  functions/
    PFN-001.yaml
  failure-modes/
    PFM-001.yaml
  effects/
    PFE-001.yaml
  causes/
    PFC-001.yaml
  controls/
    PC-001.yaml
    DC-001.yaml
  actions/
    PACT-001.yaml
  projections/
    process-map.json
    risk-register.json
    action-backlog.json
```

Example `pfmea.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: PfmeaAnalysis
metadata:
  id: PFMEA
  name: Cooling Fan Controller PFMEA
spec:
  methodology: AIAG-VDA
  scope: Manufacturing process failure analysis
  processFlowRoot: ./process-flow
```

PFMEA plugin rules must not assume DFMEA exists, but when DFMEA exists it may reference design characteristics, effects, causes, and actions.

## 9. Links And Traceability

Cross-object relationships are first-class resources.

For same-aggregate relationships, references can live inside `spec`:

```yaml
spec:
  functionRef: FN-001
  causeRefs:
    - FC-001
```

For cross-aggregate or cross-domain relationships, use link resources:

Example `projects/<project-slug>/links/LINKS-001.yaml`:

```yaml
apiVersion: quality.ai/v1
kind: TraceLinkSet
metadata:
  id: LINKS-001
spec:
  links:
    - id: LINK-001
      from:
        domain: dfmea
        kind: Characteristic
        id: CHAR-001
      to:
        domain: pfmea
        kind: ProcessStep
        id: STEP-001
      relationship: controls
```

Traceability rules:

- Links must validate both endpoint existence and allowed relationship type.
- Same-aggregate references may be embedded in `spec`.
- Cross-aggregate references must be link resources unless the plugin schema explicitly defines a stable inline reference field.
- Cross-domain references must be link resources.
- Cross-domain link resources must live under the project-level `projects/<project-slug>/links/` directory.
- Domain-local cross-aggregate link resources may live under `projects/<project-slug>/<domain>/links/`.
- A cross-domain relationship must be stored once. It must not be duplicated under both domain directories.
- Cross-project links are out of V1 scope.
- Links must be queryable by source, target, kind, and domain.
- `TraceLinkSet` is the file-backed resource. `LINK-<SEQ>` entries inside `spec.links` are local IDs within that link set and are not independently addressed by file path.

## 10. CLI Architecture

The CLI is the stable write interface.

Namespace contract:

| Namespace | Owner | V1 commands | Later scope |
| --- | --- | --- | --- |
| `quality workspace` | workspace lifecycle and discovery | `init`, `status`, `install-hooks` | workspace batch maintenance |
| `quality project` | project metadata, validation orchestration, Git operations, generated-output orchestration | `create`, `list`, `status`, `validate`, `snapshot`, `history`, `diff`, `restore`, `export`, `projection` | richer semantic history and merge helpers |
| `quality plugin` | built-in plugin enablement | `list`, `enable`, `disable` | external plugin package installation |
| `dfmea` | DFMEA domain modeling and queries | `init`, `structure`, `analysis`, `query`, `context`, `trace`, `validate`, `projection`, `export` | advanced methodology assistants |
| `pfmea` | PFMEA domain modeling and queries | none; deferred placeholder | deeper DFMEA/PFMEA synchronization |
| `control-plan` | Control Plan domain modeling | none in required V1 | future plugin CLI |

CLI responsibilities:

- Resolve workspace and project context.
- Allocate IDs.
- Write resource files atomically.
- Enforce schema validation and domain invariants.
- Rebuild projections.
- Generate exports.
- Prepare Git snapshots.
- Return stable JSON output for Agents.

The CLI must not require a service process. It should run in local shells used by OpenCode and other Agents.

### 10.1 CLI Namespace Boundary

V1 uses a split namespace with one shared project/workspace CLI and domain CLIs.

Shared `quality` commands own cross-domain or project-level operations:

- workspace discovery and initialization.
- project create/list/status/validate.
- project snapshot/history/diff/restore.
- project-wide projection rebuild/export orchestration.
- plugin list/enable/disable.

Domain commands own domain-specific modeling operations:

- `dfmea structure`, `dfmea analysis`, `dfmea query`, `dfmea context`, `dfmea trace`, `dfmea validate`, `dfmea projection`, `dfmea export`.
- PFMEA domain commands are deferred until the PFMEA plugin phase is restarted.

Git operations are not owned by domain CLIs in V1. There is no `dfmea git` command in the V1
contract, and PFMEA has no active command surface yet.

Domain-specific snapshots are expressed through project commands with domain filters:

```text
quality project snapshot --project cooling-fan-controller --domain dfmea
quality project diff --project cooling-fan-controller --domain pfmea
quality project history --project cooling-fan-controller --domain dfmea
```

Domain CLI aliases may be added later, but if added they must be thin aliases to `quality project ... --domain <domain>` and must not implement separate Git semantics.

### 10.2 Project Addressing

Commands that operate on a project must resolve a project directory.

Rules:

- `--project <value>` accepts the project directory name or `metadata.slug`.
- Project slug must be unique within one workspace.
- Project object ID is the singleton `PRJ` inside that project, so it is not used for cross-project addressing.
- If both directory name and slug are provided through different options in a future command, they must resolve to the same project or the command fails with `PROJECT_ADDRESS_MISMATCH`.
- Commands locate the workspace by walking upward from the current directory until `.quality/workspace.yaml` or `.git/` plus `.quality/` is found.
- If multiple workspaces could match, the nearest parent workspace wins.
- A command may accept `--workspace <path>` to bypass upward discovery.
- If a project cannot be resolved uniquely, the command fails with `PROJECT_NOT_FOUND` or `PROJECT_AMBIGUOUS`.

### 10.3 CLI JSON And Exit Code Contract

All CLI commands must support stable JSON output.

Success shape:

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
    "projectRoot": "projects/cooling-fan-controller"
  }
}
```

Error shape:

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
      "path": "projects/cooling-fan-controller/dfmea/failure-modes/FM-....yaml",
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

Exit code rules:

| Code | Meaning |
| --- | --- |
| `0` | Success. Warnings may be present. |
| `1` | Unexpected internal error. |
| `2` | Usage or argument error. |
| `3` | Validation failed with one or more `error` issues. |
| `4` | Workspace/project/config resolution error. |
| `5` | Git state error, dirty worktree, merge conflict, or restore precondition failure. |
| `6` | File write/lock/atomicity error. |
| `7` | Schema/plugin version mismatch or migration required. |

Severity rules:

- `error`: operation cannot be considered valid or safe.
- `warning`: operation can complete, but follow-up is recommended.
- `info`: contextual note for humans or Agents.

Stale projection is a `warning` for source-writing commands and an `error` only for commands that explicitly require fresh projection data and cannot rebuild it.

### 10.4 Common Error Codes

V1 must reserve these error codes:

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

## 11. Agent Skill Architecture

Skills are the contract between human/Agent intent and the CLI/schema layer. They turn a task into a deterministic CLI sequence with safety constraints and recoverable error paths. Skills are not a hidden data layer and not a substitute for CLI behavior; they are the interface that lets Agents use the CLI safely.

Three global invariants apply across all skills:

- Do not mutate source files when a CLI command exists for the operation.
- Do not treat generated views (`exports/`, `projections/`, `reports/`) as source data.
- Do not rewrite Git history automatically; restore must produce a forward commit.

Each skill may extend these with its own domain-specific Forbidden list.

### 11.1 Role of Skills

A skill carries eight responsibilities:

| Responsibility | Description |
| --- | --- |
| Intent recognition | Decide which skill should own a user task |
| Routing | Map a business task to a specific CLI command |
| Workflow orchestration | Sequence multi-command operations |
| Safety guardrails | Encode forbidden actions and pre-conditions |
| Error diagnostics | Map command failure to a recovery path |
| Cross-skill hand-off | Define when to delegate to a sibling skill |
| Domain knowledge | Carry the minimum business vocabulary the Agent needs |
| Evolution anchor | Pin to CLI/schema versions so changes propagate |

Skills are not optional product polish. They are the primary mechanism that prevents Agents from mutating source files without validation, and the primary way new domains are absorbed without retraining the Agent.

### 11.2 Skill Layers

The skill set is organized in four layers:

```text
Layer 0  Root SKILL.md                   entry router
Layer 1  Orchestration skills            quality, trace
Layer 2  Domain skills                   dfmea, pfmea, control-plan, ...
Layer 3  Helper skills                   git, edit (optional)
```

- L0 is the mandatory entry. Every Agent task must consult the root before dispatching.
- L1 owns cross-cutting concerns that span multiple domains.
- L2 owns one quality domain each. They are the natural units for plugin packaging.
- L3 is optional and reserved for shared helpers.

A skill at a higher layer may delegate down. A skill at a lower layer must not call up.

### 11.3 V1 Skill Inventory

V1 must ship:

- `SKILL.md` (root, L0)
- `quality/SKILL.md` (project/workspace/plugin management, L1)
- `dfmea/SKILL.md` (DFMEA domain, L2)

V1 should ship if feasible:

- `trace/SKILL.md` (cross-domain links, L1)
- `pfmea/SKILL.md` (PFMEA domain, L2)

V2 candidates:

- `control-plan/SKILL.md`
- `8d/SKILL.md`
- `evidence/SKILL.md`
- helper skills

Pre-V1 SQLite-era DFMEA skill files are removed and not migrated.

### 11.4 Skill File Contract

Every skill file uses the same shape so Agents and lint tools can parse it.

#### 11.4.1 Frontmatter

```yaml
---
name: <unique-skill-id>
apiVersion: quality.ai/v1
layer: L0 | L1 | L2 | L3
scope: <one-line description of what this skill owns>
trigger:
  keywords: [...]
  cli_namespace: <quality|dfmea|pfmea|...>
edits: [list of file globs this skill is allowed to mutate]
delegates_to: [list of skill ids this skill may hand off to]
requires_skills: [list of skill ids that must already be loaded]
references:
  schemas: [list of schema files]
  errorCodes: [list of codes from errors.yaml]
deprecated: false
---
```

#### 11.4.2 Required Body Sections

Every skill must include the following sections in order:

1. `Identity` — one-paragraph self-description.
2. `When to Use` — explicit routing conditions.
3. `Forbidden` — disallowed actions, four to ten entries.
4. `Command Catalog` — table of CLI commands this skill orchestrates.
5. `Workflows` — multi-step recipes (see 11.4.3).
6. `Errors` — error-code-to-recovery-action mapping.
7. `Hand-off` — when to delegate to other skills.
8. `Glossary` — domain terms; optional for L0/L1, required for L2.

#### 11.4.3 Workflow Sub-section Structure

Every workflow uses the same five-field shape:

```text
### Workflow X — <name>
When:      <trigger condition>
Inputs:    <data the user must supply>
Steps:     <numbered command sequence with expected JSON>
Errors:    <relevant codes from errors.yaml>
Done When: <success criterion>
```

Workflows must include the full expected JSON output for each command. Truncated examples are not acceptable in V1.

### 11.5 Supporting Artifacts

Three machine-readable artifacts back the skill system. They live in the tooling repository under `.quality-spec/` and are required for V1.

#### 11.5.1 commands.yaml

Source of truth for every CLI command. Mirrors the namespace contract in §10 and the JSON envelope in §10.3.

```yaml
apiVersion: quality.ai/v1
kind: CommandCatalog
spec:
  - command: quality.project.create
    cli: quality project create
    args:
      - name: slug
        required: true
      - name: name
        flag: --name
        required: false
    exitCodes: [0, 2, 4, 6]
    output: jsonEnvelope
    skills: [quality-project]
```

Skill lint validates that every command referenced in any skill exists here.

#### 11.5.2 errors.yaml

Source of truth for every error code reserved in §10.4 plus any codes added later.

```yaml
apiVersion: quality.ai/v1
kind: ErrorCatalog
spec:
  - code: PROJECT_NOT_FOUND
    severity: error
    messageTemplate: "Cannot resolve project {value} from current directory"
    suggestedAction: "Run quality project list, or pass --project <slug> explicitly"
    surfacedBy:
      - quality.project.status
      - quality.project.snapshot
      - quality.project.validate
```

Skill lint validates that every error code referenced in any skill exists here.

#### 11.5.3 glossary.yaml

Domain term dictionary used to keep skill prose consistent.

```yaml
apiVersion: quality.ai/v1
kind: Glossary
spec:
  - term: AP
    domain: dfmea
    expansion: Action Priority
    definition: AIAG-VDA risk priority indicator derived from S, O, D
  - term: FN
    domain: dfmea
    expansion: Function
```

Glossary entries are referenced from skill `Glossary` sections and rendered into prompts when an Agent loads a skill.

### 11.6 Evolution and Versioning

- Skill `apiVersion` must match the active schema and commands `apiVersion`.
- Adding a CLI flag does not break old skills, but the flag is unavailable until a skill mentions it.
- Renaming or removing a CLI command requires updating every skill that references it; CI lint blocks merges otherwise.
- A major schema version bump produces a new skill set; old skills carry `deprecated: true` and remain alongside the new ones for one minor cycle before deletion.

### 11.7 Lint and Tests

A new CLI command, `quality lint skills`, runs the static checks below. V1 must implement checks 1 through 5. Replay and prompt-routing tests are V2.

| # | Check | V1 |
| --- | --- | --- |
| 1 | Frontmatter completeness | yes |
| 2 | Referenced commands exist in `commands.yaml` | yes |
| 3 | Referenced error codes exist in `errors.yaml` | yes |
| 4 | Referenced schema fields exist in schema files | yes |
| 5 | `delegates_to` targets are real skills | yes |
| 6 | Workflow replay against fixture project | V2 |
| 7 | Prompt-routing accuracy with curated user phrases | V2 |

`quality lint skills` returns the standard JSON envelope so it can run in CI.

### 11.8 Registry and Discovery

The tooling repository contains a single registry file used by Agents and lint tools.

```yaml
# .skills.yaml
apiVersion: quality.ai/v1
kind: SkillRegistry
spec:
  root: ./SKILL.md
  skills:
    - id: quality-project
      path: ./quality/SKILL.md
      layer: L1
      version: v1
    - id: trace
      path: ./trace/SKILL.md
      layer: L1
      version: v1
    - id: dfmea
      path: ./dfmea/SKILL.md
      layer: L2
      version: v1
    - id: pfmea
      path: ./pfmea/SKILL.md
      layer: L2
      version: v1
```

Loading flow:

1. Agent reads `.skills.yaml`.
2. Agent reads the root skill.
3. Root skill matches user intent and dispatches to an L1 or L2 skill.
4. The dispatched skill may invoke `delegates_to` to hand off downstream.

Skills must not be loaded out of order. A V1 Agent integration that bypasses the root is non-conforming.

## 12. Optional UI Adapter

A UI is an optional future local editing and review surface. The current checked-in OpenCode UI tree
is a host for manual testing and OpenCode workflows, not the target product UI architecture. Future
UI work must be a deliberate adapter task against the Python CLI/shared-core contracts.

It must not become a separate source of truth. It reads and writes through the same CLI/plugin
contracts. V1 UI adapter writes must call the CLI or a shared plugin core used by the CLI; the UI
adapter must not implement an independent writer.

Expected UI surfaces:

- project selector.
- DFMEA/PFMEA structure tree.
- resource detail editor generated from schema.
- Agent conversation panel.
- proposed change review.
- Git status/history/diff view.
- export/report preview.

UI rule:

```text
The UI adapter is a workspace front-end, not a platform back-end.
```

It may embed OpenCode workflows, but source data remains in the project Git repository. A copied or
unintegrated external UI tree is not part of the target architecture.

## 13. Validation Architecture

Validation has three layers.

### 13.1 Schema Validation

Each resource kind has an executable schema.

V1 schema language:

- JSON Schema is the V1 structural schema language.
- Graph and methodology rules live in plugin validators.
- Richer rule languages may be evaluated later, but V1 implementation must not depend on them.

Schema validation checks:

- required fields.
- enum values.
- primitive types.
- object shape.
- version compatibility.

### 13.2 Graph Validation

Graph validation checks:

- referenced object exists.
- relationship type is allowed.
- DFMEA/PFMEA hierarchy is valid.
- no orphan objects.
- no invalid cross-domain links.

### 13.3 Methodology Validation

Methodology validation checks quality rules:

- AIAG-VDA required fields.
- severity/occurrence/detection/AP consistency.
- action status and ownership rules.
- DFMEA to PFMEA trace coverage.
- Control Plan linkage if enabled.

Validation commands must return complete issue lists, not stop at the first error.

### 13.4 Validation Severity Model

Validation issues use three severities.

| Severity | Meaning | Command behavior | Examples |
| --- | --- | --- | --- |
| `error` | Source state is invalid, unsafe, or cannot be used for the requested operation. | Validation command exits `3`; write/snapshot/restore commands fail. | duplicate ID, missing required field, invalid link endpoint, schema version mismatch |
| `warning` | Source state is usable, but follow-up is needed or generated views are not current. | Command may exit `0` if the requested operation can complete safely; issue appears in `warnings`. | stale projection after a source write, unmanaged export out of date, optional trace coverage gap |
| `info` | Contextual note for humans or Agents. | Command exits according to errors/warnings; note appears as informational issue or metadata. | generated files skipped by config, query used direct source scan instead of projection |

Severity must be stable enough for Agents to branch on it. A validator may add new issue codes, but it must not downgrade a correctness failure to `warning` just to allow a snapshot.

## 14. Projection And Export Architecture

Projections are generated read models.

```text
source YAML files
  -> in-memory resource graph
  -> projections/*.json
  -> exports/*.md / *.csv / *.html
  -> reports/*
```

Projection examples:

- structure tree.
- risk register.
- action backlog.
- traceability matrix.
- AP summary.
- design-to-process coverage.

Projection rules:

- Projections are disposable and rebuildable.
- Projections must contain enough source references for traceability.
- Projections may be committed when useful for review, but they are not authoritative.
- Export files are generated views and must never be used as write input.
- Projection builds must write a manifest containing source hashes, schema versions, build time, project slug, and project root.
- Query commands may use projections only when the manifest proves they are fresh for the current source state.
- Freshness is determined by both a total source hash and per-source file hashes.
- If any managed source file or project schema snapshot is added, removed, renamed, or hash-mismatched, the projection is stale.
- A stale projection must be rebuilt before it can be used as an authoritative query acceleration path.

### 14.1 Managed Generated Output Policy

Source resources are always managed by project snapshots. Generated projections, exports, and reports are managed only when project configuration opts them in.

Default V1 policy:

- `project.yaml`, domain source YAML files, project-level links, evidence references, project schema snapshots, and tombstones are managed by default.
- `projections/`, `exports/`, and `reports/` are generated and rebuildable, but not committed by default.
- Workspace config may define generated-output defaults, but the effective project decision must be materialized in `project.yaml`.
- `quality project snapshot` stages configured generated outputs only after rebuilding them from source.
- `quality project status` reports stale generated outputs even when they are not configured for commit.
- `quality project export --managed` may mark a specific export profile as a managed output.

This keeps Git history focused on source changes while still allowing teams to commit review artifacts when that is useful.

Example projection manifest:

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

`sourceHash` is the total hash of managed source inputs used by the projection, including project-local schema snapshots.

## 15. Git Version And Team Sync

Git is the version and team synchronization layer.

Default workflow:

```text
git pull --rebase
quality project status
dfmea command writes source files
quality project validate
quality project export
quality project snapshot
git push
```

Snapshot responsibilities:

- verify source files are valid.
- rebuild projections.
- regenerate managed exports.
- stage project source files, project-level link/evidence files, project-local schema snapshots and tombstones if changed, and configured generated outputs.
- create a commit with business context.

Commit message examples:

```text
dfmea(analysis): add cooling fan stall failure chain
quality(project): update cooling fan controller baseline
quality(restore): restore cooling-fan-controller to baseline-v1
```

V1 sync rule:

- Git is authoritative for sync and history.
- Files are text and mergeable.
- The system supports normal Git branch/rebase workflows.
- The CLI must detect dirty state before high-risk operations.
- Same-object conflicts are resolved by humans with Agent assistance.
- Automatic semantic merge of conflicting quality objects is out of V1 scope.
- Snapshot/status/restore/diff/history commands operate on one project by default.
- Workspace-level Git operations must list affected projects in command output.

Default managed source paths for a project:

```text
projects/<project-slug>/project.yaml
projects/<project-slug>/.quality/schemas/**
projects/<project-slug>/.quality/tombstones/**
projects/<project-slug>/<domain>/**/*.yaml
projects/<project-slug>/links/**
projects/<project-slug>/evidence/**
```

Configurable generated managed paths:

```text
projects/<project-slug>/<domain>/projections/**
projects/<project-slug>/exports/**
projects/<project-slug>/reports/**
```

Source files, project-local schema snapshots, and tombstones are always managed paths. Generated exports, reports, and projections are managed only when configured.

Runtime-only project files:

```text
projects/<project-slug>/.quality/locks/**
```

Lock files are not managed paths and must not be committed.

Schema snapshots live under `projects/<project-slug>/.quality/schemas/<plugin-id>/`. A project snapshot includes only the schema snapshots for plugins enabled by that project, and only when those snapshots changed.

### 15.1 Restore Semantics

Project restore is a safe forward operation.

Restore requirements:

1. Resolve workspace and project.
2. Require no unresolved Git conflicts.
3. Require managed project paths to be clean unless `--force-with-backup` is explicitly provided.
4. Resolve the target commit/tag/ref.
5. Extract the target project's managed non-generated paths from the target ref, including source files, project-local schema snapshots, tombstones, links, and evidence references.
6. Rebuild projections and configured exports from restored source files.
7. Validate the restored project.
8. Create a new Git commit describing the restore.

Restore must not run `git reset --hard` and must not rewrite history.
Restore must not restore runtime lock files. Generated files from the target ref are not authoritative and must be rebuilt from restored source resources.
Generated files from the historical target may be used for comparison only.

### 15.2 History And Diff Baseline

V1 history and diff are implemented on top of normal Git operations and project managed paths.

V1 behavior:

- `quality project history` filters commits by the selected project's managed paths.
- `quality project diff` uses Git file diffs as the authoritative change set.
- When changed files are parseable resources, the CLI adds an object summary with kind, ID, title, path, and change type.
- If a changed file cannot be parsed, the CLI still reports the raw path and Git status instead of hiding it.
- Semantic event history and object-level merge automation are V2 features.

This gives immediate value from Git without requiring an additional event store.

### 15.3 Optional Git Hooks

V1 should provide optional hook installation:

```text
quality workspace install-hooks
```

Recommended hooks:

- `pre-commit`: validate changed project source files and reject duplicate IDs.
- `pre-push`: warn if projections/managed exports are stale.

Hooks are optional because teams may have existing Git policies.

V2 direction:

- Add operation logs as JSONL for semantic merge.
- Add object-level conflict helpers.
- Add Agent-assisted merge review.

## 16. Concurrency Model

The architecture no longer optimizes for simultaneous writes to one database file.

Instead:

- Different team members can edit different resource files concurrently.
- Git handles non-overlapping file merges.
- Same-object conflicts become normal text conflicts.
- Same-object conflicts must be surfaced as review work, not hidden by automatic merge.
- CLI validation catches post-merge graph and methodology errors.
- Agent can help resolve conflicts because source data is readable.

This is the main reason SQLite is removed.

Local same-machine concurrency:

- CLI write commands must acquire a project-scoped lock before mutating source files.
- The lock file lives under `projects/<project-slug>/.quality/locks/project.lock`.
- Lock acquisition must timeout with `FILE_LOCKED` and a clear suggestion.
- Read/query commands do not require the write lock.
- Atomic replace is still required because locks are advisory and may not protect against manual edits.
- If a process dies while holding a lock, the next command may break a stale lock only after verifying the process no longer exists or after a documented timeout.
- Lock files are runtime state and must be ignored by Git.

## 17. ID And File Path Strategy

IDs are stable business identifiers.

File paths should be deterministic:

```text
failure-modes/FM-001.yaml
actions/ACT-021.yaml
```

Rules:

- IDs are allocated by CLI.
- The project directory is the namespace. IDs only need to be unique inside one project.
- IDs include a resource-type prefix plus a project-local sequence number.
- Singleton project/domain resources use exact IDs such as `PRJ`, `DFMEA`, and `PFMEA`.
- Ordinary source objects use `<TYPE>-<SEQ>`.
- Sequence numbers are at least three digits and expand when needed.
- IDs are never reused after deletion.
- Collection resource file basenames must match `metadata.id`.
- Singleton resources must use the fixed ID and fixed file name declared by the owning plugin.
- Nested local IDs must be unique within the parent resource but do not determine a file path.
- File rename is allowed only through CLI.
- Human-friendly titles can be added, but titles are not identity.
- IDs from different projects may be identical because project context comes from the path and command resolution.

Default ID shapes:

```text
Singleton resources:
  PRJ
  DFMEA
  PFMEA

Ordinary resources:
  <TYPE>-<SEQ>
```

Examples:

```text
PRJ
DFMEA
PFMEA
SYS-001
COMP-003
FN-012
FM-007
FE-003
FC-005
ACT-021
STEP-001
PFM-004
```

### 17.1 ID Allocation And Tombstones

ID allocation is file-derived, not counter-file-derived.

Allocation rules:

1. Acquire the project write lock.
2. Determine the collection directory for the target kind.
3. Scan existing source files matching `<TYPE>-*.yaml` in that collection.
4. Scan project-local tombstones under `projects/<project-slug>/.quality/tombstones/<TYPE>-*`.
5. Parse numeric suffixes, take the maximum, and allocate `max + 1`.
6. Write the new resource file atomically.

Deletion rules:

- Deleting an object creates a tombstone for the deleted ID.
- Tombstones are committed with the project so deleted IDs are not reused on other branches.
- Tombstones are zero-content or minimal YAML files; they are not domain source resources.
- Tombstones are created only for deleted IDs. They are not created for IDs that still exist after a renumber operation.

Counter files such as `id-counters.yaml` are not part of V1 because they create unnecessary Git conflicts and can drift from real files.

### 17.2 ID Conflict Repair

Project-local sequential IDs can conflict when two branches create the same kind at the same next sequence number.

Conflict rules:

- Same-ID creation normally appears as a Git add/add conflict on the same file path.
- The system must not silently auto-merge two resources with the same ID.
- The repair path is to keep one object at the conflicted ID and renumber the other object.

Required repair command shape:

```text
quality project id renumber --project cooling-fan-controller --from FM-008 --to FM-009
quality project repair id-conflicts --project cooling-fan-controller
```

Renumber must:

- rename the source file.
- update `metadata.id`.
- update all references to the old ID inside the same project.
- rebuild projections.
- validate the project after the rewrite.
- return changed paths and changed references in stable JSON.

### 17.3 Kind Prefix Registry

The prefix registry is part of the plugin contract. V1 reserves:

| Kind | ID shape | File addressing | Domain |
| --- | --- | --- | --- |
| `QualityProject` | `PRJ` | singleton `project.yaml` | project |
| `DfmeaAnalysis` | `DFMEA` | singleton `dfmea.yaml` | dfmea |
| `PfmeaAnalysis` | `PFMEA` | singleton `pfmea.yaml` | pfmea |
| `StructureNode(System)` | `SYS-<SEQ>` | collection `{id}.yaml` | dfmea |
| `StructureNode(Subsystem)` | `SUB-<SEQ>` | collection `{id}.yaml` | dfmea |
| `StructureNode(Component)` | `COMP-<SEQ>` | collection `{id}.yaml` | dfmea |
| `Function` | `FN-<SEQ>` | collection `{id}.yaml` | dfmea |
| `Requirement` | `REQ-<SEQ>` | collection `{id}.yaml` | dfmea |
| `Characteristic` | `CHAR-<SEQ>` | collection `{id}.yaml` | dfmea |
| `FailureMode` | `FM-<SEQ>` | collection `{id}.yaml` | dfmea |
| `FailureEffect` | `FE-<SEQ>` | collection `{id}.yaml` | dfmea |
| `FailureCause` | `FC-<SEQ>` | collection `{id}.yaml` | dfmea |
| `Action` | `ACT-<SEQ>` | collection `{id}.yaml` | dfmea |
| `ProcessFlow` | `FLOW-<SEQ>` | collection `{id}.yaml` | pfmea |
| `ProcessStep` | `STEP-<SEQ>` | collection `{id}.yaml` | pfmea |
| `ProcessFunction` | `PFN-<SEQ>` | collection `{id}.yaml` | pfmea |
| `ProcessFailureMode` | `PFM-<SEQ>` | collection `{id}.yaml` | pfmea |
| `ProcessEffect` | `PFE-<SEQ>` | collection `{id}.yaml` | pfmea |
| `ProcessCause` | `PFC-<SEQ>` | collection `{id}.yaml` | pfmea |
| `PreventionControl` | `PC-<SEQ>` | collection `{id}.yaml` | pfmea |
| `DetectionControl` | `DC-<SEQ>` | collection `{id}.yaml` | pfmea |
| `ProcessAction` | `PACT-<SEQ>` | collection `{id}.yaml` | pfmea |
| `TraceLinkSet` | `LINKS-<SEQ>` | collection `{id}.yaml` | project |
| `TraceLink` | `LINK-<SEQ>` local to `TraceLinkSet` | nested local ID | project |

Validation must reject IDs whose prefix does not match the resource kind. File path ID validation applies to collection resources whose file addressing is `{id}.yaml`. Singleton resources validate their fixed file name and fixed ID. Nested local IDs such as `TraceLink` entries are validated for uniqueness within their parent resource.

## 18. Write Atomicity Without SQLite

Without SQLite transactions, the CLI must provide file-level safety.

Write strategy:

1. Load current resource graph.
2. Validate intended change.
3. Prepare file writes in a temporary directory or temporary sibling files.
4. Write all changed files.
5. Atomically replace target files where possible.
6. Re-read changed files.
7. Re-run targeted validation.
8. Return stable JSON result.

For multi-file changes, the CLI should keep a rollback manifest until the operation completes.

If a write fails:

- no partial source mutation should remain when avoidable.
- if partial mutation cannot be avoided, command output must identify affected files and suggested repair command.

## 19. Integrated Architecture Mechanisms

The architecture does not depend on any external product pattern by name. The useful ideas are embedded as concrete product mechanisms.

### 19.1 Git-native Source Boundary

The quality project repository is the product data boundary. Source files are plain structured text, so the data is:

- visible in normal file explorers and code editors.
- readable by humans and Agents.
- diffable in Git.
- mergeable at object-file granularity.
- portable without a running service.

This replaces the previous database-centered boundary.

### 19.2 Plugin-declared Collections

Each quality plugin declares the collections it owns.

Example:

```yaml
apiVersion: quality.ai/v1
kind: PluginCollections
metadata:
  pluginId: dfmea
spec:
  collections:
    - kind: FailureMode
      directory: failure-modes
      fileName: "{id}.yaml"
      schema: schemas/failure-mode.schema.json
      idPrefix: FM
      titleField: metadata.title
    - kind: Action
      directory: actions
      fileName: "{id}.yaml"
      schema: schemas/action.schema.json
      idPrefix: ACT
      titleField: spec.description
```

The collection declaration is used by:

- CLI create/update/delete commands.
- validation.
- projection rebuilds.
- optional UI form generation.
- Agent context discovery.

### 19.3 Resource Envelope

All project data uses the same outer shape:

```yaml
apiVersion: quality.ai/v1
kind: <ResourceKind>
metadata:
  id: <stable-id>
  title: <human-title>
spec:
  ...
```

This gives the system:

- consistent identity handling.
- versioned schemas.
- predictable Agent parsing.
- cross-plugin discovery.
- common validation and migration hooks.

### 19.4 Declarative Source And Generated Views

Source files declare the quality facts. Generated files are rebuilt from source.

```text
source resources
  -> validate
  -> build in-memory graph
  -> generate projections
  -> generate exports/reports
```

Generated views must be disposable. If `exports/` or `projections/` are deleted, the CLI must be able to rebuild them from source files.

### 19.5 Local Traceability Graph

The system treats source files as nodes and links in a quality graph:

```text
Project
  -> DFMEA Function
  -> Failure Mode
  -> Effect / Cause / Action
  -> PFMEA Process Step
  -> Control Plan Characteristic
```

The CLI builds an in-memory graph for query, validation, trace, and export commands. This gives Agent workflows targeted context without requiring a database server.

### 19.6 Reviewable Agent Changes

Agent work should result in reviewable changes:

- small object files changed instead of one large opaque file.
- stable JSON command output explaining changed IDs and paths.
- generated Markdown/CSV views for human review.
- Git commits with business-context messages.

Future enhancement: add an explicit changeset file before applying large Agent-generated updates:

```text
.quality/changesets/
  CHG-20260502-0001.yaml
```

A changeset can describe intended create/update/delete operations, support human review, and then be applied by CLI.

### 19.7 Schema-driven Optional UI Adapter

The optional UI adapter should not hardcode every DFMEA/PFMEA form. It should derive forms and
editors from plugin collection declarations and resource schemas where practical.

UI adapter writes must still pass through the same validation and write path as CLI commands.

## 20. Migration From Historical CLI

The historical CLI had useful concepts that remain:

- Agent skill routing.
- CLI as stable interface.
- validation commands.
- projection/read models.
- Markdown exports.
- trace/query commands.
- realistic DFMEA tests.

The concepts that change:

- SQLite is removed.
- source of truth becomes structured text files.
- Git is promoted from audit helper to the primary sync/version layer.
- project dimension becomes explicit across DFMEA/PFMEA/Control Plan.
- plugin model expands beyond DFMEA.

Migration approach:

1. Preserve existing DFMEA business commands conceptually.
2. Replace SQLite repositories with file-backed resource stores.
3. Replace DB projection rebuild with file graph projection rebuild.
4. Rewrite tests around project directory fixtures.
5. Add project-scoped Git snapshot workflow.

## 21. Non-goals

V1 does not include:

- central PostgreSQL service.
- web platform backend.
- enterprise permission model.
- server-side approval workflow.
- simultaneous real-time collaborative editing.
- automatic semantic merge of conflicting quality objects.
- Markdown reverse import as official write path.
- requiring OpenCode or OpenCodeUI as the core runtime.

## 22. Architecture Risks

| Risk | Mitigation |
| --- | --- |
| YAML files become too many | deterministic folder layout, projection indexes, query commands |
| Manual edits bypass CLI rules | validation before snapshot, pre-commit hook optional |
| Git conflicts still happen | object-per-file granularity, Agent-assisted conflict guidance |
| Schema migrations become complex | `apiVersion`, migration CLI, schema tests |
| Adapter writes drift from CLI rules | adapters must call CLI or shared plugin core and use the same validation/lock contracts |
| Generated exports pollute diffs | configurable managed exports |
| Agent edits too much context | query/projection commands provide targeted context bundles |
| Large project queries degrade | projection manifests, source hashes, and focused context bundles avoid repeated full scans |

## 23. Methodology Baseline

V1 methodology scope:

- DFMEA follows AIAG-VDA DFMEA concepts.
- PFMEA follows AIAG-VDA PFMEA concepts when implemented.
- Control Plan is an extension point and is not a V1 required implementation.

Methodology rules are enforced by plugin validators, not by the resource envelope alone.

## 24. Target Architecture Summary

The target architecture is:

```text
Project-scoped quality data
  stored as Git-friendly structured resources
  validated by plugin schemas and methodology rules
  manipulated through the headless Python quality engine
  exposed first through local CLI commands
  optionally used by OpenCode, UI, IDE, or CI adapters
  projected into review/report/export files
  synchronized and versioned by Git
```

The most important architecture rule is:

```text
Source data must be human-readable, Agent-readable, Git-diffable, and Git-mergeable.
```

That rule is why the new architecture removes SQLite and centers the product on project-scoped structured files.
