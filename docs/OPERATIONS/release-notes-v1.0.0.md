# v1.0.0 Release Notes

Release date: **2026-01-01**

## Highlights

From `CHANGELOG.md`:

- Deterministic orchestrator core (schemas/policies/gates, fail-closed)
- Evidence pack: provenance + integrity verify + export zip
- Ops tooling: manage CLI (runs/dlq/suspends), reaper retention, runbook
- Policy workflow: policy-check + policy diff sim + Markdown report + policy editor
- Workflows: policy review (`urn:core:docs:policy_review`) + DLQ triage (`urn:core:ops:dlq_triage`)
- Side-effects: PR creation (integration-only, gated); merge/deploy intentionally blocked (SSOT manifest)
- Packaging: `pyproject.toml` + `orchestrator` CLI + Python SDK
- Supply-chain: SBOM/sign/verify + license/CVE gates

## Install & Quick Start (copy-paste)

From repo root:

```bash
# Policy review report (safe: no file write; evidence records would_write)
python -m src.cli run \
  --intent urn:core:docs:policy_review \
  --tenant TENANT-LOCAL \
  --dry-run true \
  --output-path policy_review.md

# DLQ triage report (safe: no file write; evidence records would_write)
python -m src.cli run \
  --intent urn:core:ops:dlq_triage \
  --tenant TENANT-LOCAL \
  --dry-run true \
  --output-path dlq_triage.md

# Ops: list recent runs
python -m src.ops.manage runs --limit 5
```

Expected behavior (high level):
- CLI prints a JSON summary including `run_id` and `evidence_path`.
- Evidence is written under `evidence/<run_id>/`.
- Because `dry_run=true`, the output files (`policy_review.md`, `dlq_triage.md`) are **not** created; the planned write is recorded as `would_write` in evidence (node outputs).

## PR side-effect (integration-only, gated)

GitHub PR creation is supported as a controlled side effect, but is **integration-only** by default:
- No real HTTP happens unless explicitly enabled.
- Do not include secrets in any docs or logs.

How to enable safely (manual steps) is documented in:
- `docs/OPERATIONS/side-effects.md`
- `docs/OPERATIONS/runbook-day1.md` (“GitHub PR side effect” section)

