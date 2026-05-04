---
name: dfmea-analysis
description: Manage DFMEA functions, requirements, characteristics, failure chains, risk fields, actions, and analysis-node deletion.
---

# DFMEA Analysis Skill

Use project-local YAML resources and stable IDs. Do not use rowids or database paths.

## Function, Requirement, Characteristic

```bash
dfmea analysis add-function --project cooling-fan-controller --component COMP-001 --title "Drive fan motor"
dfmea analysis update-function --project cooling-fan-controller --function FN-001 --title "Drive fan motor safely"
dfmea analysis delete-function --project cooling-fan-controller --function FN-001

dfmea analysis add-requirement --project cooling-fan-controller --function FN-001 --text "Maintain airflow"
dfmea analysis update-requirement --project cooling-fan-controller --requirement REQ-001 --text "Maintain required airflow"
dfmea analysis delete-requirement --project cooling-fan-controller --requirement REQ-001

dfmea analysis add-characteristic --project cooling-fan-controller --function FN-001 --text "Motor current" --value "2.0" --unit A
dfmea analysis update-characteristic --project cooling-fan-controller --characteristic CHAR-001 --value "2.2"
dfmea analysis delete-characteristic --project cooling-fan-controller --characteristic CHAR-001
```

## Failure Modes And Failure Chains

```bash
dfmea analysis add-failure-mode --project cooling-fan-controller --function FN-001 --title "Motor stalls" --severity 8

dfmea analysis add-failure-chain \
  --project cooling-fan-controller \
  --function FN-001 \
  --fm-description "Motor stalls" \
  --severity 8 \
  --fe-description "Airflow lost" \
  --fc-description "Bearing seizure" \
  --occurrence 4 \
  --detection 5 \
  --act-description "Add current spike detection" \
  --status planned \
  --target-causes 1
```

For complex chains, use `--input <json-file>` and follow `dfmea/failure-chain-schema.md`.

## Risk And Action Updates

```bash
dfmea analysis update-risk --project cooling-fan-controller --failure-mode FM-001 --severity 9
dfmea analysis update-fm --project cooling-fan-controller --failure-mode FM-001 --title "Motor intermittently stalls"
dfmea analysis update-fc --project cooling-fan-controller --failure-cause FC-001 --occurrence 3 --detection 4
dfmea analysis update-act --project cooling-fan-controller --action ACT-001 --owner alice --due 2026-06-01
dfmea analysis update-action-status --project cooling-fan-controller --action ACT-001 --status in-progress
```

Allowed action statuses are `planned`, `in-progress`, and `completed`.

## Links And Delete

```bash
dfmea analysis link-fm-requirement --project cooling-fan-controller --failure-mode FM-001 --requirement REQ-001
dfmea analysis link-fm-characteristic --project cooling-fan-controller --failure-mode FM-001 --characteristic CHAR-001
dfmea analysis delete-node --project cooling-fan-controller --node FM-001
```

Deletes create tombstones for deleted IDs. Tombstones are committed by `quality project snapshot`.

## Agent Practice

- Start from the target `COMP-*` or `FN-*` scope.
- Use `dfmea query get/list/search` to confirm IDs before mutating.
- Let the CLI allocate IDs and update same-chain references.
- Run `dfmea validate --project <slug>` and `quality project status --project <slug>` before snapshot.
