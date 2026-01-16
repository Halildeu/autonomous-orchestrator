# OPERATIONS-CHEATSHEET (Tek Kapi)

Bu liste "sik kullanilan tek kapi" operasyonlarini ve urettikleri kanit yollarini ozetler.

## Durum / Cockpit
- system-status
  - `.cache/ws_customer_default/.cache/reports/system_status.v1.json`
  - `.cache/ws_customer_default/.cache/reports/system_status.v1.md`
- ui-snapshot-bundle
  - `.cache/ws_customer_default/.cache/reports/ui_snapshot_bundle.v1.json`

## Intake / Karar
- work-intake-check (strict)
  - `.cache/ws_customer_default/.cache/index/work_intake.v1.json`
  - `.cache/ws_customer_default/.cache/reports/portfolio_status.v1.json`
- decision-inbox-build / decision-inbox-show
  - `.cache/ws_customer_default/.cache/index/decision_inbox.v1.json`
  - `.cache/ws_customer_default/.cache/reports/decision_inbox.v1.md`
- decision-apply / decision-apply-bulk
  - `.cache/ws_customer_default/.cache/index/decisions_applied.v1.jsonl`
  - `.cache/ws_customer_default/.cache/reports/decision_apply_bulk.v1.json`

## Airrunner / Auto-loop
- airrunner-baseline / airrunner-run / airrunner-tick
  - `.cache/ws_customer_default/.cache/reports/airunner_baseline.v1.json`
  - `.cache/ws_customer_default/.cache/reports/airunner_run.v1.json`
  - `.cache/ws_customer_default/.cache/reports/airunner_tick_1.v1.json` (ve devami)
- auto-loop
  - `.cache/ws_customer_default/.cache/reports/auto_loop.v1.json`
  - `.cache/ws_customer_default/.cache/reports/auto_loop_apply_details.v1.json`

## Doc Navigation
- doc-nav-check (strict)
  - `.cache/ws_customer_default/.cache/reports/doc_graph_report.strict.v1.json`
- doc-nav-check (summary)
  - `.cache/ws_customer_default/.cache/reports/doc_graph_report.v1.json`

## North Star kanitlari
- assessment_raw / assessment_eval
  - `.cache/ws_customer_default/.cache/index/assessment_raw.v1.json`
  - `.cache/ws_customer_default/.cache/index/assessment_eval.v1.json`
- gap_register
  - `.cache/ws_customer_default/.cache/index/gap_register.v1.json`
- pdca_recheck_report
  - `.cache/ws_customer_default/.cache/reports/pdca_recheck_report.v1.json`
- integrity_verify
  - `.cache/ws_customer_default/.cache/reports/integrity_verify.v1.json`

## GitHub Ops / Release / Deploy (no-wait)
- github-ops job start/poll
  - `.cache/ws_customer_default/.cache/github_ops/jobs_index.v1.json`
  - `.cache/ws_customer_default/.cache/reports/github_ops_jobs/*.v1.json`
- release-check
  - `.cache/ws_customer_default/.cache/reports/release_plan.v1.json`
  - `.cache/ws_customer_default/.cache/reports/release_manifest.v1.json`
  - `.cache/ws_customer_default/.cache/reports/release_notes.v1.md`
- deploy-check / deploy-job-poll
  - `.cache/ws_customer_default/.cache/reports/deploy_report.v1.json`
  - `.cache/ws_customer_default/.cache/reports/deploy_jobs/*.v1.json`
