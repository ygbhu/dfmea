# DFMEA Skill

Use the local `dfmea` CLI as the official DFMEA interface.

## Boundaries

- sqlite is the source of truth.
- markdown is export-only and for review or git audit.
- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Read-only SQL diagnostics are allowed, but they are non-portable and not the standard workflow.

## Terminology

- `SYS` / `SUB` / `COMP`: structure hierarchy.
- `FN`: main analysis aggregate under a component.
- `REQ` / `CHAR`: child records under an `FN`; they use rowid references, not business ids.
- `FM`: failure mode under an `FN`.
- `FE` / `FC`: row-only failure effects and causes under an `FM`.
- `ACT`: action under an `FM`; `target_causes` points to `FC` rowids in the same `FM`.

## Routing

- New database or project setup: use `dfmea init` or hand off to `dfmea-init`.
- Structure creation or edits: use `dfmea structure ...` or hand off to `dfmea-structure`.
- Function, requirement, characteristic, failure-chain, trace-link, or action work: use `dfmea analysis ...` or hand off to `dfmea-analysis`.
- Reads, search, summaries, and recursive traces: use `dfmea query ...` or `dfmea trace ...`, or hand off to `dfmea-query`.
- Validation and exports: use `dfmea validate` or `dfmea export markdown`, or hand off to `dfmea-maintenance`.

## Operating Rules

- Prefer `--format json` for agent workflows.
- Identify the DB path first; in V1 one DB contains one project.
- If both `--db` and `--project` are supplied, they must match.
- Let the CLI enforce validation, transactions, ID allocation, delete semantics, and trace rules.
- Never update the database or exported files by bypassing the CLI.
