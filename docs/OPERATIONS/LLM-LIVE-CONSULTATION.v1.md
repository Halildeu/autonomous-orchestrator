# LLM Live Consultation (KERNEL_API) — SOP v1

Bu doküman, **NO‑NETWORK default** yaklaşımını bozmadan “istişare (live)” ihtiyacını **fail‑closed + allowlist + audit** ile nasıl açtığımızın standart işletim tarifidir.

## 1) Amaç

- “İstişare” modunda (benchmark/perspective/intent tasarımı gibi) dış LLM’lerden (örn. DeepSeek / Gemini) **kontrollü** geri bildirim almak.
- Üretimde/otomatik akışlarda değil, **kasıtlı ve izli** (audited) şekilde çalışmak.

## 2) Güvenlik İlkeleri (Fail‑Closed)

- Varsayılan: **network kapalı**. Live çağrı ancak tüm kapılar açıkken yapılır.
- **Secrets asla stdout’a basılmaz**.
- Her live çağrı **audit log** üretir.
- Live çağrı ayrı bir action olarak çalışır: `llm_call_live` (mevcut `llm_call` bozulmaz).

## 3) Kapılar (Gate’ler)

Live çağrı için (deterministik) beklenen kapılar:

1) **Env flag**: `KERNEL_API_LLM_LIVE=1`
2) **Policy**: `policy_llm_live.v1.json` içinde `live_enabled=true`
3) **Kernel guardrails**: `policy_kernel_api_guardrails.v1.json` içinde:
   - `actions.allowlist` içinde `llm_call_live`
   - `actions.llm_call_live_allowed=true`
4) **Provider guardrails + registry**:
   - provider `base_url` placeholder değil
   - model allowlist’te
   - provider API key var

Bu kapılardan biri eksikse: **network çağrısı yapılmaz**, rapor `WARN/FAIL` olur.

## 4) Workspace “tek seferlik kurulum” (tekrarsız akış)

Varsayılan workspace root: `.cache/ws_customer_default`

Agent/ops şu komutlarla (kullanıcı komut yazmadan, ops üzerinden) kurulum yapar:

- `llm-live-setup`
  - `KERNEL_API_TOKEN` yoksa workspace `.env` içine yazar (token loglanmaz)
  - `llm_live_readiness.v1.json` raporu üretir
- `llm-live-set --value 1|0`
  - workspace `.env` içinde `KERNEL_API_LLM_LIVE` değerini set eder

Provider API key’leri (örn. `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`, `XAI_API_KEY`) **kullanıcı tarafından** `.cache/ws_customer_default/.env` içine konur (agent bunları otomatik üretmez).

## 4.1) Desteklenen provider’lar (standartlaştırılmış)

Bu repo, provider bağlantılarını **workspace-scoped** registry üzerinden yönetir:

- Registry: `.cache/ws_customer_default/.cache/providers/providers.v1.json`
- Provider allowlist policy: `.cache/ws_customer_default/.cache/providers/provider_policy.v1.json`
- Provider guardrails policy: `policies/policy_llm_providers_guardrails.v1.json` (workspace override varsa o kazanır)

Varsayılan (kanıt/istişare) provider seti:

- `deepseek` → `DEEPSEEK_API_KEY`
- `google` (Gemini OpenAI-compat) → `GEMINI_API_KEY` (tercih) veya `GOOGLE_API_KEY` (legacy alias)
- `openai` → `OPENAI_API_KEY`
- `qwen` (DashScope OpenAI-compat) → `DASHSCOPE_API_KEY` (tercih) veya `QWEN_API_KEY` (legacy alias)
- `xai` (Grok / OpenAI-compat) → `XAI_API_KEY`

Notlar:
- Base URL / model varsayılanları registry’de bulunur; `__REPLACE__` placeholder kalırsa live çağrı **fail-closed** olur.
- Provider seçimi `policy_llm_live.v1.json.allowed_providers` ile sınırlandırılır (workspace override varsa o kazanır).
- `qwen` için **region bazlı** base_url farklıdır (API key’ler regionlar arası taşınmaz):
  - Singapore (intl): `https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions`
  - US (Virginia): `https://dashscope-us.aliyuncs.com/compatible-mode/v1/chat/completions`
  - China (Beijing): `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`

## 5) Readiness / Kanıt dosyaları

- Readiness raporu:
  - `.cache/ws_customer_default/.cache/reports/llm_live_readiness.v1.json`
  - Not: `llm-live-readiness` artık **opsiyonel TLS verify preflight** üretir:
    - CA (trust store) var mı?
    - Provider base_url host’larına TLS handshake geçiyor mu?
    - Varsayılan davranış: `--tls-preflight auto` → yalnızca `KERNEL_API_LLM_LIVE=1` iken handshake dener.
    - Bu preflight **API çağrısı yapmaz** (yalnızca TLS handshake), ama yine de **network** kullanır.
- Live probe raporu (provider health check):
  - `.cache/ws_customer_default/.cache/reports/llm_live_probe.v1.json`
- Setup raporu:
  - `.cache/ws_customer_default/.cache/reports/llm_live_setup.v1.json`
- Token ensure raporu (ayrı çalıştırılırsa):
  - `.cache/ws_customer_default/.cache/reports/kernel_api_token_ensure.v1.json`
- Live çağrı raporu:
  - `.cache/ws_customer_default/.cache/reports/llm_live_consult.v1.json`
- Audit log (append‑only):
  - `.cache/ws_customer_default/.cache/reports/kernel_api_audit.v1.jsonl`

## 5.1) Provider health check (Live Probe)

`llm-live-probe` komutu:

- **Kanonik çıktı**: her zaman workspace altında şu dosyayı yazar:
  - `.cache/ws_customer_default/.cache/reports/llm_live_probe.v1.json`
- **Fail‑closed**:
  - `KERNEL_API_LLM_LIVE=1` değilse network’e çıkmaz; provider’lar `SKIPPED/LIVE_DISABLED` olur.
  - API key yoksa provider `SKIPPED/API_KEY_MISSING` olur.
- **Limit (anti‑abuse)**:
  - `policy_llm_live.v1.json.max_calls_per_run` probe’un kaç provider’a ping atacağını sınırlar.
  - “Hepsi test edilsin” istiyorsan bunu `allowed_providers` sayısı kadar (örn. 4) set et.

## 6) Live istişare çağrısı

`llm-live-consult` komutu:

- Önce **readiness preflight** yapar ve `llm_live_readiness.v1.json` yazar.
- Ready değilse **fail‑closed**: network çağrısı yapmadan `llm_live_consult.v1.json` içinde `LLM_LIVE_NOT_READY` ile çıkar.
- Ready ise `llm_call_live` request’leri Kernel API adapter’a aktarır; adapter:
  - allowlist/policy’leri uygular
  - audit üretir

## 7) Cockpit Lite görünürlük

- North Star ekranında “LLM_LIVE=READY/NOT_READY/UNKNOWN” badge’i gösterilir.
- Badge tooltip’i:
  - readiness `status`
  - reason listesi
  - readiness rapor path’i

## 8) Neyi standartlaştırdık? (Neden tekrar hatırlatmaya gerek yok)

- Env okuma: repo `.env` + workspace `.env` (dotenv‑aware) deterministik çözülür.
- Live gating: policy + allowlist + env flag birlikte aranır.
- Kanıt: readiness/setup/consult raporları + audit log path’leri her zaman yazılır.
