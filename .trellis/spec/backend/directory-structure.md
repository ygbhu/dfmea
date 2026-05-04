# Directory Structure

> How backend code is organized in this project.

---

## Overview

The current product is an OpenCode-bound quality assistant. OpenCode is the required product host,
while the Python engine remains the authoritative implementation for quality data, method behavior,
validation, projections, exports, and Git-aware workflows. Active CLI wiring lives under
`src/quality_adapters/cli/` and is called by the OpenCode plugin. The `dfmea_cli` package remains a
thin compatibility namespace for historical imports, while shared local-first behavior lives under
`src/quality_core/` and domain implementation lives under `src/quality_methods/`.

Do not replace the Python implementation language during V1 migration. Shared workspace, project,
resource, validation, projection, export, and Git behavior belongs in `quality_core`; domain
plugin contracts and file-backed domain services belong under `quality_methods.<domain>`. OpenCode
integrations belong under `quality_adapters.opencode` and the repository-level `plugin/` package.
They must call CLI or shared-core contracts instead of owning source data.
The old SQLite-backed `dfmea_cli.services`, `dfmea_cli.db`, `dfmea_cli.resolve`,
`dfmea_cli.schema`, and historical `dfmea_cli` JSON/error helper modules are retired.

---

## Directory Layout

```text
plugin/
  package.json
  plugin.js
  bin/opencode-quality.js
engine/
  src/
    dfmea_cli/
      __main__.py
      cli.py
      commands/
    quality_core/
      cli/
        quality.py
        output.py
        errors.py
      graph/
        loader.py
        model.py
      git/
        paths.py
        project.py
        runner.py
      projections/
        freshness.py
      methods/
        contracts.py
        registry.py
      plugins/
        contracts.py
        registry.py
        schema_snapshots.py
        project_plugins.py
      validation/
        json_schema.py
      workspace/
        discovery.py
        config.py
        project.py
      resources/
        atomic.py
        envelope.py
        ids.py
        locks.py
        paths.py
        store.py
    quality_methods/
      dfmea/
        plugin.py
        lifecycle.py
        structure_service.py
        query_service.py
        trace_service.py
        context_service.py
        projections.py
        exports.py
        schemas/
      pfmea/
        __init__.py  # placeholder only
    quality_adapters/
      cli/
        quality.py
        dfmea.py
        dfmea_commands/
      opencode/
        installer.py
        templates/
  tests/
    adapters/
      cli/
        test_quality_workspace_project.py
        test_dfmea_file_backed_commands.py
        test_dfmea_file_backed_query_trace_context.py
        test_dfmea_file_backed_projection_export.py
    core/
      test_quality_project_git_commands.py
      test_quality_methods.py
      test_quality_resources.py
```

---

## Module Organization

### Scenario: Local-first Workspace And Project Foundation

#### 1. Scope / Trigger

Use this structure when implementing `quality` CLI commands, workspace discovery, project config
loading, project-local `.quality/` state, or shared file-backed foundations.

#### 2. Signatures

Current Phase 1 module boundaries:

```python
# src/quality_core/workspace/discovery.py
def discover_workspace_root(*, workspace: Path | None = None, start: Path | None = None) -> Path: ...

# src/quality_core/workspace/config.py
def load_workspace_config(workspace_root: Path) -> WorkspaceConfig: ...
def load_workspace_plugins(workspace_root: Path) -> WorkspacePluginsConfig: ...

# src/quality_core/workspace/project.py
def create_project(*, workspace_config: WorkspaceConfig, slug: str, name: str | None = None) -> ProjectCreateResult: ...
def load_project_config(project_root: Path) -> ProjectConfig: ...
def resolve_project_root(*, workspace_config: WorkspaceConfig, project: str) -> Path: ...
```

#### 3. Contracts

- `dfmea_cli` remains import-compatible for existing DFMEA commands, but active command
  implementations live under `quality_adapters.cli.dfmea_commands`.
- `quality_core` owns shared local-first behavior and must not import from `dfmea_cli` services.
- `quality_methods.dfmea` is the DFMEA method namespace; Phase 1 keeps it as an importable package
  placeholder.
- `pyproject.toml` must expose CLI scripts through the adapter package:

```toml
[project.scripts]
dfmea = "quality_adapters.cli.dfmea:main"
quality = "quality_adapters.cli.quality:main"
```

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| Workspace discovery | `.quality/workspace.yaml` exists at explicit or ancestor root | `WORKSPACE_NOT_FOUND` |
| Project singleton ID | `metadata.id == "PRJ"` | `INVALID_PROJECT_CONFIG` |
| Project slug/address | `metadata.slug == project directory name` | `PROJECT_ADDRESS_MISMATCH` |
| Project slug format | lowercase letters, digits, hyphens | `INVALID_PROJECT_SLUG` |

#### 5. Good/Base/Bad Cases

Good:

```text
quality workspace init --workspace ./demo
quality project create cooling-fan-controller --workspace ./demo
```

Base:

```text
cd ./demo/some/nested/path
quality project create brake-controller
```

Bad:

```text
quality project create "Cooling Fan"
```

This fails because project directory identity must be a stable slug.

#### 6. Tests Required

- Import `quality_core` and `quality_methods.dfmea`.
- CLI test for `quality workspace init`.
- CLI test for `quality project create <slug>`.
- Test project loading validates `metadata.id` and `metadata.slug`.
- Test upward workspace discovery from a nested current directory.

#### 7. Wrong vs Correct

Wrong:

```python
# Do not put shared workspace behavior under dfmea_cli.
from dfmea_cli.services.projects import initialize_project
```

Correct:

```python
from quality_core.workspace.project import create_project
```

---

## Naming Conventions

- Python packages use lowercase snake_case.
- Shared local-first modules live under `quality_core`.
- Product-level quality method discovery lives under `quality_core.methods`.
- Domain method packages live under `quality_methods.<domain>`.
- Active CLI adapter entrypoints live under `quality_adapters.cli`.
- OpenCode adapter templates live under `quality_adapters.opencode`.
- The repository-level `plugin/` package is the OpenCode product entrypoint and must remain thin.
- Quality project directory slugs use lowercase letters, digits, and hyphens.
- The V1 project singleton ID is always `PRJ`.

### Scenario: Host Adapter Boundary

#### 1. Scope / Trigger

Use this boundary when adding OpenCode-facing plugin behavior or future UI host behavior.

#### 2. Signatures

The active CLI adapter is implemented under `engine/src/quality_adapters/cli/`. OpenCode-facing
modules must call one of these contracts:

```python
# preferred process boundary for hosts
quality ... --format json
dfmea ... --format json
pfmea ... --format json

# allowed only when preserving the same rules as CLI
from quality_core.resources.store import ResourceStore
from quality_core.validation.engine import validate_project
from quality_core.git.project import project_snapshot
```

#### 3. Contracts

- OpenCode-facing code is not a quality method. DFMEA, PFMEA, and future Control Plan remain under
  `quality_methods.<domain>` and are discovered through `quality_core.methods`.
