---
globs: extensions/**
---
# Extension Rules

- Structure: each PRJ-* extension follows portable pattern
- Required: manifest.json (schema, policy, ops, intake, cockpit, tests)
- Opt-in context integration: `context_integration.enabled: true` in manifest
- Extension decisions namespaced: `ext:<extension_id>:<key>`
- Outputs: `outputs.workspace_reports` defines report paths
- Extensions must not depend on other extensions directly
- All extensions subject to core gate constraints
- Test: at least 1 contract test per extension
