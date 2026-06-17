# Board Governance Managed Repo Rollout v1

Status: ACTIVE
Rollout id: `BOG-12`
Capability id: `GOVERNANCE-BOARD-CAPABILITY-v1`
Product surface: `PRJ-GITHUB-OPS`
Release channel: `0.3.0-rc.1`
Activated: 2026-06-17
Mode: controlled managed-repo standards rollout; live GitHub writes remain gated

## 1. Purpose

This document makes Governance Board Capability v1 consumable by managed
repos through the existing multi-repo standards channel.

It does not replace the repo SSOT, and it does not turn every external repo
into an automatically mutating GitHub ProjectV2 client. It defines the rollout
contract for distributing the governance board operating model, policy,
schema, workflow, and release boundary to registered managed repos.

## 2. Rollout Contract

Managed repo rollout uses the existing standards mechanism:

- source of truth: `standards.lock`
- sync runner: `scripts/sync_managed_repo_standards.py`
- target manifest: `.cache/managed_repos.v1.json`
- default mode: dry-run
- apply mode: explicit `--apply`
- post-apply verification: `--validate-after-sync`
- branch protection probe: live by default, or explicitly reported as
  `UNVERIFIED` with `--skip-branch-live-check`

The sync runner copies the union of `standards.lock.required_files` and
`standards.lock.standard_sources` from the control-plane repo to each managed
target, while preserving target-owned files listed under
`managed_repo_sync.preserve_existing_paths`.

## 3. Distributed Board Governance Package

The managed repo standards package includes these board-governance assets:

- `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
- `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md`
- `docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-PR-TEMPLATE-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-PROJECTION-MANIFEST.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-SYNC-VALIDATION-EVIDENCE.v1.md`
- `schemas/board-projection.schema.v1.json`
- `policies/policy_board_governance.v1.json`
- `.github/workflows/board-pr-merge-evidence.yml`
- `schemas/policy-board-governance.schema.v1.json`

These files make the governance board model visible and enforceable in a
managed repo. They do not grant GitHub token access, auto-create ProjectV2
boards, auto-close issues, or auto-mark work as `Done`.

## 4. Current Registered Target

Current manifest evidence:

- manifest: `.cache/managed_repos.v1.json`
- target count: `1`
- repo root: `/Users/halilkocoglu/Documents/dev`
- repo slug: `dev`
- critical: `true`

The rollout is therefore complete for the registered manifest surface when the
following evidence exists:

1. local standards validation is `OK`
2. managed repo dry-run reports the target and intended file changes
3. managed repo apply runs only against the manifest target
4. apply reports `failed_count=0`
5. apply with validation reports target validation `OK`

## 5. Product Availability Semantics

There are two separate availability layers:

- Product install availability: users running this orchestrator receive the
  `PRJ-GITHUB-OPS` ops surface and Governance Board Capability v1 docs.
- Managed repo standards availability: registered execution repos receive the
  board governance package through `standards.lock` sync.

This distinction is intentional. Product capability can be active while
per-repo live GitHub mutation remains disabled until that repo has explicit
token, board id, accepted digest, and mutation ledger evidence.

## 6. Operator Boundaries

Allowed in this rollout:

- update the board governance standards package in `standards.lock`
- run managed repo dry-run against the manifest target
- run managed repo apply against the manifest target
- run standards validation after apply
- report branch protection as `UNVERIFIED` when live branch probing is
  intentionally skipped

Not allowed in this rollout:

- mutate unregistered repos
- auto-create or backfill every historical board item
- treat board state as repo SSOT
- bypass `project-roadmap` ingestion
- use `Closes #N` as the default PR link
- move work to `Done` without deliberate acceptance evidence
- expose tokens, secrets, or PAT values in logs

## 7. Required Evidence

Minimum closeout evidence for this rollout:

- `python3 ci/check_standards_lock.py`
- `python3 scripts/sync_managed_repo_standards.py --manifest-path .cache/managed_repos.v1.json --skip-branch-live-check`
- `python3 scripts/sync_managed_repo_standards.py --manifest-path .cache/managed_repos.v1.json --apply --validate-after-sync --skip-branch-live-check`
- generated report:
  `.cache/reports/managed_repo_standards_sync/report.v1.json`
- portfolio status showing `managed_repo_standards_status=OK`

## 8. Canonical References

- `AGENTS.md`
- `standards.lock`
- `docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md`
- `extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json`
- `docs/OPERATIONS/product_catalog.v1.json`
