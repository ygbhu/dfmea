# Running And Acceptance

## Environment

- Node.js: `>=24`
- pnpm: `>=10.33.2`
- Database: PostgreSQL with pgvector, configured through `DATABASE_URL` in `.env`
- Browser E2E: local Chrome or Edge. Set `PLAYWRIGHT_CHROME_EXECUTABLE_PATH` if Chrome is not installed in the default Windows path.

The current development environment uses the remote PostgreSQL configured in `.env`; Docker is not required for acceptance.

## Commands

Install dependencies:

```powershell
pnpm install
```

Apply database migrations:

```powershell
pnpm db:migrate
```

Run backend and frontend together:

```powershell
pnpm dev
```

Backend health check:

```text
http://localhost:3000/health
```

Frontend workspace:

```text
http://localhost:5173
```

## Quality Gates

```powershell
pnpm build
pnpm test
pnpm lint
pnpm typecheck
```

Browser acceptance:

```powershell
pnpm e2e
```

`pnpm e2e` starts or reuses:

- API server on `http://127.0.0.1:3000`
- Web server on `http://127.0.0.1:5173`

It runs the cooling fan MVP flow in a real browser:

```text
workspace bootstrap
start mock runtime run
persist AI Draft Batch and Draft Patches
show Draft Review plugin
apply draft
refresh confirmed Working Tree
validate API Push
execute API Push against mock mature FMEA adapter
```

## Current Acceptance Status

The Phase 0-12 MVP baseline is implemented:

- TypeScript pnpm workspace
- NestJS Platform API
- React workspace UI
- shared contracts and plugin SDK packages
- DFMEA plugin MVP
- PostgreSQL schema and migrations through API Push
- mock knowledge provider
- mock runtime provider
- AI Draft apply/reject path
- projection freshness and rebuild path
- API Push mock validate/execute path
- unit, integration, component, and browser E2E coverage

Future product work should start from a new task and should not expand this MVP baseline without an explicit scope decision.
