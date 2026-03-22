# DFMEA CLI-First Architecture Design

## Context

The current DFMEA architecture baseline correctly establishes SQLite as the source of truth and Markdown as a derived export view. However, if the product goal is a reusable plugin for multiple coding agents such as Claude Code and Codex, the current framing is still too storage-centric. It explains how the system works internally, but it does not yet define a stable product interface for agents.

The key design change is to make a single local CLI the official portable integration contract of the DFMEA plugin. Skills remain important, but they become routing and usage adapters rather than the place where data rules are implemented.

## Problem Statement

If agents directly construct SQL, manage transactions, and implement delete or validation rules themselves, the system becomes difficult to keep consistent across different agent runtimes. That weakens the core plugin goal: one DFMEA capability set that can be safely reused by multiple agents.

The architecture therefore needs a stricter interface boundary:

- Agents should use a stable local command interface for all standard write operations and for portable cross-agent integration.
- Business rules should execute inside a shared core.
- SQLite should remain the internal storage implementation behind the portable interface.
- Markdown should remain export-only.

Read-only SQL access can still remain available for diagnostics and advanced local analysis, because the current baseline explicitly values SQL accessibility. However, direct SQL is not the stable multi-agent plugin contract and must not be the primary write path.

## Goals

- Provide one stable DFMEA interface for multiple agents.
- Keep SQLite as the single source of truth.
- Keep Markdown as a human-readable export and Git audit view.
- Centralize validation, transaction handling, ID allocation, and delete semantics.
- Make success and failure results easy for agents to parse.

## Non-Goals

- No direct agent-authored SQL as an official usage mode.
- No Markdown reverse import in V1.
- No server-side API in V1.
- No cross-project references in V1.
- No GUI editor in V1.

## Recommended Architecture

The DFMEA plugin should adopt a CLI-first architecture with the following layers.

### 1. Agent Adaptation Layer

This layer contains `SKILL.md`, sub-skills, and agent-specific usage guidance.

Responsibilities:

- Interpret user intent.
- Route work to the correct CLI command.
- Help fill in required arguments.
- Explain command results back to the user.

Constraints:

- Must not directly write SQLite.
- Must not treat Markdown exports as source data.
- Must not reimplement business rules that already exist in the CLI core.

### 2. CLI Interface Layer

The local `dfmea` command is the official portable interface and the only supported write interface.

Responsibilities:

- Parse arguments.
- Dispatch subcommands.
- Normalize errors.
- Produce stable machine-readable output.
- Serve as the compatibility contract across agents.

Design rule:

- Any agent able to invoke a local command should be able to use DFMEA through this interface.
- Direct SQL may be used in read-only diagnostic workflows, but that path is explicitly non-portable and outside the stable plugin contract.

### 3. Domain Service Layer

This layer implements DFMEA semantics independent of any specific agent.

Responsibilities:

- Transaction orchestration.
- Business ID allocation.
- Parent-child legality checks.
- Controlled delete semantics.
- Failure-chain creation and update rules.
- Recursive trace orchestration.
- Validation orchestration.
- Export orchestration.

### 4. Storage Layer

SQLite remains the only source of truth.

Responsibilities:

- Persist projects, nodes, and `fm_links`.
- Support WAL-based concurrent access.
- Support SQL-based query and recursive traversal.

Important boundary:

- SQLite is an internal implementation detail of the portable plugin contract, not the recommended direct interaction surface for agents.
- Read-only SQL inspection remains allowed for diagnostics and advanced local analysis.
- All standard writes must go through the CLI.

### 5. Export and Validation Layer

This layer produces human-readable output and performs consistency checks.

Responsibilities:

- Markdown export generation.
- `schema`, `graph`, and `integrity` validation.
- Drift detection for FE/FC descriptions against linked FMs.

## Why This Architecture Is Preferred

