# PRJ-GITHUB-OPS (Extension)

Purpose: local-first GitHub ops orchestration (job-first; network default off).

Single gate: github-ops-check (program-led).
Jobs: github-ops-job-start, github-ops-job-poll (DRY_RUN unless policy enables live gate).

Outputs:
- .cache/reports/github_ops_report.v1.json
- .cache/github_ops/jobs_index.v1.json
- .cache/reports/github_ops_jobs/*.v1.json

Policy: policies/policy_github_ops.v1.json
