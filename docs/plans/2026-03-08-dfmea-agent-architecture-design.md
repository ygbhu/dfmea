# DFMEA AI Agent Architecture Design

> This document captures the agreed architecture for a DFMEA AI agent built on OpenCode, with a UI on top and Markdown files as the canonical data source.

**Goal:** Build a project-scoped DFMEA AI agent that supports creation, completion, query, modification, and visualization without a traditional database.

**Architecture:** Use Markdown files as the canonical source of truth, shard data by business subtree, generate lightweight runtime indexes for retrieval and UI performance, and route user actions through an orchestration layer that can later delegate to skills.

**Tech Direction:** OpenCode as the agent base, UI as the interaction shell, Markdown as source-of-truth storage, generated runtime indexes for retrieval and visualization, structured patch application for safe writes.

---

## 1. Context and Constraints

### 1.1 Product Goal

The target system is a DFMEA AI agent with the following characteristics:

- Each project is an independent DFMEA workspace.
- Each DFMEA contains concepts such as product, function, requirement, characteristic, failure, failure chain, cause, and effect.
- The system must support question answering, modification, display, creation, and completion.
- The system should not depend on a traditional database for the DFMEA structure tree.
- The system should use OpenCode as the agent foundation, with an upper-layer UI.
- Persistent business data should be stored in Markdown files.

### 1.2 Architectural Principles

This design combines two reference mindsets:

- `planning-with-files`: treat the filesystem as the persistent memory and source of truth.
- `skill-creator`: decompose capabilities into maintainable modules instead of relying on one large prompt.

### 1.3 Explicit Constraints

- No traditional relational or document database is used as the source of truth.
- The architecture must remain usable when the project grows from tens of thousands to hundreds of thousands of nodes.
- The first version should expose business actions in the UI, not a skill workbench.
- Skillization is reserved as a future extension point and is not a first-version core dependency.

---

## 2. High-Level Architecture

The system is designed as four cooperating layers:

1. `content/`: canonical DFMEA Markdown source files.
2. `runtime/`: generated indexes and views used for performance and navigation.
3. `changes/`: optional result-oriented audit trail for confirmed changes.
4. `UI + Orchestrator + OpenCode`: interaction, retrieval, reasoning, proposal generation, and safe application.

The core rule is:

- `content/` is the only business truth.
- `runtime/` is derived and rebuildable.
- `changes/` stores confirmed outcomes, not chain-of-thought.
- The agent proposes and explains changes, but does not silently mutate content.

---

## 3. Project Workspace Model

Each DFMEA project is an independent workspace.

Recommended project layout:

```text
<project-root>/
  content/
  runtime/
  changes/
  ui/
```

### 3.1 Directory Responsibilities

- `content/`
  - Stores business subtree Markdown shards.
  - Is the canonical source of truth.
- `runtime/`
  - Stores generated indexes, graph edges, full-text search artifacts, and prebuilt views.
  - Can be rebuilt from `content/`.
- `changes/`
  - Stores confirmed change summaries, audit entries, or patch snapshots.
  - Stores result traces only, not agent memory logs.
- `ui/`
  - Stores UI-side configuration or local caches if needed.

### 3.2 Deliberate Exclusion

The design does not keep a dedicated `agent/` runtime memory folder such as `task_plan.md`, `findings.md`, or `progress.md` as a first-class architectural requirement.

Reason:

- The core product value is in DFMEA business data and its confirmed changes.
- If the application runs as request-response interactions, persistent AI work logs add cost without business value.
- A lightweight `changes/` layer provides enough traceability for confirmed edits.

---

## 4. Canonical Storage Model: Markdown as Source of Truth

### 4.1 Storage Strategy

The source of truth is a multi-file Markdown graph, not a single large Markdown file.

Reason:

- A single file is not viable for very large DFMEA projects.
- Large projects may contain from ten thousand to one hundred thousand nodes.
- The storage model must support localized reads, localized edits, and localized index refresh.

