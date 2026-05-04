---
name: dfmea
description: DFMEA CLI interface for local-first project files. Use when work involves DFMEA project initialization, structure nodes, functions, requirements, characteristics, failure chains, traceability, validation, projections, exports, Git snapshot, history, diff, or restore.
---

# DFMEA Skill

Use the local `quality` and `dfmea` CLIs as the standard write interface for DFMEA project files.

## Boundary Rules

- Source of truth is project files under `projects/<slug>/`, not SQLite.
- Use `--workspace <root>` and `--project <slug>` for project-scoped commands.
- Do not create or write SQLite/PostgreSQL data for target workflows.
- Projections, exports, and reports are generated views. Do not edit them as source.
- Source files, schema snapshots, tombstones, project links, and evidence are managed by Git.
- Runtime locks under `.quality/locks/**` are not source and must not be committed.
- Use `quality project snapshot` for project commits and `quality project restore` for forward restores. Do not use `git reset --hard` for project restore.

## Common Workflow

```bash
quality workspace init --workspace .
quality project create cooling-fan-controller --workspace .
dfmea init --workspace . --project cooling-fan-controller
dfmea validate --workspace . --project cooling-fan-controller
quality project snapshot --workspace . --project cooling-fan-controller --message "quality(project): baseline"
```

## Global Options

| Option | Required | Notes |
| --- | --- | --- |
| `--workspace <root>` | Usually | Workspace root. If omitted, commands use upward discovery. |
| `--project <slug>` | Yes | Project directory slug such as `cooling-fan-controller`. |
| `--format` | No | `json` by default. |
| `--quiet` | No | Suppress success output when supported. |

## IDs And Files

- IDs are project-local and readable, for example `SYS-001`, `COMP-001`, `FN-001`, `FM-001`, `FE-001`, `FC-001`, and `ACT-001`.
- Collection file names match IDs, for example `dfmea/failure-modes/FM-001.yaml`.
- Deleting a resource creates a tombstone under `.quality/tombstones/<ID>` so the ID is not reused.
- For branch or merge ID conflicts, use:

```bash
quality project id renumber --project cooling-fan-controller --from FM-001 --to FM-002
quality project repair id-conflicts --project cooling-fan-controller
```

## Routing

| Task | CLI | Sub-skill |
| --- | --- | --- |
| Workspace/project bootstrap | `quality workspace init`, `quality project create`, `dfmea init` | `dfmea-init` |
| Structure edits | `dfmea structure add-system/add-subsystem/add-component/update/move/delete` | `dfmea-structure` |
| Functions, requirements, characteristics | `dfmea analysis add-function/add-requirement/add-characteristic/...` | `dfmea-analysis` |
| Failure chains and risk updates | `dfmea analysis add-failure-chain/update-risk/update-fm/update-fc/update-act` | `dfmea-analysis` |
| Query, context, trace | `dfmea query ...`, `dfmea context failure-chain`, `dfmea trace ...` | `dfmea-query` |
| Validation, projections, exports | `dfmea validate`, `dfmea projection ...`, `dfmea export ...` | `dfmea-maintenance` |
| Git status/snapshot/history/diff/restore | `quality project status/snapshot/history/diff/restore` | `dfmea-maintenance` |

## Operating Rules

- Prefer CLI commands over manual source edits when a command exists.
- Run `dfmea validate --project <slug>` before snapshotting.
- Run `dfmea projection rebuild --project <slug>` before review when generated views need to be current.
- Use `quality project status --project <slug>` to inspect dirty managed paths and stale projections.
- Use `quality project diff --project <slug>` and `quality project history --project <slug>` for review context.
