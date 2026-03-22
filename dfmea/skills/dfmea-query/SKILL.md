# DFMEA Query Skill

Use this skill for read workflows.

## Rules

- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Route reads through `dfmea query` and `dfmea trace`.

## Command Family

- Node lookup: `dfmea query get`
- Lists and search: `dfmea query list`, `dfmea query search`
- Summaries and filters: `dfmea query summary`, `dfmea query by-ap`, `dfmea query by-severity`, `dfmea query actions`
- Recursive traversal: `dfmea trace causes`, `dfmea trace effects`

## Agent Practice

- Identify `--db` first.
- Prefer `--format json` for structured follow-up actions.
- Use `dfmea trace` when the task is recursive cause/effect traversal, not flat lookup.