### 4.2 Sharding Strategy

Confirmed approach: shard by business subtree.

This means a Markdown file represents a coherent DFMEA analysis unit, such as:

- a product module subtree,
- a function subtree,
- a business analysis slice that humans can understand and review as a whole.

This is preferred over:

- one-file-per-entity-type, which creates too much cross-file stitching at query time,
- capacity-only sharding, which weakens readability and maintainability.

### 4.3 Why Business Subtree Sharding Fits DFMEA

- Human review usually happens on meaningful analysis scopes, not on arbitrary chunks.
- Agent query and completion often need the local subtree plus a limited set of cross-references.
- UI can load and refresh by subtree instead of by entire project.
- Future change review can stay understandable to engineering users.

---

## 5. Canonical Markdown File Shape

Each shard file is a business subtree container.

It is not a freeform note. It is a human-readable but machine-stable semi-structured Markdown document.

### 5.1 Suggested File Path Pattern

```text
content/products/<product-id>/<module-id>/<subtree-id>.md
```

This path is illustrative. The exact path can evolve, but it should preserve:

- project-level isolation,
- product/module discoverability,
- deterministic and predictable file placement.

### 5.2 File-Level Metadata

Each shard should include frontmatter with file-level metadata such as:

- `project_id`
- `product_id`
- `subtree_id`
- `root_node_id`
- `title`
- `version`
- `updated_at`

### 5.3 Supported Node Types

The current baseline entity set is:

- `product`
- `function`
- `requirement`
- `characteristic`
- `failure_mode`
- `failure_effect`
- `failure_cause`
- `failure_chain`

### 5.4 Node Block Contract

Each node block should have stable structural fields. At minimum:

- `id`
- `type`
- `parent`
- `children`
- `refs`

Optional descriptive fields can include:

- `name`
- `summary`
- `status`
- `owner`
- `tags`

### 5.5 Relationship Model

Two relationship classes must be separated:

- tree relationships: expressed by `parent` and `children`
- graph relationships: expressed by `refs`

This separation is important because DFMEA is not only a hierarchy. It is also a set of causal and traceable analytical links.

### 5.6 Failure Chain Representation

Failure chains should not be only freeform prose.

Each failure chain should be represented as its own node or node-like block with explicit references such as:

- `from_ids`
- `via_ids`
- `to_ids`

This enables:

- UI chain visualization,
- impact tracing,
- agent-based completion,
- validation of chain continuity.

### 5.7 Illustrative Node Example

```md
## node: FNC-001
type: function
name: Brake signal acquisition
parent: PROD-001
children: [REQ-001, CHR-003, FM-009]
refs:
  chains: [CHAIN-002]
summary: Receives and processes brake input signal.
```

The exact Markdown syntax can evolve later. The important design decision is that node identity and structure must be stable and patchable.

---

## 6. Runtime Layer: Derived Indexes and Views

`runtime/` exists to make the system fast and navigable at scale.

It is not the source of truth.

### 6.1 Design Rules

- Runtime artifacts are generated from `content/`.
- Runtime artifacts can be rebuilt.
- Query and navigation should use runtime artifacts first.
- Write operations must still be applied to `content/`.

### 6.2 Recommended Runtime Artifacts

#### `manifest.json`

Tracks shard-level indexing state, for example:

- file path,
- file hash,
- last indexed timestamp,
- root node id,
- node count,
- dirty flag.

Purpose:

- detect changed shards,
- support incremental refresh,
- avoid full-project rebuild on every edit.

#### `nodes.jsonl` or sharded node indexes

Stores minimal searchable node data such as:

- `id`
- `type`
- `title`
- `parent`
- `refs`
- `file`
- `anchors`
- `tokens_hint`

Purpose:

- node lookup,
- query prefiltering,
- UI navigation.

#### `edges.jsonl`

Stores expanded tree edges and graph edges.

Purpose:

- tree rendering,
- failure chain rendering,
- impact analysis,
- reference traversal.