- OpenCode is the required product host, but it must not become the source-of-truth writer.
- OpenCode plugin and command code may parse the `quality.ai/v1` JSON envelope returned by CLI
  commands.
- OpenCode-facing writes must use CLI commands or shared core functions that enforce project locks,
  resource path descriptors, ID allocation, tombstones, validation, and Git contracts.
- Node/OpenCode dependencies belong in `plugin/` or UI host code, not in `quality_core` or
  `quality_methods`.
- A copied external UI tree with independent write logic is not allowed.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| Adapter writes | CLI/shared core write path with lock and validation | Architecture violation |
| Host dependency | Isolated under `plugin/`, UI host code, or `quality_adapters.opencode` templates | Architecture violation |
| Domain logic | Lives under `quality_methods.<domain>` | Architecture violation |
| Source of truth | Project files under `projects/<slug>/` | Architecture violation |

#### 5. Good/Base/Bad Cases

Good:

```python
subprocess.run(
    ["quality", "project", "status", "--workspace", str(workspace), "--project", slug],
    check=True,
    capture_output=True,
    text=True,
)
```

Base:

```python
from quality_core.resources.store import ResourceStore
```

This is acceptable only if the adapter preserves the same locking, path, validation, and Git
contracts used by CLI commands.

Bad:

```python
# Do not let an adapter invent resource paths or write source YAML directly.
(project_root / "dfmea" / "failure-modes" / "FM-001.yaml").write_text(...)
```

#### 6. Tests Required

- Adapter command/tool tests must assert `quality.ai/v1` JSON parsing.
- Adapter write tests must prove project locks, ID allocation, tombstones, and validation are
  honored through the shared write path.
- Adapter integration tests must prove no independent source-of-truth files are created outside the
  quality project model.

#### 7. Wrong vs Correct

Wrong:

```python
from quality_adapters.opencode_ui.writer import allocate_dfmea_id
```

Correct:

```python
from quality_core.resources.store import ResourceStore
```

### Scenario: Built-in Plugin Registry And Schema Snapshots

#### 1. Scope / Trigger

Use this structure when implementing built-in method discovery, project-local schema snapshots,
plugin enable/disable commands, or plugin schema version checks.

#### 2. Signatures

```python
# src/quality_core/methods/registry.py
def list_quality_methods() -> list[QualityMethod]: ...
def list_active_quality_methods() -> list[QualityMethod]: ...

# src/quality_core/plugins/registry.py
def list_builtin_plugins() -> list[BuiltinPlugin]: ...
def get_builtin_plugin(plugin_id: str) -> BuiltinPlugin: ...

# src/quality_core/plugins/schema_snapshots.py
def copy_plugin_schema_snapshot(*, plugin: BuiltinPlugin, project_root: Path) -> Path: ...
def ensure_project_schema_snapshot_current(*, plugin: BuiltinPlugin, project_root: Path) -> PluginSchemaSnapshot: ...

# src/quality_core/plugins/project_plugins.py
def list_project_plugin_statuses(project: ProjectConfig | None = None) -> list[PluginStatus]: ...
def enable_project_plugin(*, project_root: Path, plugin_id: str) -> PluginEnableResult: ...
def disable_project_plugin(*, project_root: Path, plugin_id: str) -> PluginDisableResult: ...

# src/quality_methods/dfmea/plugin.py
def get_plugin() -> BuiltinPlugin: ...

# src/quality_methods/dfmea/method.py
def get_method() -> QualityMethod: ...
```

#### 3. Contracts

- Built-in quality methods are Python modules shipped with the tooling repository.
- `quality method list` reports active and planned methods; currently DFMEA is active and PFMEA is
  planned.
- `quality plugin list` reports active schema/resource plugins for implemented methods; currently
  DFMEA only.
- External plugin installation is out of V1 scope.
- Canonical plugin schemas live under `src/quality_methods/<plugin>/schemas/`.
- `pyproject.toml` must package schema files:

```toml
[tool.setuptools.package-data]
"quality_methods.dfmea" = ["schemas/*"]
```

- Project schema snapshots are copied to
  `projects/<slug>/.quality/schemas/<plugin-id>/`.
- `plugin.yaml` in the snapshot must include `metadata.pluginId` and `metadata.version`.
- Enabled project plugins must compare snapshot version with the tooling plugin version before
  project-aware plugin commands return success.
- Phase 2 creates the plugin domain directory but does not create domain singleton resources like
  `dfmea/dfmea.yaml`; DFMEA init is a later phase.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| Unknown plugin id | ID appears in built-in registry | `PLUGIN_NOT_FOUND` |
| Disable not-enabled plugin | Project domain is enabled | `PLUGIN_NOT_ENABLED` |
| Disable non-empty domain | No domain `*.yaml` source files exist | `PLUGIN_DISABLE_BLOCKED` |
| Enabled snapshot exists | `.quality/schemas/<plugin-id>/plugin.yaml` exists | `PLUGIN_NOT_ENABLED` |
| Snapshot plugin ID | `metadata.pluginId` equals built-in plugin id | `SCHEMA_VERSION_MISMATCH` |
| Snapshot version | `metadata.version` equals tooling plugin version | `SCHEMA_VERSION_MISMATCH` |

#### 5. Good/Base/Bad Cases

Good:

```text
quality plugin list
quality plugin enable dfmea --project cooling-fan-controller
quality plugin list --project cooling-fan-controller
```

Base:

```text
quality plugin disable dfmea --project cooling-fan-controller
```

This is allowed only when the DFMEA domain has no source YAML resources.

Bad:

```text
quality plugin enable pfmea --project cooling-fan-controller
```

This fails until a PFMEA built-in plugin descriptor exists.

#### 6. Tests Required

- `quality plugin list` reports built-in `dfmea`.
- `quality plugin enable dfmea --project <project>` copies `plugin.yaml` and schemas.
- Project `spec.domains.dfmea.enabled` becomes `true`.
- `quality plugin list --project <project>` reports enabled state and snapshot version.
- Disable of an empty enabled domain sets enabled to `false` and keeps the snapshot.
- Unknown plugin returns `PLUGIN_NOT_FOUND`.
- Not-enabled disable returns `PLUGIN_NOT_ENABLED`.
- Edited snapshot version returns `SCHEMA_VERSION_MISMATCH` with exit code `7`.

#### 7. Wrong vs Correct

Wrong:

```python
# Do not hardcode schema-copy file lists in CLI handlers.
write_yaml_document(project_root / ".quality" / "schemas" / "dfmea" / "plugin.yaml", ...)
```

Correct:

```python
from quality_core.plugins.project_plugins import enable_project_plugin
```

### Scenario: File-backed Resource Store, IDs, And Locks

#### 1. Scope / Trigger

Use this structure when implementing shared file-backed resource behavior, plugin collection path
resolution, project-local ID allocation, tombstones, atomic writes, or project write locks.

#### 2. Signatures

