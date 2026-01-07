# SSOT Map (Canonical)

Bu doküman, kritik SSOT artefact’ların tek canonical haritasıdır.  
Amaç: “orphan kritik” riskini ortadan kaldırmak ve navigasyonu deterministik hale getirmek.

## Roadmaps
- roadmaps/SSOT/roadmap.v1.json
- roadmaps/SSOT/changes/.gitkeep
- roadmaps/SSOT/changes/debt/README.md
- roadmaps/PROJECTS/README.md
- roadmaps/PROJECTS/project-roadmap.template.v1.json

## Codex Config (SSOT)
- docs/OPERATIONS/CODEX-CONFIG-CONTRACT.v1.md
- .codex/config.toml
- .env.example
- src/prj_kernel_api/codex_home.py
- src/prj_kernel_api/codex_home_contract_test.py
- src/prj_kernel_api/dotenv_loader.py
- src/prj_kernel_api/dotenv_loader_contract_test.py

## Operations Docs (SSOT)
- docs/OPERATIONS/EXTENSIONS.md

## Schemas (SSOT)
- schemas/advisor-suggestions.schema.json
- schemas/airunner-heartbeat.schema.v1.json
- schemas/airunner-job.schema.v1.json
- schemas/airunner-jobs-index.schema.v1.json
- schemas/airunner-lock.schema.v1.json
- schemas/airunner-perf-event.schema.v1.json
- schemas/airunner-time-sinks.schema.v1.json
- schemas/assessment-eval.schema.v1.json
- schemas/assessment-raw.schema.v1.json
- schemas/artifact-pointer.schema.json
- schemas/autopilot-readiness.schema.json
- schemas/chg-debt.schema.json
- schemas/context-pack-router-result.schema.v1.json
- schemas/context-pack.schema.v1.json
- schemas/doc-graph-report.schema.json
- schemas/extension-help.schema.v1.json
- schemas/extension-manifest.schema.v1.json
- schemas/extension-registry.schema.v1.json
- schemas/format-autopilot-chat.schema.json
- schemas/gap.record.schema.json
- schemas/github-ops-job.schema.v1.json
- schemas/github-ops-report.schema.v1.json
- schemas/integrity-snapshot.schema.v1.json
- schemas/kernel-api-request.schema.v1.json
- schemas/kernel-api-response.schema.v1.json
- schemas/layer-boundary-report.schema.v1.json
- schemas/policy-kernel-api-guardrails.schema.json
- schemas/policy-integrity.schema.json
- schemas/policy-integrity.schema.v1.json
- schemas/policy-layer-boundary.schema.v1.json
- schemas/policy-llm-live.schema.json
- schemas/policy-llm-providers-guardrails.schema.json
- schemas/policy-pdca.schema.json
- src/prj_kernel_api/http_gateway.py
- src/prj_kernel_api/http_gateway_contract_test.py
- src/prj_kernel_api/api_guardrails.py
- src/prj_kernel_api/llm_clients.py
- src/prj_kernel_api/llm_live_probe.py
- src/prj_kernel_api/providers_registry.py
- src/prj_kernel_api/providers_registry_schema.py
- src/prj_kernel_api/providers_registry_contract_test.py
- src/prj_kernel_api/provider_guardrails.py
- schemas/intent-registry.schema.json
- schemas/north_star.control.schema.json
- schemas/north_star.maturity.schema.json
- schemas/north_star.metric.schema.json
- schemas/manual-request.schema.v1.json
- schemas/pack-advisor-suggestions.schema.json
- schemas/pack-manifest.schema.v1.json
- schemas/policy-advisor.schema.json
- schemas/policy-airunner.schema.v1.json
- schemas/policy-airunner-jobs.schema.v1.json
- schemas/policy-artifact-completeness.schema.json
- schemas/policy-autonomy.schema.json
- schemas/policy-autopilot-readiness.schema.json
- schemas/policy-benchmark.schema.json
- schemas/policy-core-immutability.schema.json
- schemas/policy-context-pack-router.schema.v1.json
- schemas/policy-cve.schema.json
- schemas/policy-data.schema.json
- schemas/policy-debt.schema.json
- schemas/policy-default.schema.json
- schemas/policy-doc-graph.schema.json
- schemas/policy-ethics.schema.json
- schemas/policy-extension-registry.schema.v1.json
- schemas/policy-extension-isolation.schema.v1.json
- schemas/policy-github-ops.schema.v1.json
- schemas/policy-harvest.schema.json
- schemas/policy-license.schema.json
- schemas/policy-ops-index.schema.json
- schemas/policy-pack-selection.schema.json
- schemas/policy-pm-suite.schema.v1.json
- schemas/policy-promotion.schema.json
- schemas/policy-quality.schema.json
- schemas/policy-quota.schema.json
- schemas/policy-release-automation.schema.v1.json
- schemas/policy-retention.schema.json
- schemas/policy-secrets.schema.json
- schemas/policy-security.schema.json
- schemas/policy-system-status.schema.json
- schemas/project-manifest.schema.json
- schemas/promote.manifest.schema.json
- schemas/promotion-manifest.schema.json
- schemas/public-candidates.schema.json
- schemas/repo-layout.schema.json
- schemas/release-manifest.schema.v1.json
- schemas/release-plan.schema.v1.json
- schemas/request-envelope.schema.json
- schemas/roadmap-change.schema.json
- schemas/roadmap-state.schema.json
- schemas/roadmap.schema.json
- schemas/script-budget.schema.json
- schemas/session-context.schema.json
- schemas/spec-capability.schema.json
- schemas/spec-core.schema.json
- schemas/system-status.schema.json
- schemas/work-intake.schema.v1.json
- schemas/work-intake-action.schema.v1.json
- schemas/policy-work-intake.schema.json
- schemas/policy-work-intake.schema.v1.json
- schemas/policy-work-intake-exec.schema.v1.json

