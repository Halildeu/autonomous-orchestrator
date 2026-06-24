# Airunner Board/GitHub Ops Boundary v1

Status: ACTIVE
Boundary id: `AIRUNNER-BOARD-GITHUB-OPS-BOUNDARY-v1`
Product surface: `PRJ-AIRUNNER` consuming `PRJ-GITHUB-OPS`
Default mode: `report_only`

## Purpose

This boundary defines how Airunner may orchestrate the Governance Board
Capability and GitHub operations without turning autonomous mode into an
unreviewed live GitHub writer.

Airunner is allowed to observe, route, report, and start dry-run/report-only
GitHub ops jobs. It is not allowed to autonomously apply ProjectV2 changes,
close issues, move issues to `Done`, mutate labels, merge PRs without explicit
tracked evidence, or mutate unregistered targets.

## Default Contract

The default contract is fail-closed:

- board governance operations run as projection/report-only unless a live apply
  boundary is explicitly opened
- GitHub ops jobs are dry-run/report-only unless both Airunner network live
  decision and GitHub ops live gate are enabled
- live apply requires accepted digest, explicit target board id, explicit
  operator confirmation, token environment, and per-target gate evidence
- `Needs Verify` remains the acceptance queue
- `Done` and issue close remain deliberate acceptance actions, not automatic
  side effects of PR merge or job success

## Policy Surface

The boundary is encoded in:

- `policies/policy_airunner.v1.json`
- `policies/policy_auto_mode.v1.json`
- `schemas/policy-airunner.schema.v1.json`
- `schemas/policy-auto-mode.schema.v1.json`

Required policy fields:

- `enabled`
- `default_mode`
- `allow_autonomous_board_apply`
- `allow_autonomous_github_mutation`
- `require_operator_approval_for_live`
- `require_github_ops_live_gate`
- `require_network_live_decision`
- `allowed_report_only_ops`
- `forbidden_autonomous_actions`
- `required_evidence_fields`

## Runtime Evidence

Airunner dispatch plans attach a `boundary_decision` object to board/governance
and GitHub ops candidates. The evidence must include:

- `boundary_id`
- `mode`
- `autonomous_mutation_allowed`
- `dry_run_required`
- `requires_operator_approval`
- `requires_github_ops_live_gate`
- `requires_network_live_decision`
- `blocked_reasons`
- `does_not_prove`

This makes the boundary visible to status reports, doer/actionability reports,
and proof bundles without requiring live GitHub mutation.

## Allowed Report-Only Operations

Airunner may route or request these operations in report-only/dry-run mode:

- `board-live-probe`
- `board-projection-live`
- `board-metadata-live`
- `board-sync`
- `github-ops-check`
- `github-ops-job-poll`
- `github-ops-job-start`

`board-sync` is only safe here when run as dry-run or when an external live
apply gate has already produced accepted digest and explicit target evidence.

## Forbidden Autonomous Actions

Airunner must not autonomously perform:

- `issue_close`
- `done_transition`
- `projectv2_apply`
- `label_mutation`
- `pr_merge_without_tracked_by`
- `unregistered_repo_mutation`

These actions require a separate operator-approved live path.

## Acceptance Criteria

This boundary is accepted when:

- policy files carry the boundary contract
- policy schemas reject unknown or incomplete boundary shape
- dispatch output includes `boundary_decision` for `PRJ-GITHUB-OPS`
  candidates
- board/governance manual requests remain plan-only unless an explicit live
  boundary is opened
- live mutation remains blocked by missing Airunner network live decision and
  GitHub ops live gate
- contract tests prove the report-only boundary and forbidden actions

## Does Not Prove

This boundary does not prove:

- live GitHub mutation is enabled
- operator approval has been granted
- a ProjectV2 apply is authorized
- issue close or `Done` transition is authorized
- every managed repository has received the board governance rollout
- future GitHub ProjectV2 drift cannot recur

## References

- `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
- `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`
- `docs/OPERATIONS/BOARD-PROJECTION-MANIFEST.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-SYNC-VALIDATION-EVIDENCE.v1.md`
- `policies/policy_github_ops.v1.json`
- `src/prj_airunner/auto_mode_dispatch.py`