```python
# src/quality_core/resources/envelope.py
def make_resource(
    *,
    kind: str,
    resource_id: str,
    spec: dict | None = None,
    metadata: dict | None = None,
    api_version: str = API_VERSION,
) -> Resource: ...
def load_resource(path: Path) -> Resource: ...
def dump_resource(resource: Resource) -> str: ...

# src/quality_core/resources/paths.py
def find_collection(
    plugin: BuiltinPlugin,
    *,
    kind: str,
    resource_id: str | None = None,
    id_prefix_value: str | None = None,
) -> PluginCollection: ...
def resource_path(*, project_root: Path, plugin: BuiltinPlugin, resource: Resource) -> Path: ...
def validate_resource_path(*, plugin: BuiltinPlugin, resource: Resource, path: Path) -> None: ...

# src/quality_core/resources/ids.py
def allocate_next_id(
    *,
    project_root: Path,
    plugin: BuiltinPlugin,
    collection: PluginCollection,
    id_prefix: str,
) -> str: ...
def write_tombstone(*, project_root: Path, resource_id: str, resource_kind: str) -> Path: ...

# src/quality_core/resources/locks.py
def project_lock_path(project_root: Path) -> Path: ...

# src/quality_core/resources/atomic.py
def atomic_write_text(path: Path, text: str) -> None: ...

# src/quality_core/resources/store.py
class ResourceStore:
    def ref(self, *, kind: str, resource_id: str) -> ResourceRef: ...
    def load(self, ref: ResourceRef) -> Resource: ...
    def list(self, selector: ResourceSelector | None = None) -> list[Resource]: ...
    def create(self, resource: Resource) -> WriteResult: ...
    def create_collection_resource(self, *, kind: str, id_prefix: str, spec: dict, metadata: dict | None = None) -> WriteResult: ...
    def update(self, resource: Resource) -> WriteResult: ...
    def delete(self, ref: ResourceRef) -> WriteResult: ...
```

#### 3. Contracts

- `quality_core.resources` is the shared local-first storage layer and must not import
  `dfmea_cli` services.
- Resource files use the `apiVersion/kind/metadata/spec` envelope and YAML serialization.
- Plugin descriptors declare singleton fixed paths and collection `{id}.yaml` paths; the store must
  resolve paths through those descriptors instead of hardcoding DFMEA directories.
- Collection file names must match `metadata.id`, and the ID prefix must be declared by the
  collection. Prefix comparisons use the parsed prefix set from `PluginCollection.id_prefix`, not
  substring matching.
- Singleton resources must use both the declared fixed file name and fixed ID.
- All write operations acquire `projects/<slug>/.quality/locks/project.lock`; reads do not require
  the lock.
- `atomic_write_text` writes a temporary sibling file, fsyncs it, then replaces the target with
  `os.replace`.
- ID allocation scans collection source files and `.quality/tombstones/<ID>` files, then returns
  `max + 1` with at least three digits. V1 must not add SQLite, PostgreSQL, or counter files for
  this purpose.
- Delete removes the resource file and creates a tombstone YAML document with
  `kind: IdTombstone`, `metadata.id`, `spec.deletedAt`, and `spec.resourceKind`.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| Resource envelope | `apiVersion == "quality.ai/v1"` and `metadata/spec` are mappings | `INVALID_PROJECT_CONFIG` |
| Unknown resource path target | Plugin has no matching singleton or collection | `RESOURCE_NOT_FOUND` |
| Existing create target | Target YAML file does not already exist | `ID_CONFLICT` |
| Collection ID prefix | Prefix appears in `allowed_prefixes(collection)` | `ID_PREFIX_MISMATCH` |
| Collection file name | Path basename equals `{metadata.id}.yaml` | `ID_PREFIX_MISMATCH` |
| Singleton path and ID | Declared file and fixed ID both match | `ID_PREFIX_MISMATCH` |
| Project write lock | Lock file can be exclusively created before timeout | `FILE_LOCKED` |
| Atomic write | Temporary sibling can be written and replaced | `ATOMIC_WRITE_FAILED` |

#### 5. Good/Base/Bad Cases

Good:

```python
store.create_collection_resource(
    kind="FailureMode",
    id_prefix="FM",
    metadata={"title": "Motor stalls"},
    spec={"functionRef": "FN-001"},
)
```

Base:

```python
store.update(make_resource(kind="FailureMode", resource_id="FM-001", spec={"severity": 8}))
```

Bad:

```python
# Do not infer path by concatenating DFMEA-specific strings in callers.
project.root / "dfmea" / "failure-modes" / "FM-001.yaml"
```

Use `ResourceStore.ref(...)` or `resource_path(...)` so plugin declarations remain the source of
truth.

#### 6. Tests Required

- Create, load, list, update, and delete a collection resource.
- Assert creating a resource whose YAML file already exists raises `ID_CONFLICT`.
- Assert generated collection YAML basename equals `metadata.id`.
- Assert singleton fixed ID and fixed file name validation.
- Assert filename/ID mismatch raises `ID_PREFIX_MISMATCH`, including through `ResourceStore.list`.
- Assert selector ID prefixes are exact parsed prefixes, not substrings.
- Assert deleting `FM-001` writes `.quality/tombstones/FM-001` and the next allocation returns
  `FM-002`.
- Assert concurrent writes fail with `FILE_LOCKED`.
- Assert an unacquired lock object cannot remove a lock owned by another operation.
- Assert atomic writes replace content and leave no temporary sibling files.

#### 7. Wrong vs Correct

Wrong:

```python
if selector.id_prefix and selector.id_prefix in collection.id_prefix:
    ...
```

Correct:

```python
from quality_core.resources.paths import allowed_prefixes

if selector.id_prefix in allowed_prefixes(collection):
    ...
```

### Scenario: DFMEA Init And Structure Command Migration

#### 1. Scope / Trigger

Use this structure when migrating `dfmea init` or `dfmea structure` commands from historical
SQLite-backed services to local-first project files.

#### 2. Signatures

```python
# src/quality_methods/dfmea/lifecycle.py
def initialize_dfmea_domain(
    *,
    workspace: Path | None,
    project: str,
    name: str | None = None,
) -> DfmeaInitResult: ...
def load_initialized_dfmea_project(
    *,
    workspace: Path | None,
    project: str,
) -> DfmeaProjectContext: ...

# src/quality_methods/dfmea/structure_service.py
def add_structure_node(
    *,
    project: ProjectConfig,
    node_type: str,
    title: str,
    parent_ref: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructureMutationResult: ...
def update_structure_node(
    *,
    project: ProjectConfig,
    node_ref: str,
    title: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructureMutationResult: ...
def move_structure_node(*, project: ProjectConfig, node_ref: str, parent_ref: str | None) -> StructureMutationResult: ...
def delete_structure_node(*, project: ProjectConfig, node_ref: str) -> StructureMutationResult: ...

# src/quality_adapters/cli/dfmea_commands/init.py
def init_command(
    project: str,
    workspace: Path | None = None,
    name: str | None = None,
    output_format: OutputFormat = OutputFormat.JSON,
    quiet: bool = False,
) -> None: ...

# src/quality_adapters/cli/dfmea_commands/structure.py
dfmea structure add-system --project <slug> --title <title>
dfmea structure add-subsystem --project <slug> --parent SYS-001 --title <title>
dfmea structure add-component --project <slug> --parent SUB-001 --title <title>
dfmea structure add/update/move/delete --project <slug> ...
```

