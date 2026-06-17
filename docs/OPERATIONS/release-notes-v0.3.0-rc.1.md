# v0.3.0-rc.1 Release Notes

Release channel: internal RC
Date: 2026-06-17

## Highlights

- Governance Board Capability v1 is active under `PRJ-GITHUB-OPS`.
- The core repo now has a live GitHub ProjectV2 governance board at
  `https://github.com/users/Halildeu/projects/5`.
- Board-visible work uses `project-roadmap` ingestion, `Tracked by #N` PR
  relation, `Needs Verify` acceptance queue, and deliberate `Done` plus issue
  close.
- Live projection and sync validation are available through program-led ops:
  `board-projection-live`, `board-metadata-live`, and `board-sync`.
- Managed repo rollout is active as a controlled standards package through
  `standards.lock` and `BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`.
- Issue `#78` completed the full acceptance path and is the live proof for the
  capability.

## Product Surface

- Product catalog module: `PRJ-GITHUB-OPS`
- Capability doc:
  `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- Managed repo rollout doc:
  `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
- Extension manifest:
  `extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json`
- Primary docs:
  `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`,
  `docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md`

## Boundaries

This RC does not mean:

- unregistered repos have received the managed repo rollout
- historical backlog import is complete
- ungated live ProjectV2 mutation is enabled
- board state replaces repo SSOT

Live writes remain gated by explicit confirmation, token boundary, target board
id, accepted digest, and mutation ledger.

## Acceptance Evidence

- `#78` final closure:
  `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4727550151`
- PR `#79` merge evidence:
  `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725492674`
- Product capability doc:
  `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- Managed repo rollout contract:
  `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
