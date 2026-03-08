# DFMEA Master Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the first end-to-end working version of a local-first DFMEA AI agent built on OpenCode, with Markdown as the canonical source of truth and OpenChamber reused as the OpenCode-facing shell.

**Architecture:** Build a pnpm TypeScript monorepo centered on `packages/orchestrator`, a file-backed `packages/filesystem`, a local `packages/runtime-indexer`, and a lightweight `packages/dfmea-domain`, while reusing OpenChamber as the OpenCode-facing shell. Treat OpenCode as the agent runtime foundation accessed through SDK or API. Keep first-version behavior local-only, business-subtree-oriented, and review-before-apply.

**Tech Stack:** pnpm workspaces, TypeScript, Next.js App Router, Vitest, Zod, Node.js filesystem APIs, OpenCode local runtime via SDK or HTTP API.

---

## Implementation Objectives

This plan assumes the following first-version boundaries are already agreed:

- OpenCode is the bottom agent runtime.
- OpenChamber is the preferred first-version OpenCode-facing shell.
- The DFMEA application is the domain-specific product layer.
- `content/` is the canonical source of truth.
- `runtime/` is rebuildable and local-first.
- `changes/` stores confirmed result history only.
- Canonical content is sharded by business subtree.
- First-version action scope is `Local` only.
- The product is AI-first, not tree-first.
- Node-level schema remains intentionally flexible in v1, as long as content follows DFMEA semantics.

The main purpose of this plan is to get the skeleton operational, not to freeze every low-level format.

---

## First-Version Minimum Contracts

This section defines the minimum usable behavior for the three most important first-version areas:

- canonical `content/` organization,
- local `runtime/` generation,
- `review-apply` confirmation flow.

These contracts are intentionally lightweight. They are designed to stabilize the product skeleton without prematurely freezing a detailed node schema.

### 1. Minimum Viable `content/` Organization

The first version should treat `content/` as a set of DFMEA business-subtree documents, not as a fully normalized node database.

Recommended minimum layout:

```text
projects/<project-id>/
  project.md
  content/
    <domain-or-module>/
      <subtree-id>.md
```

Rules:

- `project.md` is the project-level entry context.
- each subtree file represents one meaningful local DFMEA analysis unit,
- subtree files should be readable Markdown first and structured enough for AI assistance second,
- the exact low-level node syntax may evolve later.

Every canonical subtree file should at minimum communicate these semantic sections:

- subtree title and scope,
- product or module context,
- function context,
- requirements and characteristics,
- failures, causes, and effects,
- failure chain notes,
- open questions or completion notes.

First-version design rule:

- prefer stable subtree document boundaries over detailed schema completeness.

### 2. Minimum Viable `runtime/` Generation

The first version should not skip runtime entirely, but it should keep runtime very small.

Recommended minimum runtime layout:

```text
projects/<project-id>/
  runtime/
    manifest.json
    shards/
      <subtree-id>/
        meta.json
        nodes.json
        edges.json
```

Rules:

- one canonical subtree file maps to one runtime shard,
- `manifest.json` tracks subtree files, shard locations, hash values, and dirty state,
- `meta.json` stores local shard metadata,
- `nodes.json` stores the minimum local lookup structure,
- `edges.json` stores the minimum local relationship structure.

First-version design rule:

- runtime exists to support local lookup, local answering, and local refresh,
- runtime does not replace canonical Markdown,
- runtime does not need to be a full graph database.

After a confirmed write, the system should refresh only:

- the affected subtree shard,
- the project manifest.

It should not perform project-wide rebuilds as the normal path.

### 2.1 Minimum Runtime Field Draft

The first version should define a minimum field draft for runtime artifacts so implementation can proceed without turning runtime into a second canonical schema.

These fields are guidance for implementation, not a commitment to a frozen long-term format.

#### `runtime/manifest.json`

Recommended minimum shape:

```json
{
  "projectId": "demo-brake",
  "updatedAt": "2026-03-08T00:00:00.000Z",
  "subtrees": [
    {
      "subtreeId": "brake-signal",
      "sourceFile": "content/braking/brake-signal.md",
      "shardPath": "runtime/shards/brake-signal",
      "sourceHash": "...",
      "dirty": false,
      "lastIndexedAt": "2026-03-08T00:00:00.000Z"
    }
  ]
}
```

