# DFMEA Skeleton Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first working repository and project-workspace skeleton for a local-first DFMEA AI agent on top of OpenCode.

**Architecture:** Use a pnpm TypeScript workspace with a thin `apps/copilot-ui` entry shell, a central `packages/orchestrator` for `create / query / complete / review-apply`, a file-backed `packages/filesystem`, and a local `packages/runtime-indexer` that builds one runtime shard per canonical content subtree file. Keep node-level schema intentionally loose in v1; index subtree files and local scope first.

**Tech Stack:** pnpm workspaces, TypeScript, Next.js App Router, Vitest, Zod, Node.js filesystem APIs.

---

## First-Version Execution Constraints

This implementation plan must follow these first-version constraints while executing tasks:

- treat `content/` as a collection of DFMEA business-subtree Markdown files,
- keep canonical subtree files readable Markdown first and structured enough for AI assistance second,
- keep `runtime/` minimal and local-only,
- map one canonical subtree file to one runtime shard,
- use `manifest.json`, `meta.json`, `nodes.json`, and `edges.json` as the minimum runtime artifacts,
- keep `nodes.json` and `edges.json` lightweight and non-canonical,
- keep `query` read-only,
- let `complete` produce proposals only,
- use `review-apply` as the only normal confirmed write path,
- record confirmed or failed outcomes in `changes/`, not chain-of-thought.

When implementation detail conflicts with convenience, these constraints win.

---

### Task 1: Bootstrap the workspace and shared toolchain

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `tsconfig.base.json`
- Create: `vitest.workspace.ts`
- Create: `.gitignore`
- Create: `packages/dfmea-domain/package.json`
- Create: `packages/dfmea-domain/tsconfig.json`
- Create: `packages/dfmea-domain/src/index.ts`
- Test: `packages/dfmea-domain/src/__tests__/smoke.test.ts`

**Step 1: Write the failing smoke test**

```ts
import { describe, expect, it } from 'vitest'
import { ACTION_IDS, QUERY_SCOPE } from '../index'

describe('dfmea-domain exports', () => {
  it('exposes first-version action ids and local-only scope', () => {
    expect(ACTION_IDS).toEqual({
      create: 'create',
      query: 'query',
      complete: 'complete',
      reviewApply: 'review-apply',
    })
    expect(QUERY_SCOPE).toEqual({ local: 'local' })
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/dfmea-domain/src/__tests__/smoke.test.ts`
Expected: FAIL because the workspace config and package exports do not exist yet.

**Step 3: Write the minimal workspace and domain package setup**

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
```

Also create the root workspace files so `pnpm`, TypeScript, and Vitest can resolve packages.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/dfmea-domain/src/__tests__/smoke.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add package.json pnpm-workspace.yaml tsconfig.base.json vitest.workspace.ts .gitignore packages/dfmea-domain
git commit -m "chore: bootstrap dfmea workspace skeleton"
```

### Task 2: Implement project workspace initialization in filesystem package

**Files:**
- Create: `packages/filesystem/package.json`
- Create: `packages/filesystem/tsconfig.json`
- Create: `packages/filesystem/src/index.ts`
- Create: `packages/filesystem/src/initProjectWorkspace.ts`
- Create: `packages/filesystem/src/readProjectContext.ts`
- Create: `packages/filesystem/src/ensureProjectDirs.ts`
- Create: `packages/filesystem/src/createSubtreeFile.ts`
- Create: `packages/filesystem/src/listSubtreeFiles.ts`
- Create: `packages/filesystem/src/readSubtreeFile.ts`
- Create: `packages/filesystem/src/writeChangeRecord.ts`
- Test: `packages/filesystem/src/__tests__/initProjectWorkspace.test.ts`
- Test: `packages/filesystem/src/__tests__/subtreeFiles.test.ts`

**Step 1: Write the failing initialization test**

```ts
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { initProjectWorkspace } from '../initProjectWorkspace'

describe('initProjectWorkspace', () => {
  it('creates the minimal project skeleton', async () => {
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
Expected: FAIL because the package and initializer do not exist.

**Step 3: Write the minimal filesystem implementation**

```ts
export async function initProjectWorkspace(input: {
  projectsRoot: string
  projectId: string
  title: string
}) {
  // create projects/<project-id>/
  // create project.md
  // create content/, runtime/, changes/
  // create runtime/manifest.json
  return ''
}
```

Also export helpers to:

- read `project.md`,
- create a canonical subtree file under `content/<domain-or-module>/<subtree-id>.md`,
- list subtree files,
- read subtree files,
- append confirmed result entries into `changes/`.

The canonical subtree helper should preserve first-version content rules:

- one file equals one business subtree,
- subtree files remain readable Markdown,
- subtree files should support semantic sections like scope, context, requirements, failures, causes, effects, chain notes, and open completion notes,
- the exact final node schema is intentionally deferred.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/filesystem/src/__tests__/initProjectWorkspace.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/filesystem
git commit -m "feat: add project workspace filesystem primitives"
```

