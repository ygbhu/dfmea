# DFMEA Runtime Index Buildout Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current OpenChamber-based DFMEA fork into a usable backend-first DFMEA system by strengthening the runtime index, local lookup, and review-apply path while keeping Markdown as canonical storage.

**Architecture:** Use `packages/dfmea` as the domain/runtime layer, keep `packages/web/server/index.js` as the narrow backend surface, and keep UI work limited to configuration and action exposure only. Runtime-first lookup should become the primary path for query and node retrieval; Markdown remains canonical and is only read for source-of-truth content and writes.

**Tech Stack:** OpenChamber monorepo, Bun, TypeScript, Express-based web server, Markdown canonical content, derived runtime index.

---

### Task 1: Add canonical storage helpers to `packages/dfmea`

**Files:**
- Create: `packages/dfmea/src/content.ts`
- Create: `packages/dfmea/src/storage.ts`
- Modify: `packages/dfmea/src/index.ts`

**Step 1: Write the failing test**

Define a test showing that a DFMEA workspace root can derive canonical `content`, `runtime`, and `changes` roots plus stable subtree file locations.

**Step 2: Run the test to verify it fails**

Expected: FAIL until the new helpers exist.

**Step 3: Write the minimal implementation**

Implement helpers that:

- derive canonical roots,
- derive subtree markdown file paths,
- keep Markdown canonical.

**Step 4: Run the test to verify it passes**

Expected: PASS.

### Task 2: Add runtime manifest and shard builders to `packages/dfmea`

**Files:**
- Create: `packages/dfmea/src/runtimeIndex.ts`
- Modify: `packages/dfmea/src/index.ts`

**Step 1: Write the failing test**

Define a test showing that one canonical subtree file maps to one runtime shard entry and a manifest entry.

**Step 2: Run the test to verify it fails**

Expected: FAIL until runtime index generation exists.

**Step 3: Write the minimal implementation**

Implement:

- manifest entries,
- shard metadata,
- extracted local node summaries,
- extracted local edges.

**Step 4: Run the test to verify it passes**

Expected: PASS.

### Task 3: Add runtime keyword/node lookup helpers

**Files:**
- Create: `packages/dfmea/src/runtimeSearch.ts`
- Modify: `packages/dfmea/src/index.ts`

**Step 1: Write the failing test**

Define a test showing that a keyword or title can retrieve the most relevant local node/shard hit.

**Step 2: Run the test to verify it fails**

Expected: FAIL until runtime search exists.

**Step 3: Write the minimal implementation**

Implement:

- title/summary matching,
- path/subtree context-aware ranking,
- local node lookup by id.

**Step 4: Run the test to verify it passes**

Expected: PASS.

### Task 4: Add DFMEA runtime search backend endpoints

**Files:**
- Modify: `packages/web/server/index.js`
- Modify: `packages/web/src/api/dfmea.ts`
- Modify: `packages/web/src/api/index.ts`
- Modify: `packages/ui/src/lib/api/types.ts`

**Step 1: Write a failing command-level verification**

Define a manual request expectation for a new `/api/dfmea/search` endpoint.

**Step 2: Run the request to verify it fails**

Expected: FAIL until the endpoint exists.

**Step 3: Write the minimal implementation**

Implement backend endpoint(s) for:

- local context,
- local keyword search,
- local node lookup.

**Step 4: Run manual QA to verify it passes**

Call the endpoint and show JSON output.

### Task 5: Add backend review-apply execution path

**Files:**
- Create: `packages/dfmea/src/reviewApply.ts`
- Modify: `packages/dfmea/src/index.ts`
- Modify: `packages/web/server/index.js`

**Step 1: Write a failing verification case**

Define a request or test that shows confirmed review-apply should write canonical content and rebuild runtime.

**Step 2: Run it to verify it fails**

Expected: FAIL until review-apply exists.

**Step 3: Write the minimal implementation**

Implement:

- confirmed proposal apply,
- content write,
- runtime shard rebuild,
- result recording.

**Step 4: Run manual QA to verify it passes**

Show that source content and runtime artifacts both change.

### Task 6: Audit and verify the usable backend-first DFMEA system

**Files:**
- Verify only: `packages/dfmea/**`
- Verify only: `packages/web/**`
- Verify only: `docs/plans/*.md`

**Step 1: Run project verification**

- `bun run type-check:ui`
- `bun run build:web`
- DFMEA-specific tests

**Step 2: Run manual QA**

- `/api/dfmea/context`
- `/api/dfmea/search`
- review-apply endpoint

**Step 3: Final audit**

Document exactly:

- what is now usable,
- what remains deferred,
- what next backend priority should be.
