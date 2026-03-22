# DFMEA Node Schema

This file is a quick node-model reference for CLI users.

## Boundary Rules

- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Use `dfmea` commands to create, update, move, delete, validate, and export data.

## Node Types

- `SYS`: top-level structure node; stored with `parent_id = 0`.
- `SUB`: child of `SYS`.
- `COMP`: child of `SUB`.
- `FN`: child of `COMP`; primary analysis aggregate.
- `REQ`: child of `FN`; row-only record with no business id.
- `CHAR`: child of `FN`; row-only record with no business id.
- `FM`: child of `FN`; has business id.
- `FE`: child of `FM`; row-only record with no business id.
- `FC`: child of `FM`; row-only record with no business id.
- `ACT`: child of `FM`; has business id.

## Identity Rules

- Business ids are used for `SYS`, `SUB`, `COMP`, `FN`, `FM`, and `ACT`.
- `REQ`, `CHAR`, `FE`, and `FC` are referenced by rowid.
- Valid business ids match `SYS-001`, `COMP-001`, `FN-001`, `FM-001`, or `ACT-001` style patterns.

## Analysis Rules

- `FN` owns its `REQ`, `CHAR`, and `FM` records.
- `ACT` belongs to an `FM`, not to an `FC`.
- `ACT.target_causes` stores same-`FM` `FC` rowids.
- `fm_links` carries cross-layer FE->FM and FC->FM trace links.

## CLI Mapping

- Structure nodes: `dfmea structure add|update|move|delete`
- `FN`, `REQ`, `CHAR`, `FM`, `FE`, `FC`, `ACT`: `dfmea analysis ...`
- Reads and recursion: `dfmea query ...` and `dfmea trace ...`
- Consistency checks: `dfmea validate`