Compared with a skill-first architecture, this design reduces agent-to-agent behavior drift. Compared with a tool-only architecture, it still preserves skill-based routing and task understanding. The result is a hybrid system where skills decide what to do, but the CLI decides how it is safely executed.

This is the right fit for a plugin product because it keeps the product interface stable even if agent vendors, prompts, or integration styles evolve.

## Official Interface Contract

The CLI is the formal portable contract exposed to all agents. In V1, it is the only supported write contract. Read-only SQL remains an advanced local capability, but it is not the stable cross-agent integration boundary.

### Command Tree

```text
dfmea
  init
  structure
    add
    update
    delete
    move
  analysis
    add-function
    update-function
    add-requirement
    update-requirement
    delete-requirement
    add-characteristic
    update-characteristic
    delete-characteristic
    add-failure-chain
    update-fm
    update-fe
    update-fc
    update-act
    link-fm-requirement
    unlink-fm-requirement
    link-fm-characteristic
    unlink-fm-characteristic
    link-trace
    unlink-trace
    update-action-status
    delete-node
  query
    get
    search
    summary
    by-ap
    by-severity
    actions
    list
  trace
    causes
    effects
  validate
  export
    markdown
```

### Global Arguments

All commands should support a consistent minimum set of global arguments.

```text
--db <path>
--project <id>
--format <json|text|markdown>
--quiet
--busy-timeout-ms <n>
--retry <n>
```

Default recommendation:

- Agents should prefer `--format json`.
- Human-oriented workflows may use `text` or `markdown` where appropriate.
- `json` is the only stability-guaranteed machine contract in V1.
- `text` and `markdown` are convenience views for humans and may change between minor versions.

Global resolution rules:

- One DB file contains exactly one DFMEA project in V1.
- If both `--db` and `--project` are provided, the CLI must verify they refer to the same project and fail on mismatch.
- If `--db` is provided and `--project` is omitted, the CLI derives the single project from the DB.
- If `--project` is provided without `--db`, resolution is implementation-defined and not required in V1.

Concurrency rules:

- The CLI should configure a default SQLite busy timeout.
- Write commands should retry transient lock acquisition failures a bounded number of times.
- Exhausted contention must return a stable `DB_BUSY` error code with retry guidance.

## V1 Command Surface

### Initialization

```text
dfmea init --db <path> --project <id> --name <name>
```

Optional metadata:

```text
--schema-version <v>
--methodology AIAG-VDA-DFMEA
--owner <name>
--status <draft|active|archived>
```

### Structure Commands

```text
dfmea structure add --db <path> --project <id> --type <SYS|SUB|COMP> --name <name> [--parent <id|rowid>]
dfmea structure update --db <path> --project <id> --node <id|rowid> [--name <name>] [--description <text>] [--metadata <json>]
dfmea structure move --db <path> --project <id> --node <id|rowid> --parent <id|rowid>
dfmea structure delete --db <path> --project <id> --node <id|rowid>
```

Structure rules:

- `SYS` creation omits `--parent`; the CLI stores it with `parent_id = 0` and the provided `project_id`.
- `SUB` requires a `SYS` parent.
- `COMP` requires a `SUB` parent.
- `move` is the formal operation for changing structure ownership.
- `update` changes node metadata only and does not alter ownership.

### Analysis Commands