#### `fts/`

Stores full-text search artifacts.

Purpose:

- natural-language lookup,
- keyword search,
- evidence-node retrieval.

#### `views/`

Stores optional lightweight derived summaries for future UI or explanation use.

Purpose:

- support minimal entry-point rendering when needed,
- provide optional prebuilt local summaries without becoming a required first-version UI dependency.

### 6.3 Source Control Strategy

The default decision is:

- treat runtime artifacts as rebuildable,
- do not treat them as the canonical collaboration layer.

In practice, most runtime files should be considered cache-like and can be ignored or selectively persisted depending on deployment needs.

---

## 7. Agent and Orchestration Role

OpenCode is not just a chat frontend.

In this architecture, it acts as a DFMEA-aware operation orchestrator.

### 7.0 OpenCode as the Foundation

The system should treat OpenCode as the agent runtime foundation, not as a UI widget and not as application code that needs to be reimplemented.

The intended role split is:

- OpenCode provides the agent runtime,
- the DFMEA system provides domain orchestration.

In practice, OpenCode should own:

- session lifecycle,
- model and provider access,
- tool execution,
- local file interaction,
- agent reasoning loop,
- HTTP or SDK-facing agent interface.

The DFMEA application should own:

- project workspace structure,
- `content/`, `runtime/`, and `changes/`,
- local workset selection,
- `create`, `query`, `complete`, and `review-apply`,
- DFMEA-specific prompts, rules, and constraints,
- DFMEA-specific extensions on top of the chosen OpenCode-facing shell.

### 7.0.1 Preferred Integration Pattern

The recommended integration pattern is:

- treat OpenCode as a local agent server or sidecar,
- connect the DFMEA application through SDK or HTTP API,
- keep DFMEA business logic outside OpenCode core.

This is preferred over forking OpenCode or embedding business-specific changes deep into its internals.

### 7.0.2 Why This Pattern Fits the DFMEA Product

This pattern is a good fit because:

- it preserves OpenCode as an upgradeable foundation,
- it keeps the DFMEA product focused on domain behavior,
- it avoids coupling DFMEA logic to OpenCode internals,
- it makes later plugin, MCP, or skill expansion easier.

### 7.0.3 Practical Integration Stages

Recommended staged adoption:

#### Stage 1

- use OpenCode as the local runtime foundation,
- reuse an existing OpenCode-facing frontend shell,
- let the DFMEA orchestrator and extension layer call OpenCode through API or SDK,
- keep all DFMEA business flow in the application layer.

#### Stage 2

- add DFMEA-specific tools through plugin or MCP when useful,
- expose operations such as local subtree retrieval, local validation, runtime rebuild, or patch proposal generation as bounded tools.

#### Stage 3

- optionally convert stable DFMEA workflows into reusable skills or packaged extensions.

### 7.0.4 Open Source References

The following references are useful for implementation thinking:

- `anomalyco/opencode`
  - the official OpenCode repository,
  - most useful for understanding the runtime model, HTTP server, SDK, session system, tools, plugin system, and MCP integration.
- `different-ai/openwork`
  - useful as a reference for building a more productized experience on top of OpenCode.
- `btriapitsyn/openchamber`
  - the preferred first-version frontend shell choice for this project,
  - useful as a ready-made GUI wrapper around OpenCode that can be extended with DFMEA-specific views and actions.
- `kcrommett/opencode-web`
  - useful as a reference for browser-based access patterns.
- `awesome-opencode/awesome-opencode`
  - useful as an ecosystem index for plugins, sessions, workspace helpers, memory systems, and other integration ideas.

### 7.0.5 Design Rule

The DFMEA product should not treat OpenCode as the final product surface.

Instead:

- OpenCode is the agent operating layer,
- the DFMEA application is the domain-specific product layer built above it.

### 7.0.6 DFMEA-to-OpenCode Call Chain

The first-version DFMEA application should call OpenCode through SDK or HTTP API using a layered call chain, with OpenChamber acting as the reusable OpenCode-facing shell.

