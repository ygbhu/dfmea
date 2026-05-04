---
name: quality-core
description: Use the Python local-first quality assistant from OpenCode for workspace, project, plugin, validation, projection, export, Git snapshot, restore, and adapter-boundary work.
compatibility: opencode
---

# Quality Core Skill

Use this skill when OpenCode is asked to operate a repository as the quality management assistant.

## Boundaries

- The quality product core is Python.
- `quality` owns workspace, project, method discovery, plugin/schema, validation, projection,
  export, and Git commands.
- `dfmea` owns the active DFMEA method command namespace.
- DFMEA and PFMEA are quality methods. PFMEA is a planned placeholder until `quality method list`
  reports it active.
- OpenCode is the required product host, while Python project files remain the source of truth.
- OpenCode plugins, commands, and skills may orchestrate CLI calls but must not duplicate domain
  write rules.
- Do not introduce SQLite/PostgreSQL target storage.
- Do not implement or expose PFMEA until the PFMEA phase explicitly starts.

## Command Interface

If this is the source checkout and `scripts/quality_cli.py` exists, prefer:

```powershell
python .\scripts\quality_cli.py quality --help
python .\scripts\quality_cli.py quality method list --workspace .
python .\scripts\quality_cli.py dfmea --help
```

For installed usage, prefer:

```powershell
quality --help
quality method list --workspace .
dfmea --help
```

## Operating Rules

- Use CLI or shared Python core for writes.
- Project source data lives under `projects/<slug>/`.
- Runtime locks under `.quality/locks/**` are not source data.
- Generated projections and exports are views; do not edit them as source.
- Run validation before snapshot/export workflows.
- Discover available methods with `quality method list`; do not assume planned methods are active.
- Use `quality project snapshot` and `quality project restore`; do not use `git reset --hard` for
  quality project restore.