```text
dfmea analysis add-function --db <path> --project <id> --comp <id|rowid> --name <name> --description <text>
dfmea analysis update-function --db <path> --project <id> --fn <id|rowid> [--name <name>] [--description <text>]
dfmea analysis add-requirement --db <path> --project <id> --fn <id|rowid> --text <text> [--source <text>]
dfmea analysis update-requirement --db <path> --project <id> --req <rowid> [--text <text>] [--source <text>]
dfmea analysis delete-requirement --db <path> --project <id> --req <rowid>
dfmea analysis add-characteristic --db <path> --project <id> --fn <id|rowid> --text <text> [--value <text>] [--unit <text>]
dfmea analysis update-characteristic --db <path> --project <id> --char <rowid> [--text <text>] [--value <text>] [--unit <text>]
dfmea analysis delete-characteristic --db <path> --project <id> --char <rowid>
dfmea analysis add-failure-chain --db <path> --project <id> --fn <id|rowid> --fm-description <text> --severity <1-10> [--violates-req <rowid>]... [--related-char <rowid>]... [--fe-description <text>]... [--fe-level <text>]... [--fc-description <text>]... [--occurrence <1-10>]... [--detection <1-10>]... [--ap <High|Medium|Low>]... [--act-description <text>]... [--kind <prevention|detection>]... [--status <planned|in-progress|completed>]... [--owner <text>]... [--due <date>]... [--target-causes <rowid,rowid,...>]...
dfmea analysis update-fm --db <path> --project <id> --fm <id|rowid> [--description <text>] [--severity <1-10>]
dfmea analysis update-fe --db <path> --project <id> --fe <rowid> [--description <text>] [--level <text>]
dfmea analysis update-fc --db <path> --project <id> --fc <rowid> [--description <text>] [--occurrence <1-10>] [--detection <1-10>] [--ap <High|Medium|Low>]
dfmea analysis update-act --db <path> --project <id> --act <id|rowid> [--description <text>] [--kind <prevention|detection>] [--status <planned|in-progress|completed>] [--owner <text>] [--due <date>] [--target-causes <rowid,rowid,...>]
dfmea analysis link-fm-requirement --db <path> --project <id> --fm <id|rowid> --req <rowid>
dfmea analysis unlink-fm-requirement --db <path> --project <id> --fm <id|rowid> --req <rowid>
dfmea analysis link-fm-characteristic --db <path> --project <id> --fm <id|rowid> --char <rowid>
dfmea analysis unlink-fm-characteristic --db <path> --project <id> --fm <id|rowid> --char <rowid>
dfmea analysis link-trace --db <path> --project <id> --from <fe|fc>:<rowid> --to-fm <id|rowid>
dfmea analysis unlink-trace --db <path> --project <id> --from <fe|fc>:<rowid> --to-fm <id|rowid>
dfmea analysis update-action-status --db <path> --project <id> --act <id|rowid> --status <planned|in-progress|completed>
dfmea analysis delete-node --db <path> --project <id> --node <id|rowid>
```

Analysis rules:

- `delete-node` in the analysis namespace only applies to `FN`, `FM`, `FE`, `FC`, `ACT`, `REQ`, and `CHAR`.
- `update-action-status` is a convenience command over `update-act` for the common workflow.
- The CLI, not the agent, is responsible for validating same-FM `target_causes`, valid REQ/CHAR ownership, and trace-link directionality.
- V1 should avoid opaque generic patch payloads in the public contract.
- For complex chain creation, V1 should support a structured input mode such as `--input <json-file>` in addition to repeated flags. Repeated FE/FC/ACT flags are only a convenience shorthand and must document grouping rules explicitly.

### Query and Trace Commands

```text
dfmea query get --db <path> --project <id> --node <id|rowid>
dfmea query search --db <path> --project <id> --keyword <text>
dfmea query summary --db <path> --project <id> --comp <id|rowid>
dfmea query by-ap --db <path> --project <id> --ap <High|Medium|Low>
dfmea query by-severity --db <path> --project <id> --gte <1-10>
dfmea query actions --db <path> --project <id> --status <planned|in-progress|completed>
dfmea query list --db <path> --project <id> --type <type> [--parent <id|rowid>]

dfmea trace causes --db <path> --project <id> --fm <id|rowid> [--depth 10]
dfmea trace effects --db <path> --project <id> --fm <id|rowid> [--depth 10]
```

### Maintenance Commands

```text
dfmea validate --db <path> --project <id> [--scope <schema|graph|integrity|all>] [--node <id|rowid>]
dfmea export markdown --db <path> --project <id> --out <dir>
```

Validation semantics:

- Validation findings are represented in `data.summary` and `data.issues`.
- If validation returns no `error`-level issue, `ok` is `true` and the process exits zero.
- If validation returns one or more `error`-level issues, `ok` is `false`, the process exits non-zero, and `errors` must include `VALIDATION_FAILED` while still returning the full issue list.
- If validation returns only `warning` or `info` issues, `ok` remains `true` and the process exits zero.

## Output Contract

The CLI should default to stable JSON output so different agents can consume the same contract.

Every JSON result should carry a contract version and enough object identity information for follow-up commands.

### Success Shape

```json
{
  "contract_version": "1.0",
  "ok": true,
  "command": "analysis add-function",
  "data": {
    "project_id": "motor-dfmea",
    "fn_id": "FN-001",
    "parent_comp_id": "COMP-003",
    "affected_objects": [
      {
        "type": "FN",
        "id": "FN-001",
        "rowid": 42
      }
    ]
  },
  "warnings": [],
  "errors": [],
  "meta": {
    "db": "E:\\study\\dfmeaDemo\\dfmea\\example.db"
  }
}
```

### Failure Shape

```json
{
  "contract_version": "1.0",
  "ok": false,
  "command": "structure delete",
  "data": null,
  "warnings": [],
  "errors": [
    {
      "code": "NODE_NOT_EMPTY",
      "message": "COMP-003 still has child FN nodes",
      "target": {
        "type": "COMP",
        "id": "COMP-003",
        "rowid": 17
      },
      "suggested_action": "Delete or move child nodes first"
    }
  ],
  "meta": {
    "db": "E:\\study\\dfmeaDemo\\dfmea\\example.db"
  }
}
```

### Validation Result Shape

```json
{
  "contract_version": "1.0",
  "ok": true,
  "command": "validate",
  "data": {
    "summary": {
      "errors": 0,
      "warnings": 1
    },
    "issues": [
      {
        "level": "warning",
        "kind": "DESCRIPTION_DRIFT",
        "target": {
          "rowid": 128
        },
        "reason": "FC description differs from linked FM description",
        "suggested_action": "Review whether snapshot should be synchronized"
      }
    ]
  },
  "warnings": [],
  "errors": [],
  "meta": {
    "db": "E:\\study\\dfmeaDemo\\dfmea\\example.db"
  }
}
```

Error code guidance:

- `INVALID_PARENT`
- `NODE_NOT_EMPTY`
- `INVALID_REFERENCE`
- `DB_BUSY`
- `PROJECT_DB_MISMATCH`
- `VALIDATION_FAILED`

Concurrency behavior:

- The CLI should set a default busy timeout, for example 5000 ms.
- Write operations should retry transient lock failures up to a small bounded count, for example 3 attempts.
- Exhausted retries must return `DB_BUSY` with guidance to retry later.

## Domain Rules That Must Stay Inside the CLI Core

The following rules should not be distributed across agent skills.

- Transaction boundaries.
- Business ID allocation.
- Parent-child legality enforcement.
- FC deletion cleanup for `ACT.target_causes`.
- Recursive cleanup behavior.
- `fm_links` integrity.
- Validation category execution.
- Export generation and traceability guarantees.

Keeping these rules in one executable boundary is the main reason the plugin remains reliable across agents.

## Implementation Inspiration from CLI-Anything

The implementation approach can borrow several ideas from `HKUDS/CLI-Anything` while staying domain-specific to DFMEA.

Useful ideas to reuse:

- A single installable local CLI as the stable agent-facing surface.
- Agent adapters for multiple platforms, while keeping one shared executable core.
- Strong `--help` discoverability so agents can inspect command capabilities directly.
- Default JSON output for machine consumption, with text-oriented formats for humans.
- A packaged `SKILL.md` or equivalent agent guidance artifact that ships with the tool.
- CLI subprocess tests that validate the installed command, not only internal functions.
- A shared methodology document for generation, validation, and maintenance workflows.

Recommended adaptation for DFMEA:

- Use one domain CLI, `dfmea`, rather than generating one CLI per target application.
- Keep the command tree centered on DFMEA domain actions, not generic harness-building phases.
- Treat the SQLite-backed domain core as the equivalent of the reusable harness backend.
- Let skills for Claude Code, Codex, and other agents act as thin adapters over the same CLI contract.
- Keep an optional REPL or interactive shell as a possible V2 enhancement, not a V1 requirement.

Ideas that are inspirational but should not be copied directly:

- CLI generation pipeline phases are not the product here; the DFMEA CLI itself is the product.
- A global registry or marketplace model is optional and not needed in V1.
- Per-application harness packaging is unnecessary because DFMEA is already a single bounded domain tool.

Practical V1 implementation direction:

- Prefer a mature Python CLI framework such as Click or Typer.
- Organize commands by domain namespace (`structure`, `analysis`, `query`, `trace`, `validate`, `export`).
- Keep parsing and command dispatch thin; move all business rules into a service layer.
- Add CLI-level tests for argument parsing, JSON contract shape, exit codes, and installed-command subprocess execution.

## Skill Package Implications

The existing skill package structure still makes sense, but each skill should be reframed as a CLI adapter.

### Main Skill

`dfmea/SKILL.md` should define:

- Terminology.
- Scope boundaries.
- Routing rules.
- The rule that agents must use `dfmea` commands instead of direct DB writes.

### Sub-Skills

- `dfmea-init`: route to `dfmea init`
- `dfmea-structure`: route to `dfmea structure *`
- `dfmea-analysis`: route to `dfmea analysis *`
- `dfmea-query`: route to `dfmea query *` and `dfmea trace *`
- `dfmea-maintenance`: route to `dfmea validate` and `dfmea export markdown`

### Skill Handoff Rules

Sub-skills should exchange both context and command responsibility.

- Structure skills must identify target project and valid structure parent before calling CLI.
- Analysis skills must identify target project and `COMP` or `FN` scope before calling CLI.
- Query skills must identify the DB path and output format before calling CLI.
- Maintenance skills must distinguish validation from export before calling CLI.

## Impact on the Existing Architecture Baseline

The current architecture baseline remains largely valid. The main required change is not a storage-model rewrite; it is a boundary rewrite.

What stays the same:

- SQLite as source of truth.
- Markdown as export-only derived view.
- Three-table database design.
- Function as the main analysis aggregate.
- `fm_links` as recursive trace support.
- Controlled delete semantics and validation taxonomy.

What changes:

- The portable external product interface becomes the CLI rather than direct write access.
- Agent skills stop being implied executors of DB operations and become adapters to CLI commands.
- The architecture description becomes interface-first rather than storage-first.

## Required Changes to the Architecture Document

The formal architecture baseline should be updated in the following ways.

1. Reframe the product as an agent-agnostic local CLI plugin.
2. Add CLI interface layer and domain service layer to the overall architecture.
3. Add a top-level decision that `dfmea` CLI is the only supported external write interface.
4. Clarify that SQLite is internal storage, not the recommended direct agent interaction surface.
5. Rewrite operation semantics around CLI contracts, with transaction rules described as internal execution guarantees.
6. Reframe query architecture as `dfmea query` and `dfmea trace` capabilities backed by SQL.
7. Promote output contract into a formal stable JSON schema.
8. Redefine skill package responsibilities as command-routing responsibilities.
9. Explicitly defer direct agent-authored SQL and Markdown reverse import from V1.

## Recommendation

Adopt the CLI-first architecture as the formal product architecture for V1.

This keeps the current strong domain model and storage choices, while making the plugin substantially more reusable, safer, and easier to integrate across multiple agents.

## Next Step

Once this design is accepted, the next planning step should define:

- The final CLI argument grammar.
- The stable JSON output schema.
- The architecture document edits needed to align the current baseline with this design.
- The implementation plan for the CLI core and skill adapters.
