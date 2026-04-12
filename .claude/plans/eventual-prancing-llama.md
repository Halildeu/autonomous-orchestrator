# PRJ-LLM-CAPABILITIES — Kapsamlı Proje Planı (rev 2)

**Proje Kodu:** PRJ-LLM-CAPABILITIES
**Tarih:** 2026-04-12
**Revizyon:** 2 (CNS-20260412-001 + CNS-20260412-002 uzlaşısı)
**Codex Verdict:** B → revize edilerek A hedefleniyor
**Durum:** PLAN — onay bekleniyor

---

## 1. BAĞLAM VE AMAÇ

### 1.1 Problem

Mevcut orchestrator 14 güçlü katmana sahip (deterministic routing, 6 provider, policy gates, live probe, batch, OTEL, decision quality, memory abstraction, context packs, 6-stage pipeline, workflow fingerprinting, budget tracking, deterministic stubs, multi-agent coordination).

Ancak LLM katmanında **kritik boşluklar** var:
- Provider Protocol sadece `summarize_markdown_to_json` biliyor (provider.py:6-8)
- Structured output `_extract_first_json_object()` regex (claude_provider.py:22-42, openai_provider.py:18-39) — DRY ihlali + kırılgan
- Tool/function calling yok — agent otonom hareket edemez
- `retry_count` guardrails'te tanımlı ama **hiç kullanılmıyor**; `max_retries:2` + `rate_limit_rps:1` providers_registry.py:101-102'de ayrı otorite
- adapter_llm_actions_runtime.py 1164 satır — her PR dokunacak hotspot, seam extraction zorunlu
- Probe 8 multimodal aile tanıyor (llm_live_probe_runtime.py:542-615) ama live call sadece text chat
- provider_capability_registry.v1.json, llm_router.py, provider-local flags — 3 capability SSOT drift

### 1.2 Hedef

Provider-native protokoller + ince yardımcı kütüphanelerle boşlukları kapatmak. Framework almıyoruz, çekirdek DIY kalıyor.

### 1.3 Kapsam Dışı

- Full framework adoption (LangGraph, Pydantic AI, SK)
- Response caching (diskcache ertelendi — Codex: invalidation > storage)
- Async/concurrent (throughput sorunu kanıtlanmadan erken)
- Adaptive routing (önce E9 olgunlaşsın)

---

## 2. İSTİŞARE GEÇMİŞİ

| ID | Tarih | Taraflar | Verdict | Kritik Çıktı |
|---|---|---|---|---|
| CNS-20260412-001 | 2026-04-12 | Claude→Codex | D (hibrit DIY) | E9 yükseltildi, E5/E7 ertelendi, E11/E12 eklendi |
| CNS-20260412-002 | 2026-04-12 | Claude→Codex | B (orta revizyon) | PR0 zorunlu, retry SSOT çelişkisi, tool calling fail-closed değil, PR4 bölünmeli |

### CNS-002 İtirazları ve Yanıtlar

| # | Codex İtirazı | Kabul/Red | Plan Etkisi |
|---|---|---|---|
| 1 | PR0 refactor (seam extraction) zorunlu | **KABUL** | PR0 eklendi, tüm sıralama değişti |
| 2 | Claude structured output wire shape yanlış | **KABUL** | PR1: `output_config.format` + model-level fallback |
| 3 | retry_count vs max_retries çelişki | **KABUL** | PR2: tek SSOT + precedence tanımı |
| 4 | Tool calling fail-closed değil | **KABUL** | PR3: `allowed_tools=[]`, `fail_action=block`, typed allowlist |
| 5 | PR4 dördüncü SSOT riski | **KABUL** | PR4 ikiye bölündü: 4a manifest, 4b unification |
| 6 | tiktoken heuristic yetmez | **KABUL** | PR5: Anthropic count_tokens API live preflight |
| 7 | Golden set strata eksik | **KABUL** | PR6: 6 strata tanımlandı |
| 8 | Experiment governance eksik | **KABUL** | PR7: experiment_id, lane, rollout, promote eklendi |

---

## 3. DEPENDENCY DEĞİŞİKLİĞİ

| Paket | Versiyon | Hangi PR | Neden | Risk |
|---|---|---|---|---|
| `tenacity` | >=9.0.0 | PR2 | Exponential backoff, retry decorator | Minimal dependency (stdlib-compat) |
| `tiktoken` | >=0.9.0 | PR5 | OpenAI tokenizer | Model-specific encoding files (~5MB) |
| `httpx` | >=0.28.0 | PR8 (Faz 2) | Streaming SSE + async transport | Faz 1'de gerekmiyor |

**Faz 1: 2 paket** (tenacity, tiktoken). httpx Faz 2'de.

---

## 4. PR BAĞIMLILIK GRAFİĞİ (revize)

```
PR0: Runtime Seam Extraction (BLOCKER) ──────────────────────────┐
  ├──► PR1: Structured Output (response_format + DRY)            │
  ├──► PR2: Retry + Circuit Breaker + Rate Limit SSOT            │
  └──► PR4a: Capability Manifest + Negotiation                   │
                                                                  │
PR1 + PR2 ──► PR3: Tool Calling + ToolGateway                    │
PR4a ──► PR4b: Router + Invocation Unification                   │
PR4a ──► PR5: Token Counting + Usage (Anthropic API + tiktoken)  │
PR6: Eval Harness (bağımsız, PR0 sonrası)                        │
PR7: Prompt Registry + Experiment Governance (PR6 sonrası)        │
                                                                  │
--- FAZ 2 ---                                                     │
PR8: Streaming (httpx, PR0 seam'e bağlı)                         │
PR9: Runtime Moderation (PR3 tool calling açıksa Faz 1'e çekilir)│
PR10: RAG v1                                                      │
```

