# Phase 0 Engineering Skeleton

## Goal
Create the initial TypeScript-first pnpm monorepo skeleton described in DEVELOPMENT_PLAN.md Phase 0.

## Requirements
- Add a pnpm workspace at the repository root.
- Create `apps/api` as a minimal NestJS backend with a health check.
- Create `apps/web` as a minimal React + Vite frontend.
- Create `packages/shared`, `packages/plugin-sdk`, and `packages/capability-sdk`.
- Create an empty `plugins/dfmea` plugin workspace.
- Create `infra/docker-compose.yml` with PostgreSQL plus pgvector.
- Configure TypeScript, ESLint, Prettier, and Vitest for the workspace.
- Add root scripts for `dev`, `build`, `test`, `lint`, and `db:migrate`.

## Acceptance Criteria
- [x] `pnpm install` succeeds.
- [x] `pnpm build` succeeds.
- [x] `pnpm test` succeeds.
- [x] Backend health check code exists and is covered by a basic test.
- [x] Frontend dev server can be started with the workspace script.
- [x] PostgreSQL + pgvector compose configuration exists.

## Completion Note

Completed as part of the Phase 0-12 MVP baseline. Current run and acceptance commands are documented in `docs/RUNNING_AND_ACCEPTANCE.md`.

## Technical Notes
- Do not modify `legacy/dfmea-cli-prototype/` or `OpenCodeUI/`; they are reference assets only.
- Keep Phase 0 limited to runnable scaffolding and baseline tooling.
- Defer database schemas, plugin registry implementation, and business logic to later phases.