### Task 3: Implement local runtime manifest and per-subtree shard generation

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
    expect(existsSync(join('tmp/projects/demo-brake', 'runtime', 'manifest.json'))).toBe(true)

    const meta = readFileSync(join(result.shardRoot, 'meta.json'), 'utf8')
    expect(meta).toContain('brake-signal')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/runtime-indexer/src/__tests__/rebuildSubtreeShard.test.ts`
Expected: FAIL because the runtime-indexer package does not exist.

**Step 3: Write the minimal indexer implementation**

```ts
export async function rebuildSubtreeShard(input: {
  projectRoot: string
  subtreeFile: string
  subtreeId: string
}) {
  // read subtree markdown
  // emit runtime/shards/<subtree-id>/meta.json
  // emit runtime/shards/<subtree-id>/nodes.json
  // emit runtime/shards/<subtree-id>/edges.json
  // update runtime/manifest.json
  return { shardRoot: '' }
}
```

In v1, keep indexing shallow: treat each content file as one local subtree unit without freezing detailed node schema.

The minimal runtime fields should be aligned with the master plan:

- `manifest.json`
  - `projectId`, `updatedAt`, and `subtrees[]` with `subtreeId`, `sourceFile`, `shardPath`, `sourceHash`, `dirty`, `lastIndexedAt`
- `meta.json`
  - `subtreeId`, `sourceFile`, `sourceHash`, `title`, `nodeCount`, `edgeCount`, `lastBuiltAt`, `version`
- `nodes.json`
  - lightweight entries such as `id`, `kind`, `title`, `section`, `parentId`, `refIds`, `anchor`, `summary`
- `edges.json`
  - lightweight entries such as `from`, `to`, `type` with first-version types limited to `tree`, `ref`, and `chain`

Do not turn runtime into a second canonical schema.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/runtime-indexer/src/__tests__/rebuildSubtreeShard.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/runtime-indexer
git commit -m "feat: add local runtime shard generation"
```

### Task 4: Implement orchestrator with local-only action routing

**Files:**
- Create: `packages/orchestrator/package.json`
- Create: `packages/orchestrator/tsconfig.json`
- Create: `packages/orchestrator/src/index.ts`
- Create: `packages/orchestrator/src/routeAction.ts`
- Create: `packages/orchestrator/src/handlers/create.ts`
- Create: `packages/orchestrator/src/handlers/query.ts`
- Create: `packages/orchestrator/src/handlers/complete.ts`
- Create: `packages/orchestrator/src/handlers/reviewApply.ts`
- Test: `packages/orchestrator/src/__tests__/routeAction.test.ts`

**Step 1: Write the failing orchestrator test**

```ts
import { describe, expect, it } from 'vitest'
import { routeAction } from '../routeAction'

describe('routeAction', () => {
  it('routes local query requests to the query handler', async () => {
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
Expected: FAIL because the orchestrator package does not exist.

**Step 3: Write the minimal orchestrator implementation**

```ts
export async function routeAction(input: {
  actionId: 'create' | 'query' | 'complete' | 'review-apply'
  scope: 'local'
  projectId: string
  workset?: { subtreeId?: string }
  input: Record<string, unknown>
}) {
  // dispatch to create/query/complete/review-apply
}
```

Minimum first-version handler behavior:

- `create`: initialize project or subtree skeleton.
- `query`: read local runtime and return answer plus evidence.
- `complete`: return a structured local proposal without writing.
- `review-apply`: be the only normal write-confirmation path.

The first-version proposal object should remain lightweight and reviewable. At minimum it should carry:

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

Required first-version state flow:

- normal: `proposed -> confirmed -> applied`
- failure: `proposed -> confirmed -> failed`

Failure handling rule:

- if canonical content write fails, return `failed`
- if runtime refresh fails after canonical content write, still return `failed`
- failed outcomes must remain visible and must be recordable in `changes/`

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/routeAction.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/orchestrator
git commit -m "feat: add local-only action orchestrator"
```

### Task 5: Prepare OpenChamber integration instead of building a custom shell

**Files:**
- Create: `integrations/openchamber/README.md`
- Create: `integrations/openchamber/plan.md`
- Create: `integrations/openchamber/dfmea-extension-points.md`

**Step 1: Define what OpenChamber is responsible for**

Document that OpenChamber should provide the generic OpenCode-facing shell, including session UI and generic interaction surfaces.

**Step 2: Define what DFMEA should add on top**

Document DFMEA-specific additions such as:

- local workset awareness,
- local project and subtree context injection,
- normalized `query / complete / review-apply` results,
- proposal review and confirmation entry points.

**Step 3: Record what should not be rebuilt**

Document that the first version should not rebuild a generic OpenCode shell from scratch if OpenChamber is adopted.

**Step 4: Save the integration notes**

Expected: the integration notes exist and clearly describe how DFMEA sits on top of OpenChamber.

**Step 5: Commit**

```bash
git add integrations/openchamber
git commit -m "docs: define openchamber integration approach"
```

### Task 6: Add an end-to-end local skeleton flow fixture

