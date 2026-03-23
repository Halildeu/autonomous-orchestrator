---
name: context-health
description: Run context health check with Eval-G scoring
user_invocable: true
---
Check context health:
1. Execute: `python scripts/check_context_health.py --workspace-root .cache/ws_customer_default`
2. Report: overall score (0-100), grade, sub-metrics (freshness, coverage, compliance, completeness, drift, extension health)
