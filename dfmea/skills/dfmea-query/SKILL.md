# DFMEA Query Skill

Use this skill for read workflows.

## Rules

- Do not write SQLite directly.
- Do not write projection rows directly.
- Do not treat exported Markdown as source data.
- Route reads through `dfmea query` and `dfmea trace`.

## Command Family

- Node lookup: `dfmea query get`
- Project navigation: `dfmea query map`
- Lists and search: `dfmea query list`, `dfmea query search`
- Review views: `dfmea query bundle`, `dfmea query dossier`
- Summaries and filters: `dfmea query summary`, `dfmea query by-ap`, `dfmea query by-severity`, `dfmea query actions`
- Recursive traversal: `dfmea trace causes`, `dfmea trace effects`

## Agent Practice

- Identify `--db` first.
- Prefer `--format json` for structured follow-up actions.
- Use `dfmea query map` to orient on the project before diving into a component or function.
- Use `dfmea query bundle` for component-centric review and `dfmea query dossier` for function-centric review.
- For projection-backed reads, pay attention to `meta.projection` to see whether data was fresh or rebuilt.
- Use `dfmea trace` when the task is recursive cause/effect traversal, not flat lookup.