Recommended flow:

1. the user sends a request through OpenChamber with DFMEA-specific entry actions or extension points,
2. the DFMEA orchestrator resolves the current project and local workset,
3. the orchestrator prepares a DFMEA-scoped agent request,
4. the request is sent to OpenCode through SDK or HTTP API,
5. OpenCode runs the agent session and tools,
6. the DFMEA application receives streamed or final results,
7. the DFMEA application interprets the result as answer, proposal, or apply outcome,
8. the DFMEA application updates `runtime/` and `changes/` when appropriate.

The important design point is that DFMEA business flow wraps OpenCode execution rather than being embedded directly inside OpenCode.

### 7.0.7 First-Version Request Preparation

Before calling OpenCode, the DFMEA application should prepare:

- current project root,
- local subtree scope,
- relevant `project.md` context,
- relevant `content/` paths or summaries,
- relevant `runtime/` lookup results,
- the requested business action: `create`, `query`, `complete`, or `review-apply`.

This preparation layer is where DFMEA-specific context shaping should happen.

OpenCode should receive a bounded, already-scoped request rather than being asked to discover the whole DFMEA project by itself.

### 7.0.8 Response Interpretation Layer

After OpenCode returns, the DFMEA application should normalize the result into one of the first-version business result types:

- `answer`
- `proposal`
- `apply_result`
- `error`

The OpenChamber-based extension layer should consume normalized DFMEA results, not raw OpenCode internals.

This keeps the product stable even if OpenCode transport details evolve.

### 7.0.9 Write Boundary Through OpenCode

The DFMEA application should preserve the same write boundary even when OpenCode performs the reasoning.

That means:

- `query` remains read-only,
- `complete` returns a proposal,
- only `review-apply` performs confirmed writes.

If OpenCode generates edits or suggestions, the DFMEA layer should still treat them as proposals until they pass through the application review path.

### 7.0.10 Suggested Integration Interfaces

The first version should expose a small internal integration surface between the DFMEA application and OpenCode.

Suggested internal operations:

- `startSession(projectRoot)`
- `sendScopedPrompt(sessionId, actionId, localWorkset, context)`
- `streamSessionEvents(sessionId)`
- `cancelSession(sessionId)`
- `closeSession(sessionId)`

These names are conceptual. The implementation can map them onto the real OpenCode SDK or HTTP routes later.

### 7.0.11 First-Version Operational Pattern

For the first version, the recommended operational pattern is:

- run OpenCode locally,
- treat it as a sidecar or local service,
- let `packages/orchestrator` be the DFMEA-side caller,
- reuse OpenChamber as the OpenCode-facing shell,
- add DFMEA-specific interaction surfaces on top of OpenChamber rather than building a new generic shell from scratch.

This keeps the product architecture aligned with the previously agreed repository skeleton.

### 7.1 Core Responsibilities

The agent layer is responsible for:

- locating relevant nodes or subtrees,
- answering questions from scoped evidence,
- proposing additions or edits,
- generating safe structured patch proposals,
- validating structure and DFMEA rules before apply.

### 7.2 Working Set Strategy

The agent must not load the whole project by default.

The standard working pattern is:

1. Use `runtime/` to locate candidate nodes, files, and subtrees.
2. Select a bounded workset.
3. Load only relevant Markdown shards and a limited set of cross-references.
4. Produce answer, proposal, or validation result.

This keeps the architecture compatible with very large node counts.

### 7.3 No Silent Mutation

The agent does not directly overwrite Markdown as a side effect of reasoning.

Instead:

- read operations return answers and evidence,
- propose operations return patch proposals,
- apply operations happen only after explicit confirmation.

---

## 8. Interaction Entry Strategy

The first-version product is AI-first, built on top of OpenCode and surfaced through OpenChamber.

The system should not require a fixed tree-first or graph-first UI.

### 8.1 Primary Entry Point

