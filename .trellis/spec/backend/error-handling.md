# Error Handling

> How errors are handled in this project.

---

## Overview

The shared `quality` CLI returns stable Agent-friendly JSON by default. Commands raise
`QualityCliError` for expected failures and the CLI layer converts those errors into the
`quality.ai/v1` response envelope.

---

## Error Types

### Scenario: `quality` CLI JSON Error Contract

#### 1. Scope / Trigger

Use this contract for shared local-first commands under `quality_core.cli`, especially workspace,
project, plugin, resource, validation, projection, export, and Git commands.

#### 2. Signatures

```python
# src/quality_core/cli/errors.py
@dataclass(slots=True)
class QualityCliError(Exception):
    code: str
    message: str
    path: str | None = None
    field: str | None = None
    suggestion: str | None = None
    target: dict[str, Any] | None = None
    severity: str = "error"

    @property
    def resolved_exit_code(self) -> int: ...
    def to_error(self) -> dict[str, Any]: ...

# src/quality_core/cli/output.py
def success_result(*, command: str, data: dict[str, Any] | None = None, warnings: list[dict[str, Any]] | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]: ...
def failure_result(*, command: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]] | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]: ...
```

#### 3. Contracts

Success payload:

```json
{
  "contractVersion": "quality.ai/v1",
  "ok": true,
  "command": "quality project create",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "workspaceRoot": "...",
    "projectSlug": "cooling-fan-controller",
    "projectRoot": "..."
  }
}
```

Failure payload:

```json
{
  "contractVersion": "quality.ai/v1",
  "ok": false,
  "command": "quality project create",
  "data": null,
  "warnings": [],
  "errors": [
    {
      "code": "PROJECT_NOT_FOUND",
      "severity": "error",
      "message": "Project 'demo' was not found.",
      "suggestion": "Create the project with `quality project create <slug>`."
    }
  ],
  "meta": {}
}
```

Use camelCase field names for the new `quality` contract. Do not reuse the historical
`dfmea_cli.contracts` `contract_version` shape for new shared commands.

#### 4. Validation & Error Matrix

| Error family | Codes | Exit code |
| --- | --- | --- |
| Unexpected/internal | `UNKNOWN` or unmapped codes | 1 |
| Validation failed | `VALIDATION_FAILED` | 3 |
| Workspace/project/plugin/resource config | `WORKSPACE_NOT_FOUND`, `PROJECT_NOT_FOUND`, `PROJECT_AMBIGUOUS`, `PROJECT_ADDRESS_MISMATCH`, `INVALID_WORKSPACE_CONFIG`, `INVALID_PROJECT_CONFIG`, `INVALID_PROJECT_SLUG`, `PLUGIN_NOT_FOUND`, `PLUGIN_NOT_ENABLED`, `PLUGIN_DISABLE_BLOCKED`, `RESOURCE_NOT_FOUND`, `ID_CONFLICT`, `ID_PREFIX_MISMATCH`, `INVALID_PARENT`, `NODE_NOT_EMPTY`, `OPENCODE_ADAPTER_CONFLICT` | 4 |
| Git state | `GIT_DIRTY`, `GIT_CONFLICT`, `RESTORE_PRECONDITION_FAILED` | 5 |
| File write/lock/atomicity | `FILE_LOCKED`, `ATOMIC_WRITE_FAILED`, `FILE_WRITE_FAILED` | 6 |
| Schema/plugin version | `SCHEMA_VERSION_MISMATCH`, `MIGRATION_REQUIRED` | 7 |

#### 5. Good/Base/Bad Cases

Good:

```python
raise QualityCliError(
    code="PROJECT_NOT_FOUND",
    message=f"Project '{project}' was not found.",
    target={"project": project},
    suggestion="Create the project with `quality project create <slug>`.",
)
```

Base:

```python
payload = success_result(
    command="quality project create",
    data={"project": {"id": "PRJ", "slug": project.slug}},
    meta={"workspaceRoot": str(workspace_root), "projectSlug": project.slug},
)
```

Bad:

```python
typer.echo("project created")
```

Human-only output is not the default because Agents need stable JSON fields.

#### 6. Tests Required

