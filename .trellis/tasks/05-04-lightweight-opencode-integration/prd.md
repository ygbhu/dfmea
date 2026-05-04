# Lightweight OpenCode Integration

## Goal

Make this quality assistant easy for OpenCode/OpenCode UI to use without turning OpenCode or the UI
into the core runtime.

## What I Already Know

- The Python engine currently lives under `end/`.
- OpenCode UI has been downloaded into `ui/`.
- The current manual workflow asks OpenCode to read `AGENTS.md`, enter `end/`, and run CLI commands.
- The user feels that workflow is not lightweight enough.
- PFMEA is deferred and must remain placeholder-only.
- Core constraints still apply: Python engine, no SQLite/PostgreSQL target storage, no UI-owned
  source-of-truth writes.

## Assumptions

- The desired experience should feel like installing/using a project tool, not manually remembering
  paths and commands.
- The integration should be reusable from any quality workspace, not only this repo.

## Open Questions

- Confirm whether the MVP should be a repo-local OpenCode pack first, followed by an installable
  generator command.

## Requirements

- Preserve `quality` / `dfmea` CLI as the authoritative write path.
- Make OpenCode usage discoverable and repeatable.
- Keep UI/OpenCode optional from the engine perspective.

## Acceptance Criteria

- [ ] A user can point OpenCode at the repo and discover quality commands without reading long docs.
- [ ] Standard checks and DFMEA smoke workflows are one-command or one-prompt operations.
- [ ] The integration does not register PFMEA or add database storage.

## Definition of Done

- Tests/validation commands still pass.
- Docs explain the OpenCode usage model.
- Integration files are small and do not fork core logic.

## Out of Scope

- Rewriting the engine as an OpenCode plugin.
- Making OpenCode UI the source of truth.
- Implementing PFMEA.

## Technical Notes

- Research Trellis and comparable project layouts before selecting the approach.

## Research Notes

### What Trellis Does

- Trellis does not turn its workflow runtime into an OpenCode-only plugin. It keeps `.trellis/` as
  the shared source of truth and generates host-specific files for OpenCode under `.opencode/`.
- Its OpenCode integration writes native OpenCode commands, skills, agents, and optional plugins.
- Its configurator keeps init-time file generation and update-time template tracking in sync by
  enumerating the same OpenCode template file set from one function.

### What OpenCode Supports Natively

- OpenCode custom commands can be project-local Markdown files under `.opencode/commands/`.
- OpenCode skills can be project-local `SKILL.md` files under `.opencode/skills/<name>/SKILL.md`.
- OpenCode also discovers `.agents/skills/<name>/SKILL.md`, which allows a shared skill layout for
  multiple agent hosts.
- OpenCode plugins can add hooks and custom tools, but they introduce JavaScript/TypeScript runtime
  surface and should be reserved for cases where Markdown commands/skills are not enough.

### Constraints From This Project

- Python remains the core implementation language.
- The authoritative write path remains `quality` / `dfmea` CLI or shared Python core.
- OpenCode and OpenCode UI are optional hosts, not source-of-truth runtimes.
- PFMEA remains a placeholder and must not be registered as an active command or skill workflow.
- No SQLite/PostgreSQL target storage should be introduced.

### Feasible Approaches

**Approach A: Repo-local OpenCode Pack** (recommended first step)

- How it works: add `.opencode/commands/quality/*.md` and `.opencode/skills/quality-*` /
  `.opencode/skills/dfmea-*` that call the existing Python CLI from `end/`.
- Pros: immediately usable in OpenCode UI, no new runtime, no plugin loader risk, easy to review.
- Cons: initially repo-local; portability comes from copying or a later generator command.

**Approach B: Python Generator Command**

- How it works: add a Python command such as `quality adapter opencode init` that writes the
  `.opencode/` pack into any workspace, following the Trellis configurator pattern.
- Pros: portable and repeatable; good long-term packaging shape.
- Cons: requires a small adapter/template management layer and tests.

**Approach C: OpenCode Plugin / MCP Tool Adapter**

- How it works: expose quality operations as OpenCode plugin tools or MCP tools.
- Pros: strongest tool UX once mature.
- Cons: heavier runtime, more moving parts, JavaScript or protocol surface, unnecessary for the
  first lightweight OpenCode experience.

## Recommendation

Start with Approach A, but structure the files so Approach B can later package exactly the same
templates. Avoid Approach C until commands and skills are insufficient.
