# DFMEA Resource Model

DFMEA source resources are project-local YAML files. Use CLI commands for writes.

## Resource Kinds

| Prefix | Kind | Parent / Scope | File Directory |
| --- | --- | --- | --- |
| `SYS` | `StructureNode` system | none | `dfmea/structure/` |
| `SUB` | `StructureNode` subsystem | `SYS-*` | `dfmea/structure/` |
| `COMP` | `StructureNode` component | `SUB-*` | `dfmea/structure/` |
| `FN` | `Function` | `COMP-*` | `dfmea/functions/` |
| `REQ` | `Requirement` | `FN-*` | `dfmea/requirements/` |
| `CHAR` | `Characteristic` | `FN-*` | `dfmea/characteristics/` |
| `FM` | `FailureMode` | `FN-*` | `dfmea/failure-modes/` |
| `FE` | `FailureEffect` | `FM-*` | `dfmea/effects/` |
| `FC` | `FailureCause` | `FM-*` | `dfmea/causes/` |
| `ACT` | `Action` | `FM-*` | `dfmea/actions/` |

## ID Rules

- Ordinary IDs use `<TYPE>-<SEQ>`, such as `FM-001`.
- File names match IDs, such as `dfmea/failure-modes/FM-001.yaml`.
- IDs are unique inside one project directory.
- Deleted IDs are tombstoned under `.quality/tombstones/<ID>` and are not reused.
- Branch ID conflicts are repaired with `quality project id renumber` or
  `quality project repair id-conflicts`.

## CLI Mapping

- Structure: `dfmea structure add-system/add-subsystem/add-component/update/move/delete`.
- Analysis: `dfmea analysis add-function/add-requirement/add-characteristic/add-failure-chain/...`.
- Query/context/trace: `dfmea query ...`, `dfmea context failure-chain`, and `dfmea trace ...`.
- Validation and generated views: `dfmea validate`, `dfmea projection ...`, and `dfmea export ...`.
- Git workflows: `quality project status/snapshot/history/diff/restore`.