- Assert `contractVersion == "quality.ai/v1"` for new shared commands.
- Assert project commands include `meta.projectSlug` and `meta.projectRoot`.
- Assert expected failures return a non-zero exit code and an `errors[0].code`.
- Assert schema version mismatch returns exit code `7` and `SCHEMA_VERSION_MISMATCH`.
- Keep historical `dfmea` JSON shape unchanged until those commands are explicitly migrated.

#### 7. Wrong vs Correct

Wrong:

```python
from dfmea_cli.contracts import success_result
```

Correct:

```python
from quality_core.cli.output import success_result
```

### Scenario: Resource Store Errors

#### 1. Scope / Trigger

Use this contract for `quality_core.resources` failures raised while resolving plugin resource
paths, validating resource IDs, allocating IDs, deleting resources, acquiring locks, or writing
files atomically.

#### 2. Signatures

```python
# src/quality_core/cli/errors.py
def exit_code_for_error(code: str) -> int: ...

# src/quality_core/resources/store.py
class ResourceStore:
    def create(self, resource: Resource) -> WriteResult: ...
    def update(self, resource: Resource) -> WriteResult: ...
    def delete(self, ref: ResourceRef) -> WriteResult: ...

# src/quality_core/resources/locks.py
class ProjectWriteLock:
    def acquire(self) -> ProjectWriteLock: ...
    def release(self) -> None: ...
```

#### 3. Contracts

- Expected resource failures raise `QualityCliError`; callers must not convert them to ad hoc
  strings.
- Resource identity and path errors are user-correctable project/resource config failures and return
  exit code `4`.
- Lock and atomic write failures are filesystem/write failures and return exit code `6`.
- Resource errors should include `path` when tied to a file and `target` when tied to a
  `kind/resourceId` pair.
- Project lock release must remove `.quality/locks/project.lock` only when that lock object acquired
  the file.

#### 4. Validation & Error Matrix

| Case | Code | Exit code | Required fields |
| --- | --- | --- | --- |
| Resource file or descriptor target missing | `RESOURCE_NOT_FOUND` | 4 | `path` or `target` |
| Create target already exists | `ID_CONFLICT` | 4 | `path`, `target.kind`, `target.resourceId` |
| Prefix/path/singleton ID mismatch | `ID_PREFIX_MISMATCH` | 4 | `path` or `target` |
| Invalid DFMEA structure parent hierarchy | `INVALID_PARENT` | 4 | `target.nodeType`, `target.parentRef` |
| Delete blocked by child structure nodes | `NODE_NOT_EMPTY` | 4 | `target.nodeId`, `target.children` |
| Project lock already held until timeout | `FILE_LOCKED` | 6 | `path`, `suggestion` |
| Temporary sibling write or replace fails | `ATOMIC_WRITE_FAILED` | 6 | `path`, `suggestion` |

#### 5. Good/Base/Bad Cases

Good:

```python
raise QualityCliError(
    code="ID_CONFLICT",
    message=f"Resource '{resource.resource_id}' already exists.",
    path=str(path),
    target={"kind": resource.kind, "resourceId": resource.resource_id},
    suggestion="Allocate a new ID or update the existing resource.",
)
```

Base:

```python
raise QualityCliError(
    code="FILE_LOCKED",
    message=f"Project write lock is held at '{lock_path}'.",
    path=str(lock_path),
    suggestion="Wait for the other write command to finish and retry.",
)
```

Bad:

```python
raise RuntimeError("could not write resource")
```

#### 6. Tests Required

- Assert resource error codes map to exit code `4`.
- Assert DFMEA structure hierarchy errors map to exit code `4`.
- Assert `FILE_LOCKED` and `ATOMIC_WRITE_FAILED` map to exit code `6`.
- Assert lock contention raises `FILE_LOCKED`.
- Assert create collision raises `ID_CONFLICT` when a target file already exists.
- Assert path/ID mismatch raises `ID_PREFIX_MISMATCH`.

#### 7. Wrong vs Correct

Wrong:

```python
except FileExistsError:
    return {"ok": False, "message": "busy"}
```

Correct:

```python
except FileExistsError as exc:
    raise QualityCliError(
        code="FILE_LOCKED",
        message=f"Project write lock is held at '{self.path}'.",
        path=str(self.path),
        suggestion="Wait for the other write command to finish and retry.",
    ) from exc
```

### Scenario: Migrated DFMEA Analysis And ID Repair Errors

#### 1. Scope / Trigger

Use this contract for migrated `dfmea analysis` commands and `quality project id/repair` commands
that operate on local-first YAML resources.

#### 2. Signatures

```python
# src/quality_methods/dfmea/analysis_service.py
def add_failure_chain(*, project: ProjectConfig, function_ref: str, chain_spec: dict[str, Any]) -> AnalysisMutationResult: ...

# src/quality_core/resources/repair.py
def renumber_project_resource_id(*, project: ProjectConfig, from_id: str, to_id: str) -> RenumberResult: ...
def repair_project_id_conflicts(*, project: ProjectConfig) -> IdConflictRepairResult: ...
```

#### 3. Contracts

- Migrated `dfmea analysis` commands emit the same `quality.ai/v1` envelope as shared `quality`
  commands.
- User input validation failures use `VALIDATION_FAILED` with `field` or `target.option`.
- Missing initialized DFMEA state is still `PLUGIN_NOT_ENABLED`.
- Parent/scope mismatch uses `INVALID_PARENT`, for example attaching an FN to `SYS-*` or linking a
  REQ from a different function to an FM.
- ID repair failures use existing resource error codes: `RESOURCE_NOT_FOUND`, `ID_CONFLICT`, and
  `ID_PREFIX_MISMATCH`.
- `quality project repair id-conflicts` may return success with an empty `renumbers` list when no
  repairable path/metadata conflicts exist.

#### 4. Validation & Error Matrix

| Case | Code | Exit code | Required fields |
| --- | --- | --- | --- |
| Missing option after alias normalization | `VALIDATION_FAILED` | 3 | `target.option` |
| Malformed `--input` JSON | `VALIDATION_FAILED` | 3 | `path` |
| S/O/D outside 1-10 | `VALIDATION_FAILED` | 3 | `field` |
| Unknown AP/action/status value | `VALIDATION_FAILED` | 3 | `field` |
| Function component is not `COMP-*` | `INVALID_PARENT` | 4 | `target.componentRef` |
| REQ/CHAR/FC belongs to a different parent scope | `INVALID_PARENT` | 4 | `target.resourceId` |
| Explicit renumber source missing | `RESOURCE_NOT_FOUND` | 4 | `target.fromId` |
| Explicit renumber source duplicated | `ID_CONFLICT` | 4 | `target.paths` |
| Explicit renumber target already used or tombstoned | `ID_CONFLICT` | 4 | `path` or `target.toId` |

#### 5. Good/Base/Bad Cases

Good:

```python
raise QualityCliError(
    code="VALIDATION_FAILED",
    message="Field 'severity' must be in range 1-10.",
    field="severity",
    target={"field": "severity"},
    suggestion="Provide severity in range 1-10.",
)
```

Base:

```python
raise QualityCliError(
    code="ID_CONFLICT",
    message="Target ID 'FM-002' is already used.",
    path=str(existing_path),
    target={"toId": "FM-002", "existingPath": str(existing_path)},
    suggestion="Choose an unused ID.",
)
```

Bad:

```python
raise ValueError("bad severity")
```

Expected user-correctable input errors must remain structured.

### Scenario: Validation Issue Reporting

#### 1. Scope / Trigger

Use this contract for local-first validation reports returned by `dfmea validate` and future
`quality project validate`.

#### 2. Signatures

```python
# src/quality_core/validation/issue.py
class ValidationIssue:
    def to_dict(self) -> dict[str, Any]: ...

# src/quality_core/cli/output.py
def validation_result(*, command: str, data: dict[str, Any], ok: bool, warnings: list[dict[str, Any]] | None = None, errors: list[dict[str, Any]] | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]: ...
```

#### 3. Contracts

- Validation issues are data, not exceptions.
- `ValidationIssue.to_dict()` uses camelCase keys: `resourceId`, `pluginId`, and `field`.
- Error-level validation issues cause the command envelope to include a top-level
  `VALIDATION_FAILED` error and exit with code `3`.