The primary user entry is a chat-style interaction model provided through OpenChamber, with DFMEA-specific actions layered on top.

Users should be able to ask for actions such as:

- create a DFMEA project or subtree,
- complete a local analysis scope,
- query failures, causes, effects, or chains,
- validate a selected analysis scope,
- review and confirm proposed changes.

### 8.2 Minimal UI Requirement

The first version does not need a custom general-purpose frontend shell. It only needs DFMEA-specific entry points and result presentation on top of OpenChamber.

Required entry capabilities are:

- accept user requests,
- pass current context or selected scope when available,
- show answers,
- show evidence or related local content when requested,
- show patch proposals for confirmation.

These should be implemented as DFMEA-oriented extensions over the chosen OpenChamber shell rather than as a new standalone frontend product.

### 8.3 Deliberate Non-Requirement

The first version does not require:

- a permanently visible full tree,
- a permanently visible full graph,
- a fixed multi-panel engineering workspace.

If the user wants to inspect a subtree or a chain, the system can reveal only that local part on demand.

### 8.4 Product Principle

The product should be biased toward AI-guided work, not toward manual navigation-first work.

Structure, graph, and diff views are supporting outputs that appear when useful, not mandatory primary screens. OpenChamber provides the generic shell; DFMEA supplies the domain-specific overlays and actions.

---

## 9. Business Action Gateway

Skillization is intentionally deferred.

However, the architecture should preserve an internal capability gateway so future skills can replace local handlers without changing the UI contract.

### 9.1 Current Business Actions

The first-version UI should expose business actions such as:

- `create_dfmea`
- `complete_subtree`
- `query_dfmea`
- `validate_subtree`

### 9.2 Minimal Internal Action Contract

The internal gateway should support at least:

- `actionId`
- `workset`
- `input`
- `mode`
- `result`
- `patchProposal`

### 9.3 Operation Modes

Recommended initial modes:

- `read`
- `propose`
- `apply`

This preserves a clean write boundary and leaves room for later skill-based implementations.

---

## 10. Core Business Workflows

### 10.1 Create Workflow

Purpose:

- initialize a new DFMEA project workspace,
- generate the first Markdown subtree shards,
- build the initial runtime index.

Input examples:

- project metadata,
- initial product structure,
- starting module or function tree,
- optional template.

Expected result:

- a navigable DFMEA workspace,
- stable ids and predictable file placement,
- an initial but not necessarily complete analysis structure.

Design rule:

- prefer generating a correct skeleton over forcing one-shot completeness.

### 10.2 Complete Workflow

Purpose:

- enrich an existing subtree with missing requirements, characteristics, failures, causes, effects, or chains.

Standard flow:

1. Select workset.
2. Read relevant shards and required references.
3. Generate structured patch proposal.
4. Run structural validation.
5. Run DFMEA rule validation.
6. Present proposal to the user.
7. Apply on confirmation.
8. Refresh runtime incrementally.

Expected result:

- a reviewed proposal set rather than silent direct mutation.

### 10.3 Query Workflow

Purpose:

- answer DFMEA questions using scoped evidence.

Standard flow:

1. Parse the user question.
2. Select workset through runtime lookup.
3. Retrieve relevant nodes, edges, and evidence.
4. Compose answer.
5. Return evidence nodes and jump targets.

Expected output should include:

- answer text,
- evidence nodes,
- jump locations for tree or chain view.

Query is strictly read-only.

---

## 11. Modification and Patch Model

This is the safety-critical layer of the architecture.

### 11.1 Why Patches Are Required

Because the source of truth is multi-file Markdown, the system must not treat writes as freeform text replacement.

All write intents should first become structured patch proposals.

### 11.2 Patch Proposal Operations

Recommended initial operations:

- `add_node`
- `update_node`
- `move_node`
- `delete_node`
- `link_node`
- `unlink_node`

### 11.3 Operation Constraints

- `update_node` changes fields only and must not silently change node identity.
- `move_node` must explicitly describe parent change.
- `delete_node` must pass reference checks before apply.
- link operations must preserve graph consistency.

