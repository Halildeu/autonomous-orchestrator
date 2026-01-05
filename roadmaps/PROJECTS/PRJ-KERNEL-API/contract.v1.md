# PRJ-KERNEL-API — contract.v1 (locked)

## Single-Gate Mapping (program-led)
- /v1/status/project  -> project-status
- /v1/status/system   -> system-status
- /v1/doc-nav         -> doc-nav-check (summary default; strict optional, ayrı rapor)
- /v1/roadmap/finish  -> roadmap-finish (bounded)
- /v1/roadmap/follow  -> roadmap-follow (max-steps=1)
- /v1/pause           -> roadmap-pause
- /v1/resume          -> roadmap-resume

Strict izolasyon kuralı:
- summary report: doc_graph_report.v1.json + cockpit refresh
- strict report: doc_graph_report.strict.v1.json (cockpit'i etkilemez)

## Request Envelope v1 (input)
- workspace_root
- mode: summary|detail|strict
- detail: true|false
- strict: true|false
- correlation_id
- client_project_id

## Response Envelope v1 (output)
- status
- overall_status
- evidence_paths
- actions_top
- notes
- machine_json_tail

## Versioning
- v1; backward compatible fields only

## Program-led notu
Codex yalnızca raporlar; program yürütür. Kullanıcı komut yazmaz.

## Adapter Library Entry Point
- Module: src/prj_kernel_api/adapter.py
- Entry: handle_request(req: dict) -> dict
- Actions (stable): project_status | system_status | doc_nav_check | roadmap_finish | roadmap_follow
- Actions (llm): llm_providers_init | llm_list_providers | llm_call | llm_live_probe
- Import notu: `from src.prj_kernel_api.adapter import handle_request`

## HTTP Gateway v0.2 (stdlib, program-led)
- Endpoint: POST /v1/kernel-api
- Request/Response: kernel-api-request.schema.v1.json / kernel-api-response.schema.v1.json
- Kural: request ve response şema-valid olmalı; aksi FAIL + deterministic error_code.
- Strict rapor cockpit'i etkilemez; strict ayrı rapor üretir.

## API Guardrails (v0.3.2, program-led)
- Auth varsayılan zorunlu: bearer veya hmac (policy ile yönetilir).
- Rate limit + concurrency limit (in-memory, deterministic) uygulanır.
- Action allowlist zorunlu (policy).
- Audit log workspace-root altında, redacted (token/secret yok).
- LLM live çağrı kapalı: dry_run=false => LIVE_CALL_DISABLED.
- LLM live probe: live gate kapalıyken OK döner, tüm providerlar SKIPPED (reason=LIVE_DISABLED) olur.

## LLM Guardrails (program-led, offline)
- Default: dry_run=true (policy default).
- dry_run=false iken: LIVE_CALL_DISABLED (offline mode).
- model verilmezse: provider guardrails default_model kullanılır; yoksa MODEL_REQUIRED.
- Allowlist + provider enabled + allow_models + boyut limitleri zorunlu; api_key asla loglanmaz.
- api_key kaynak sirasi: workspace .env -> repo .env -> process env (yalnizca var/yok raporlanir; process sadece env_mode=process ile).

## Error Codes (deterministic)
- KERNEL_API_SCHEMA_INVALID
- KERNEL_API_BAD_JSON
- KERNEL_API_RESPONSE_INVALID
- KERNEL_API_WORKSPACE_MISMATCH
- KERNEL_API_INTERNAL_ERROR
 - KERNEL_API_UNAUTHORIZED
 - KERNEL_API_ACTION_DENIED
- KERNEL_API_BODY_TOO_LARGE
- KERNEL_API_JSON_TOO_DEEP
- KERNEL_API_RATE_LIMITED
- KERNEL_API_RATE_LIMIT_INVALID
- KERNEL_API_CONCURRENCY_LIMIT
- KERNEL_API_CONCURRENCY_INVALID
 - PROVIDER_NOT_ALLOWED
 - PROVIDER_DISABLED
 - PROVIDER_NOT_FOUND
 - PROVIDER_CONFIG_MISSING
 - LIVE_CALL_DISABLED
