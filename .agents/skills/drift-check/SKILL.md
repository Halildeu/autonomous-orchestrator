---
name: drift-check
description: Check context drift across sessions and managed repos
---
1. Execute: `python -m src.ops.manage drift-scoreboard --workspace-root .cache/ws_customer_default`
2. Report: drifted artifacts, hash mismatches, staleness scores
