# v0.4.0-rc.2 Release Notes

Release channel: internal RC
Date: 2026-06-24

## Highlights

- Clean RC transition for the Airunner Board/GitHub Ops Boundary line.
- Includes the `v0.4.0-rc.1` release metadata and the follow-up board merge
  evidence workflow bootstrap fix.
- Release automation now supports an explicit `rc_number` policy field, so
  `release-check --channel rc` can produce the active RC sequence instead of a
  hard-coded `rc.1`.
- The current Governance Board Capability release channel is `0.4.0-rc.2`.

## Product Surface

- Product module: `PRJ-AIRUNNER`
- Consumed capability: `PRJ-GITHUB-OPS`
- Capability doc:
  `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- Managed repo rollout doc:
  `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
- Policy surface:
  `policies/policy_release_automation.v1.json`
- Release automation source:
  `src/prj_release_automation/release_engine.py`

## Included Since rc.1

- Release metadata PR `#84` published `v0.4.0-rc.1`.
- Board merge evidence workflow remediation PR `#85` added workspace bootstrap
  before `board-pr-merge`.
- Current RC metadata declares `rc_number: 2` and keeps network publishing
  disabled by default.

## Boundaries

This RC does not enable:

- automatic network publish
- live GitHub mutation outside explicit operator action
- live ProjectV2 apply
- issue close or `Done` automation
- unregistered target mutation

Live apply still requires accepted digest, explicit target board id, explicit
operator confirmation, token environment, and per-target gate evidence.

## Acceptance Evidence

- `release-check --channel rc` must return `release_version=0.4.0-rc.2`.
- Release contract test must pass, including `rc_number` to `rc_version`
  suffix alignment.
- Schema validation and policy-check must pass before publication.
- Main branch CI must be green on the release tag target commit.
- Board PR Merge Evidence workflow must complete successfully after the
  workflow bootstrap fix.

## Does Not Prove

This RC does not prove that every managed repository has adopted the
capability, that live GitHub writes are enabled, or that local `.git` metadata
in every workspace is clean. It proves the clean RC control-plane transition
and release-channel metadata for the current repo.
