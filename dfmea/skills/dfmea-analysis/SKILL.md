# DFMEA Analysis Skill

Use this skill for `FN`, `REQ`, `CHAR`, `FM`, `FE`, `FC`, `ACT`, and trace-link work.

## Rules

- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Route analysis changes through `dfmea analysis` commands.

## Command Family

- Functions: `dfmea analysis add-function`, `update-function`
- Requirements: `dfmea analysis add-requirement`, `update-requirement`, `delete-requirement`
- Characteristics: `dfmea analysis add-characteristic`, `update-characteristic`, `delete-characteristic`
- Failure chains: `dfmea analysis add-failure-chain`, `update-fm`, `update-fe`, `update-fc`, `update-act`
- Links: `dfmea analysis link-fm-requirement`, `unlink-fm-requirement`, `link-fm-characteristic`, `unlink-fm-characteristic`, `link-trace`, `unlink-trace`
- Actions and delete: `dfmea analysis update-action-status`, `delete-node`

## Agent Practice

- Start from the target `COMP` or `FN` scope.
- Use rowids for `REQ`, `CHAR`, `FE`, and `FC` references.
- Use `--input <json-file>` for complex failure chains.
- Prefer `--format json` and let the CLI validate ownership, references, and delete semantics.