#### 3. Contracts

- `quality_adapters.cli.dfmea_commands.init` and
  `quality_adapters.cli.dfmea_commands.structure` are Typer wiring only; domain logic lives under
  `quality_methods.dfmea`.
- `dfmea_cli.commands.*` modules are compatibility wrappers and must not contain new command
  implementation logic.
- Migrated commands use `quality_core.cli.output` and return `contractVersion: "quality.ai/v1"` with
  camelCase fields.
- Migrated init/structure commands do not require or accept `--db`, `--busy-timeout-ms`, or
  SQLite retry options.
- `dfmea init --project <slug>` requires an existing quality project, enables the DFMEA plugin if
  needed, creates schema snapshots, ensures all declared DFMEA collection directories, and creates
  `dfmea/dfmea.yaml` with fixed ID `DFMEA`.
- Structure commands require an initialized DFMEA domain. If the plugin is disabled or
  `dfmea/dfmea.yaml` is missing, return `PLUGIN_NOT_ENABLED`.
- Structure source resources use `kind: StructureNode`, collection IDs `SYS-*`, `SUB-*`, or
  `COMP-*`, title in `metadata.title`, type in `spec.nodeType`, and parent relationship in
  `spec.parentRef`.
- Valid parent hierarchy is `SYS -> SUB -> COMP`; systems have no parent.
- Delete refuses nodes with children and otherwise removes the source YAML through `ResourceStore`,
  creating a tombstone under `.quality/tombstones/<ID>`.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| Project exists | `--project` resolves under workspace projects root | `PROJECT_NOT_FOUND` |
| DFMEA initialized for structure commands | plugin enabled and `dfmea/dfmea.yaml` exists | `PLUGIN_NOT_ENABLED` |
| Structure ID/type prefix | `SYS`, `SUB`, or `COMP` | `ID_PREFIX_MISMATCH` |
| Parent hierarchy | no parent for `SYS`, `SYS` parent for `SUB`, `SUB` parent for `COMP` | `INVALID_PARENT` |
| Parent existence | referenced parent YAML exists | `RESOURCE_NOT_FOUND` |
| Delete precondition | no resource has `spec.parentRef == node_id` | `NODE_NOT_EMPTY` |
| Metadata JSON | `--metadata` decodes to a JSON object | `VALIDATION_FAILED` |

#### 5. Good/Base/Bad Cases

Good:

```text
dfmea init --workspace ./demo --project cooling-fan-controller
dfmea structure add-system --workspace ./demo --project cooling-fan-controller --title "Fan Controller"
dfmea structure add-subsystem --workspace ./demo --project cooling-fan-controller --parent SYS-001 --title "Motor Control"
dfmea structure add-component --workspace ./demo --project cooling-fan-controller --parent SUB-001 --title "Motor Driver"
```

Base:

```text
dfmea structure update --project cooling-fan-controller --node COMP-001 --title "Motor Driver Assembly"
dfmea structure move --project cooling-fan-controller --node COMP-001 --parent SUB-002
dfmea structure delete --project cooling-fan-controller --node COMP-001
```

Bad:

```text
dfmea structure add-component --project cooling-fan-controller --parent SYS-001 --title "Motor Driver"
```

This fails because a component must have a subsystem parent.

#### 6. Tests Required

- `dfmea init --workspace <root> --project <slug>` succeeds without `--db`.
- Init creates `dfmea/dfmea.yaml`, project-local schema snapshot, and every declared DFMEA
  collection directory.
- `add-system`, `add-subsystem`, and `add-component` create `SYS-001.yaml`, `SUB-001.yaml`, and
  `COMP-001.yaml`.
- Update changes source YAML `metadata.title`, optional metadata fields, and `spec.description`.
- Move changes `spec.parentRef`.
- Delete removes the source file and creates `.quality/tombstones/<ID>`.
- Missing parent returns a non-zero JSON response with `errors[0].code == "RESOURCE_NOT_FOUND"`.

#### 7. Wrong vs Correct

Wrong:

```python
from dfmea_cli.services.structure import add_structure_node
```

Correct:

```python
from quality_methods.dfmea.structure_service import add_structure_node
```

### Scenario: DFMEA Analysis Command Migration And ID Repair

#### 1. Scope / Trigger

Use this structure when migrating `dfmea analysis` commands or implementing project-local ID
renumber/repair behavior for file-backed resources.

#### 2. Signatures

```python
# src/quality_methods/dfmea/analysis_service.py
def add_function(*, project: ProjectConfig, component_ref: str, title: str, description: str | None = None) -> AnalysisMutationResult: ...
def add_requirement(*, project: ProjectConfig, function_ref: str, text: str, source: str | None = None) -> AnalysisMutationResult: ...
def add_characteristic(*, project: ProjectConfig, function_ref: str, text: str, value: str | None = None, unit: str | None = None) -> AnalysisMutationResult: ...
def add_failure_chain(*, project: ProjectConfig, function_ref: str, chain_spec: dict[str, Any]) -> AnalysisMutationResult: ...
def update_failure_cause(*, project: ProjectConfig, failure_cause_ref: str, occurrence: int | None = None, detection: int | None = None, ap: str | None = None, title: str | None = None) -> AnalysisMutationResult: ...
def update_action_status(*, project: ProjectConfig, action_ref: str, status: str) -> AnalysisMutationResult: ...
def compute_ap(severity: int, occurrence: int, detection: int) -> str: ...

# src/quality_core/resources/repair.py
def renumber_project_resource_id(*, project: ProjectConfig, from_id: str, to_id: str) -> RenumberResult: ...
def repair_project_id_conflicts(*, project: ProjectConfig) -> IdConflictRepairResult: ...
```

#### 3. Contracts

- `quality_adapters.cli.dfmea_commands.analysis` is Typer wiring only; migrated business logic
  lives in `quality_methods.dfmea.analysis_service`.
- `dfmea_cli.commands.analysis` is a compatibility wrapper and must not contain new command
  implementation logic.
- Migrated analysis commands use `--workspace` plus `--project` and do not accept `--db`,
  `--busy-timeout-ms`, or SQLite retry options.
- Analysis command output uses `quality.ai/v1` camelCase fields from `quality_core.cli.output`.
- `Function` resources store `metadata.title`, `spec.componentRef`, and optional
  `spec.description`.
- `Requirement` and `Characteristic` resources store `spec.functionRef`; same-function links from
  failure modes are stored in `FailureMode.spec.requirementRefs` and
  `FailureMode.spec.characteristicRefs`.
- Failure chains store `FailureMode.spec.functionRef`, `FailureEffect.spec.failureModeRef`,
  `FailureCause.spec.failureModeRef`, and `Action.spec.failureModeRef`.