### 11.4 Review Experience

The review UI should show diffs grouped by:

- file,
- node,
- field.

Users should be able to understand:

- what is being added,
- what is being modified,
- what references are affected,
- whether any warnings are raised.

### 11.5 Apply Sequence

The apply sequence should be:

1. User confirms patch proposal.
2. Patch applier writes precise Markdown changes.
3. Structural validation runs.
4. DFMEA rule validation runs.
5. Runtime indexes refresh incrementally.
6. Confirmed result is recorded in `changes/`.

This creates a reliable human-in-the-loop mutation flow.

---

## 12. Validation Model

Two validation layers are required.

### 12.1 Structural Validation

Checks examples:

- frontmatter validity,
- node block format,
- unique ids,
- parent-child consistency,
- reference existence,
- chain field integrity.

### 12.2 DFMEA Rule Validation

Checks examples:

- required child types under a function,
- missing cause or effect for a failure mode,
- broken failure chain continuity,
- naming or completeness rules.

Validation should run before confirmed writes are accepted as complete.

---

## 13. Large-Scale Runtime Performance Strategy

This section defines the runtime strategy for projects that may grow from ten thousand to one hundred thousand nodes.

The first version is explicitly optimized for local-first usage.

### 13.1 Local-First Runtime Assumption

The first version should optimize for:

- local project usage,
- local indexing,
- local incremental refresh,
- bounded on-demand query execution.

The design should remain portable to a future shared or service-backed architecture, but it should not start with service-level complexity.

### 13.2 Runtime Shard Mapping Rule

Confirmed rule:

- one `content` business subtree file maps to exactly one `runtime` shard.

This means a canonical subtree file such as:

```text
content/products/.../<subtree-id>.md
```

maps to a deterministic runtime directory such as:

```text
runtime/shards/<subtree-id>/
```

This rule is intentionally strict because it improves:

- predictability,
- localized debugging,
- localized refresh,
- localized invalidation,
- source-to-runtime traceability.

### 13.3 Runtime Shard Contents

Each shard should remain lightweight and should not duplicate the full source Markdown.

Recommended shard files:

- `meta.json`
  - subtree id,
  - source file path,
  - source file hash,
  - root node id,
  - node count,
  - edge count,
  - last build timestamp,
  - schema version.
- `nodes.json`
  - lightweight node index fields such as id, type, title, parent, child ids, ref ids, status, anchor.
- `edges.json`
  - expanded tree edges and graph edges.
- optional summary or explanation-oriented lightweight view files when needed later.

Design rule:

- `nodes.json` and `edges.json` support retrieval and reasoning.
- source Markdown remains the authority for final evidence and writes.

### 13.4 Incremental Refresh Strategy

The system should not perform full runtime rebuilds after normal edits.

The standard refresh flow should be:

1. A confirmed content change updates the source file hash.
2. The corresponding entry in `runtime/manifest.json` is marked dirty.
3. Only the matching shard is rebuilt.
4. The shard updates its `meta.json`, `nodes.json`, and `edges.json`.
5. Global lookup and search artifacts are updated only for affected entries.

This makes the normal refresh path proportional to a single subtree, not to total project size.

### 13.5 Cross-Shard Reference Handling

DFMEA data includes cross-shard references, so not every change is purely local.

The first-version strategy should be:

- default to rebuilding only the directly changed shard,
- detect potentially propagated impact when changes affect ids, moves, deletions, or critical references,
- run lightweight follow-up checks or delayed rebuilds on impacted shards.

This is a practical compromise:

- local edits stay cheap,
- dangerous cross-reference edits still trigger additional safety handling,
- the system avoids pretending to be a fully global compiler on every save.

### 13.6 Global Runtime Layer Responsibilities

The global layer must stay thin.

It should not become a second source of truth or a second full graph store.

Recommended global responsibilities:

- `manifest`
  - tracks shard existence, hash, dirty state, and rebuild metadata.
