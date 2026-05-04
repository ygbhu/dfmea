---
name: dfmea-query
description: Read, search, summarize, trace, and build Agent context bundles from local-first DFMEA project files.
---

# DFMEA Query Skill

Read workflows use the file-backed graph and stable JSON output.

## Query Commands

```bash
dfmea query get --project cooling-fan-controller FM-001
dfmea query list --project cooling-fan-controller --type FM
dfmea query search --project cooling-fan-controller --keyword "motor"
dfmea query map --project cooling-fan-controller
dfmea query summary --project cooling-fan-controller --component COMP-001
dfmea query by-ap --project cooling-fan-controller --ap High
dfmea query by-severity --project cooling-fan-controller --gte 7
dfmea query actions --project cooling-fan-controller --status planned
```

Compatibility aliases still exist for some older command names, but prefer the current options above.

## Context And Trace

```bash
dfmea context failure-chain --project cooling-fan-controller --failure-mode FM-001
dfmea trace causes --project cooling-fan-controller --fm FM-001 --depth 3
dfmea trace effects --project cooling-fan-controller --fm FM-001 --depth 3
```

Context output includes the root resource, related resources, links, source paths, and freshness metadata.

## Agent Practice

- Use `dfmea query map` first for project shape, then focused queries for IDs.
- Use `dfmea context failure-chain` before editing a failure chain.
- Check `meta.freshness` and `quality project status` when generated projections may be stale.
- Query results include source paths. Edit source through CLI commands, not generated projections.
