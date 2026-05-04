---
name: dfmea-maintenance
description: Validate DFMEA files, rebuild projections, export review files, and manage project-scoped Git status, snapshot, history, diff, and restore.
---

# DFMEA Maintenance Skill

Use this for validation, generated views, exports, and Git workflows.

## Validation And Projections

```bash
dfmea validate --workspace . --project cooling-fan-controller
dfmea projection status --workspace . --project cooling-fan-controller
dfmea projection rebuild --workspace . --project cooling-fan-controller
```

Projection files live under `dfmea/projections/` and are generated. Do not edit them as source.

## Exports

```bash
dfmea export markdown --workspace . --project cooling-fan-controller --out ./out --layout review
dfmea export risk-csv --workspace . --project cooling-fan-controller --out ./out
```

Exports are generated review artifacts. They are not committed by default unless `project.yaml`
explicitly opts generated outputs into management.

## Git Project Commands

```bash
quality project status --workspace . --project cooling-fan-controller
quality project snapshot --workspace . --project cooling-fan-controller --message "quality(project): update dfmea"
quality project history --workspace . --project cooling-fan-controller --limit 10
quality project diff --workspace . --project cooling-fan-controller --from HEAD~1
quality project restore --workspace . --project cooling-fan-controller --ref baseline-v1
```

Snapshot validates, rebuilds projections, stages managed source paths, schema snapshots, tombstones,
and configured generated outputs, then creates a Git commit. Locks are excluded.

Restore is a safe forward operation: it restores managed non-generated paths from the target ref,
excludes locks, rebuilds generated outputs, validates, and creates a new commit. Do not use
`git reset --hard` as a project restore workflow.

## Agent Practice

- Run validation before snapshot.
- Use `quality project status` to inspect dirty managed paths and stale projections.
- Use `quality project diff` for raw changed paths plus parsed resource summaries.
- Treat `exports/`, `reports/`, and `dfmea/projections/` as disposable generated outputs.
