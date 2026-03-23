---
name: system-status
description: Run system status report and display current health, blockers, and open gaps
---
1. Execute: `python -m src.ops.manage system-status --workspace-root .cache/ws_customer_default`
2. Read output from `.cache/ws_customer_default/.cache/reports/system_status.v1.json`
3. Summarize: overall health, active blockers, open gaps, recommended next actions
