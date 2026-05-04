---
description: Inspect local quality project state
---

Inspect a local quality project and summarize what needs attention.

Use `$1` as the project slug. If `$1` is missing, inspect `projects/` and choose the only project if
there is exactly one; otherwise ask the user for the slug.

Prefer the source-checkout runner when available:

```powershell
python .\scripts\quality_cli.py quality plugin list --workspace . --project $1
python .\scripts\quality_cli.py quality method list --workspace . --project $1
python .\scripts\quality_cli.py quality project status --workspace . --project $1
python .\scripts\quality_cli.py dfmea validate --workspace . --project $1
python .\scripts\quality_cli.py dfmea projection status --workspace . --project $1
```

Otherwise use:

```powershell
quality plugin list --workspace . --project $1
quality method list --workspace . --project $1
quality project status --workspace . --project $1
dfmea validate --workspace . --project $1
dfmea projection status --workspace . --project $1
```

Summarize enabled/planned quality methods, validation errors, stale generated outputs, dirty
managed paths, and the next useful command. Do not change source files unless the user asks for a
fix.
