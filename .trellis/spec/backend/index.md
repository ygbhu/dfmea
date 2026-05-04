# Python Core Development Guidelines

> Project-specific guidelines for the local-first Python CLI/core implementation.

---

## Overview

This directory contains the active implementation guidelines for the Python local-first quality
assistant. The retired TypeScript platform API, frontend, and database guideline layers are no
longer part of this project architecture.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Active |
| [Error Handling](./error-handling.md) | Error types and CLI response contracts | Active |

---

## Pre-Development Checklist

- For `quality` or `dfmea` CLI changes, read [Directory Structure](./directory-structure.md)
  and [Error Handling](./error-handling.md).
- For workspace, project, plugin, resource, validation, projection, export, or Git behavior, keep
  implementation under `quality_core` or the relevant `quality_methods.<domain>` package.
- Do not restore SQLite/PostgreSQL storage, the old TypeScript platform API, or an independent UI
  write path.

## Quality Check

- Run `python -m pytest`.
- Run `python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_methods tests`.
- Run `python -m compileall -q src tests`.
- If CLI contracts changed, update [Error Handling](./error-handling.md) and the relevant canonical
  design/development document.

**Language**: All documentation should be written in **English**.
