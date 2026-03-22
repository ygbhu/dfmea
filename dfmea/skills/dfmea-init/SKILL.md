# DFMEA Init Skill

Use this skill only for project bootstrap.

## Rules

- Do not write SQLite directly.
- Do not treat exported Markdown as source data.
- Route project creation through `dfmea init`.

## Command

```text
dfmea init --db <path> --project <id> --name <name> --format json
```

## Checklist

- Choose a new or empty DB path.
- Choose the project id and project name.
- Prefer `--format json` for agent use.
- Report the created project id and DB path from CLI output.