- `FailureMode.spec.effectRefs`, `causeRefs`, and `actionRefs` mirror same-chain child resource IDs.
- `Action.spec.targetCauseRefs` stores FC resource IDs, while `add-failure-chain --target-causes`
  accepts 1-based FC creation-order indexes for the current request.
- AP calculation preserves the historical simplified matrix and returns `High`, `Medium`, or `Low`.
- `quality project id renumber` acquires the project write lock, rewrites the resource file and
  `metadata.id`, and replaces exact string references in resource `spec`/`status` values.
- `quality project repair id-conflicts` repairs collection files whose path ID and `metadata.id`
  conflict; it does not infer ambiguous semantic references between duplicated objects.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| DFMEA initialized for analysis commands | plugin enabled and `dfmea/dfmea.yaml` exists | `PLUGIN_NOT_ENABLED` |
| Component for function | `COMP-*` structure node with `spec.nodeType == "component"` | `INVALID_PARENT` |
| Function-local REQ/CHAR links | linked resource `spec.functionRef` equals FM `spec.functionRef` | `INVALID_PARENT` |
| S/O/D values | integers in range 1-10 | `VALIDATION_FAILED` |
| AP/action/status values | one of declared allowed values | `VALIDATION_FAILED` |
| Delete function | no REQ/CHAR/FM children still reference the FN | `NODE_NOT_EMPTY` |
| Renumber source | exactly one collection resource has `metadata.id == --from` | `RESOURCE_NOT_FOUND` or `ID_CONFLICT` |
| Renumber target | prefix valid for same kind and no file/resource/tombstone uses `--to` | `ID_PREFIX_MISMATCH` or `ID_CONFLICT` |

#### 5. Good/Base/Bad Cases

Good:

```text
dfmea analysis add-function --project cooling-fan-controller --component COMP-001 --title "Drive fan motor"
dfmea analysis add-failure-chain --project cooling-fan-controller --function FN-001 --fm-description "Motor stalls" --severity 8 --fc-description "Bearing seizure" --occurrence 4 --detection 5 --act-description "Add detection" --target-causes 1
quality project id renumber --project cooling-fan-controller --from FM-001 --to FM-002
```

Base:

```text
dfmea analysis update-action-status --project cooling-fan-controller --action ACT-001 --status in-progress
quality project repair id-conflicts --project cooling-fan-controller
```

Bad:

```text
dfmea analysis add-function --project cooling-fan-controller --component SYS-001 --title "Drive fan motor"
```

This fails because analysis functions must attach to component structure nodes.

#### 6. Tests Required

- `dfmea analysis add-function` creates `dfmea/functions/FN-001.yaml`.
- `dfmea analysis add-failure-chain` creates FM/FE/FC/ACT resources and same-chain refs.
- Updating FC occurrence/detection recalculates AP unless an explicit AP is provided.
- `dfmea analysis update-action-status` rewrites `Action.spec.status`.
- `quality project id renumber --from FM-001 --to FM-002` renames the resource and updates
  FE/FC/ACT references.
- `quality project repair id-conflicts` repairs a path/metadata same-ID conflict fixture.

#### 7. Wrong vs Correct

Wrong:

```python
from dfmea_cli.services.analysis import add_failure_chain
```

Correct:

```python
from quality_methods.dfmea.analysis_service import add_failure_chain
```

### Scenario: Local-first Validation Engine

#### 1. Scope / Trigger

Use this structure when implementing validation over local-first project source resources, migrating
`dfmea validate`, adding core schema/path/ID checks, or adding plugin-specific graph/methodology
rules.

#### 2. Signatures

```python
# src/quality_core/validation/issue.py
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    path: Path | str | None = None
    resource_id: str | None = None
    kind: str | None = None
    field: str | None = None
    suggestion: str | None = None
    target: dict[str, Any] | None = None
    plugin_id: str | None = None

# src/quality_core/validation/report.py
@dataclass(frozen=True, slots=True)
class ValidationReport:
    project: ProjectConfig
    issues: tuple[ValidationIssue, ...]
    schema_versions: dict[str, str]

# src/quality_core/validation/engine.py
def validate_project(*, project: ProjectConfig, plugin_validators: dict[str, PluginValidator] | None = None) -> ValidationReport: ...
def scan_project_resources(*, project: ProjectConfig, plugins: tuple[BuiltinPlugin, ...], snapshots: dict[str, PluginSchemaSnapshot]) -> ResourceScan: ...

# src/quality_methods/dfmea/validators.py
def validate_dfmea_project(*, project: ProjectConfig, resources: tuple[Resource, ...]) -> list[ValidationIssue]: ...

# src/quality_adapters/cli/dfmea_commands/validate.py
dfmea validate --workspace <root> --project <slug>
```

#### 3. Contracts

- `quality_core.validation` owns reusable validation issue/report types, enabled-plugin resource
  scanning, schema snapshot loading, JSON Schema subset checks, ID/path validation, duplicate ID
  checks, and nested `spec.links[].id` uniqueness checks.
- `quality_methods.dfmea.validators` owns DFMEA graph and methodology rules over the local-first
  resource shapes written by `structure_service` and `analysis_service`.
- `quality_adapters.cli.dfmea_commands.validate` is command wiring only and must not import
  historical `dfmea_cli.services.validate`.
- `dfmea_cli.commands.validate` is a compatibility wrapper.
- Validation findings are returned as `data.issues`; expected project setup failures still raise
  `QualityCliError` and use the normal failure envelope.
- Validation commands return `contractVersion: "quality.ai/v1"` and exit code `3` when any issue has
  `severity == "error"`.
- The V1 JSON Schema checker intentionally implements the subset used by plugin snapshots:
  `type`, `required`, `properties`, `const`, `enum`, and string `pattern`.
- Core validation should collect as many issues as possible instead of stopping on the first
  resource/schema/path problem.
- DFMEA validation must use exact resource IDs, not legacy SQLite rowids.

#### 4. Validation & Error Matrix

| Check | Valid | Issue code |
| --- | --- | --- |
| Resource envelope/schema | plugin snapshot schema subset passes | `SCHEMA_VALIDATION_FAILED` |
| Collection path and `metadata.id` | file basename equals `{metadata.id}.yaml` | `ID_PREFIX_MISMATCH` |
| Duplicate project-local resource IDs | one source resource per ID | `DUPLICATE_ID` |
| Nested link IDs | `spec.links[].id` unique inside parent resource | `DUPLICATE_ID` |
| Structure hierarchy | `SYS -> SUB -> COMP` | `INVALID_PARENT` or `REFERENCE_NOT_FOUND` |
| Function component reference | `Function.spec.componentRef` points to component node | `REFERENCE_NOT_FOUND` or `INVALID_PARENT` |
| Failure-chain references | FM/FE/FC/ACT same-chain refs resolve | `REFERENCE_NOT_FOUND` or `INVALID_PARENT` |
| AP consistency | `FailureCause.spec.ap == compute_ap(S,O,D)` | `AP_MISMATCH` warning |
| Action ownership | open action has owner | `ACTION_OWNER_MISSING` warning |