- Warning-only reports may return `ok: true`; warning issues remain in `data.issues`.
- Command setup/config failures, such as missing workspace or missing enabled plugin, still use
  `failure_result` with `QualityCliError`.
- Validation should report all practical issues in one run; malformed resources become
  `SCHEMA_VALIDATION_FAILED` issues instead of aborting the whole command.

#### 4. Validation & Error Matrix

| Case | Issue/Error code | Exit code | Location |
| --- | --- | --- | --- |
| Clean project | none | 0 | `data.summary.errors == 0` |
| Resource schema/envelope invalid | `SCHEMA_VALIDATION_FAILED` | 3 | `data.issues[]` |
| Duplicate source ID | `DUPLICATE_ID` | 3 | `data.issues[]` |
| Missing reference | `REFERENCE_NOT_FOUND` | 3 | `data.issues[]` |
| Invalid path or prefix | `ID_PREFIX_MISMATCH` | 3 | `data.issues[]` |
| AP mismatch | `AP_MISMATCH` warning | 0 if no errors | `data.issues[]` |
| Missing workspace/project/plugin | existing `QualityCliError` code | mapped code | top-level `errors[]` |

#### 5. Good/Base/Bad Cases

Good:

```json
{
  "contractVersion": "quality.ai/v1",
  "ok": false,
  "command": "dfmea validate",
  "data": {
    "summary": {"errors": 1, "warnings": 0, "issues": 1},
    "issues": [
      {
        "code": "REFERENCE_NOT_FOUND",
        "severity": "error",
        "field": "spec.causeRefs[0]"
      }
    ]
  },
  "errors": [{"code": "VALIDATION_FAILED", "severity": "error"}]
}
```

Bad:

```python
raise QualityCliError(code="REFERENCE_NOT_FOUND", ...)
```

Do not raise for ordinary validation findings after the project and plugin can be loaded.

---

### Scenario: Migrated DFMEA Query, Trace, And Context Errors

#### 1. Scope / Trigger

Use this contract for `dfmea query`, `dfmea trace`, and `dfmea context` commands that read
local-first YAML resources through `quality_core.graph`.

#### 2. Signatures

```python
# src/quality_methods/dfmea/query_service.py
def query_get(*, project: ProjectConfig, resource_id: str) -> DfmeaQueryResult: ...

# src/quality_methods/dfmea/trace_service.py
def trace_causes(*, project: ProjectConfig, failure_mode_ref: str, depth: int) -> DfmeaTraceResult: ...

# src/quality_methods/dfmea/context_service.py
def failure_chain_context(*, project: ProjectConfig, failure_mode_ref: str) -> DfmeaContextResult: ...
```

#### 3. Contracts

- Migrated read commands emit the `quality.ai/v1` envelope, not the historical `dfmea_cli.contracts`
  snake_case envelope.
- Command setup/config failures use `QualityCliError` and `failure_result`.
- Invalid user filter options use `VALIDATION_FAILED` and exit code `3`.
- Missing graph resources use `RESOURCE_NOT_FOUND` and exit code `4`.
- Valid IDs with the wrong kind/scope use `INVALID_PARENT` and exit code `4`.
- Query/trace/context success metadata includes `meta.freshness.mode == "source-scan"` until Phase 8
  introduces projection manifest freshness enforcement.
- Do not wrap malformed project source as SQLite errors; local-first read failures should point to
  the YAML path or project resource target.

#### 4. Validation & Error Matrix

| Case | Code | Exit code | Required fields |
| --- | --- | --- | --- |
| Missing `--type`, `--keyword`, `--fm`, etc. | `VALIDATION_FAILED` | 3 | `target.option` |
| Bad integer option such as `--gte abc` | `VALIDATION_FAILED` | 3 | `target.option`, `target.value` |
| Unsupported AP/action status/filter type | `VALIDATION_FAILED` | 3 | relevant target field |
| Query resource not found | `RESOURCE_NOT_FOUND` | 4 | `target.resourceId` |
| Summary component is not `COMP-*` | `INVALID_PARENT` | 4 | `target.resourceId`, `target.kind` |
| Trace/context root is not a `FailureMode` | `INVALID_PARENT` | 4 | `target.resourceId`, `target.kind` |
| Project link set filename/ID mismatch | `ID_PREFIX_MISMATCH` | 4 | `path`, `target.resourceId` |

