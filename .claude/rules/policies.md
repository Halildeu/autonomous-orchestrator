---
globs: policies/**
---
# Policy Authoring Rules

- Naming: `policy_<domain>.v<N>.json`
- Must reference a valid schema via `$schema` or `schema_ref`
- All policy files validated against their schema on CI
- Deterministic: no randomness, no external state dependency
- Guardrails: define `fail_action` (block/warn/log) for each rule
- Dry-run support: all policies must work with `report_only: true`
- Test: `python ci/policy_dry_run.py --fixtures fixtures/envelopes`