**Files:**
- Create: `projects/demo-brake/project.md`
- Create: `projects/demo-brake/content/braking/brake-signal.md`
- Test: `packages/orchestrator/src/__tests__/localSkeletonFlow.test.ts`

**Step 1: Write the failing end-to-end skeleton test**

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
Expected: FAIL until the fixture project and orchestrator wiring are complete.

**Step 3: Write the minimal demo fixture and finish the flow wiring**

```md
# Demo Brake DFMEA

This project is a local-first DFMEA skeleton fixture.
```

```md
# Brake Signal Subtree

This file represents one canonical DFMEA business subtree.
```

Make sure `query` can answer from the fixture, `complete` can emit a proposal, and `review-apply` can:

- require explicit confirmation,
- persist a confirmed result into `changes/`,
- refresh the matching local runtime shard,
- expose failure state when apply or refresh fails.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/localSkeletonFlow.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add projects/demo-brake packages/orchestrator
git commit -m "feat: add local skeleton demo flow"
```

### Task 7: Add explicit review-apply verification coverage

**Files:**
- Create: `packages/orchestrator/src/__tests__/reviewApply.test.ts`
- Modify: `packages/orchestrator/src/handlers/reviewApply.ts`
- Modify: `packages/filesystem/src/writeChangeRecord.ts`

**Step 1: Write the failing review-apply verification test**

```ts
import { describe, expect, it } from 'vitest'
import { reviewApply } from '../handlers/reviewApply'

describe('reviewApply', () => {
  it('requires confirmation and records applied state', async () => {
    const result = await reviewApply({
      projectRoot: 'tmp/projects/demo-brake',
      confirmed: true,
      proposal: {
        proposalId: 'prop-001',
        actionId: 'complete',
        projectId: 'demo-brake',
        subtreeId: 'brake-signal',
        summary: 'Complete local failure section',
        targetFiles: ['content/braking/brake-signal.md'],
        operations: [
          {
            type: 'update_section',
            file: 'content/braking/brake-signal.md',
            section: 'failures',
            description: 'Add local failure descriptions',
          },
        ],
        status: 'proposed',
        createdAt: '2026-03-08T00:00:00.000Z',
      },
    })

    expect(result.kind).toBe('apply_result')
    expect(result.applied).toBe(true)
    expect(result.status).toBe('applied')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm vitest packages/orchestrator/src/__tests__/reviewApply.test.ts`
Expected: FAIL until the confirmation path and applied-state handling are implemented.

**Step 3: Write the minimal review-apply verification behavior**

Make sure the implementation proves all of the following:

- unconfirmed proposals do not write,
- confirmed proposals can write,
- the result exposes `applied` and `status`,
- failures are surfaced as `failed`,
- `changes/` records applied and failed outcomes.

**Step 4: Run test to verify it passes**

Run: `pnpm vitest packages/orchestrator/src/__tests__/reviewApply.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/orchestrator packages/filesystem
git commit -m "test: verify review apply confirmation flow"
```

### Task 8: Add root verification scripts and developer entry commands

**Files:**
- Modify: `package.json`
- Create: `README.md`

**Step 1: Write the failing verification expectation**

Document the expected commands before wiring them:

```text
pnpm test
pnpm --filter @dfmea/copilot-ui dev
```

The test expectation is that root verification should run all package tests from one command.

**Step 2: Run test command to verify it fails or is incomplete**

Run: `pnpm test`
Expected: FAIL or report missing scripts before root scripts are added.

**Step 3: Write the minimal root scripts and README**

Add root scripts for:

- `dev`
- `test`
- `build`

Add a README section describing:

- how to install dependencies,
- how to initialize the demo workspace,
- how to start the copilot shell,
- how the first-version local loop works.

**Step 4: Run verification to verify it passes**

Run: `pnpm test`
Expected: PASS across all implemented package tests.

Run: `pnpm --filter @dfmea/copilot-ui dev`
Expected: local Next.js dev server starts successfully.

**Step 5: Commit**

```bash
git add package.json README.md
git commit -m "docs: add skeleton verification commands"
```

### Task 9: Final manual verification of the first-version loop

**Files:**
- Verify only: `projects/demo-brake/project.md`
- Verify only: `projects/demo-brake/content/braking/brake-signal.md`
- Verify only: `projects/demo-brake/runtime/manifest.json`
- Verify only: `projects/demo-brake/changes/`

**Step 1: Start the app**

Run: `pnpm --filter @dfmea/copilot-ui dev`
Expected: local app starts.

**Step 2: Exercise the create/query/complete/review-apply loop**

Manual flow:

1. open the copilot shell,
2. target `demo-brake`,
3. run a local query,
4. run a local complete request,
5. confirm a proposal through review-apply.

Expected:

- answers come back from local scope,
- proposals are visible before write,
- confirmed changes update `content/`,
- `runtime/manifest.json` refreshes,
- `changes/` records the result.

**Step 3: Commit**

```bash
git add .
git commit -m "feat: complete first-version dfmea skeleton"
```
