# PRJ-DEPLOY (Extension)

Purpose: plan-first deploy orchestration (static FE + selfhost BE). Live deploy is policy-gated and default OFF.

## Entrypoints
- ops: deploy-check, deploy-job-start, deploy-job-poll
- kernel_api_actions: none
- cockpit_sections: system-status, ui-snapshot-bundle

## Outputs
- .cache/deploy/jobs_index.v1.json
- .cache/reports/deploy_plan.v1.json
- .cache/reports/deploy_report.v1.json

## Policies
- policies/policy_deploy.v1.json

## Tests
- extensions/PRJ-DEPLOY/tests/contract_test.py

## Notes
- Provider packs planned: static FE + selfhost BE.
- Prod gate must be a decision (no implicit live deploy).
