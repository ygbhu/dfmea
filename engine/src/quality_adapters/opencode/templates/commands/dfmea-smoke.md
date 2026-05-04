---
description: Run an isolated DFMEA smoke workflow
---

Run an isolated DFMEA smoke workflow under `.run/` without touching real project data.

On Windows PowerShell:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$workspace = ".run\opencode-dfmea-smoke-$stamp"
$project = "smoke-dfmea"
$runner = if (Test-Path ".\scripts\quality_cli.py") { "python .\scripts\quality_cli.py" } else { "" }

if ($runner) {
  python .\scripts\quality_cli.py quality workspace init --workspace $workspace
  python .\scripts\quality_cli.py quality project create $project --workspace $workspace
  python .\scripts\quality_cli.py dfmea init --workspace $workspace --project $project
  python .\scripts\quality_cli.py dfmea structure add-system --workspace $workspace --project $project --title "Smoke System"
  python .\scripts\quality_cli.py dfmea structure add-subsystem --workspace $workspace --project $project --parent SYS-001 --title "Smoke Subsystem"
  python .\scripts\quality_cli.py dfmea structure add-component --workspace $workspace --project $project --parent SUB-001 --title "Smoke Component"
  python .\scripts\quality_cli.py dfmea analysis add-function --workspace $workspace --project $project --component COMP-001 --title "Provide smoke function"
  python .\scripts\quality_cli.py dfmea analysis add-failure-chain --workspace $workspace --project $project --function FN-001 --fm-description "Function unavailable" --severity 7 --fe-description "System output lost" --fc-description "Control signal missing" --occurrence 3 --detection 4 --act-description "Add signal diagnostic" --status planned --target-causes 1
  python .\scripts\quality_cli.py dfmea validate --workspace $workspace --project $project
  python .\scripts\quality_cli.py dfmea projection rebuild --workspace $workspace --project $project
  python .\scripts\quality_cli.py dfmea export markdown --workspace $workspace --project $project
} else {
  quality workspace init --workspace $workspace
  quality project create $project --workspace $workspace
  dfmea init --workspace $workspace --project $project
  dfmea structure add-system --workspace $workspace --project $project --title "Smoke System"
  dfmea structure add-subsystem --workspace $workspace --project $project --parent SYS-001 --title "Smoke Subsystem"
  dfmea structure add-component --workspace $workspace --project $project --parent SUB-001 --title "Smoke Component"
  dfmea analysis add-function --workspace $workspace --project $project --component COMP-001 --title "Provide smoke function"
  dfmea analysis add-failure-chain --workspace $workspace --project $project --function FN-001 --fm-description "Function unavailable" --severity 7 --fe-description "System output lost" --fc-description "Control signal missing" --occurrence 3 --detection 4 --act-description "Add signal diagnostic" --status planned --target-causes 1
  dfmea validate --workspace $workspace --project $project
  dfmea projection rebuild --workspace $workspace --project $project
  dfmea export markdown --workspace $workspace --project $project
}
```

Report the workspace path and pass/fail result. Do not delete existing `.run/` directories unless
the user asks for cleanup.
