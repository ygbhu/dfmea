# Development Workflow

This repository uses Trellis only as lightweight AI workflow support. The product implementation is
the Python local-first quality assistant under `src/`.

## Start

```bash
python ./.trellis/scripts/get_context.py
python ./.trellis/scripts/get_context.py --mode packages
```

Before editing code, read:

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/directory-structure.md`
- `.trellis/spec/backend/error-handling.md`
- `.trellis/spec/guides/index.md`

## Current Project Shape

- Single-repo Python project.
- No active frontend spec layer.
- No TypeScript platform, PostgreSQL infrastructure, or SQLite source-of-truth storage.
- Active code lives under `src/quality_adapters`, `src/quality_core`, and `src/quality_plugins`.
  `src/dfmea_cli` is a compatibility namespace. `src/quality_plugins/pfmea` is a placeholder only.

## Quality Checks

```bash
python -m pytest
python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_plugins tests
python -m compileall -q src tests
```

## Task Records

Task records are optional working notes. Completed or obsolete task directories should not be kept
as product documentation; canonical requirements, architecture, design, and development status live
under `docs/`.

## Session Records

Session journals under `.trellis/workspace/` may be used to record human-reviewed work after a
commit. They are not a source of product requirements.
