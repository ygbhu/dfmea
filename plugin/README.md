# OpenCode Quality Assistant Plugin

This package is the OpenCode-facing product entrypoint. OpenCode is the required host; the Python
quality engine remains responsible for workspace files, DFMEA logic, validation, projections, and
exports.

## Local Development

From the repository root:

```powershell
node .\plugin\bin\opencode-quality.js doctor
node .\plugin\bin\opencode-quality.js init --workspace .
opencode serve --cors http://localhost:5173
```

The CLI prefers the source checkout runner at `scripts/quality_cli.py`. In installed usage it falls
back to `quality` and `dfmea` console scripts from the Python package. `init` writes npm-style
`opencode.json`; for source checkout development, `quality opencode init` can install local
`.opencode/plugins/*.js` without requiring the npm package to be published.

## OpenCode Config

For npm-installed usage, OpenCode can load this package through `opencode.json`:

```json
{
  "plugin": ["opencode-quality-assistant"]
}
```
