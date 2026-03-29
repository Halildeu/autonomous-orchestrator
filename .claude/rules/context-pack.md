# Context Pack Rules

- Profile resolution FIRST: check `policies/policy_context_profile_registry.v1.json` before loading any context
- Active profile artifact: `.cache/index/active_context_profile.v1.json` (schema: `active-context-profile.schema.v1.json`)
- Load only sections listed in the active profile's `required` + `optional` — never load `forbidden` sections
- `task_scope_hints` on TASK_EXECUTION profile narrow `required_files` dynamically — respect them
- Context pack size limit: `max_context_pack_bytes` from `policy_context_orchestration.v1.json` (default 65536)
- All context pack outputs validated against `schemas/context-pack.schema.v1.json`
- Router results validated against `schemas/context-pack-router-result.schema.v1.json`
- Merge operations use `schemas/context-pack-merge.schema.v1.json`
- No network calls in context pack building — offline-first, workspace-bound sources only
- Evidence: context pack creation writes trace to `.cache/reports/context_orchestration_status.v1.json`
