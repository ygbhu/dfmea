---
description: Create a local quality workspace and DFMEA project
---

Bootstrap a local-first quality workspace and DFMEA project.

Use `$1` as the project slug. If `$1` is missing, ask the user for a lowercase slug before running
commands.

If this is the quality assistant source checkout and `scripts/quality_cli.py` exists, use:

```powershell
python .\scripts\quality_cli.py quality workspace init --workspace .
python .\scripts\quality_cli.py quality project create $1 --workspace .
python .\scripts\quality_cli.py quality method list --workspace . --project $1
python .\scripts\quality_cli.py dfmea init --workspace . --project $1
python .\scripts\quality_cli.py dfmea validate --workspace . --project $1
```

Otherwise use installed console scripts:

```powershell
quality workspace init --workspace .
quality project create $1 --workspace .
quality method list --workspace . --project $1
dfmea init --workspace . --project $1
dfmea validate --workspace . --project $1
```

If workspace or project config already exists, inspect it instead of overwriting it. DFMEA is the
active method in the current baseline; do not create PFMEA files while it is planned/placeholder.
