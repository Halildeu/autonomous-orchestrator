# Governance Board Capability v1

Status: ACTIVE
Capability id: `GOVERNANCE-BOARD-CAPABILITY-v1`
Product surface: `PRJ-GITHUB-OPS`
Release channel: `0.3.0-rc.1`
Activated: 2026-06-17
Mode: product capability; live writes remain digest, target, confirmation, and token gated

## 1. Purpose

This capability turns the board governance model into a versioned product
feature instead of a repo-local practice.

It gives the product a governed GitHub ProjectV2 operating path for work that
needs cross-session visibility, source-ready verification, and deliberate
acceptance.

## 2. Product Contract

The capability provides:

- curated board ingestion through the `project-roadmap` label
- a minimal board field contract: `Status`, `Faz`, `Track`, `Priority`, `Kind`
- PR linkage through `Tracked by #N` for runtime, GitOps, governance, and
  acceptance work
- `Needs Verify` as the source-ready acceptance queue
- deliberate `Done` and issue close only after acceptance evidence
- live projection and drift detection from GitHub issue and ProjectV2 inventory
- operator-bound sync through accepted projection digest and explicit target
  board id
- append-only issue evidence for source, runtime/live, and final acceptance

The capability does not make the board the source of truth. Repo SSOT files
remain authoritative.

## 3. Program-Led Entrypoints

The user does not run shell commands. The agent routes natural-language board
requests through bounded ops commands.

Core board commands:

- `board-list`
- `board-claim`
- `board-heartbeat`
- `board-release`
- `board-verify`
- `board-backlog-add`
- `board-projection`
- `board-projection-live`
- `board-pr-merge`
- `board-sync`
- `board-live-probe`
- `board-setup`
- `board-auth-preflight`
- `board-seed`
- `board-metadata-live`

Product extension surface:

- `github-ops-check`
- `github-ops-job-start`
- `github-ops-job-poll`

## 4. Live Acceptance Evidence

The capability is accepted for this repo by the completed issue `#78` flow:

- ProjectV2 board `#5` exists and is field-compatible
- governed issue `#78` was seeded into the board
- live projection returned `OK` and drift `0`
- live metadata map was generated for ProjectV2 fields and item ids
- `board-sync` promoted the item to `Needs Verify` through accepted digest
- PR `#79` merged to `main`
- main push gates passed
- issue `#78` was deliberately accepted and closed
- ProjectV2 item status is `Done`

Evidence comments:

- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725314501`
- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725408977`
- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725492674`
- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4727549192`
- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4727550151`

## 5. Product Availability

Availability:

- Core repo: ACTIVE
- Product catalog: `PRJ-GITHUB-OPS`
- Install mode: embedded
- Tiers: Pro, Enterprise
- Default network posture: OFF
- Live GitHub writes: explicit enable only

## 6. Managed Repo Availability

Managed repo rollout is active as a controlled standards package:

- rollout contract:
  `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
- distribution source: `standards.lock`
- runner: `scripts/sync_managed_repo_standards.py`
- current registered manifest: `.cache/managed_repos.v1.json`
- current registered target: `/Users/halilkocoglu/Documents/dev`

This makes the board governance model part of the managed-repo standards
surface. It does not enable blind ProjectV2 mutation in target repos.

## 7. Boundaries

This capability does not prove:

- historical backlog import is complete
- every future board item will be modeled correctly without review
- future ProjectV2 drift can never recur
- every unmanaged or unregistered repo has received the capability
- live ProjectV2 mutation is enabled for every target repo
- broader process adoption outside registered standards targets is complete

Managed repo rollout is controlled by the rollout contract and standards sync.
It is not silently enabled outside registered manifest targets.

## 8. Canonical References

- `AGENTS.md`
- `docs/OPERATIONS/CODEX-UX.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`
- `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md`
- `docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-PR-TEMPLATE-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-PROJECTION-MANIFEST.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-SYNC-VALIDATION-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-ISSUE-78-ACCEPTANCE-CHECKLIST.v1.md`
- `extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json`
- `docs/OPERATIONS/product_catalog.v1.json`
