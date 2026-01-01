# v0.1.1 Release Notes

Release date: **2026-01-01**

## Highlights

From `CHANGELOG.md`:

- Add policy review workflow intent (`urn:core:docs:policy_review`)
- Add CLI shortcut (`python -m src.cli run --intent ...`)

## Install & Quick Start (copy-paste)

From repo root:

```bash
# Dry-run policy review report (safe: no file write; evidence records would_write)
python -m src.cli run \
  --intent urn:core:docs:policy_review \
  --tenant TENANT-LOCAL \
  --dry-run true \
  --output-path policy_review.md
```

Expected behavior:
- Prints a JSON summary including `run_id` and `evidence_path`.
- Generates evidence under `evidence/<run_id>/`.
- Because `dry_run=true`, it does **not** create `policy_review.md`; the planned write is recorded as `would_write` in evidence (node outputs).

