# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | To fill |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | To fill |
| [Error Handling](./error-handling.md) | Error types, handling strategies | To fill |
| [Platform API Guidelines](./platform-api-guidelines.md) | REST/SSE endpoints, envelopes, and API tests | Active |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | To fill |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | To fill |

---

## Pre-Development Checklist

- For Platform API or SSE changes, read [Platform API Guidelines](./platform-api-guidelines.md).
- For repository or migration changes, read [Database Guidelines](./database-guidelines.md).
- For API error behavior, read [Error Handling](./error-handling.md) and the error matrix in Platform API Guidelines.

## Quality Check

- Run `pnpm lint`.
- Run `pnpm test`.
- Run `pnpm typecheck`.
- If API contracts changed, update [Platform API Guidelines](./platform-api-guidelines.md) and `/api/openapi.json`.

## How to Fill These Guidelines

For each guideline file:

1. Document your project's **actual conventions** (not ideals)
2. Include **code examples** from your codebase
3. List **forbidden patterns** and why
4. Add **common mistakes** your team has made

The goal is to help AI assistants and new team members understand how YOUR project works.

---

**Language**: All documentation should be written in **English**.
