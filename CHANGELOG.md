# Changelog


## [0.1.2] - 2026-01-01
- Add DLQ triage workflow intent (`urn:core:ops:dlq_triage`)
- Add `MOD_DLQ_TRIAGE` module (deterministic Markdown report from `dlq/*.json`)
- CLI example: `python -m src.cli run --intent urn:core:ops:dlq_triage ...`

## [0.1.1] - 2026-01-01
- Add policy review workflow intent (`urn:core:docs:policy_review`)
- Add CLI shortcut (`python -m src.cli run --intent ...`)

## [0.1.0] - 2025-12-31
- Initial public skeleton: control plane, evidence, gates, ops CLI, SDK, packaging