- `lookup`
  - resolves node id to source file, shard, and anchor.
- `reverse_refs`
  - stores lightweight reverse dependency information for impact analysis.
- `fts`
  - supports keyword or natural-language candidate recall.

Boundary rule:

- global layer answers where to look,
- shard layer answers what the local structure is,
- source Markdown answers what the final truth says.

### 13.7 Query Pipeline at Scale

Large-scale query execution should follow a four-stage path:

1. global recall,
2. workset narrowing,
3. shard-local refinement,
4. source readback only when necessary.

Interpretation:

- `fts`, `lookup`, and current context produce candidates,
- candidates are reduced into a bounded workset,
- only relevant shard indexes are loaded for structural reasoning,
- source Markdown is read only for high-fidelity evidence or pending writes.

This avoids whole-project loading during normal question answering.

### 13.8 Workset Definition

A workset is not merely a set of matched nodes.

It is a bounded runtime context with at least:

- `seed`
- `allowed_shards`
- `expansion_rules`
- `budget`

This allows the system to explicitly control how far retrieval is allowed to expand.

### 13.9 Recommended First-Version Workset Budgets

Conservative first-version defaults are recommended.

Suggested defaults for standard query mode:

- shard budget: current shard plus two to three external shards,
- node budget: about 150 to 400 lightweight nodes,
- expansion budget: up to two cross-reference or chain hops,
- source readback budget: only a small number of final evidence fragments.

These numbers can be tuned later, but the architectural rule should stay the same:

- bounded retrieval is preferred over unconstrained completeness.

### 13.10 Workset Expansion Priority

When expanding context, priority should be fixed to reduce drift.

Recommended order:

1. current UI-selected or request-selected subtree,
2. highest relevance nodes inside that subtree,
3. direct referenced external nodes,
4. only then one additional layer of reverse or neighboring references if needed.

If candidate scope exceeds budget, the system should rank and prune rather than keep expanding.

### 13.11 Query Scope Policy

The first version should support only one explicit query scope:

- `Local`
  - the default and only supported first-version query scope,
  - constrained to the current or explicitly selected business subtree shard,
  - used for query, completion, validation, and patch proposal generation.

Implementation note:

- very small direct-reference lookups may still be allowed internally when needed for explanation or consistency checks,
- but the product should still treat the operation as local rather than exposing broader query modes.

Design rule:

- first-version behavior should prefer a stable local workset over broader retrieval strategies.

### 13.12 UI Implication Under AI-First Interaction

Because the product is AI-first, the large-scale runtime does not need to support eager rendering of the full tree or full graph in the first version.

Instead, runtime should optimize for:

- fast answer generation,
- bounded local evidence extraction,
- on-demand reveal of only the subtree, chain, or patch detail the user asks to inspect.

This keeps performance strategy aligned with the product direction.

---

## 14. Decisions Confirmed So Far

The following decisions are already agreed:

- Use `A + C` lightweight hybrid architecture.
- Each project is an independent DFMEA workspace.
- Do not use a single giant Markdown file.
- Use multi-file Markdown as the canonical source of truth.
- Shard canonical content by business subtree.
- Use generated runtime indexes for retrieval and UI speed.
- Do not keep persistent agent-memory files as a first-class product layer.
- Keep a lightweight `changes/` audit layer for confirmed results.
- Let the UI expose business actions, not low-level skills.
- Defer detailed skill design; keep only an internal capability entry point.
- Define three core workflows first: create, complete, query.
- Use structured patch proposals plus explicit review before apply.
- Optimize the first-version runtime for local-first usage.
- Map one canonical content shard to one runtime shard.
- Use incremental shard rebuild instead of full runtime rebuild.
- Keep the global runtime layer thin: manifest, lookup, reverse refs, and fts.
- Use bounded worksets instead of unconstrained project-wide loading.
- Support only `Local` query scope in the first version.
- Keep large-scale runtime aligned with AI-first interaction, not full-tree-first rendering.

