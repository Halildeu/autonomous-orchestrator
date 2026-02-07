# Module Kit (v0.1)

This folder is a **template** for adding a new module deterministically.

## What to edit

- `registry_entry.json`: copy into `registry/registry.v1.json` → `modules[]` (also define `allowed_tools`).
- `node_input.schema.json` / `node_output.schema.json`: start schemas for your node I/O contracts.
- `fixture_envelope.json`: a minimal request envelope fixture for your new `intent`.

## Capability / policy guidance

- Prefer Tool Gateway tools (`fs_read`, `fs_write`, `secrets_get`) instead of direct I/O.
- Deny-by-default: only add tools you really need to `allowed_tools`.
- Keep fixtures `dry_run=true` until MOD-B side effects are explicitly reviewed.
