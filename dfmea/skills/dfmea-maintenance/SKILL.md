# DFMEA Maintenance Skill

Use this skill for consistency checks and exports.

## Rules

- Do not write SQLite directly.
- Do not write projection rows directly.
- Do not treat exported Markdown as source data.
- Route maintenance work through `dfmea projection`, `dfmea validate`, and `dfmea export markdown`.

## Command Family

- Projection: `dfmea projection status`, `dfmea projection rebuild`
- Validation: `dfmea validate`
- Export: `dfmea export markdown`

## Agent Practice

- Use `dfmea projection status --format json` to check freshness before review-heavy workflows.
- Use `dfmea projection rebuild --format json` when derived read models need to be refreshed explicitly.
- Use `dfmea validate --format json` when checking schema, graph, integrity, or projection issues.
- Treat validation output as the authoritative issue report.
- Use `dfmea export markdown --layout review` for review-oriented multi-file export.
- Keep default `ledger` export when compatibility with the old single-file flow matters.
- Use exported Markdown for review, sharing, and git audit only.