## Policies (SSOT)
- policies/policy_advisor.v1.json
- policies/policy_airunner.v1.json
- policies/policy_airunner_jobs.v1.json
- policies/policy_artifact_completeness.v1.json
- policies/policy_autonomy.v1.json
- policies/policy_autopilot_readiness.v1.json
- policies/policy_benchmark.v1.json
- policies/policy_core_immutability.v1.json
- policies/policy_context_pack_router.v1.json
- policies/policy_cve.v1.json
- policies/policy_data.v1.json
- policies/policy_debt.v1.json
- policies/policy_default.v1.json
- policies/policy_doc_graph.v1.json
- policies/policy_ethics.v1.json
- policies/policy_extension_registry.v1.json
- policies/policy_extension_isolation.v1.json
- policies/policy_github_ops.v1.json
- policies/policy_harvest.v1.json
- policies/policy_integrity.v1.json
- policies/policy_license.v1.json
- policies/policy_kernel_api_guardrails.v1.json
- policies/policy_layer_boundary.v1.json
- policies/policy_llm_live.v1.json
- policies/policy_llm_providers_guardrails.v1.json
- policies/policy_ops_index.v1.json
- policies/policy_pdca.v1.json
- policies/policy_pack_selection.v1.json
- policies/policy_promotion.v1.json
- policies/policy_quality.v1.json
- policies/policy_quota.v1.json
- policies/policy_release_automation.v1.json
- policies/policy_retention.v1.json
- policies/policy_secrets.v1.json
- policies/policy_security.v1.json
- policies/policy_system_status.v1.json
- policies/policy_work_intake.v1.json
- policies/policy_work_intake.v2.json
- policies/policy_work_intake_exec.v1.json

## CAPABILITY Specs (SSOT)
- capabilities/CAP-PR-PACKAGER.v1.json
- capabilities/CAP_ARCH_ADR_DRAFT.v1.json
- capabilities/CAP_DOC_CONTROLLED_DOC.v1.json
- capabilities/CAP_ISO_CONTROL_BASE.v1.json
- capabilities/CAP_NIST_AI_RMF_BASE.v1.json
- capabilities/CAP_OWASP_AI_BASE.v1.json

## Standards Packs (SSOT)
- packs/standards/pack-iso9001-2015/pack.manifest.v1.json
- packs/standards/pack-iso9001-2015/controls.v1.json
- packs/standards/pack-iso9001-2015/metrics.v1.json
- packs/standards/pack-owasp-ai/pack.manifest.v1.json
- packs/standards/pack-owasp-ai/controls.v1.json
- packs/standards/pack-owasp-ai/metrics.v1.json
- packs/standards/pack-nist-ai-rmf/pack.manifest.v1.json
- packs/standards/pack-nist-ai-rmf/controls.v1.json
- packs/standards/pack-nist-ai-rmf/metrics.v1.json

## Extensions (SSOT)
- extensions/release-automation/extension.manifest.v1.json
- extensions/PRJ-AIRUNNER/extension.manifest.v1.json
- extensions/prj-github-ops/extension.manifest.v1.json
- extensions/PRJ-KERNEL-API/extension.manifest.v1.json
- extensions/PRJ-M0-MAINTAINABILITY/extension.manifest.v1.json
- extensions/PRJ-PM-SUITE/extension.manifest.v1.json
- extensions/PRJ-WORK-INTAKE/extension.manifest.v1.json

## Notes
- Bu listede olmayan dosyalar yardımcı olabilir; ancak kritik SSOT olarak değerlendirilmez.
- Workspace‑bound referanslar (ISO core `*.v1.md`) tenant/workspace altında tutulur ve ayrı sınıftadır.
- Kernel API audit log (workspace): .cache/reports/kernel_api_audit.v1.jsonl
- LLM live probe report (workspace): .cache/reports/llm_live_probe.v1.json
- Archive (legacy, non-canonical): docs/ARCHIVE/extensions/PRJ-RELEASE-AUTOMATION/extension.manifest.v1.json
- Archive (legacy, non-canonical): docs/ARCHIVE/extensions/PRJ-KERNEL-API/extension.manifest.v1.json
- Archive (legacy, non-canonical): docs/ARCHIVE/extensions/PRJ-M0-MAINTAINABILITY/extension.manifest.v1.json
- Archive (legacy, non-canonical): docs/ARCHIVE/extensions/PRJ-WORK-INTAKE/extension.manifest.v1.json
