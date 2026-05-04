---
name: finish-work
description: "Pre-commit quality checklist for the Python local-first quality assistant. Runs pytest, ruff, compileall, verifies docs/spec sync, and checks that retired TypeScript/DB paths were not restored. Use when code is written and tested but not yet committed, before submitting changes, or as a final review before git commit."
---

# Finish Work - Pre-Commit Checklist

Before submitting or committing, use this checklist to ensure work completeness.

**Timing**: After code is written and tested, before commit

---

## Checklist

### 1. Code Quality

```bash
# Must pass
python -m pytest
python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_methods tests
python -m compileall -q src tests
```

- [ ] `python -m pytest` passes?
- [ ] `python -m ruff check ...` passes?
- [ ] `python -m compileall -q src tests` passes?
- [ ] Tests pass?
- [ ] No restored `dfmea_cli.services`, SQLite source-of-truth code, TypeScript platform, or
  PostgreSQL infrastructure?

### 2. Code-Spec Sync

**Code-Spec Docs**:
- [ ] Does `.trellis/spec/backend/` need updates?
  - New patterns, new modules, new conventions
- [ ] Does `.trellis/spec/guides/` need updates?
  - New cross-layer flows, lessons from bugs

**Key Question**: 
> "If I fixed a bug or discovered something non-obvious, should I document it so future me (or others) won't hit the same issue?"

If YES -> Update the relevant code-spec doc.

### 2.5. Code-Spec Hard Block (Infra/Cross-Layer)

If this change touches infra or cross-layer contracts, this is a blocking checklist:

- [ ] Spec content is executable (real signatures/contracts), not principle-only text
- [ ] Includes file path + command/API name + payload field names
- [ ] Includes validation and error matrix
- [ ] Includes Good/Base/Bad cases
- [ ] Includes required tests and assertion points

**Block Rule**:
If infra/cross-layer changed but the related spec is still abstract, do NOT finish. Run `$update-spec` manually first.

### 3. CLI Contract Changes

If you modified CLI command inputs or outputs:

- [ ] Input schema updated?
- [ ] Output schema updated?
- [ ] Error handling/spec docs updated?
- [ ] Agent skill examples updated?

### 4. Retired Architecture Guard

These are blockers:

- [ ] No SQLite/PostgreSQL target storage was added.
- [ ] No `apps/api`, `apps/web`, `packages/*`, or old plugin SDK code was restored.
- [ ] No unintegrated UI write path was added.

### 5. Cross-Layer Verification

If the change spans multiple layers:

- [ ] Data flows correctly through all layers?
- [ ] Error handling works at each boundary?
- [ ] Resource envelope, schema, validator, command output, and tests are consistent?

### 6. Manual Testing

- [ ] CLI command works with `--workspace` and `--project` where applicable?
- [ ] Edge cases tested?
- [ ] Error states tested?
- [ ] Generated projections/exports are treated as rebuildable output, not source?

---

## Quick Check Flow

```bash
# 1. Code checks
python -m pytest
python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_methods tests
python -m compileall -q src tests

# 2. View changes
git status
git diff --name-only

# 3. Based on changed files, check relevant items above
```

---

## Common Oversights

| Oversight | Consequence | Check |
|-----------|-------------|-------|
| Code-spec docs not updated | Others don't know the change | Check .trellis/spec/ |
| Spec text is abstract only | Easy regressions in infra/cross-layer changes | Require signature/contract/matrix/cases/tests |
| Retired architecture restored | Project direction drifts | Search for old TS/DB paths |
| CLI contract docs stale | Agents call wrong commands | Check docs and skills |
| Tests not updated | False confidence | Run full test suite |
| Generated files edited as source | Bad Git history | Check managed project paths |

---

## Relationship to Other Commands

```
Development Flow:
  Write code -> Test -> $finish-work -> git commit -> $record-session
                          |                              |
                   Ensure completeness              Record progress
                   
Debug Flow:
  Hit bug -> Fix -> $break-loop -> Knowledge capture
                       |
                  Deep analysis
```

- `$finish-work` - Check work completeness (this skill)
- `$record-session` - Record session and commits
- `$break-loop` - Deep analysis after debugging

---

## Core Principle

> **Delivery includes not just code, but also documentation, verification, and knowledge capture.**

Complete work = Code + Docs + Tests + Verification