---

## 15. Topics Deferred to Next Discussion

The next major topics should focus on how to stand up the first-version skeleton without prematurely freezing low-level schemas.

Open items for the next session:

- how to initialize the project workspace and directory skeleton,
- how to wire OpenCode as the primary interaction entry,
- how to map `create`, `complete`, `query`, and review-apply into first-version handlers,
- how to organize canonical Markdown content so it follows DFMEA semantics without freezing final node details,
- how to generate the minimum viable runtime layer for local retrieval,
- how to record confirmed changes in `changes/`,
- whether broader than local retrieval is ever needed after the first version.

---

## 16. Recommended Next Step

Use this document as the stable architecture baseline.

The next design discussion should focus on first-version skeleton delivery, especially:

- workspace skeleton,
- OpenCode entry integration,
- business action routing,
- minimum viable content organization,
- minimum viable runtime generation,
- review and apply loop.

---

## 17. Current Implementation Direction

The repository is no longer following the earlier custom-shell implementation path.

The current implementation direction is:

- use OpenChamber as the repository base and OpenCode-facing shell,
- keep DFMEA as a domain-specific backend and project-layer extension,
- strengthen runtime indexing and project-local DFMEA execution before adding more UI.

### 17.1 Current Repository Shape

The current repository should be understood as:

```text
repo/
  packages/
    ui/
    web/
    desktop/
    vscode/
    dfmea/
  integrations/
    openchamber/
  docs/plans/
```

This means earlier custom packages such as standalone `filesystem`, `runtime-indexer`, `orchestrator`, or `copilot-ui` are no longer the active implementation path in code, even if they remain useful in earlier planning documents.

### 17.2 Active DFMEA Direction Inside OpenChamber

The active direction is to add DFMEA through narrow extension seams:

- `packages/dfmea/`
  - DFMEA domain types, context, and proposal-level abstractions.
- `packages/web/server/index.js`
  - DFMEA backend endpoints and server-side runtime integration.
- `packages/web/src/api/*`
  - DFMEA web runtime adapters.
- `packages/ui/src/lib/*`
  - DFMEA project config, action presets, and runtime API typing.
- `packages/ui/src/components/sections/projects/*`
  - project-scoped DFMEA settings and action entry surfaces.

### 17.3 Near-Term Product Priority

The near-term priority is not richer UI.

The near-term priority is:

1. stronger runtime indexing,
2. stable project-local DFMEA storage conventions,
3. local query / complete / review-apply backend flow,
4. explicit reviewable mutation handling,
5. keeping OpenChamber as the reusable shell rather than rebuilding a new one.

### 17.4 Strong Runtime Index Direction

The strongest next architectural move is to deepen `runtime/` rather than replace Markdown canonical storage.

That means:

- keep Markdown subtree files canonical,
- improve extracted runtime nodes and edges,
- add stronger local lookup and keyword retrieval,
- support bounded local worksets,
- defer any canonical database migration until the runtime layer clearly becomes the bottleneck.

### 17.5 Current Definition of “Usable DFMEA System”

For the current repository direction, a usable DFMEA system means:

1. a project can expose DFMEA settings and local scope context,
2. a DFMEA runtime adapter can resolve local content/runtime roots,
3. local query and completion can be routed through explicit DFMEA backend endpoints,
4. review-apply can remain a first-class confirmed mutation path,
5. runtime index quality is sufficient to support node lookup and keyword retrieval without broad scans.

### 17.6 Delivery Principle From This Point Forward

From this point forward, the repository should optimize for:

- OpenChamber-compatible DFMEA backend integration,
- strong local runtime indexing,
- project-local retrieval and mutation safety,
- minimal UI work until backend/runtime behavior is solid.

It should not optimize for:

- replacing OpenChamber with a custom shell,
- prematurely introducing PostgreSQL as canonical storage,
- broad global retrieval modes,
- heavy graph visualization before backend retrieval quality is ready.
