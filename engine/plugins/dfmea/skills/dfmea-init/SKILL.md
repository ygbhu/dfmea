---
name: dfmea-init
description: Initialize a local-first quality workspace, project, and DFMEA domain files.
---

# DFMEA Initialization Skill

Use this when bootstrapping a new local-first DFMEA project.

## Commands

```bash
quality workspace init --workspace <workspace-root>
quality project create <project-slug> --workspace <workspace-root> --name "<project name>"
dfmea init --workspace <workspace-root> --project <project-slug>
```

## Outputs Created

- Workspace config: `.quality/workspace.yaml` and `.quality/plugins.yaml`.
- Project config: `projects/<slug>/project.yaml`.
- Project state directories: `.quality/schemas`, `.quality/tombstones`, `.quality/locks`.
- DFMEA domain root: `projects/<slug>/dfmea/dfmea.yaml`.
- DFMEA source directories for structure, functions, requirements, characteristics, failure modes, effects, causes, and actions.

## Example

```bash
quality workspace init --workspace .
quality project create cooling-fan-controller --workspace . --name "Cooling Fan Controller"
dfmea init --workspace . --project cooling-fan-controller
quality project status --workspace . --project cooling-fan-controller
```

## Checklist

1. Choose a lowercase project slug such as `cooling-fan-controller`.
2. Initialize the workspace if `.quality/workspace.yaml` is missing.
3. Create the project with `quality project create`.
4. Initialize DFMEA with `dfmea init`.
5. Commit the baseline with `quality project snapshot --project <slug> --message "<message>"`.
