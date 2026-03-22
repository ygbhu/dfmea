# DFMEA Storage Spec

This file describes the storage boundary behind the CLI.

## Boundary Rules

- SQLite is the source of truth.
- Markdown is export-only.
- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Standard writes must go through `dfmea` commands.

## Storage Model

- One SQLite database holds one DFMEA project in V1.
- Core tables: `projects`, `nodes`, and `fm_links`.
- `nodes` stores all structure and analysis nodes.
- `fm_links` stores FE->FM and FC->FM trace relationships.

## Operational Rules

- SQLite runs in WAL mode for concurrent local access.
- The CLI owns transactions, retries, busy timeout behavior, validation, and delete cleanup.
- Read-only SQL inspection is allowed for diagnostics, but it is not the portable product interface.
- Markdown exports are derived views for human review and git audit, not editable source records.

## CLI Contract

- Create project DB: `dfmea init`
- Mutate structure: `dfmea structure ...`
- Mutate analysis: `dfmea analysis ...`
- Read/query/trace: `dfmea query ...` and `dfmea trace ...`
- Validate and export: `dfmea validate` and `dfmea export markdown`
