# RUN-CARD-TEMPLATE.v1 (Workspace-Only, Gunluk / Tek Seferlik)

Bu dosya gunluk/tek seferlik degerleri L2 workspace icinde tutar.
Kalici SSOT'a gunluk saat/parametre yazilmaz.

## Meta
- date: YYYY-MM-DD
- until_local_time: "17:00" (ornek; kalici kural degil)
- timezone: Europe/Istanbul
- objective_today: ""

## Budget / Auto
- budget_seconds_per_loop: 0
- auto_mode_enabled: true|false
- selection_mode: selected_only|mixed|suggested_only

## Network policy (decision-gated)
- network_policy: OFF|DECISION_GATED|ON (default OFF)
- decision_required: true|false
- env_prereqs_present: [GITHUB_TOKEN, GITHUB_API_URL] (presence-only)

## Decision policy
- safe_defaults: true|false
- require_user_for: [CORE_UNLOCK_SCOPE_WIDEN, NETWORK_LIVE_ENABLE, DEPLOY_LIVE]

## Stop conditions
- hard_gate_fail: true|false
- hard_exceeded_gt_0: true|false
- secrets_leak: true|false
- schema_validation_fail: true|false

## Reporting (evidence pointers)
- system_status: .cache/ws_customer_default/.cache/reports/system_status.v1.json
- ui_snapshot: .cache/ws_customer_default/.cache/reports/ui_snapshot_bundle.v1.json
- work_intake: .cache/ws_customer_default/.cache/index/work_intake.v1.json
- decision_inbox: .cache/ws_customer_default/.cache/index/decision_inbox.v1.json
- doc_nav_strict: .cache/ws_customer_default/.cache/reports/doc_graph_report.strict.v1.json
- assessment_eval: .cache/ws_customer_default/.cache/index/assessment_eval.v1.json
- gap_register: .cache/ws_customer_default/.cache/index/gap_register.v1.json
- pdca_recheck_report: .cache/ws_customer_default/.cache/reports/pdca_recheck_report.v1.json
