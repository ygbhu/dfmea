# DFMEA Structure Skill

Use this skill for `SYS`, `SUB`, and `COMP` work.

## Rules

- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Route structure changes through `dfmea structure` commands.

## Command Family

- Create: `dfmea structure add`
- Edit metadata: `dfmea structure update`
- Re-parent: `dfmea structure move`
- Delete empty node: `dfmea structure delete`

## Parent Checks

- `SYS` has no parent.
- `SUB` must use a `SYS` parent.
- `COMP` must use a `SUB` parent.

## Agent Practice

- Identify `--db` first.
- Supply `--project` when known; otherwise let CLI resolve the single project from the DB.
- Prefer `--format json`.