---

## 5. FAZ 1 — PR'LAR (detay)

---

### PR0: Runtime Seam Extraction (BLOCKER)

**Problem:** `adapter_llm_actions_runtime.py` 1164 satır. Her PR aynı 992-1131 bloğuna dokunacak. Merge/regression riski çok yüksek. Provider-native mantık hem provider class'larda hem kernel runtime'da yaşıyor (drift: openai_provider.py:95-123 vs runtime:1010-1027).

**Amaç:** Hotspot dosyayı 4 modüle ayır. Her PR kendi seam'ini değiştirsin.

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `src/prj_kernel_api/llm_request_builder.py` | ~200 | Provider-native request body + headers oluşturma |
| `src/prj_kernel_api/llm_transport.py` | ~150 | HTTP execution (urlopen), TLS, timeout, error classification |
| `src/prj_kernel_api/llm_response_normalizer.py` | ~150 | Response bytes → normalized dict (text, usage, tool_calls, error) |
| `src/prj_kernel_api/llm_post_processors.py` | ~100 | Evidence writing, output save, payload construction |

**Değişen Dosyalar:**

| Dosya | Değişiklik |
|---|---|
| `adapter_llm_actions_runtime.py` | 992-1131 bloğu → 4 modüle delege. ~400 satır azalma. |
| `adapter_llm_actions.py` | `_extract_llm_output_text()` → `llm_response_normalizer` taşı |

**Test Planı:**
| Test | Dosya | Kapsam |
|---|---|---|
| Seam parity | `tests/contract/test_runtime_seam_parity.py` | Refactor öncesi/sonrası aynı output ürettiğini doğrula |
| Request builder | `src/prj_kernel_api/llm_request_builder_contract_test.py` | Provider-specific header + body build |
| Transport | `src/prj_kernel_api/llm_transport_contract_test.py` | HTTP mock, timeout, error classification |
| Normalizer | `src/prj_kernel_api/llm_response_normalizer_contract_test.py` | Claude/OpenAI/generic response parse |

**DoD:**
- [ ] adapter_llm_actions_runtime.py < 800 satır
- [ ] 4 yeni modül < 200 satır (her biri)
- [ ] Mevcut tüm testler kırılmamış (`pytest tests/ -x` + `pytest src/prj_kernel_api/ -x`)
- [ ] Seam parity test: refactor öncesi/sonrası output byte-for-byte eşit
- [ ] `ci/validate_schemas.py` geçiyor
- [ ] Provider-native logic tek yerde (request_builder), runtime'da duplikasyon yok

**Başarı Kriteri:** Hotspot dosya bölünmüş, sonraki PR'lar bağımsız seam'lere dokunuyor.

**Risk:**

| Risk | Olasılık | Etki | Mitigation |
|---|---|---|---|
| Refactor sırasında davranış değişikliği | Orta | Yüksek | Parity test + diff-based review |
| İç API signature breaking | Düşük | Orta | Tüm internal caller'ları grep ile bul |

**Rollback:** `git revert` — saf refactor, yeni feature yok.

---

### PR1: E1 — Structured Output

**Problem:** Regex parser kırılgan. Provider-native `response_format` kullanılmıyor.

**Codex Düzeltmeleri:**
- Claude: `output_config.format` + `type=json_schema` (güncel API). Model-level fallback (claude-3-haiku desteklemeyebilir → regex fallback).
- OpenAI: Repo `/responses` endpoint kullanıyor (openai_provider.py:95). Responses API'ye uygun wire shape.
- Kernel live path bağlantısı zorunlu (sadece provider class değil, runtime da).

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `src/providers/response_parser.py` | ~120 | Tek kaynak regex parser + schema validation |
| `src/providers/structured_output.py` | ~120 | Provider+model-level response_format builder |

**response_parser.py API:**
```python
def extract_first_json_object(text: str) -> dict | None:
    """Mevcut regex — tek kaynak (DRY fix)."""

def validate_structured_response(data: dict, schema: dict) -> tuple[bool, list[str]]:
    """jsonschema.Draft202012Validator ile doğrulama. Fail-closed."""

def parse_provider_response(
    resp_bytes: bytes,
    *,
    provider_id: str,
    expected_schema: dict | None = None,
) -> dict[str, Any]:
    """Birleşik parser. Returns: {text, parsed_json, validation_errors, parse_method, usage, tool_calls}"""
```

**structured_output.py API:**
```python
def build_response_format(
    provider_id: str,
    model: str,
    schema: dict | None = None,
) -> dict[str, Any] | None:
    """Provider+model-native response_format.
    - claude (sonnet/opus): output_config.format + json_schema
    - claude (haiku-old): None (fallback to regex)
    - openai (Responses API): response_format json_schema
    - google: response_mime_type + response_schema
    - diğer: None
    """

def model_supports_structured_output(provider_id: str, model: str) -> bool:
    """Model structured output destekliyor mu? Capability registry'den kontrol."""
```

