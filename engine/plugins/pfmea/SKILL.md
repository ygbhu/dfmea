---
name: pfmea
description: Reserved PFMEA skill placeholder. PFMEA is intentionally deferred and has no active commands in the current implementation.
---

# PFMEA Placeholder

PFMEA is reserved as a future quality domain plugin. It is not implemented in the current DFMEA-first
baseline.

## Boundary Rules

- Do not call `pfmea` CLI commands; the current package does not expose a `pfmea` console script.
- Do not register `pfmea` as an active schema plugin until the PFMEA implementation phase starts.
- Do not create PFMEA source files manually as an official write path.
- Future PFMEA work must use the same `quality_core` resource, validation, lock, schema snapshot, and
  Git contracts as DFMEA.

## Future Placeholder

Reserved locations:

- `src/quality_methods/pfmea/`
- `pfmea/SKILL.md`
- future `quality_adapters.cli.pfmea`
- future `quality_adapters.cli.pfmea_commands`
