# Frontend Development Guidelines

> Best practices for frontend development in this project.

---

## Overview

This directory contains guidelines for frontend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | To fill |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | To fill |
| [Hook Guidelines](./hook-guidelines.md) | Custom hooks, data fetching patterns | To fill |
| [State Management](./state-management.md) | Local state, global state, server state | To fill |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | To fill |
| [Type Safety](./type-safety.md) | Type patterns, validation | To fill |
| [Workspace UI Guidelines](./workspace-ui-guidelines.md) | Workspace data flow, API client, SSE, tree adapters | Active |

---

## Pre-Development Checklist

- For Workspace UI changes, read [Workspace UI Guidelines](./workspace-ui-guidelines.md).
- For component-only changes, read [Component Guidelines](./component-guidelines.md).
- For hook/state/data fetching changes, read [Hook Guidelines](./hook-guidelines.md) and [State Management](./state-management.md).

## Quality Check

- Run `pnpm lint`.
- Run `pnpm test`.
- Run `pnpm typecheck`.
- If UI/API data contracts change, update [Workspace UI Guidelines](./workspace-ui-guidelines.md).

## How to Fill These Guidelines

For each guideline file:

1. Document your project's **actual conventions** (not ideals)
2. Include **code examples** from your codebase
3. List **forbidden patterns** and why
4. Add **common mistakes** your team has made

The goal is to help AI assistants and new team members understand how YOUR project works.

---

**Language**: All documentation should be written in **English**.
