# Failure Chain Input Schema

`dfmea analysis add-failure-chain --input <json-file>` reads a JSON object that creates one
`FailureMode` and optional `FailureEffect`, `FailureCause`, and `Action` resources under a function.

## JSON Shape

```json
{
  "fm": {
    "description": "Motor stalls",
    "severity": 8,
    "requirementRefs": ["REQ-001"],
    "characteristicRefs": ["CHAR-001"]
  },
  "fe": [
    {
      "description": "Airflow lost",
      "level": "vehicle"
    }
  ],
  "fc": [
    {
      "description": "Bearing seizure",
      "occurrence": 4,
      "detection": 5,
      "ap": "High"
    }
  ],
  "act": [
    {
      "description": "Add current spike detection",
      "kind": "detection",
      "status": "planned",
      "owner": "quality",
      "due": "2026-06-01",
      "targetCauseIndexes": [1]
    }
  ]
}
```

Compatibility keys from older JSON payloads may still be accepted by the service in limited cases,
but new Agent-authored files should use the camelCase fields above.

## Field Notes

- `fm.description` and `fm.severity` are required.
- `requirementRefs` and `characteristicRefs` use project-local resource IDs such as `REQ-001` and
  `CHAR-001`.
- `fc.ap` may be omitted to let the CLI compute AP from severity, occurrence, and detection.
- `act.targetCauseIndexes` uses 1-based indexes into the `fc` array in the same request. It does not
  use persisted FC IDs because those IDs are allocated during creation.

## Repeated Flag Mode

```bash
dfmea analysis add-failure-chain --project cooling-fan-controller --function FN-001 \
  --fm-description "Motor overheats" --severity 8 \
  --requirement REQ-001 --characteristic CHAR-001 \
  --fe-description "System shutdown" --fe-level "vehicle" \
  --fc-description "Bearing wear" --occurrence 4 --detection 6 --ap High \
  --act-description "Add temperature sensor" --kind prevention --target-causes "1"
```

`--input` and repeated creation flags are mutually exclusive.