Purpose:

- project-level runtime lookup,
- local shard discovery,
- dirty tracking,
- rebuild scheduling.

#### `runtime/shards/<subtree-id>/meta.json`

Recommended minimum shape:

```json
{
  "subtreeId": "brake-signal",
  "sourceFile": "content/braking/brake-signal.md",
  "sourceHash": "...",
  "title": "Brake Signal Subtree",
  "nodeCount": 0,
  "edgeCount": 0,
  "lastBuiltAt": "2026-03-08T00:00:00.000Z",
  "version": 1
}
```

Purpose:

- describe the local shard,
- support local debug and verification,
- provide lightweight UI or logging context.

#### `runtime/shards/<subtree-id>/nodes.json`

Recommended minimum item shape:

```json
[
  {
    "id": "FNC-001",
    "kind": "function",
    "title": "Brake signal acquisition",
    "section": "functions",
    "parentId": null,
    "refIds": ["CHAIN-001"],
    "anchor": "function-brake-signal-acquisition",
    "summary": "Receives and processes brake input signal."
  }
]
```

Purpose:

- local lookup,
- local answering,
- local completion context,
- anchor-based source readback.

Design rule:

- keep `nodes.json` small,
- store local summaries rather than full source content,
- avoid turning this file into a duplicate of canonical Markdown.

#### `runtime/shards/<subtree-id>/edges.json`

Recommended minimum item shape:

```json
[
  {
    "from": "FNC-001",
    "to": "CHAIN-001",
    "type": "ref"
  }
]
```

Allowed first-version edge types:

- `tree`
- `ref`
- `chain`

Purpose:

- express the minimum local structural and analytical relationships,
- support bounded local reasoning without requiring a full graph engine.

### 2.2 Runtime Field Guardrails

While implementing runtime fields in the first version:

- prefer a smaller field set over speculative completeness,
- prefer readability over hyper-optimization,
- prefer local usefulness over project-wide ambition,
- do not encode business truth that should stay in canonical Markdown,
- do not require stable full-node schemas before indexing can work.

### 3. Minimum Viable `review-apply` Confirmation Flow

The first version should use a strict human-in-the-loop confirmation flow for all normal canonical writes.

Required flow:

1. a mutable action produces a proposal,
2. the UI shows the proposal in a readable local form,
3. the user explicitly confirms,
4. the application writes canonical content,
5. the application refreshes the local runtime shard,
6. the application records the confirmed result in `changes/`.

Minimum proposal shape:

- `proposalId`
- `actionId`
- `subtreeId`
- `summary`
- `targetFiles`
- `status`

Allowed first-version statuses:

- `proposed`
- `confirmed`
- `applied`
- `failed`

First-version design rules:

- `query` is always read-only,
- `complete` may propose but may not write,
- `review-apply` is the only normal confirmed write path,
- confirmed changes should be recorded as outcomes, not chain-of-thought.

### 3.1 Minimum Proposal Object Draft

The first version should define a minimal proposal object that remains easy to review by humans without requiring a heavy patch schema.

Recommended minimum shape:

```json
{
  "proposalId": "prop-001",
  "actionId": "complete",
  "projectId": "demo-brake",
  "subtreeId": "brake-signal",
  "summary": "Complete local failure and cause sections",
  "targetFiles": ["content/braking/brake-signal.md"],
  "operations": [
    {
      "type": "update_section",
      "file": "content/braking/brake-signal.md",
      "section": "failures",
      "description": "Add local failure descriptions"
    }
  ],
  "status": "proposed",
  "createdAt": "2026-03-08T00:00:00.000Z"
}
```

Required first-version fields:

- `proposalId`
- `actionId`
- `projectId`
- `subtreeId`
- `summary`
- `targetFiles`
- `operations`
- `status`
- `createdAt`

Allowed first-version operation types:

- `add_section`
- `update_section`
- `append_note`

Purpose:

- show human-reviewable change intent,
- identify local write scope,
- support the first-version confirmation path without requiring a detailed patch engine.

### 3.2 Review-Apply State Flow

The first version should use a deliberately simple proposal state machine.

Normal path:

- `proposed -> confirmed -> applied`

Failure path:

- `proposed -> confirmed -> failed`

Rules:

- `proposed` is created by `complete` or another mutable action,
- `confirmed` is entered only after explicit human confirmation,
- `applied` means canonical content write and local runtime refresh both succeeded,
- `failed` means one or more required apply steps did not complete successfully.

First-version simplification rule:

- do not add `cancelled`, `rolled_back`, or `partially_applied` unless implementation proves they are necessary.

### 3.3 Failure Handling Rules

The first version is not a transaction database, but it still requires explicit failure semantics.

Required rules:

- if the user does not confirm, no canonical write occurs,
- if canonical content write fails, the proposal result becomes `failed`,
- if canonical content write succeeds but local runtime refresh fails, the proposal result still becomes `failed`,
- failed outcomes should be recorded in `changes/` with enough detail to understand what failed.

At minimum, the failure result should communicate:

- which proposal failed,
- which subtree was affected,
- whether canonical content write happened,
- whether runtime refresh happened,
- the failure reason if known.

### 3.4 Review-Apply Guardrails

While implementing the first version:

- do not let `query` write,
- do not let `complete` silently apply changes,
- do not hide confirmation behind implicit UI actions,
- do not overbuild proposal semantics before the skeleton works,
- do not lose failed apply visibility.

### 4. Product Guardrails

While implementing the first version, use these guardrails:

- do not expand into global retrieval,
- do not overdesign graph visualization,
- do not block on final node schema design,
- do not move business logic into OpenCode internals,
- do not bypass review-apply for convenience.

These constraints are part of the product definition, not temporary shortcuts.

---

### Task 1: Bootstrap the monorepo and shared developer toolchain

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `tsconfig.base.json`
- Create: `vitest.workspace.ts`
- Create: `.gitignore`
- Create: `README.md`
- Create: `packages/dfmea-domain/package.json`
- Create: `packages/dfmea-domain/tsconfig.json`
- Create: `packages/dfmea-domain/src/index.ts`
- Test: `packages/dfmea-domain/src/__tests__/workspace-smoke.test.ts`

**Step 1: Write the failing smoke test**

```ts
import { describe, expect, it } from 'vitest'
import { ACTION_IDS, QUERY_SCOPE, STORAGE_LAYERS } from '../index'

describe('dfmea-domain workspace constants', () => {
  it('exposes the first-version action ids, local-only scope, and storage layers', () => {
    expect(ACTION_IDS).toEqual({
      create: 'create',
      query: 'query',
      complete: 'complete',
      reviewApply: 'review-apply',
    })

    expect(QUERY_SCOPE).toEqual({ local: 'local' })

    expect(STORAGE_LAYERS).toEqual({
      content: 'content',
      runtime: 'runtime',
      changes: 'changes',
    })
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/dfmea-domain/src/__tests__/workspace-smoke.test.ts`
Expected: FAIL because the workspace and package exports do not exist yet.

**Step 3: Write the minimal workspace setup**

Create root package manager and TypeScript wiring, then export the smallest domain constants required by the rest of the system.

```ts
export const ACTION_IDS = {
  create: 'create',
  query: 'query',
  complete: 'complete',
  reviewApply: 'review-apply',
} as const

export const QUERY_SCOPE = {
  local: 'local',
} as const

export const STORAGE_LAYERS = {
  content: 'content',
  runtime: 'runtime',
  changes: 'changes',
} as const
```

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/dfmea-domain/src/__tests__/workspace-smoke.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add package.json pnpm-workspace.yaml tsconfig.base.json vitest.workspace.ts .gitignore README.md packages/dfmea-domain
git commit -m "chore: bootstrap dfmea monorepo workspace"
```

### Task 2: Implement the project workspace skeleton and initialization flow

**Files:**
- Create: `packages/filesystem/package.json`
- Create: `packages/filesystem/tsconfig.json`
- Create: `packages/filesystem/src/index.ts`
- Create: `packages/filesystem/src/initProjectWorkspace.ts`
- Create: `packages/filesystem/src/readProjectContext.ts`
- Create: `packages/filesystem/src/ensureProjectDirs.ts`
- Test: `packages/filesystem/src/__tests__/initProjectWorkspace.test.ts`

**Step 1: Write the failing initialization test**

```ts
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { initProjectWorkspace } from '../initProjectWorkspace'

