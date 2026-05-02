# DFMEA Workspace

AI-first Quality Engineering Workspace for DFMEA drafting, review, projection, and API Push integration.

This repository contains the MVP baseline for a quality engineering workspace where an Agent Runtime can generate DFMEA draft data, the user can review and apply it, and the platform can rebuild confirmed projections and push structured output to a mature FMEA system adapter.

## Current Status

The Phase 0-12 MVP baseline is implemented:

- TypeScript pnpm workspace.
- NestJS Platform API.
- React workspace UI.
- shared contracts and SDK packages.
- DFMEA domain plugin MVP.
- PostgreSQL schema and migrations.
- mock knowledge provider.
- mock runtime provider.
- AI Draft Batch, Draft Patch, apply, and reject flow.
- working tree projection rebuild and freshness tracking.
- API Push validate and execute flow against a mock mature FMEA adapter.
- unit, integration, component, and browser E2E coverage.

## Product Scope

The platform is an AI-first workspace, not a full enterprise FMEA lifecycle system.

The core flow is:

```text
User Goal
  -> Agent Runtime
  -> Workspace Capability Server / Platform API
  -> Domain Plugin Skill
  -> AI Draft Batch
  -> User Review / Apply
  -> Canonical Artifact and Edge Data
  -> Workspace Revision
  -> Projection Rebuild
  -> Knowledge Query / API Push
```

Enterprise permissions, approval workflows, signoff, official release, long-term compliance records, and final quality ownership are expected to remain in the mature FMEA system.

## Repository Layout

```text
apps/
  api/                 NestJS Platform API, services, repositories, migrations
  web/                 React workspace UI
packages/
  shared/              shared contracts, IDs, events, statuses, errors
  plugin-sdk/          domain plugin SDK primitives
  capability-sdk/      capability server SDK primitives
plugins/
  dfmea/               DFMEA plugin skills, validators, projections, prompts
docs/                  architecture, detailed design, planning, acceptance docs
tests/e2e/             Playwright browser acceptance tests
infra/                 local infrastructure notes
```

`legacy/` and `OpenCodeUI/` are reference assets and are ignored by Git in this project.

## Prerequisites

- Node.js `>=24`
- pnpm `>=10.33.2`
- PostgreSQL with pgvector
- Chrome or Edge for Playwright E2E

Docker is not required for the current acceptance flow. Use a remote PostgreSQL instance through `.env`.

## Environment

Create `.env` from `.env.example` and set the PostgreSQL connection string:

```powershell
Copy-Item .env.example .env
```

```env
DATABASE_URL=postgres://postgres:password@host:5432/vector_db
```

Optional environment variables:

- `PORT`: API server port. Default: `3000`.
- `VITE_API_BASE_URL`: web client API base URL. Default: `http://localhost:3000`.
- `PLAYWRIGHT_CHROME_EXECUTABLE_PATH`: local browser path for E2E if Playwright cannot find Chrome automatically.

Do not commit real credentials. `.env` and `.env.*` are ignored.

## Quick Start

Install dependencies:

```powershell
pnpm install
```

Apply database migrations:

```powershell
pnpm db:migrate
```

Start API and web together:

```powershell
pnpm dev
```

Default local URLs:

- API health check: `http://localhost:3000/health`
- Web workspace: `http://localhost:5173`

## Validation

Run the main quality gates:

```powershell
pnpm build
pnpm test
pnpm lint
pnpm typecheck
```

Run browser acceptance:

```powershell
pnpm e2e
```

`pnpm e2e` starts or reuses:

- API server on `http://127.0.0.1:3000`
- Web server on `http://127.0.0.1:5173`

The E2E flow covers workspace bootstrap, mock runtime draft generation, draft review, apply, working tree refresh, API Push validation, and API Push execution.

## Main Documents

- [Architecture](docs/ARCHITECTURE.md)
- [Development Plan](docs/DEVELOPMENT_PLAN.md)
- [Running And Acceptance](docs/RUNNING_AND_ACCEPTANCE.md)
- [Workspace UI Design](docs/WORKSPACE_UI_DESIGN.md)
- [Platform API Design](docs/PLATFORM_API_DESIGN.md)
- [DFMEA Plugin Design](docs/DFMEA_PLUGIN_DESIGN.md)
- [Documentation Index](docs/README.md)

## Development Notes

- Keep the workspace UI data sources separate: Working Tree, Draft Preview, Runtime Events, and API Push.
- The Structure plugin is the default left-side plugin; Draft Review, Runtime Events, and API Push are switchable plugins.
- Do not call domain plugin handlers directly from the UI.
- Prefer adding new product work through a scoped task and update docs when contracts change.
