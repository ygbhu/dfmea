# OpenChamber DFMEA Fork Integration

This repository now uses OpenChamber as the base UI shell.

DFMEA-specific behavior should be added with minimal invasion through:

- project-scoped config in `packages/ui/src/lib/openchamberConfig.ts`
- project actions and settings surfaces in `packages/ui/src/components/sections/projects/*`
- runtime adapters in `packages/web/src/api/*`
- backend endpoints in `packages/web/server/index.js`
- DFMEA domain package in `packages/dfmea`
