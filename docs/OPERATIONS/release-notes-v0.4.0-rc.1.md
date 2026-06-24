# v0.4.0-rc.1 Release Notes

Release channel: internal RC
Date: 2026-06-24

## Highlights

- PRJ-AIRUNNER now has an explicit board/governance and GitHub ops
  implementation boundary.
- Airunner consumes Governance Board Capability v1 in fail-closed
  `report_only` mode by default.
- Dispatch plans attach `boundary_decision` evidence for board/governance and
  GitHub ops candidates.
- Board/governance manual requests remain plan-only unless a separate live
  boundary is opened.
- GitHub queued/running jobs keep priority over internal Airunner jobs.
- Live GitHub and ProjectV2 mutation remain disabled by default.

## Product Surface

- Product module: `PRJ-AIRUNNER`
- Consumed capability: `PRJ-GITHUB-OPS`
- Boundary doc:
  `docs/OPERATIONS/AIRUNNER-BOARD-GITHUB-OPS-BOUNDARY.v1.md`
- Capability doc:
  `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- Policy surface:
  `policies/policy_airunner.v1.json`,
  `policies/policy_auto_mode.v1.json`,
  `policies/policy_release_automation.v1.json`

## Boundaries

This RC does not enable:

- live GitHub mutation
- live ProjectV2 apply
- issue close or `Done` automation
- label mutation
- unregistered target mutation

Live apply still requires accepted digest, explicit target board id, explicit
operator confirmation, token environment, and per-target gate evidence.

## Acceptance Evidence

- PR `#83` merged to `main`:
  `https://github.com/Halildeu/autonomous-orchestrator/pull/83`
- Main commit:
  `d1254d70dad87eb19b008ecd267a3f93d150d951`
- Main CI:
  `21/21 success`
- Manual request closeout:
  `completed_by_PR_83_main_d1254d70_CI_21_of_21_success`
- Boundary contract test:
  `src/prj_airunner/airrunner_board_github_boundary_contract_test.py`

## Does Not Prove

This RC does not prove that every managed repository has adopted the capability,
that live GitHub writes are enabled, or that local `.git` metadata in every
workspace is clean. It proves the product boundary and release-channel metadata
for the current control-plane repo.
