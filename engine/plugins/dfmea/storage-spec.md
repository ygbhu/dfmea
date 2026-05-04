# DFMEA Storage Specification

DFMEA source data is stored as local-first project files under `projects/<slug>/`.

## Source Boundary

Source of truth:

- `projects/<slug>/project.yaml`
- `projects/<slug>/.quality/schemas/**`
- `projects/<slug>/.quality/tombstones/**`
- `projects/<slug>/dfmea/**/*.yaml`, excluding generated directories
- `projects/<slug>/links/**`
- `projects/<slug>/evidence/**`

Runtime state:

- `projects/<slug>/.quality/locks/**`

Generated views:

- `projects/<slug>/dfmea/projections/**`
- `projects/<slug>/exports/**`
- `projects/<slug>/reports/**`

Generated views are rebuildable and are not source data.

## Resource Files

All DFMEA source resources use the `apiVersion/kind/metadata/spec` envelope.

Collection resources use the project-local ID as file name:

```text
dfmea/failure-modes/FM-001.yaml
dfmea/causes/FC-001.yaml
dfmea/actions/ACT-001.yaml
```

Deleting a resource writes a tombstone under `.quality/tombstones/<ID>`. ID allocation scans both
source files and tombstones, so deleted IDs are not reused.

## Git Contract

Use `quality project snapshot` to commit managed paths. It includes source files, schema snapshots,
tombstones, links, evidence, and configured generated outputs. It excludes locks and unmanaged
generated outputs.

Use `quality project restore` instead of history rewriting. Restore creates a forward commit after
restoring non-generated managed paths, rebuilding generated outputs, and validating the project.
