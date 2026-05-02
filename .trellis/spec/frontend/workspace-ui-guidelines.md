# Workspace UI Guidelines

## Scenario: Phase 10 Workspace UI MVP

### 1. Scope / Trigger

- Trigger: Changing `apps/web/src/App.tsx`, `platformApi.ts`, `workspaceModel.ts`, or UI state/data-flow for the workspace.
- Applies to the MVP flow: bootstrap scope, start mock run, show runtime events, show draft preview, apply/reject draft, refresh working projection.
- Layout convention: the workspace uses a left plugin workbench and a right Agent conversation panel. The structure tree plugin is the default/priority plugin; draft review is available through plugin switching and must not be permanently displayed as a third primary column.

### 2. Signatures

Frontend API client entry points:

```typescript
createWorkspace(name: string): Promise<WorkspaceRecord>
createProject(workspaceId: string, name: string): Promise<ProjectRecord>
createSession(projectId: string): Promise<SessionRecord>
startRun(sessionId: string, goal: string): Promise<RunStartResult>
getWorkingProjection(projectId: string): Promise<ProjectionReadResult>
getDraftPreview(draftBatchId: string): Promise<DraftPreviewResponse>
applyDraft(draftBatchId: string): Promise<ApplyDraftResponse>
rejectDraft(draftBatchId: string): Promise<DraftBatchRecord>
validateApiPush(projectId: string): Promise<ApiPushResult>
executeApiPush(projectId: string): Promise<ApiPushResult>
connectPlatformEvents(path, eventTypes, onEvent, onError): () => void
```

UI model adapters:

```typescript
buildWorkingTree(projection: ProjectionReadResult | null): UiTreeNode[]
buildDraftTree(preview: DraftPreview | null): UiTreeNode[]
eventLabel(event: RuntimeEventRecord | PlatformEvent): string
patchLabel(patch: DraftPatchRecord): string
```

### 3. Contracts

The UI must keep these sources separate:

```text
Working Tree
  Source: GET /api/projects/{projectId}/projections?plugin_id=dfmea&kind=working_tree
  Meaning: confirmed workspace data

Draft Preview
  Source: GET /api/ai-drafts/{draftBatchId}/preview and preview SSE
  Meaning: candidate data only

Runtime Events
  Source: GET /api/runs/{runId}/events/stream
  Meaning: run timeline, not canonical data

API Push
  Source: POST /api/api-push/validate and POST /api/api-push/execute
  Meaning: export integration job/record only, not canonical data
```

Left-side plugin workbench:

```text
Structure Plugin
  Default active plugin.
  Contains Working/Draft tree mode switch.

Draft Review Plugin
  User-selected review surface.
  Contains draft summary, patch list, preview events, Apply/Reject.

Runtime Events Plugin
  User-selected expanded runtime event stream.
  The right conversation panel can still show compact events.

API Push Plugin
  User-selected validate/execute surface.
  Shows latest job, source revision, checksum, external status, and recent API Push events.
```

Default API base:

```text
VITE_API_BASE_URL or http://localhost:3000
```

The UI never calls plugin handlers directly and never reads canonical artifact/edge tables.

### 4. Validation & Error Matrix

| Case | UI Behavior | Assertion |
| --- | --- | --- |
| API bootstrap fails | Set visible error and setup-failed status | App remains renderable |
| Run start fails | Keep existing working tree, show error | Draft state remains empty |
| Draft preview missing | Disable Draft tree tab and Apply | No direct canonical changes |
| Apply succeeds | Clear draft state, switch to Structure Plugin + Working tree | Projection freshness is `fresh` |
| SSE disconnects | Show stream error, close EventSource | No retry loop in component render |
| No active draft | Keep Draft Review plugin selectable but idle | Draft review is not default visible content |
| API Push validate/execute succeeds | Keep current structure tree state, update API Push plugin result | No canonical state mutation is implied |
| API Push fails | Show error in Agent panel status area | Existing working/draft tree state remains intact |

### 5. Good/Base/Bad Cases

Base flow:

```text
App mount -> create scope -> fetch working projection -> start run -> connect SSE -> fetch persisted draft preview -> apply -> refresh projection
```

Good:

```typescript
const nodes = buildDraftTree(draftPreview);
```

Bad:

```typescript
const nodes = draftPatches.map((patch) => patch.afterPayload);
```

The bad case leaks backend patch shape into view components and loses status/marker behavior.

### 6. Tests Required

When changing Workspace UI data flow, keep or extend:

```text
apps/web/src/App.test.tsx
apps/web/src/workspaceModel.test.ts
```

Required assertions:

- Static render contains the workspace shell, plugin switcher, structure plugin, and run action.
- Static render contains the API Push plugin entry.
- `buildWorkingTree` maps projection roots/children into depth-aware `UiTreeNode` records.
- `buildDraftTree` maps persisted draft preview nodes into candidate statuses.
- `eventLabel` and `patchLabel` produce stable labels for runtime timeline and draft list.

### 7. Wrong vs Correct

#### Wrong

```typescript
useEffect(() => {
  startRun(sessionId, goal).then((run) => setDraftBatchId(run.draftBatchId));
}, [goal]);
```

This starts backend runs from render-driven state changes.

#### Correct

```typescript
async function handleStartRun(): Promise<void> {
  const run = await startRun(session.sessionId, goal);
  setActiveRun(run);
  setDraftPreview((await getDraftPreview(run.draftBatchId)).preview);
}
```

Commands stay in explicit user actions, and effects only subscribe/cleanup external streams.

#### Wrong

```tsx
<StructurePanel />
<AgentPanel />
<DraftReviewPanel />
```

This makes review a permanent page column and crowds the workspace.

#### Correct

```tsx
<PluginWorkspace activePluginId={activePluginId} />
<AgentPanel />
```

Draft review is a left-side plugin, while the conversation remains the stable right-side control surface.