describe('initProjectWorkspace', () => {
  it('creates the agreed first-version project skeleton', async () => {
    const root = await initProjectWorkspace({
      projectsRoot: 'tmp/projects',
      projectId: 'demo-brake',
      title: 'Demo Brake DFMEA',
    })

    expect(existsSync(join(root, 'project.md'))).toBe(true)
    expect(existsSync(join(root, 'content'))).toBe(true)
    expect(existsSync(join(root, 'runtime'))).toBe(true)
    expect(existsSync(join(root, 'changes'))).toBe(true)
    expect(existsSync(join(root, 'runtime', 'manifest.json'))).toBe(true)

    const projectMd = readFileSync(join(root, 'project.md'), 'utf8')
    expect(projectMd).toContain('Demo Brake DFMEA')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/filesystem/src/__tests__/initProjectWorkspace.test.ts`
Expected: FAIL because filesystem primitives do not exist.

**Step 3: Write the minimal filesystem implementation**

Implement project initialization with this guaranteed shape:

```text
projects/<project-id>/
  project.md
  content/
  runtime/
  changes/
```

Create `runtime/manifest.json` as a minimal valid file even if no subtree exists yet.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/filesystem/src/__tests__/initProjectWorkspace.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/filesystem
git commit -m "feat: add project workspace initialization"
```

### Task 3: Add canonical content helpers for business-subtree Markdown files

**Files:**
- Create: `packages/filesystem/src/createSubtreeFile.ts`
- Create: `packages/filesystem/src/listSubtreeFiles.ts`
- Create: `packages/filesystem/src/readSubtreeFile.ts`
- Test: `packages/filesystem/src/__tests__/subtreeFiles.test.ts`

**Step 1: Write the failing subtree file test**

```ts
import { describe, expect, it } from 'vitest'
import { createSubtreeFile, listSubtreeFiles, readSubtreeFile } from '../index'

describe('subtree file helpers', () => {
  it('creates and reads a canonical subtree markdown file', async () => {
    await createSubtreeFile({
      projectRoot: 'tmp/projects/demo-brake',
      relativePath: 'content/braking/brake-signal.md',
      title: 'Brake Signal Subtree',
      body: '# Brake Signal Subtree\n',
    })

    const files = await listSubtreeFiles({ projectRoot: 'tmp/projects/demo-brake' })
    const file = await readSubtreeFile({
      projectRoot: 'tmp/projects/demo-brake',
      relativePath: 'content/braking/brake-signal.md',
    })

    expect(files).toContain('content/braking/brake-signal.md')
    expect(file).toContain('Brake Signal Subtree')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/filesystem/src/__tests__/subtreeFiles.test.ts`
Expected: FAIL because subtree content helpers do not exist.

**Step 3: Write the minimal canonical content helpers**

Important first-version rule:

- do not freeze the final node schema,
- do preserve predictable subtree file placement,
- do ensure files are readable as Markdown and clearly represent one DFMEA business subtree.

The helper should create the file and any required parent directories.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/filesystem/src/__tests__/subtreeFiles.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/filesystem
git commit -m "feat: add canonical subtree markdown helpers"
```

### Task 4: Implement local runtime manifest and one-file-to-one-shard indexing

**Files:**
- Create: `packages/runtime-indexer/package.json`
- Create: `packages/runtime-indexer/tsconfig.json`
- Create: `packages/runtime-indexer/src/index.ts`
- Create: `packages/runtime-indexer/src/rebuildProjectRuntime.ts`
- Create: `packages/runtime-indexer/src/rebuildSubtreeShard.ts`
- Create: `packages/runtime-indexer/src/updateManifest.ts`
- Test: `packages/runtime-indexer/src/__tests__/rebuildSubtreeShard.test.ts`

**Step 1: Write the failing shard rebuild test**

```ts
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { rebuildSubtreeShard } from '../rebuildSubtreeShard'

describe('rebuildSubtreeShard', () => {
  it('creates one runtime shard for one content subtree file', async () => {
    const result = await rebuildSubtreeShard({
      projectRoot: 'tmp/projects/demo-brake',
      subtreeFile: 'content/braking/brake-signal.md',
      subtreeId: 'brake-signal',
    })

    expect(existsSync(join(result.shardRoot, 'meta.json'))).toBe(true)
    expect(existsSync(join(result.shardRoot, 'nodes.json'))).toBe(true)
    expect(existsSync(join(result.shardRoot, 'edges.json'))).toBe(true)

    const meta = readFileSync(join(result.shardRoot, 'meta.json'), 'utf8')
    expect(meta).toContain('brake-signal')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/runtime-indexer/src/__tests__/rebuildSubtreeShard.test.ts`
Expected: FAIL because runtime indexing does not exist.

**Step 3: Write the minimal runtime indexer**

Implement the confirmed rule:

- one `content` subtree file maps to one `runtime/shards/<subtree-id>/` directory.

The indexer should:

- read the subtree file,
- emit `meta.json`, `nodes.json`, and `edges.json`,
- update `runtime/manifest.json`,
- stay shallow in v1 rather than depending on frozen node schema.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/runtime-indexer/src/__tests__/rebuildSubtreeShard.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/runtime-indexer
git commit -m "feat: add local runtime shard generation"
```

### Task 5: Add lightweight confirmed-change recording

**Files:**
- Create: `packages/filesystem/src/writeChangeRecord.ts`
- Create: `packages/filesystem/src/listChangeRecords.ts`
- Test: `packages/filesystem/src/__tests__/changeRecords.test.ts`

**Step 1: Write the failing change record test**

```ts
import { describe, expect, it } from 'vitest'
import { listChangeRecords, writeChangeRecord } from '../index'

describe('change record helpers', () => {
  it('stores confirmed result records without agent chain-of-thought', async () => {
    await writeChangeRecord({
      projectRoot: 'tmp/projects/demo-brake',
      kind: 'review-apply',
      subtreeId: 'brake-signal',
      summary: 'Applied local completion proposal',
    })

    const records = await listChangeRecords({ projectRoot: 'tmp/projects/demo-brake' })
    expect(records[0]?.summary).toContain('Applied local completion proposal')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/filesystem/src/__tests__/changeRecords.test.ts`
Expected: FAIL because change record helpers do not exist.

**Step 3: Write the minimal change recording layer**

The first-version record should capture:

- timestamp,
- action kind,
- subtree id,
- summary,
- touched files if known.

It should not store chain-of-thought or large transient reasoning traces.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/filesystem/src/__tests__/changeRecords.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/filesystem
git commit -m "feat: add confirmed change recording"
```

### Task 6: Implement the OpenCode gateway abstraction in the orchestrator layer

**Files:**
- Create: `packages/orchestrator/package.json`
- Create: `packages/orchestrator/tsconfig.json`
- Create: `packages/orchestrator/src/index.ts`
- Create: `packages/orchestrator/src/opencodeGateway.ts`
- Create: `packages/orchestrator/src/normalizeResult.ts`
- Test: `packages/orchestrator/src/__tests__/opencodeGateway.test.ts`

**Step 1: Write the failing gateway test**

```ts
import { describe, expect, it } from 'vitest'
import { createGatewayRequest } from '../opencodeGateway'

describe('opencode gateway request shaping', () => {
  it('prepares a local scoped request for OpenCode', () => {
    const request = createGatewayRequest({
      projectRoot: 'projects/demo-brake',
      actionId: 'query',
      localWorkset: { subtreeId: 'brake-signal' },
      context: { projectTitle: 'Demo Brake DFMEA' },
      prompt: 'Summarize this subtree',
    })

    expect(request.actionId).toBe('query')
    expect(request.localWorkset.subtreeId).toBe('brake-signal')
    expect(request.prompt).toContain('Summarize this subtree')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/orchestrator/src/__tests__/opencodeGateway.test.ts`
Expected: FAIL because the orchestrator gateway does not exist.

**Step 3: Write the minimal OpenCode gateway abstraction**

Do not complete the real OpenCode integration in depth. Instead, build the stable abstraction your application will call.

Include conceptual operations such as:

- `startSession(projectRoot)`
- `sendScopedPrompt(sessionId, actionId, localWorkset, context)`
- `streamSessionEvents(sessionId)`
- `closeSession(sessionId)`

Normalize responses into:

- `answer`
- `proposal`
- `apply_result`
- `error`

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/opencodeGateway.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/orchestrator
git commit -m "feat: add opencode gateway abstraction"
```

### Task 7: Implement local-only action routing and handler boundaries

**Files:**
- Create: `packages/orchestrator/src/routeAction.ts`
- Create: `packages/orchestrator/src/handlers/create.ts`
- Create: `packages/orchestrator/src/handlers/query.ts`
- Create: `packages/orchestrator/src/handlers/complete.ts`
- Create: `packages/orchestrator/src/handlers/reviewApply.ts`
- Test: `packages/orchestrator/src/__tests__/routeAction.test.ts`

**Step 1: Write the failing routing test**

```ts
import { describe, expect, it } from 'vitest'
import { routeAction } from '../routeAction'

describe('routeAction', () => {
  it('routes local query requests to the query path', async () => {
    const result = await routeAction({
      actionId: 'query',
      scope: 'local',
      projectId: 'demo-brake',
      workset: { subtreeId: 'brake-signal' },
      input: { prompt: 'What is this subtree about?' },
    })

    expect(result.actionId).toBe('query')
    expect(result.scope).toBe('local')
    expect(result.kind).toBe('answer')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/orchestrator/src/__tests__/routeAction.test.ts`
Expected: FAIL because routeAction and handlers do not exist.

**Step 3: Write the minimal routing layer**

Preserve the agreed first-version behavior:

- `create` may write skeleton files directly,
- `query` is strictly read-only,
- `complete` returns a proposal only,
- `review-apply` is the only normal confirmed write path.

Keep the routing logic local-only.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/routeAction.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/orchestrator
git commit -m "feat: add local-only action routing"
```

### Task 8: Implement the review-apply confirmation loop

**Files:**
- Modify: `packages/orchestrator/src/handlers/reviewApply.ts`
- Create: `packages/orchestrator/src/buildProposal.ts`
- Test: `packages/orchestrator/src/__tests__/reviewApply.test.ts`

**Step 1: Write the failing review-apply test**

```ts
import { describe, expect, it } from 'vitest'
import { reviewApply } from '../handlers/reviewApply'

describe('reviewApply', () => {
  it('writes only after explicit confirmation and records the confirmed result', async () => {
    const result = await reviewApply({
      projectRoot: 'tmp/projects/demo-brake',
      confirmed: true,
      proposal: {
        summary: 'Apply local completion',
        subtreeId: 'brake-signal',
        updates: ['content/braking/brake-signal.md'],
      },
    })

    expect(result.kind).toBe('apply_result')
    expect(result.applied).toBe(true)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/orchestrator/src/__tests__/reviewApply.test.ts`
Expected: FAIL because the handler does not enforce the confirmation path yet.

**Step 3: Write the minimal confirmation flow**

Required sequence:

1. accept reviewed proposal,
2. reject if not confirmed,
3. write canonical content updates,
4. refresh affected runtime shard,
5. append confirmed result in `changes/`.

In v1, do not overdesign patch schema. A small proposal object with touched files and summary is enough to prove the loop works.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/reviewApply.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/orchestrator packages/filesystem packages/runtime-indexer
git commit -m "feat: add review apply confirmation loop"
```

### Task 9: Prepare OpenChamber integration strategy instead of building a custom shell

**Files:**
- Create: `integrations/openchamber/README.md`
- Create: `integrations/openchamber/plan.md`
- Create: `integrations/openchamber/dfmea-extension-points.md`

**Step 1: Define the integration target clearly**

Write down the exact assumption:

- OpenChamber provides the generic OpenCode-facing shell,
- DFMEA adds domain-specific actions, workset handling, result interpretation, and review/apply behavior.

**Step 2: Document the first-version OpenChamber integration surface**

Define the minimum needed extension points, such as:

- launching or attaching to OpenCode sessions,
- passing project and local subtree context,
- surfacing normalized DFMEA results,
- exposing proposal review and apply actions.

**Step 3: Record what should NOT be rebuilt**

Record that the first version should not rebuild:

- generic OpenCode chat shell,
- generic session management UI,
- generic diff or tool panels already provided by OpenChamber.

**Step 4: Save the integration notes**

Expected: files exist and clearly describe how DFMEA will sit on top of OpenChamber.

**Step 5: Commit**

```bash
git add integrations/openchamber
git commit -m "docs: define openchamber integration approach"
```

### Task 10: Create a demo project and prove the local end-to-end loop

**Files:**
- Create: `projects/demo-brake/project.md`
- Create: `projects/demo-brake/content/braking/brake-signal.md`
- Test: `packages/orchestrator/src/__tests__/localSkeletonFlow.test.ts`

**Step 1: Write the failing end-to-end test**

```ts
import { describe, expect, it } from 'vitest'
import { routeAction } from '../routeAction'

describe('local skeleton flow', () => {
  it('supports query -> complete -> review-apply inside one local subtree', async () => {
    const query = await routeAction({
      actionId: 'query',
      scope: 'local',
      projectId: 'demo-brake',
      workset: { subtreeId: 'brake-signal' },
      input: { prompt: 'Summarize this subtree' },
    })

    const complete = await routeAction({
      actionId: 'complete',
      scope: 'local',
      projectId: 'demo-brake',
      workset: { subtreeId: 'brake-signal' },
      input: { prompt: 'Propose local completion' },
    })

    expect(query.kind).toBe('answer')
    expect(complete.kind).toBe('proposal')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/orchestrator/src/__tests__/localSkeletonFlow.test.ts`
Expected: FAIL until the demo project and handler wiring are complete.

**Step 3: Write the minimal demo fixture and finish local flow wiring**

Use a demo subtree like:

```md
# Brake Signal Subtree

This file represents one local DFMEA business subtree for v1 skeleton verification.
```

Make sure:

- `query` reads from the local subtree,
- `complete` generates a local proposal,
- `review-apply` can persist the confirmed result and refresh the local runtime.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/localSkeletonFlow.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add projects/demo-brake packages/orchestrator
git commit -m "feat: add demo local dfmea flow"
```

### Task 11: Add root scripts and verification commands

**Files:**
- Modify: `package.json`
- Modify: `README.md`

**Step 1: Write the failing verification expectation**

Document the expected top-level commands first:

```text
pnpm test
pnpm dev
pnpm --filter @dfmea/copilot-ui dev
```

Expectation: all package tests and the app entry shell should be reachable from root scripts.

**Step 2: Run root verification to verify it fails or is incomplete**

Run: `pnpm test`
Expected: FAIL or report missing scripts before root scripts are added.

**Step 3: Write the minimal root scripts and README guidance**

Add root scripts for:

- `dev`
- `test`
- `build`

Update the README to explain:

- how to install,
- how to initialize a project workspace,
- how the local-only loop works,
- how OpenCode is used as the bottom runtime.

**Step 4: Run verification to verify it passes**

Run: `pnpm test`
Expected: PASS across all implemented tests.

Run: `pnpm --filter @dfmea/copilot-ui dev`
Expected: replace this with the chosen OpenChamber startup or integration verification command when the shell integration is implemented.

**Step 5: Commit**

```bash
git add package.json README.md
git commit -m "docs: add root scripts and setup guidance"
```

### Task 12: Final manual verification of the first-version product loop

**Files:**
- Verify only: `projects/demo-brake/project.md`
- Verify only: `projects/demo-brake/content/braking/brake-signal.md`
- Verify only: `projects/demo-brake/runtime/manifest.json`
- Verify only: `projects/demo-brake/runtime/shards/brake-signal/meta.json`
- Verify only: `projects/demo-brake/changes/`

**Step 1: Start the app**

Run: the chosen OpenChamber startup or integration verification command.
Expected: the OpenCode-facing shell starts and can expose DFMEA extension behavior.

**Step 2: Exercise the local-only loop manually**

Manual flow:

1. open the DFMEA copilot shell,
2. target `demo-brake`,
3. run a local query,
4. run a local complete request,
5. confirm a proposal through review-apply.

Expected evidence:

- answers come back from the local scope,
- proposals appear before any write,
- confirmed changes update `content/`,
- the matching runtime shard refreshes,
- `changes/` records the confirmed outcome.

**Step 3: Commit**

```bash
git add .
git commit -m "feat: complete first-version dfmea master skeleton"
```

---

## Notes For Execution

- Keep first-version schema intentionally light.
- Do not slip into global query design.
- Do not overbuild graph UI.
- Do not deeply couple business logic into OpenCode internals.
- Keep the product AI-first and local-subtree-first.
- Treat review-apply as the only normal confirmed write path.