#### 5. Good/Base/Bad Cases

Good:

```text
dfmea validate --workspace ./demo --project cooling-fan-controller
```

Returns `ok: true` when no error-level issues exist.

Base:

```text
dfmea validate --project cooling-fan-controller
```

Returns `ok: false`, exit code `3`, and all collected `data.issues` when source files contain
validation errors.

Bad:

```python
from dfmea_cli.services.validate import run_validation
```

Do not call the legacy SQLite validation service from migrated validation commands.

#### 6. Tests Required

- Clean initialized DFMEA project validates with `summary.errors == 0`.
- Duplicate same-project resource IDs emit `DUPLICATE_ID`.
- Missing resource references emit `REFERENCE_NOT_FOUND`.
- Collection file/ID mismatch emits `ID_PREFIX_MISMATCH` without preventing other issues from being
  returned.
- Duplicate nested `spec.links[].id` values emit `DUPLICATE_ID` with the nested field path.
- Existing Phase 1-5 file-backed command tests still pass.

#### 7. Wrong vs Correct

Wrong:

```python
# Stops after the first malformed resource and hides later issues.
resource = load_resource(path)
validate_resource_path(plugin=plugin, resource=resource, path=path)
```

Correct:

```python
report = validate_project(
    project=context.project,
    plugin_validators={"dfmea": validate_dfmea_project},
)
```

---

### Scenario: Local-first Graph, Query, Trace, And Context

#### 1. Scope / Trigger

Use this structure when implementing local-first read/query behavior, graph indexes, DFMEA trace
commands, or Agent context bundle commands.

#### 2. Signatures

```python
# src/quality_core/graph/loader.py
def load_project_graph(*, project: ProjectConfig) -> ProjectGraph: ...

# src/quality_core/graph/model.py
@dataclass(frozen=True, slots=True)
class ProjectGraph:
    project: ProjectConfig
    resources: tuple[Resource, ...]
    resources_by_id: dict[str, Resource]
    resources_by_kind: dict[str, tuple[Resource, ...]]
    references_by_id: dict[str, tuple[GraphReference, ...]]
    links_by_source: dict[str, tuple[GraphLink, ...]]
    links_by_target: dict[str, tuple[GraphLink, ...]]
    actions_by_status: dict[str, tuple[Resource, ...]]
    risks_by_ap: dict[str, tuple[Resource, ...]]

# src/quality_methods/dfmea/query_service.py
def query_get(*, project: ProjectConfig, resource_id: str) -> DfmeaQueryResult: ...
def query_list(*, project: ProjectConfig, node_type: str, parent_ref: str | None = None) -> DfmeaQueryResult: ...
def query_search(*, project: ProjectConfig, keyword: str) -> DfmeaQueryResult: ...
def query_summary(*, project: ProjectConfig, component_ref: str) -> DfmeaQueryResult: ...
def query_map(*, project: ProjectConfig) -> DfmeaQueryResult: ...
def query_by_ap(*, project: ProjectConfig, ap: str) -> DfmeaQueryResult: ...
def query_by_severity(*, project: ProjectConfig, gte: int) -> DfmeaQueryResult: ...
def query_actions(*, project: ProjectConfig, status: str) -> DfmeaQueryResult: ...

# src/quality_methods/dfmea/trace_service.py
def trace_causes(*, project: ProjectConfig, failure_mode_ref: str, depth: int) -> DfmeaTraceResult: ...
def trace_effects(*, project: ProjectConfig, failure_mode_ref: str, depth: int) -> DfmeaTraceResult: ...

# src/quality_methods/dfmea/context_service.py
def failure_chain_context(*, project: ProjectConfig, failure_mode_ref: str) -> DfmeaContextResult: ...
```

#### 3. Contracts

- `quality_core.graph` owns reusable source graph loading/indexing and must not import historical
  `dfmea_cli.services`.
- Graph loading reads enabled plugin singleton/collection YAML resources plus project-level
  `links/*.yaml` `TraceLinkSet` resources.
- Graph loading validates plugin schema snapshot freshness enough to reject version mismatches, but
  Phase 7 query commands use direct source scans rather than generated projections.
- Graph indexes include `resources_by_id`, `resources_by_kind`, `resources_by_path`,
  `references_by_id`, `links_by_source`, `links_by_target`, `actions_by_status`, and `risks_by_ap`.
- `quality_adapters.cli.dfmea_commands.query`, `trace`, and `context` are Typer wiring only; DFMEA
  read semantics live under `quality_methods.dfmea`.
- `dfmea_cli.commands.query`, `trace`, and `context` are compatibility wrappers.
- Migrated query/trace/context commands use `--workspace` plus `--project`; they do not accept
  `--db`, SQLite retry, or busy-timeout options.
- Query resource summaries include `id`, `kind`, `domain`, `path`, `title`, and `summary`.
- Phase 7 freshness metadata uses `mode: source-scan`, `projectionStatus: not-built`, and
  `stale: false`. Full projection manifest freshness enforcement belongs to Phase 8.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| DFMEA initialized | plugin enabled and `dfmea/dfmea.yaml` exists | `PLUGIN_NOT_ENABLED` |
| Query ID | resource exists in graph | `RESOURCE_NOT_FOUND` |
| Query type | known DFMEA kind or prefix | `VALIDATION_FAILED` |
| Component summary | `component_ref` is a component `StructureNode` | `INVALID_PARENT` |
| AP filter | `High`, `Medium`, or `Low` | `VALIDATION_FAILED` |
| Severity threshold | integer 1-10 | `VALIDATION_FAILED` |
| Action status | `planned`, `in-progress`, or `completed` | `VALIDATION_FAILED` |
| Trace root | existing `FailureMode` resource | `RESOURCE_NOT_FOUND` or `INVALID_PARENT` |
| Trace depth | non-negative integer | `VALIDATION_FAILED` |
| Project-level link set | `kind: TraceLinkSet`, file stem equals `metadata.id` | `INVALID_PROJECT_CONFIG` or `ID_PREFIX_MISMATCH` |

#### 5. Good/Base/Bad Cases

Good:

```text
dfmea query get --workspace ./demo --project cooling-fan-controller FM-001
dfmea query actions --workspace ./demo --project cooling-fan-controller --status completed
dfmea context failure-chain --workspace ./demo --project cooling-fan-controller --failure-mode FM-001
```

Base:

```text
dfmea trace causes --project cooling-fan-controller --fm FM-001 --depth 2
```

Walks `TraceLinkSet` links whose source is an FC under the current FM and whose target is another FM.

Bad:

```python
from dfmea_cli.services.query import query_get
```

Do not call SQLite-backed query/trace services from migrated read commands.

#### 6. Tests Required

- `dfmea query get` returns resource `id`, `kind`, `path`, `title`, and source-scan freshness.
- `dfmea query list/search/summary/map/by-ap/by-severity/actions` read from YAML graph resources.
- `dfmea trace causes/effects` walks project link-set relationships without SQLite.
- `dfmea context failure-chain` returns root, related resources, links, paths, and freshness.
- Existing Phase 1-6 file-backed tests still pass.

