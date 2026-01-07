# Extensions (Program-led)

Bu dokuman extension modelini tek yerde, minimal ve deterministik bicimde ozetler.

## Model
- Extension = L1 manifest + L2 workspace output + L0 program-led entrypoints.
- L0/L1/L2/L3 sinirlari ve core_lock kurallari gecerlidir.

## Kullanim
- Insan: UI veya Kernel API action ile tek kapi akisi kullanir.
- Yapay zeka: manifest + policy + schema + ops entrypoint dosyalari uzerinden calisir.
- Shell komut yok; yalniz program-led tek kapi aciklamasi.

## Dogrulama
- Gates: validate_schemas, smoke_fast, script_budget, system-status, work-intake.
- Evidence: workspace altinda JSON raporlari.

## Policy/Gate Modeli
- Network default kapali; publish/deploy policy ile ve explicit enable ile.
- Plan yok => IDLE (non-fatal).

## AI Context Pack
- AGENTS.md
- docs/LAYER-MODEL-LOCK.v1.md
- docs/ROADMAP.md
- docs/OPERATIONS/SSOT-MAP.md
- policies/policy_extension_registry.v1.json
- schemas/extension-manifest.schema.v1.json
- extensions/*/extension.manifest.v1.json
- Extension'a ozel policy + schema + ops entrypoint dosyalari

## Extension Index
<a id="ext-PRJ-RELEASE-AUTOMATION"></a>
### PRJ-RELEASE-AUTOMATION
- Purpose: local-first release plan/prepare (publish default SKIP).
- Single gate: release-check.
- Outputs: .cache/reports/release_plan.v1.json, release_manifest.v1.json, release_notes.v1.md
- Policies: policies/policy_release_automation.v1.json

<a id="ext-PRJ-KERNEL-API"></a>
### PRJ-KERNEL-API
- Purpose: program-led Kernel API adapter actions.
- Entry: Kernel API actions (project_status, system_status, doc_nav_check, intake_*).
- Outputs: .cache/reports/kernel_api_audit.v1.jsonl
- Policies: policies/policy_kernel_api_guardrails.v1.json

<a id="ext-PRJ-WORK-INTAKE"></a>
### PRJ-WORK-INTAKE
- Purpose: work-intake build/check/exec (TICKET safe-only).
- Single gate: work-intake-check.
- Outputs: .cache/index/work_intake.v1.json, .cache/reports/work_intake_exec_ticket.v1.json
- Policies: policies/policy_work_intake.v2.json, policies/policy_work_intake_exec.v1.json

<a id="ext-PRJ-M0-MAINTAINABILITY"></a>
### PRJ-M0-MAINTAINABILITY
- Purpose: script-budget guardrails and M0 maintainability planning.
- Single gate: script-budget.
- Outputs: .cache/script_budget/report.json
- Policies: ci/script_budget.v1.json

<a id="ext-PRJ-GITHUB-OPS"></a>
### PRJ-GITHUB-OPS
- Purpose: local-first GitHub ops orchestration (job-first; network default off).
- Single gate: github-ops-check.
- Outputs: .cache/reports/github_ops_report.v1.json, .cache/github_ops/jobs_index.v1.json, .cache/reports/github_ops_jobs/*.v1.json
- Policies: policies/policy_github_ops.v1.json

<a id="ext-PRJ-PM-SUITE"></a>
### PRJ-PM-SUITE
- Purpose: professional project management schemas + cockpit summary (skeleton).
- Single gate: pm-suite-check (planned).
- Outputs: .cache/reports/pm_suite_status.v1.json
- Policies: policies/policy_pm_suite.v1.json

<a id="ext-PRJ-AIRUNNER"></a>
### PRJ-AIRUNNER
- Purpose: background automation runner: intake->plan->apply (policy gated).
- Default: core policy disabled; workspace override can enable schedule.
- Single gate: airunner-status (report-only), airunner-run (tick loop, default IDLE).
- Outputs: .cache/reports/airunner_tick.v1.json, airunner_tick.v1.md
- Policies: policies/policy_airunner.v1.json
