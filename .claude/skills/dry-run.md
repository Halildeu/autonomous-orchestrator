---
name: dry-run
description: Run policy dry-run simulation against test fixtures
user_invocable: true
---
Run dry-run simulation:
1. Execute: `python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json`
2. Read sim_report.json
3. Report: pass/fail per envelope, policy violations, gate results
