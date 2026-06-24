# PRJ-GITHUB-OPS (Extension)

Purpose: local-first GitHub ops orchestration plus Governance Board Capability v1.

Single gate: github-ops-check (program-led).
Jobs: github-ops-job-start, github-ops-job-poll (DRY_RUN unless policy enables live gate).
Capability: Governance Board Capability v1 is ACTIVE for the core repo under release channel 0.4.0-rc.2.
Managed repo rollout: ACTIVE as a controlled standards package through standards.lock.

Outputs:
- .cache/reports/board_projection_live*.v1.json
- .cache/reports/board_metadata_live*.v1.json
- .cache/reports/board_sync*.v1.json
- .cache/reports/github_ops_report.v1.json
- .cache/github_ops/jobs_index.v1.json
- .cache/reports/github_ops_jobs/*.v1.json

Program-led board ops:
- board-list / board-claim / board-heartbeat / board-release / board-verify / board-backlog-add
- board-projection / board-projection-live / board-metadata-live / board-sync
- board-pr-merge / board-live-probe / board-setup / board-auth-preflight / board-seed

Policies:
- policies/policy_github_ops.v1.json
- policies/policy_board_governance.v1.json

Capability docs:
- docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md
- docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md
- docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md
- docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md
