---
name: dfmea
description: Work with DFMEA project files through the local-first Python CLI for initialization, structure, functions, requirements, characteristics, failure chains, query, trace, validation, projections, and exports.
compatibility: opencode
---

# DFMEA Skill

Use this skill when work involves the active DFMEA quality method.

DFMEA is a quality method implemented by the Python engine and exposed through the OpenCode product
host. Do not duplicate DFMEA write logic in JavaScript, Markdown commands, or UI code.

## Commands

Use the source-checkout runner when available:

```powershell
python .\scripts\quality_cli.py dfmea --help
python .\scripts\quality_cli.py dfmea init --workspace . --project <slug>
python .\scripts\quality_cli.py dfmea validate --workspace . --project <slug>
```

For installed usage:

```powershell
dfmea --help
dfmea init --workspace . --project <slug>
dfmea validate --workspace . --project <slug>
```

## Deeper Guidance

If the source checkout includes `engine/plugins/dfmea/`, read:

- `engine/plugins/dfmea/SKILL.md`
- `engine/plugins/dfmea/skills/dfmea-init/SKILL.md`
- `engine/plugins/dfmea/skills/dfmea-structure/SKILL.md`
- `engine/plugins/dfmea/skills/dfmea-analysis/SKILL.md`
- `engine/plugins/dfmea/skills/dfmea-query/SKILL.md`
- `engine/plugins/dfmea/skills/dfmea-maintenance/SKILL.md`

## Rules

- Use `--workspace <root>` and `--project <slug>` for project-scoped operations.
- Prefer CLI commands over manual YAML edits when a command exists.
- Do not create SQLite/PostgreSQL state.
- Do not implement PFMEA as part of DFMEA work.
- Generated projections and exports are views; do not edit them as source.