---

### Scenario: Local-first Projection And Export

#### 1. Scope / Trigger

Use this structure when implementing projection manifests, projection freshness, generated
projection files, or generated DFMEA exports.

#### 2. Signatures

```python
# src/quality_core/projections/freshness.py
def collect_project_source_hashes(project: ProjectConfig) -> dict[str, str]: ...
def projection_freshness(*, project: ProjectConfig, domain: str) -> ProjectionFreshness: ...
def write_projection_manifest(
    *,
    project: ProjectConfig,
    domain: str,
    schema_versions: dict[str, str],
    projections: dict[str, str],
) -> dict[str, Any]: ...

# src/quality_methods/dfmea/projections.py
def get_projection_status(*, project: ProjectConfig) -> DfmeaProjectionResult: ...
def rebuild_projections(*, project: ProjectConfig) -> DfmeaProjectionResult: ...
def build_tree_projection(*, graph: ProjectGraph) -> dict[str, Any]: ...
def build_risk_register_projection(*, graph: ProjectGraph) -> dict[str, Any]: ...
def build_action_backlog_projection(*, graph: ProjectGraph) -> dict[str, Any]: ...
def build_traceability_projection(*, graph: ProjectGraph) -> dict[str, Any]: ...

# src/quality_methods/dfmea/exports.py
def export_markdown(*, project: ProjectConfig, out_dir: Path | None = None, layout: str = "review") -> DfmeaExportResult: ...
def export_risk_csv(*, project: ProjectConfig, out_dir: Path | None = None) -> DfmeaExportResult: ...
```

#### 3. Contracts

- `quality_core.projections` owns reusable source hashing, total `sourceHash`, projection manifest
  writing, and freshness checks.
- `quality_methods.dfmea.projections` owns DFMEA projection shapes built from `quality_core.graph`.
- `quality_methods.dfmea.exports` owns generated Markdown/CSV exports and must include source IDs
  and source paths.
- Projection source hashes include `project.yaml`, enabled domain source YAML files, project-level
  `links/*.yaml`, `.quality/schemas/**`, and tombstones. They exclude generated `projections/`,
  `exports/`, and `reports/` directories.
- `dfmea projection rebuild` writes:
  - `dfmea/projections/tree.json`
  - `dfmea/projections/risk-register.json`
  - `dfmea/projections/action-backlog.json`
  - `dfmea/projections/traceability.json`
  - `dfmea/projections/manifest.json`
- `dfmea projection status` reports stale when the manifest is missing, source file hashes differ,
  source files are added/removed/renamed, or schema snapshot hashes differ.
- Generated output config is materialized in `project.yaml` under `spec.generatedOutputs` and
  defaults to unmanaged generated outputs:
  `projectionsManaged: false`, `exportsManaged: false`, `reportsManaged: false`,
  `exportProfiles: []`.
- `quality_adapters.cli.dfmea_commands.projection` and
  `quality_adapters.cli.dfmea_commands.export_markdown` are Typer wiring only and must not call
  historical SQLite-backed `dfmea_cli.services.projections` or
  `dfmea_cli.services.export_markdown`.
- `dfmea_cli.commands.projection` and `dfmea_cli.commands.export_markdown` are compatibility
  wrappers.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| DFMEA initialized | plugin enabled and `dfmea/dfmea.yaml` exists | `PLUGIN_NOT_ENABLED` |
| Manifest JSON | object with `apiVersion: quality.ai/v1` and `kind: ProjectionManifest` | `INVALID_PROJECT_CONFIG` |
| Projection freshness | manifest sources and `sourceHash` match current source hashes | status `fresh`; otherwise status `stale` |
| Export layout | `review` or `ledger` | `VALIDATION_FAILED` |
| Export output path | directory or absent | `VALIDATION_FAILED` |
| Atomic writes | projection/export files can be replaced | `ATOMIC_WRITE_FAILED` |

#### 5. Good/Base/Bad Cases

Good:

```text
dfmea projection rebuild --workspace ./demo --project cooling-fan-controller
dfmea projection status --workspace ./demo --project cooling-fan-controller
dfmea export markdown --workspace ./demo --project cooling-fan-controller
dfmea export risk-csv --workspace ./demo --project cooling-fan-controller --out ./out
```

Base:

```text
dfmea projection status --project cooling-fan-controller
```

Returns `data.freshness.status == "missing"` before the first rebuild and `stale == true`.

Bad:

```python
from dfmea_cli.services.projections import rebuild_projections
```

Do not use SQLite-derived projection services from migrated Phase 8 commands.

#### 6. Tests Required

- `dfmea projection rebuild` writes the four DFMEA projection JSON files and manifest.
- Manifest includes `sourceHash`, source file hashes, schema versions, and projection hashes.
- Source YAML edits mark projection status stale.
- Project schema snapshot edits mark projection status stale.
- `project.yaml` generated output config defaults are materialized and unmanaged.
- Markdown export includes source IDs and source paths.
- CSV risk export includes source IDs and source paths.
- Existing Phase 1-7 file-backed tests still pass.

---

### Scenario: Project Git Version Commands

#### 1. Scope / Trigger

Use this structure when implementing `quality project status`, `snapshot`, `history`, `diff`, or
`restore` over local-first project files.

#### 2. Signatures

```python
# src/quality_core/git/paths.py
def collect_managed_project_paths(project: ProjectConfig) -> ManagedProjectPaths: ...

# src/quality_core/git/runner.py
def find_git_root(start: Path) -> Path: ...
def ensure_no_unresolved_conflicts(repo_root: Path) -> None: ...

# src/quality_core/git/project.py
def project_status(*, project: ProjectConfig) -> ProjectGitResult: ...
def project_snapshot(*, project: ProjectConfig, message: str | None = None) -> ProjectGitResult: ...
def project_history(*, project: ProjectConfig, limit: int = 20) -> ProjectGitResult: ...
def project_diff(*, project: ProjectConfig, from_ref: str | None = None, to_ref: str | None = None) -> ProjectGitResult: ...
def project_restore(*, project: ProjectConfig, ref: str, message: str | None = None, force_with_backup: bool = False) -> ProjectGitResult: ...
```

#### 3. Contracts

- Git behavior lives under `quality_core.git`; it must not import historical `dfmea_cli.services`.
- Managed source paths include `project.yaml`, schema snapshots, tombstones, enabled domain source
  YAML, project `links/**`, and `evidence/**`.
- Runtime locks under `.quality/locks/**` are never staged or restored.
- Generated projections, exports, and reports are staged only when `project.yaml`
  `spec.generatedOutputs` opts them in.
- Snapshot validates before commit, rebuilds enabled DFMEA projections, stages managed paths, and
  creates a Git commit only when staged managed changes exist.
- Restore never rewrites history. It restores managed non-generated paths from the target ref,
  rebuilds generated outputs, validates, stages managed paths, and creates a forward commit.