**Değişen Dosyalar:**

| Dosya | Satır | Değişiklik |
|---|---|---|
| `claude_provider.py` | 22-42 | `_extract_first_json_object` → import response_parser |
| `claude_provider.py` | 93-153 | `call_chat()`: `response_format` param, model-level check |
| `openai_provider.py` | 18-39 | `_extract_first_json_object` → import response_parser |
| `openai_provider.py` | 92-176 | Responses API uyumlu `response_format` |
| `llm_request_builder.py` (PR0) | — | `response_format` body'ye koy |
| `llm_response_normalizer.py` (PR0) | — | `parse_provider_response()` delege et |
| `llm_clients.py` | 8-33 | `response_format` parametresi ekle |

**Test Planı:**

| Test | Dosya | Kapsam | Teknik |
|---|---|---|---|
| DRY parity | `tests/contract/test_response_parser.py` | Eski regex davranış korunuyor | Aynı input → aynı output |
| Schema validation | `tests/contract/test_response_parser.py` | Valid/invalid schema kontrol | jsonschema fixtures |
| Claude format | `src/providers/structured_output_contract_test.py` | output_config.format shape | Mock, model-level fallback |
| OpenAI format | `src/providers/structured_output_contract_test.py` | Responses API wire shape | Mock |
| Google format | `src/providers/structured_output_contract_test.py` | response_mime_type | Mock |
| Model fallback | `src/providers/structured_output_contract_test.py` | haiku → regex, sonnet → schema | Model allowlist |
| Kernel path | `tests/contract/test_structured_kernel_path.py` | llm_call_live response_format kullanıyor | End-to-end mock |

**DoD:**
- [ ] `_extract_first_json_object` tek dosyada (response_parser.py)
- [ ] Claude: output_config.format + json_schema (destekleyen modeller)
- [ ] Claude: model-level fallback (desteklemeyen → regex)
- [ ] OpenAI: Responses API uyumlu wire shape
- [ ] Google: response_mime_type + response_schema
- [ ] Kernel live path (llm_request_builder) response_format iletebiliyor
- [ ] llm_response_normalizer schema validation yapıyor
- [ ] 0 breaking change (response_format opsiyonel, default=None → eski davranış)
- [ ] 7 test dosyası, min 15 test case

**Başarı Kriteri:**
- Schema-enforced JSON output Claude Sonnet + OpenAI GPT-4o ile çalışıyor
- Desteklemeyen modellerde graceful regex fallback
- Validation hataları evidence'a yazılıyor

**Risk:**

| Risk | Olasılık | Etki | Mitigation |
|---|---|---|---|
| Claude API output_config.format desteği sınırlı | Orta | Orta | Model-level fallback, allowlist'te belirt |
| OpenAI Responses API wire shape farkı | Düşük | Yüksek | Resmi API doc'a göre implement, contract test |
| Mevcut caller'lar kırılması | Düşük | Yüksek | Default None → eski davranış korunuyor |

**Rollback:** `git revert` — opsiyonel parametre, eski yol çalışmaya devam eder.

---

### PR2: E3 — Retry + Circuit Breaker + Rate Limit SSOT

