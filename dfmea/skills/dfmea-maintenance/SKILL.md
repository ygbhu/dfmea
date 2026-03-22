# DFMEA Maintenance Skill

Use this skill for consistency checks and exports.

## Rules

- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Route maintenance work through `dfmea validate` and `dfmea export markdown`.

## Command Family

- Validation: `dfmea validate`
- Export: `dfmea export markdown`

## Agent Practice

- Use `dfmea validate --format json` when checking schema, graph, or integrity issues.
- Treat validation output as the authoritative issue report.
- Use exported Markdown for review, sharing, and git audit only.