- History and diff use Git path filtering over managed paths and add parsed resource summaries when
  changed YAML files use the resource envelope.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| Git workspace | Project root is inside a Git work tree | `RESTORE_PRECONDITION_FAILED` |
| Conflicts | No unresolved Git conflict paths | `GIT_CONFLICT` |
| Snapshot validation | no error-level validation issues | `VALIDATION_FAILED` |
| Restore dirty paths | managed restore paths clean, unless `--force-with-backup` | `GIT_DIRTY` |
| Restore validation | restored project validates before commit | `VALIDATION_FAILED` |

#### 5. Good/Base/Bad Cases

Good:

```text
quality project status --workspace ./demo --project cooling-fan-controller
quality project snapshot --workspace ./demo --project cooling-fan-controller --message "quality(project): update baseline"
quality project restore --workspace ./demo --project cooling-fan-controller --ref baseline-v1
```

Base:

```text
quality project diff --project cooling-fan-controller --from HEAD~1
quality project history --project cooling-fan-controller --limit 10
```

Bad:

```python
subprocess.run(["git", "reset", "--hard", ref])
```

Restore must create a forward commit instead of rewriting history.

#### 6. Tests Required

- `quality project status` reports dirty managed paths and stale projections.
- Snapshot creates a commit containing source paths, schema snapshots, and tombstones.
- Snapshot excludes `.quality/locks/**` and unmanaged generated projections.
- History filters commits by managed project paths.
- Diff reports raw changed paths and parsed resource summaries.
- Restore restores non-generated managed paths, excludes locks, rebuilds projections, validates, and
  creates a forward commit.

---

### Scenario: Deferred PFMEA Placeholder

#### 1. Scope / Trigger

Use this structure before the first PFMEA implementation is explicitly restarted. PFMEA is reserved
as a future plugin, but the current baseline must not expose active PFMEA commands or register a
PFMEA built-in plugin.

#### 2. Signatures

```python
# src/quality_methods/pfmea/__init__.py
"""Reserved package for the future PFMEA quality method."""
```

#### 3. Contracts

- `quality plugin list` reports DFMEA only.
- `quality plugin enable pfmea --project <slug>` returns `PLUGIN_NOT_FOUND`.
- There is no `pfmea` console script in `pyproject.toml`.
- There is no `src/quality_adapters/cli/pfmea.py`, `src/quality_adapters/cli/pfmea_commands/`, or
  `src/pfmea_cli/` implementation in the current baseline.
- `src/quality_methods/pfmea/` may exist only as a placeholder package plus planned method
  metadata; it must not include a plugin descriptor, schemas, validators, lifecycle, or command
  services.
- `project.yaml` may keep a disabled `spec.domains.pfmea` entry as a future project-file slot, but
  no command should enable or mutate it until PFMEA is implemented.

#### 4. Validation & Error Matrix

| Check | Valid | Error |
| --- | --- | --- |
| PFMEA enable request | PFMEA implementation exists and is registered | `PLUGIN_NOT_FOUND` |
| PFMEA command surface | no active command in current baseline | command not found/import error |
| PFMEA package content | placeholder only | architecture violation |

#### 5. Good/Base/Bad Cases

Good:

```text
quality plugin list
```

Base:

```text
quality plugin enable pfmea --project cooling-fan-controller
```

This currently fails with `PLUGIN_NOT_FOUND`.

Bad:

```text
pfmea init --workspace ./demo --project cooling-fan-controller
```

There is no active PFMEA command surface until the PFMEA phase is explicitly implemented.

#### 6. Tests Required

- `quality method list` includes active `dfmea` and planned `pfmea`.
- Built-in plugin list includes `dfmea` only.
- `quality plugin enable pfmea` returns `PLUGIN_NOT_FOUND` until PFMEA is implemented.
- Importing `quality_methods.pfmea` succeeds as a placeholder.

---

## Examples

- `src/quality_adapters/cli/quality.py`: Typer command registration for shared `quality` commands.
- `src/quality_adapters/cli/dfmea.py`: DFMEA console entrypoint adapter.
- `src/quality_adapters/cli/dfmea_commands/`: active DFMEA Typer command wiring.
- `src/quality_core/graph/loader.py`: local-first graph loading over enabled plugin source files.
- `src/quality_core/graph/model.py`: graph indexes and trace link/reference value objects.
- `src/quality_core/git/paths.py`: managed project path classification.
- `src/quality_core/git/project.py`: project-scoped Git status, snapshot, history, diff, and restore.
- `src/quality_core/git/runner.py`: subprocess Git wrappers and conflict checks.
- `src/quality_core/methods/registry.py`: product-level quality method discovery.
- `src/quality_core/projections/freshness.py`: projection source hashing, manifest, and freshness.
- `src/quality_core/plugins/project_plugins.py`: project-aware plugin enable/disable behavior.
- `src/quality_core/plugins/schema_snapshots.py`: schema snapshot copy/version checks.
- `src/quality_core/resources/store.py`: project-aware file-backed resource create/load/list/update/delete.
- `src/quality_core/resources/paths.py`: plugin-declared path and ID validation.
- `src/quality_core/resources/repair.py`: project-local resource renumbering and ID conflict repair.
- `src/quality_core/resources/ids.py`: file-derived ID allocation and tombstone writing.
- `src/quality_core/resources/locks.py`: project write lock at `.quality/locks/project.lock`.
- `src/quality_core/resources/atomic.py`: atomic YAML/text file replacement helper.
- `src/quality_core/validation/engine.py`: reusable local-first validation scanning and core rules.
- `src/quality_core/validation/issue.py`: stable validation issue shape.
- `src/quality_core/validation/report.py`: validation summary/report data model.
- `src/quality_core/workspace/config.py`: workspace YAML loading and writing.
- `src/quality_core/workspace/project.py`: project YAML creation and validation.
- `src/quality_methods/dfmea/plugin.py`: DFMEA underlying schema plugin descriptor.
- `src/quality_methods/dfmea/lifecycle.py`: DFMEA initialization and initialized project resolution.
- `src/quality_methods/dfmea/structure_service.py`: file-backed DFMEA structure mutations.
- `src/quality_methods/dfmea/analysis_service.py`: file-backed DFMEA analysis mutations and AP
  calculation.
- `src/quality_methods/dfmea/query_service.py`: file-backed DFMEA query/read views.
- `src/quality_methods/dfmea/trace_service.py`: DFMEA trace traversal over graph links.
- `src/quality_methods/dfmea/context_service.py`: Agent context bundles for failure chains.
- `src/quality_methods/dfmea/projections.py`: DFMEA tree/risk/action/traceability projections.
- `src/quality_methods/dfmea/exports.py`: DFMEA Markdown and CSV generated exports.
- `src/quality_methods/dfmea/validators.py`: DFMEA graph and methodology validation rules.
- `src/quality_methods/pfmea/__init__.py`: reserved placeholder for future PFMEA implementation.
- `src/dfmea_cli/cli.py` and `src/dfmea_cli/commands/`: historical compatibility wrappers.