**Problem:** İki otorite çelişiyor:
- `provider_guardrails.py:134` → `retry_count: 0`
- `providers_registry.py:101-102` → `max_retries: 2`, `rate_limit_rps: 1`
Her ikisi de validated (schema'da zorunlu) ama hiçbiri kullanılmıyor.

**Codex Düzeltmesi:** Tek SSOT + precedence tanımla.

**Karar:** `providers_registry` policy → **kaynak otorite** (daha detaylı: max_retries + rate_limit_rps). `provider_guardrails.retry_count` → **deprecated**, registry'ye yönlendir.

**Yeni Dependency:** `tenacity>=9.0.0`

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `src/prj_kernel_api/llm_retry.py` | ~200 | Retry decorator + retryable error classification |
| `src/prj_kernel_api/circuit_breaker.py` | ~180 | Per-provider circuit breaker (thread-safe) |
| `src/prj_kernel_api/rate_limiter.py` | ~100 | Token bucket rate limiter (rate_limit_rps) |

**llm_retry.py API:**
```python
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
NON_RETRYABLE_STATUS = frozenset({400, 401, 403, 404})

class LLMHTTPError(Exception):
    status_code: int
    body: bytes
    provider_id: str
    is_retryable: bool  # computed property

def execute_with_retry(
    fn: Callable[[], tuple[int, bytes]],
    *,
    max_retries: int,  # providers_registry'den
    provider_id: str,
    request_id: str,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> tuple[int, bytes]:
    """tenacity: exponential backoff (1s, 2s, 4s... max 30s).
    max_retries=0 → no retry.
    429 → Retry-After header'a uy.
    on_retry callback → evidence logging.
    """
```

**circuit_breaker.py API:**
```python
class CircuitState(Enum):
    CLOSED = "closed"      # normal
    OPEN = "open"          # reject
    HALF_OPEN = "half_open"  # test

class ProviderCircuitBreaker:
    def __init__(self, provider_id: str, failure_threshold: int = 5,
                 recovery_timeout_s: float = 60.0): ...
    @property
    def state(self) -> CircuitState: ...
    def allow_request(self) -> tuple[bool, str]: ...  # (allowed, reason)
    def record_success(self) -> None: ...
    def record_failure(self, error: Exception) -> None: ...
    def status_dict(self) -> dict[str, Any]: ...  # for evidence

# Thread-safe registry
_registry_lock: threading.Lock
def get_circuit_breaker(provider_id: str) -> ProviderCircuitBreaker: ...
def get_all_circuit_status() -> dict[str, dict]: ...
```

**rate_limiter.py API:**
```python
class TokenBucketRateLimiter:
    def __init__(self, rps: float): ...
    def acquire(self, timeout_s: float = 5.0) -> bool: ...

def get_rate_limiter(provider_id: str, rps: float) -> TokenBucketRateLimiter: ...
```

**Değişen Dosyalar:**

| Dosya | Değişiklik |
|---|---|
| `llm_transport.py` (PR0) | `urlopen()` → `execute_with_retry()` + circuit breaker + rate limiter |
| `providers_registry.py:95-105` | Canonical retry/rate source olarak belgelendi |
| `provider_guardrails.py:126-135` | `retry_count` → deprecated log + registry'ye yönlendirme |
| `pyproject.toml` | `tenacity>=9.0.0` eklendi |
| `policies/policy_llm_providers_guardrails.v1.json` | `circuit_breaker` defaults eklendi |
| `schemas/policy-llm-providers-guardrails.schema.json` | `circuit_breaker` opsiyonel object |

**Precedence Kuralı (SSOT):**
```
retry ayarı: providers_registry.policy.max_retries (canonical)
             > provider_guardrails.defaults.retry_count (deprecated, log warning)
rate limit:  providers_registry.policy.rate_limit_rps (canonical, tek yer)
circuit:     policy_llm_providers_guardrails.circuit_breaker (yeni alan)
```

**Test Planı:**

| Test | Dosya | Kapsam |
|---|---|---|
| Retry success | `src/prj_kernel_api/llm_retry_contract_test.py` | N fail → success, count doğru |
| Non-retryable | `src/prj_kernel_api/llm_retry_contract_test.py` | 400/401 → anında fail |
| 429 Retry-After | `src/prj_kernel_api/llm_retry_contract_test.py` | Header parse + wait |
| Circuit states | `src/prj_kernel_api/circuit_breaker_contract_test.py` | CLOSED→OPEN→HALF_OPEN→CLOSED |
| Thread safety | `src/prj_kernel_api/circuit_breaker_contract_test.py` | Concurrent record_failure/allow |
| Rate limiter | `src/prj_kernel_api/rate_limiter_contract_test.py` | rps=1 → 2. çağrı bekler |
| Precedence | `tests/contract/test_retry_precedence.py` | registry > guardrails, warning log |
| Entegrasyon | `tests/contract/test_retry_transport.py` | llm_transport + retry + circuit + rate |

**DoD:**
- [ ] max_retries=0 → eski davranış (0 retry)
- [ ] max_retries=2 → 429/5xx'te 2 deneme, exponential backoff
- [ ] 400/401/403 → anında fail
- [ ] 429 → Retry-After header'a uyum
- [ ] Circuit breaker: N fail → OPEN, timeout → HALF_OPEN, success → CLOSED
- [ ] Rate limiter: rps aşımında bekleme
- [ ] retry_count kullanımı → deprecation warning log
- [ ] Precedence: providers_registry canonical
- [ ] Evidence: retry sayısı + circuit state + rate wait response payload'da
- [ ] Thread-safe (concurrent calls, 10 thread test)
- [ ] 8 test dosyası, min 25 test case

**Risk:**

| Risk | Olasılık | Etki | Mitigation |
|---|---|---|---|
| tenacity version conflict | Düşük | Düşük | Minimal deps, wide version range |
| Retry storm (tüm provider'lar aynı anda 429) | Orta | Orta | Circuit breaker + per-provider isolation |
| Precedence geçiş sırasında confusion | Orta | Düşük | Deprecation warning + migration doc |

**Rollback:** `git revert` — default max_retries=0 ise hiç retry olmaz.

---

### PR3: E2 — Tool Calling + ToolGateway

**Problem:** Agent araç çağıramıyor. Codex itirazı: `allowed_tools=[*]` + `fail_action=warn` fail-closed değil. Raw `ops_command` string güvenli değil.

**Codex Düzeltmeleri:**
- ToolGateway tarzı typed allowlist (tools/gateway.py:31-48 referans)
- Default `allowed_tools=[]` (hiçbir tool izinli değilken açık whitelist zorunlu)
- Default `fail_action=block`
- Read-only / mutating ayrımı
- Cycle detection (aynı tool+arg tekrarı)

**Bağımlılık:** PR0 (seam), PR1 (structured output), PR2 (retry)

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `schemas/tool-registry.schema.v1.json` | ~80 | Tool tanım şeması |
| `schemas/policy-tool-calling.schema.v1.json` | ~50 | Tool calling policy şeması |
| `policies/policy_tool_calling.v1.json` | ~30 | **Fail-closed defaults** |
| `policies/tool_registry.v1.json` | ~60 | Başlangıç tool seti (read-only ops) |
| `src/prj_kernel_api/tool_calling.py` | ~300 | Format build + parse + policy |
| `src/prj_kernel_api/tool_gateway.py` | ~250 | Typed allowlist + dispatch + cycle detection |

**policy_tool_calling.v1.json (fail-closed):**
```json
{
  "version": "v1",
  "enabled": false,
  "max_tool_calls_per_request": 5,
  "max_tool_rounds": 3,
  "allowed_tools": [],
  "blocked_tools": [],
  "tool_permissions": {
    "default": "read_only",
    "mutating_requires_confirmation": true
  },
  "cycle_detection": {
    "enabled": true,
    "max_identical_calls": 2
  },
  "fail_action": "block"
}
```

**tool_gateway.py API:**
```python
@dataclass(frozen=True)
class ToolPermission:
    tool_name: str
    permission: str  # "read_only" | "mutating"
    ops_command: str
    allowed_args_schema: dict  # JSON Schema for input validation

class ToolGateway:
    """Typed allowlist + permission enforcement + cycle detection."""
    def __init__(self, registry: list[ToolPermission], policy: dict): ...
    def authorize_call(self, tool_name: str, tool_input: dict, call_history: list) -> tuple[bool, str]: ...
    def dispatch(self, tool_name: str, tool_input: dict, *, workspace_root: str, request_id: str) -> dict: ...

def run_tool_loop(
    *,
    messages: list[dict],
    initial_tool_calls: list[dict],
    gateway: ToolGateway,
    workspace_root: str,
    request_id: str,
    max_rounds: int,
    make_llm_call: Callable,
) -> dict[str, Any]:
    """Agentic loop: call→authorize→dispatch→result→call.
    Fail-closed: unauthorized tool → block, loop kırılır.
    Cycle detection: aynı tool+input 2. kez → block.
    """
```

**Test Planı:**

| Test | Dosya | Kapsam |
|---|---|---|
| Tool format (Claude) | `src/prj_kernel_api/tool_calling_contract_test.py` | tool_use build + parse |
| Tool format (OpenAI) | `src/prj_kernel_api/tool_calling_contract_test.py` | tool_calls build + parse |
| Authorization | `src/prj_kernel_api/tool_gateway_contract_test.py` | allowed/blocked/mutating |
| Cycle detection | `src/prj_kernel_api/tool_gateway_contract_test.py` | Aynı call 2x → block |
| Input validation | `src/prj_kernel_api/tool_gateway_contract_test.py` | Schema-invalid input → block |
| Tool loop | `tests/contract/test_tool_loop.py` | max_rounds, fail-closed, cycle |
| Read-only default | `tests/contract/test_tool_permissions.py` | Mutating tool → confirmation |
| Policy disabled | `tests/contract/test_tool_policy.py` | enabled=false → 0 tool calling |

**DoD:**
- [ ] `enabled: false` → eski davranış, 0 tool calling
- [ ] `allowed_tools: []` → hiçbir tool çağrılamaz (fail-closed)
- [ ] Tool input JSON Schema ile validate
- [ ] Cycle detection: aynı tool+input 2x → block
- [ ] Read-only default, mutating → confirmation gerekli
- [ ] Claude tool_use + OpenAI tool_calls format doğru
- [ ] Agentic loop max_rounds ile sınırlı
- [ ] Evidence: her tool call + result + authorization kararı loglanıyor
- [ ] 8 test dosyası, min 30 test case

**Risk:**

| Risk | Olasılık | Etki | Mitigation |
|---|---|---|---|
| Tool dispatch'te command injection | Düşük | Kritik | Typed allowlist, input schema validation, no raw string exec |
| Infinite loop (LLM sürekli tool çağırıyor) | Orta | Yüksek | max_rounds + cycle detection + fail-closed |
| Mutating tool istemeden çalışma | Düşük | Yüksek | default read_only, mutating_requires_confirmation |

**Rollback:** `enabled: false` → anında devre dışı.

---

### PR4a: Capability Manifest + Negotiation

**Problem (Codex'in en sert itirazı):** 3 ayrı capability SSOT drift üretiyor:
1. `registry/provider_capability_registry.v1.json` (15 class: batch, continuation, extended_thinking, code_agentic...)
2. `llm_router.py:43-203` (intent→class mapping)
3. Provider-local flags (`claude_provider.py:17` → `frozenset(["chat"])`)

Plan yeni 4. SSOT ekleme riski taşıyordu → Codex çözümü: mevcut registry'yi canonical yap, diğerlerini oradan türet.

**Amaç:** `provider_capability_registry.v1.json` → tek SSOT. Provider-local flags ve router bunu oku.

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `src/providers/capability_model.py` | ~200 | Registry loader + CapabilityManifest + negotiation |

**capability_model.py API:**
```python
class ProviderCapability(Enum):
    CHAT = "chat"
    TOOL_USE = "tool_use"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    EMBEDDINGS = "embeddings"
    VISION = "vision"
    AUDIO = "audio"
    IMAGE_GEN = "image_gen"
    MODERATION = "moderation"
    BATCH = "batch"
    CONTINUATION = "continuation"
    EXTENDED_THINKING = "extended_thinking"
    CODE_AGENTIC = "code_agentic"

@dataclass(frozen=True)
class CapabilityManifest:
    provider_id: str
    model: str
    capabilities: frozenset[ProviderCapability]
    max_context_tokens: int
    max_output_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float

def load_capability_registry(repo_root: Path) -> dict:
    """provider_capability_registry.v1.json → canonical SSOT."""

def resolve_manifest(
    provider_id: str, model: str,
    *, registry: dict, probe_state: dict | None = None,
) -> CapabilityManifest:
    """Static registry + runtime probe overlay."""

def negotiate(required: set[ProviderCapability], manifest: CapabilityManifest) -> tuple[bool, set[ProviderCapability]]:
    """Gerekli kabiliyetler var mı? Eksik set döner."""
```

**Değişen Dosyalar:**

| Dosya | Değişiklik |
|---|---|
| `provider.py` | `supports_capability()` → `capability_model.resolve_manifest()` delege |
| `claude_provider.py:17` | `_SUPPORTED_CAPABILITIES` → registry'den oku |
| `llm_router.py` | Route öncesi capability negotiation check |
| `llm_request_builder.py` (PR0) | Body build öncesi capability check |

**Test Planı:**

| Test | Dosya | Kapsam |
|---|---|---|
| Registry load | `src/providers/capability_model_contract_test.py` | Valid/invalid registry |
| Manifest resolve | `src/providers/capability_model_contract_test.py` | Static + probe overlay |
| Negotiation | `src/providers/capability_model_contract_test.py` | Match/mismatch |
| Router integration | `tests/contract/test_capability_routing.py` | Route + negotiate |

**DoD:**
- [ ] `provider_capability_registry.v1.json` tek canonical SSOT
- [ ] Provider-local flags registry'den türetiliyor
- [ ] Router capability negotiation yapıyor
- [ ] Desteklenmeyen capability → açık hata kodu (CAPABILITY_NOT_SUPPORTED)
- [ ] Probe state runtime overlay çalışıyor
- [ ] batch, continuation, extended_thinking, code_agentic enum'da

---

### PR4b: Router + Invocation Unification

**Amaç:** probe↔invocation kopukluğunu kapat. 8 probe ailesi (chat, embeddings, vision, audio, image_gen, moderation, realtime, video_gen) invocation surface'e bağlansın.

**Değişen Dosyalar:**

| Dosya | Değişiklik |
|---|---|
| `llm_request_builder.py` | Capability-aware body builder (embeddings, vision, audio dahil) |
| `llm_response_normalizer.py` | Multi-modal response normalization |
| `llm_transport.py` | Provider-specific endpoint routing (embeddings → /embeddings vs /embedContent) |

**DoD:**
- [ ] `llm_call_live` action embeddings, vision, moderation destekliyor
- [ ] Probe ailesi ile invocation ailesi 1:1 eşleşiyor
- [ ] Desteklenmeyen aile → `CAPABILITY_NOT_SUPPORTED` + capability manifest ile açıklama

---

### PR5: E6 — Token Counting + Usage Normalization

**Codex Düzeltmesi:** Anthropic `messages/count_tokens` API live preflight'ta kullanılmalı. Heuristic yalnız offline/dry-run fallback.

**Yeni Dependency:** `tiktoken>=0.9.0`

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `src/providers/token_counter.py` | ~250 | Multi-provider token counting + cost |

**token_counter.py API:**
```python
def count_tokens(
    messages: list[dict],
    *,
    provider_id: str,
    model: str,
    api_key: str | None = None,
    live_enabled: bool = False,
) -> dict[str, Any]:
    """Multi-provider token counting.
    - openai/xai: tiktoken (offline, kesin)
    - claude (live): POST /v1/messages/count_tokens (kesin, tools+images dahil)
    - claude (offline): heuristic fallback
    - google/deepseek/qwen: heuristic
    Returns: {estimated_tokens, method, model, is_exact}
    """

class UsageRecord:
    provider_id: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float  # capability_registry cost_per_1k ile hesapla
    timestamp: str

class UsageTracker:
    """Per-run cumulative usage (thread-safe)."""
    def check_budget(self, estimated: int) -> tuple[bool, int]: ...
    def record(self, usage: UsageRecord) -> None: ...
    def summary(self) -> dict[str, Any]: ...
```

**DoD:**
- [ ] OpenAI: tiktoken kesin sayım
- [ ] Claude (live): Anthropic count_tokens API
- [ ] Claude (offline): heuristic ±50% (sadece dry-run)
- [ ] Pre-flight: budget aşımı → TOKEN_BUDGET_EXCEEDED (fail-closed)
- [ ] Post-call: actual vs estimated evidence'a
- [ ] Cost: capability_registry cost_per_1k ile hesaplama
- [ ] max_tokens_per_run=0 → unlimited (backward compat)

---

### PR6: E9 — Eval Harness

**Codex Düzeltmeleri:** Golden set 6 strata. `decision_quality.py:22-53` çağıran yok — bağla.

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `src/orchestrator/eval_harness.py` | ~350 | 6 eval check + suite runner |
| `src/orchestrator/eval_golden_set.py` | ~150 | Golden set loader + regression |
| `policies/policy_eval.v1.json` | ~35 | Eval policy |
| `schemas/policy-eval.schema.v1.json` | ~50 | Eval policy schema |
| `fixtures/eval/golden_set.v1.json` | ~80 | 6 strata × min 2 case |

**6 Eval Check:**
1. `json_conformance` — Schema uygunluğu
2. `groundedness` — Output iddialar context'te var mı (overlap score)
3. `citation_completeness` — Beklenen referanslar var mı
4. `tool_result_consistency` — Tool sonuçları output'la tutarlı mı
5. `refusal_correctness` — Policy'e göre reddetme/kabul doğru mu
6. `truncation_safety` — max_tokens kesilme durumunda output hâlâ kullanılabilir mi

**Golden Set 6 Strata:**
1. Structured output (valid JSON, schema uygun)
2. Tool loop (tool call + dispatch + result)
3. Refusal (izinsiz istek → reddetme)
4. Citation (source reference doğru)
5. Truncation/max_tokens edge case
6. Negative groundedness (hallucinated claim)

**Entegrasyon:**
- `quality_gate.py:130-136` → `eval_harness` gate ekle
- `llm_post_processors.py` (PR0) → eval çalıştır, payload'a ekle
- `decision_quality.py:22-53` → **ilk kez çağrılacak** (PR6 bunu bağlar)

**DoD:**
- [ ] 6 eval check çalışıyor
- [ ] Golden set 6 strata × min 2 case = min 12 fixture
- [ ] Regression: önceki run ile karşılaştırma, alert
- [ ] decision_quality.py entegre (çağrılıyor, JSONL üretiyor)
- [ ] Quality gate entegrasyon: eval score < threshold → warn/block
- [ ] `enabled: false` → eski davranış

---

### PR7: E11 — Prompt Registry + Experiment Governance

**Codex Düzeltmesi:** Sadece lineage yetmez, experiment governance (A/B, canary, shadow, rollout, promote) da gerekli.

**Yeni Dosyalar:**

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `schemas/prompt-registry.schema.v1.json` | ~80 | Prompt + experiment schema |
| `policies/prompt_registry.v1.json` | ~60 | Başlangıç prompt + experiment set |
| `src/prj_kernel_api/prompt_registry.py` | ~250 | Registry + resolve + lineage + experiment |

**prompt_registry.v1.json yapısı:**
```json
{
  "version": "v1",
  "prompts": [{
    "prompt_id": "summarize_to_json",
    "version": "1.0.0",
    "prompt_hash": "sha256:...",
    "template": "...",
    "model_compatibility": ["claude-*", "gpt-*"],
    "tool_schema_version": null,
    "guardrail_version": "v1",
    "input_schema": null,
    "output_schema": null,
    "eval_score": null,
    "last_tested_at": null,
    "experiment": {
      "experiment_id": null,
      "lane": "control",
      "rollout_pct": 100,
      "owner": null,
      "status": "active",
      "promoted_at": null
    }
  }]
}
```

**Lane Types:**
- `control` — aktif, %100 trafik (default)
- `treatment` — A/B test treatment
- `canary` — küçük % ile deneme
- `shadow` — paralel çalıştır, karşılaştır, serve etme

**DoD:**
- [ ] Prompt registry schema-validated
- [ ] Model compatibility matching
- [ ] Experiment lanes: control/treatment/canary/shadow
- [ ] Rollout yüzdesi + promote mekanizması
- [ ] Prompt hash ile değişiklik takibi
- [ ] Lineage JSONL: prompt×model×experiment×eval_score×run_id
- [ ] decision_quality_log'a prompt + experiment bilgisi

---

## 6. FAZ 2 — İHTİYAÇ DOĞUNCA

| PR | Tetikleyici | Efor |
|---|---|---|
| PR8: Streaming | İnteraktif UX ihtiyacı | S (2-3 gün) |
| PR9: Runtime Moderation | PR3 mutating tools açıksa → Faz 1'e çekilir | S (2-3 gün) |
| PR10: RAG v1 | Doküman retrieval somutlaşınca | L (8-12 gün) |

---

## 7. GENEL TEST STRATEJİSİ

| Seviye | Konum | Çalıştırma | Minimum |
|---|---|---|---|
| Unit/Contract (kernel) | `src/prj_kernel_api/*_contract_test.py` | `pytest src/prj_kernel_api/ -x` | 15 dosya |
| Unit/Contract (provider) | `src/providers/*_contract_test.py` | `pytest src/providers/ -x` | 5 dosya |
| Integration | `tests/contract/test_*.py` | `pytest tests/contract/ -x` | 10 dosya |
| Schema validation | `ci/validate_schemas.py` | CI gate | 0 hata |
| Policy dry-run | `ci/policy_dry_run.py` | CI gate | 0 hata |
| Regression | Mevcut tüm testler | `pytest tests/ -x` | 0 kırılma |

**Toplam yeni test hedefi:** >= 50 dosya, >= 150 test case

---

## 8. RİSK MATRİSİ

| # | Risk | Olasılık | Etki | Skor | Mitigation |
|---|---|---|---|---|---|
| R1 | adapter_llm_actions_runtime.py merge conflict | Yüksek | Yüksek | 16 | PR0 seam extraction (BLOCKER) |
| R2 | Tool dispatch command injection | Düşük | Kritik | 12 | Typed allowlist, input schema validation |
| R3 | Claude API değişikliği (output_config) | Orta | Orta | 9 | Model-level fallback, contract test |
| R4 | Retry storm (concurrent 429) | Orta | Orta | 9 | Circuit breaker + per-provider isolation |
| R5 | Capability registry drift (4. SSOT) | Orta | Yüksek | 12 | Tek SSOT: mevcut registry canonical |
| R6 | tiktoken model encoding eksik | Düşük | Düşük | 4 | Heuristic fallback |
| R7 | Eval false positive → legitimate output block | Orta | Orta | 9 | enabled=false default, golden set calibration |
| R8 | Breaking change (provider Protocol) | Düşük | Yüksek | 8 | Backward compat: eski method korunuyor |

---

## 9. ZAMAN ÇİZELGESİ

```
Hafta 1:     PR0 (Runtime Seam Extraction) ◄── BLOCKER
Hafta 2:     PR1 (Structured Output) + PR2 (Retry) [paralel]
Hafta 3:     PR3 (Tool Calling) + PR4a (Capability Manifest) [paralel]
Hafta 4:     PR4b (Invocation Unification) + PR5 (Token Counting) [paralel]
Hafta 5:     PR6 (Eval Harness) + PR7 (Prompt Registry) [paralel]
Hafta 6:     Entegrasyon test + stabilizasyon + edge case

--- Faz 2 (ihtiyaç bazlı) ---
+1-2 hafta:  PR8 (Streaming) | PR9 (Moderation) | PR10 (RAG v1)
```

---

## 10. BAŞARI KRİTERLERİ

| # | Kriter | Hedef | Ölçüm |
|---|---|---|---|
| BK-1 | Mevcut test regression | 0 kırılma | `pytest tests/ -x` |
| BK-2 | Yeni test coverage | >= 50 dosya, >= 150 case | pytest count |
| BK-3 | Schema validation | 0 hata | `ci/validate_schemas.py` |
| BK-4 | Dosya bütçesi | Her yeni dosya < 800 satır | `wc -l` |
| BK-5 | Runtime hotspot | < 800 satır (PR0 sonrası) | `wc -l` |
| BK-6 | Structured output | Claude Sonnet + OpenAI GPT-4o çalışıyor | Contract test |
| BK-7 | Retry | 429/5xx retry + circuit breaker aktif | Evidence log |
| BK-8 | Tool calling | Claude + OpenAI tool loop çalışıyor | Contract test |
| BK-9 | Token counting | tiktoken ±0, Anthropic API kesin | Contract test |
| BK-10 | Eval harness | 6 check + golden set regression | Golden set pass |
| BK-11 | Capability SSOT | Tek canonical registry, 0 drift | Drift check script |
| BK-12 | Backward compat | Tüm yeni özellikler enabled=false default | Policy check |
| BK-13 | Evidence trail | Her PR kendi evidence path'ini üretiyor | JSONL dosyaları |
| BK-14 | Dependency count | Faz 1: 2 paket (tenacity, tiktoken) | pyproject.toml |

---

## 11. KABUL TESTİ SENARYOLARI (end-to-end)

| # | Senaryo | Beklenen Sonuç |
|---|---|---|
| AT-1 | Tüm policy'ler default (enabled=false) | Sistem eski gibi çalışıyor, 0 değişiklik |
| AT-2 | Structured output ON, Claude Sonnet, valid schema | JSON response, schema-validated |
| AT-3 | Structured output ON, Claude Haiku (eski), valid schema | Regex fallback, schema-validated |
| AT-4 | retry_count=3, mock 429 2x, 3. success | 2 retry, success |
| AT-5 | retry_count=3, mock 401 | Anında fail, 0 retry |
| AT-6 | 5 ardışık fail, circuit open | 6. çağrı → CIRCUIT_OPEN |
| AT-7 | Tool calling ON, allowed_tools=["system-status"] | Tool dispatch + result |
| AT-8 | Tool calling ON, blocked tool | Block, evidence log |
| AT-9 | Tool loop, 3. round'da max_rounds | Loop kırılır, partial result |
| AT-10 | Token budget 1000, request 2000 token | TOKEN_BUDGET_EXCEEDED |
| AT-11 | Eval harness ON, hallucinated output | Groundedness fail, warn |
| AT-12 | Golden set regression | Önceki score vs current, delta rapor |

---

## 12. RACI

| | Human | Claude | Codex |
|---|---|---|---|
| Karar onay | **A** | R | C |
| Kod yazım | A | **R** | C (review) |
| Test yazım | A | **R** | C |
| PR review | **R** | C | I |
| Schema design | A | **R** | C |
| İstişare | A | **R** | **R** |

---

## 13. CORE LOCK NOTU

Tüm PR'lar `src/` yazımı yapıyor → `CORE_UNLOCK=1` + `CORE_UNLOCK_REASON` zorunlu.
Her PR'da unlock reason: `PRJ-LLM-CAPABILITIES PR<N>: <kısa açıklama>`

---

## 14. KARAR UYUM KONTROLU

- providers_registry `max_retries`/`rate_limit_rps` → artık canonical (tek SSOT)
- provider_capability_registry.v1.json → artık canonical capability SSOT (yeni registry oluşturulmadı)
- Tüm tool calling → ToolGateway typed allowlist, fail-closed, read-only default
- Eval harness → decision_quality.py'yi ilk kez çağırıyor (telemetry seed bağlandı)
- Prompt registry → experiment governance dahil (A/B, canary, shadow)
