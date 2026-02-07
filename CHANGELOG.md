# Changelog



## [1.0.0] - 2026-01-01
- Deterministic orchestrator core (`schemas/`, `policies/`, `ci/`, fail-closed)
- Evidence pack: provenance + integrity verify + export zip
- Ops tooling: manage CLI (runs/dlq/suspends), reaper retention, runbook
- Policy workflow: policy-check + policy diff sim + Markdown report + policy editor
- Workflows: policy review (`urn:core:docs:policy_review`) + DLQ triage (`urn:core:ops:dlq_triage`)
- Side-effects: PR creation (integration-only, gated); merge/deploy intentionally blocked (SSOT manifest)
- Packaging: `pyproject.toml` + `orchestrator` CLI + Python SDK
- Supply-chain: SBOM/sign/verify + license/CVE gates

## [0.1.2] - 2026-01-01
- Add DLQ triage workflow intent (`urn:core:ops:dlq_triage`)
- Add `MOD_DLQ_TRIAGE` module (deterministic Markdown report from `dlq/*.json`)
- CLI example: `python -m src.cli run --intent urn:core:ops:dlq_triage ...`

## [0.1.1] - 2026-01-01
- Add policy review workflow intent (`urn:core:docs:policy_review`)
- Add CLI shortcut (`python -m src.cli run --intent ...`)

## [0.1.0] - 2025-12-31
- Initial public skeleton: control plane, evidence, gates, ops CLI, SDK, packaging
