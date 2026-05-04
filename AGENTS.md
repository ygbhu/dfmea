# Project Guide For Agents

This repository contains an OpenCode-bound quality assistant. OpenCode is the required product host;
the Python engine owns quality data and domain behavior.

## Active Boundaries

- `plugin/` is the OpenCode product entrypoint: npm package, `opencode-quality` CLI, and plugin
  module.
- `engine/` is the Python quality engine and CLI package.
- `engine/src/quality_core/` owns workspace, project, method registry, resource, validation,
  projection, and Git logic.
- `engine/src/quality_methods/dfmea/` owns the active DFMEA quality method.
- `engine/src/quality_adapters/cli/` owns the `quality` and `dfmea` CLI entrypoints used by the
  plugin.
- `engine/src/quality_adapters/opencode/` owns generated OpenCode commands, skills, and hook
  templates.
- `engine/src/dfmea_cli/` is a compatibility namespace only.
- `engine/src/quality_methods/pfmea/` is a placeholder only. Do not implement or expose PFMEA unless
  explicitly requested.
- `ui/` is the OpenCode UI host for manual testing and future second-stage UI work.

## Standard Checks

Use the root runner for quality project operations:

```powershell
python .\scripts\quality_cli.py quality --help
python .\scripts\quality_cli.py quality method list --workspace .
python .\scripts\quality_cli.py dfmea --help
npm run opencode:doctor
```

Run Python checks from `engine/`:

```powershell
python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_methods tests
python -m compileall -q src tests
python -m pytest
```

Run OpenCode UI checks from `ui/`:

```powershell
npm run typecheck
npm run lint
npm run test:run
npm run build
```

## Architecture Rules

- Keep Python as the quality engine implementation language.
- OpenCode is intentionally required as the product host.
- Do not introduce SQLite or PostgreSQL as target storage.
- Project source data lives in local YAML/JSON project files under `projects/<slug>/`.
- DFMEA/PFMEA are quality methods discovered through `quality method list`.
- Use CLI/shared core paths for writes; do not let plugin or UI code write quality source files
  directly.
- PFMEA remains placeholder-only until explicitly restarted.

## OpenCode Boundary

- `plugin/` should stay thin: host context, init/status/doctor, OpenCode plugin export.
- `.opencode/commands/`, `.opencode/skills/`, and `.opencode/plugins/quality-assistant.js` are
  generated adapter files for this checkout.
- OpenCode-facing code must call `scripts/quality_cli.py`, installed `quality` / `dfmea`, or the
  same Python CLI/shared-core contracts.
- Do not duplicate resource writes, ID allocation, schema validation, projection rebuilds, exports,
  or Git restore semantics in JavaScript, Markdown, or UI code.
