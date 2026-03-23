---
name: policy-check
description: Run policy compliance check across schemas and policies
user_invocable: true
---
Run policy check:
1. Execute: `python -m src.ops.manage policy-check --source both --workspace-root .cache/ws_customer_default`
2. Report: violations, warnings, compliance score
