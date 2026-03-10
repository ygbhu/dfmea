# DFMEA Master Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the first end-to-end working version of a local-first DFMEA AI agent built on OpenCode, with Markdown as the canonical source of truth and OpenChamber reused as the OpenCode-facing shell.

**Architecture:** Build on top of the current OpenChamber repository base, keep Markdown subtree files as canonical DFMEA content, strengthen a derived runtime index for local lookup and keyword retrieval, and add DFMEA backend/runtime behavior through narrow extensions in `packages/dfmea`, `packages/web`, and `packages/ui` config surfaces. Treat OpenCode as the agent runtime foundation. Keep first-version behavior local-only, business-subtree-oriented, and review-before-apply.

**Tech Stack:** pnpm workspaces, TypeScript, Next.js App Router, Vitest, Zod, Node.js filesystem APIs, OpenCode local runtime via SDK or HTTP API.

---

## Implementation Objectives

This plan assumes the following first-version boundaries are already agreed:

- OpenCode is the bottom agent runtime.
- OpenChamber is now the active repository base and preferred OpenCode-facing shell.
- The DFMEA application is the domain-specific product layer.
- `content/` is the canonical source of truth.
- `runtime/` is rebuildable and local-first.
- `changes/` stores confirmed result history only.
- Canonical content is sharded by business subtree.
- First-version action scope is `Local` only.
- The product is AI-first, not tree-first.
- Node-level schema remains intentionally flexible in v1, as long as content follows DFMEA semantics.

The main purpose of this plan is no longer to invent a custom skeleton from scratch. It is to finish the missing DFMEA backend/runtime capabilities inside the existing OpenChamber-based repository.

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

## Current Remaining Buildout Plan

The earlier custom-shell implementation tasks below are no longer the active repository path.

From this point forward, remaining work should be understood as OpenChamber-based DFMEA backend/runtime work.

### Task 1: Implement canonical DFMEA content storage conventions inside the current repo

**Files:**
- Create: `packages/dfmea/src/content.ts`
- Create: `packages/dfmea/src/storage.ts`
- Modify: `packages/dfmea/src/index.ts`
- Test: `packages/dfmea/src/content.test.ts`

**Step 1: Write a failing test for canonical subtree file conventions**

Expected: FAIL until the DFMEA package can derive and validate canonical subtree storage paths and roots from a workspace.

**Step 2: Implement the minimum content/storage helpers**

- derive `contentRoot`, `runtimeRoot`, `changesRoot`,
- derive canonical subtree file locations,
- keep Markdown as canonical storage.

**Step 3: Run test to verify it passes**

Run the DFMEA package test command and confirm PASS.

### Task 2: Implement a stronger runtime index inside `packages/dfmea`

**Files:**
- Create: `packages/dfmea/src/runtimeIndex.ts`
- Create: `packages/dfmea/src/runtimeSearch.ts`
- Modify: `packages/dfmea/src/index.ts`
- Test: `packages/dfmea/src/runtimeIndex.test.ts`

**Step 1: Write a failing runtime index test**

Expected: FAIL until the DFMEA package can build a runtime manifest/shard model from canonical subtree content.

**Step 2: Implement the minimum runtime index**

- manifest generation,
- subtree-to-shard mapping,
- extracted node summaries,
- extracted local edges,
- keyword-oriented lookup helpers.

**Step 3: Run test to verify it passes**

Run the DFMEA package runtime test command and confirm PASS.

### Task 3: Implement backend DFMEA query context and local runtime search endpoints

**Files:**
- Modify: `packages/web/server/index.js`
- Modify: `packages/web/src/api/dfmea.ts`
- Modify: `packages/web/src/api/index.ts`
- Modify: `packages/ui/src/lib/api/types.ts`

**Step 1: Write a failing backend behavior test or reproducible command**

Expected: FAIL until `/api/dfmea/context` and the DFMEA backend can also return runtime-backed search results.

**Step 2: Implement narrow DFMEA backend endpoints**

- local context resolution,
- runtime-backed keyword search,
- subtree lookup by id or title,
- response payloads suitable for OpenChamber-side extensions.

**Step 3: Run verification**

Call the endpoints manually and confirm valid JSON responses.

### Task 4: Implement project-scoped review-apply backend behavior

**Files:**
- Modify: `packages/web/server/index.js`
- Create: `packages/dfmea/src/reviewApply.ts`
- Modify: `packages/dfmea/src/index.ts`

**Step 1: Write a failing review-apply test or reproducible command**

Expected: FAIL until the backend can accept a confirmed DFMEA proposal and write canonical content plus runtime refresh.

**Step 2: Implement the minimum review-apply path**

- accept confirmed proposal payload,
- write Markdown canonical content,
- refresh affected runtime shard,
- append confirmed result into `changes/`.

**Step 3: Run verification**

Execute the review-apply path manually and confirm canonical content + runtime change are both visible.

### Task 5: Keep OpenChamber UI changes minimal and configuration-oriented

**Files:**
- Modify only if needed: `packages/ui/src/lib/openchamberConfig.ts`
- Modify only if needed: `packages/ui/src/lib/dfmea.ts`
- Modify only if needed: `packages/ui/src/components/sections/projects/DfmeaSection.tsx`

**Step 1: Limit scope intentionally**

Do not broaden UI work beyond what is required to expose project-scoped DFMEA configuration and actions.

**Step 2: Verify UI compatibility**

Run `bun run type-check:ui` and confirm PASS.

### Task 6: Final verification and project audit

**Files:**
- Verify: `packages/dfmea/**`
- Verify: `packages/web/**`
- Verify: `packages/ui/**`
- Verify: `docs/plans/*.md`

**Step 1: Run verification commands**

- `bun run type-check:ui`
- `bun run build:web`
- any added DFMEA package tests

**Step 2: Manual QA**

- call `/api/dfmea/context`
- call the new DFMEA runtime search endpoint
- call the review-apply path if implemented

**Step 3: Audit remaining gaps**

At the end of implementation, explicitly list:

- what is already usable,
- what remains intentionally deferred,
- what the next backend priority should be.

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