#### 5. Good/Base/Bad Cases

Good:

```python
raise QualityCliError(
    code="RESOURCE_NOT_FOUND",
    message=f"Resource '{resource_id}' was not found.",
    target={"resourceId": resource_id},
    suggestion="Use an existing project-local resource ID.",
)
```

Bad:

```python
except sqlite3.Error:
    ...
```

Migrated Phase 7 read commands must not depend on SQLite.

---

### Scenario: Migrated DFMEA Projection And Export Errors

#### 1. Scope / Trigger

Use this contract for `dfmea projection` and `dfmea export` commands that build generated files from
local-first YAML source resources.

#### 2. Signatures

```python
# src/quality_core/projections/freshness.py
def projection_freshness(*, project: ProjectConfig, domain: str) -> ProjectionFreshness: ...

# src/quality_methods/dfmea/projections.py
def rebuild_projections(*, project: ProjectConfig) -> DfmeaProjectionResult: ...

# src/quality_methods/dfmea/exports.py
def export_markdown(*, project: ProjectConfig, out_dir: Path | None = None, layout: str = "review") -> DfmeaExportResult: ...
def export_risk_csv(*, project: ProjectConfig, out_dir: Path | None = None) -> DfmeaExportResult: ...
```

#### 3. Contracts

- Migrated projection/export commands emit the `quality.ai/v1` envelope.
- Missing workspace/project/DFMEA initialization uses existing `QualityCliError` config codes.
- Stale projections are status data, not command failures, for `dfmea projection status`.
- Malformed projection manifests use `INVALID_PROJECT_CONFIG` with `path`.
- Export option validation uses `VALIDATION_FAILED`.
- Projection and export file writes use `atomic_write_text` where practical; atomic write failures
  surface as `ATOMIC_WRITE_FAILED`.
- Generated outputs are not source data and are reported with generated output management metadata,
  not staged or committed by Phase 8 commands.

#### 4. Validation & Error Matrix

| Case | Code/status | Exit code | Required fields |
| --- | --- | --- | --- |
| Projection manifest missing | `data.freshness.status == "missing"` | 0 | `data.freshness.manifestPath` |
| Source/schema hash changed | `data.freshness.status == "stale"` | 0 | `data.freshness.reasons[]` |
| Malformed manifest JSON | `INVALID_PROJECT_CONFIG` | 4 | `path` |
| Unsupported markdown layout | `VALIDATION_FAILED` | 3 | `target.layout` |
| Export output is a file | `VALIDATION_FAILED` | 3 | `path`, `target.out` |
| Projection/export write failed | `ATOMIC_WRITE_FAILED` | 6 | `path` |

#### 5. Good/Base/Bad Cases

Good:

```python
raise QualityCliError(
    code="VALIDATION_FAILED",
    message=f"Unsupported export layout '{layout}'.",
    target={"layout": layout},
    suggestion="Use --layout review or --layout ledger.",
)
```

Base:

```json
{
  "freshness": {
    "status": "stale",
    "stale": true,
    "reasons": ["sources_changed"]
  }
}
```

Bad:

```python
from dfmea_cli.services.export_markdown import export_markdown
```

Migrated Phase 8 commands must not call SQLite-backed export services.

---

## Error Handling Patterns

- Business/config functions raise `QualityCliError`; command functions catch it once and emit JSON.
- Include `path` when the error is tied to a file.
- Include `field` when a YAML/JSON field is invalid.
- Include `suggestion` for every expected user-correctable failure.

---

## API Error Responses

This project currently exposes local CLI responses, not HTTP responses, for the quality core. The
stable response envelope is still treated as an API contract because Agents consume it.

---

## Common Mistakes

- Do not print ad hoc success strings from shared `quality` commands by default.
- Do not return snake_case contract fields from new `quality_core` commands.
- Do not catch broad `Exception` in command handlers unless converting it to a documented internal
  error shape.
