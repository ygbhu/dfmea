---
name: dfmea-structure
description: Manage DFMEA structure hierarchy resources: SYS, SUB, and COMP.
---

# DFMEA Structure Skill

Manage `SYS`, `SUB`, and `COMP` source resources through the CLI.

## Commands

### Add

```bash
dfmea structure add-system --workspace . --project cooling-fan-controller --title "Fan Controller"
dfmea structure add-subsystem --workspace . --project cooling-fan-controller --parent SYS-001 --title "Motor Control"
dfmea structure add-component --workspace . --project cooling-fan-controller --parent SUB-001 --title "Motor Driver"
```

Generic compatibility form:

```bash
dfmea structure add --project cooling-fan-controller --type COMP --parent SUB-001 --title "Motor Driver"
```

### Update, Move, Delete

```bash
dfmea structure update --project cooling-fan-controller --node COMP-001 --title "Motor Driver Assembly"
dfmea structure move --project cooling-fan-controller --node COMP-001 --parent SUB-002
dfmea structure delete --project cooling-fan-controller --node COMP-001
```

## Hierarchy

- `SYS` has no parent.
- `SUB` must have a `SYS-*` parent.
- `COMP` must have a `SUB-*` parent.
- Deleting a structure node requires no children. Delete creates `.quality/tombstones/<ID>`.

## Agent Practice

- Use project-local IDs, not rowids.
- Check existing structure with `dfmea query map --project <slug>`.
- Validate after structural edits: `dfmea validate --project <slug>`.
- Snapshot reviewed changes with `quality project snapshot --project <slug> --message "<message>"`.
