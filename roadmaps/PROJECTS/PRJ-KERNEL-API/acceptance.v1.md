# PRJ-KERNEL-API — acceptance.v1 (stub)

## DoD (doc-only)
- Program-led akış net ve tek kapı yaklaşımıyla tanımlı.
- AUTOPILOT CHAT + JSON tail standardı referanslı.
- Strict rapor cockpit'i NOT_READY'a düşürmez.
- Program-led çağrılar deterministiktir.
- Adapter entrypoint: src.prj_kernel_api.adapter:handle_request.
- HTTP gateway request/response şema-valid (v1).
- workspace_root dışına yazım yok.
- LLM dry_run offline çalışır; live çağrı offline modda LIVE_CALL_DISABLED döner.
- LLM live probe: live gate kapalıyken OK döner; provider sonuçları SKIPPED/LIVE_DISABLED; secrets yazılmaz.
- Legacy provider registry normalizasyonu idempotenttir (ikinci çalıştırma değişiklik üretmez).
- No secrets: api_key/token redacted; log/evidence sızdırılmaz.
- Auth varsayılan zorunlu (bearer/hmac); yanlış/eksik auth FAIL döner.
- Audit log redacted ve workspace-root altında tutulur.
- LLM guardrails: provider enabled/allow_models/size limitleri enforced; PROVIDER_DISABLED/MODEL_NOT_ALLOWED/REQUEST_TOO_LARGE deterministik döner.
- LLM guardrails: model verilmezse default_model kullanılır; yoksa MODEL_REQUIRED döner.

## Safety invariants
- core_lock açık; core’a yazım yok.
- strict rapor cockpit’i bozmaz.
- secrets yok.
- workspace_root dışına yazım yok.
- allowlist/disabled provider kontrolleri fail-closed.
- guardrails limitleri (rate/concurrency/body) fail-closed.

## Test plan (isim olarak)
- smoke_test.py (fast/full)
- doc-nav-check (summary/detail/strict)
- system-status (workspace-scoped)
