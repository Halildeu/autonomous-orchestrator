# v0.1.2 Release Notes

Release date: **2026-01-01**

## Highlights

From `CHANGELOG.md`:

- Add DLQ triage workflow intent (`urn:core:ops:dlq_triage`)
- Add `MOD_DLQ_TRIAGE` module (deterministic Markdown report from `dlq/*.json`)
- CLI example: `python -m src.cli run --intent urn:core:ops:dlq_triage ...`

## Install & Quick Start (copy-paste)

From repo root:

```bash
# Dry-run DLQ triage report (safe: no file write; evidence records would_write)
python -m src.cli run \
  --intent urn:core:ops:dlq_triage \
  --tenant TENANT-LOCAL \
  --dry-run true \
  --output-path dlq_triage.md
```

Expected behavior:
- Prints a JSON summary including `run_id` and `evidence_path`.
- Generates evidence under `evidence/<run_id>/`.
- Because `dry_run=true`, it does **not** create `dlq_triage.md`; the planned write is recorded as `would_write` in evidence (node outputs).

