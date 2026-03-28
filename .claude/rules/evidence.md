# Evidence Rules

- Every side-effect (state write, policy decision, approval request) MUST produce an evidence trace
- Evidence path convention: `.cache/reports/<artifact_type>_evidence.v1.jsonl` (append-only JSONL)
- Evidence record must include: `timestamp`, `operation`, `actor` (agent_id), `before`, `after`, `status`
- Use `src.shared.utils.write_json_atomic` for evidence file writes — never raw `open()`
- Secrets must NEVER appear in evidence records — scrub before writing
- Evidence is workspace-scoped (L2): never write evidence to core repo paths (L0)
- Approval requests: written to `.cache/reports/approval_inbox.v1.jsonl` per `policy_human_approval_request.v1.json`
- Quality gate results: summarised via `src.orchestrator.quality_gate.quality_gate_summary()` before recording
- Evidence refs must be included in context pack `evidence_refs` array (pointer schema)
- CI contract tests validate evidence output format — update tests when adding new evidence types
