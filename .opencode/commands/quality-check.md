---
description: Run the Python quality assistant verification suite
---

Run the local quality assistant checks.

Use the Python engine under `engine/`. If dependencies are missing, run:

```powershell
cd engine
python -m pip install -e ".[dev]"
```

Then run:

```powershell
cd engine
python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_methods tests
python -m compileall -q src tests
python -m pytest
```

Report each command result. Fix only the Python quality engine or tests unless the user explicitly
asks for UI work. Do not implement planned methods such as PFMEA or add SQLite/PostgreSQL storage.
