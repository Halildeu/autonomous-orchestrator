---
globs: schemas/**
---
# Schema Authoring Rules

- Naming: `<domain>.schema.v<N>.json` or `<domain>.schema.json`
- $id format: `urn:ao:<domain>:<version>`
- Required top-level: `$schema`, `$id`, `title`, `description`, `type`, `properties`, `required`
- `additionalProperties: false` by default (fail-closed)
- All enum values must have `description`
- 2-space indent, UTF-8, no trailing whitespace
- Backwards compatibility: never remove required fields, only add optional ones
- Run `python ci/validate_schemas.py` after any change
