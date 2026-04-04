# Context Engine v2 — Tam Otonom, Drift-Proof, Self-Evolving Bagam Sistemi

## Context (Neden Bu Degisiklik?)

Mevcut context sistemi **mimaride guclu, pratikte kirilgan**:
- Bootstrap tanimli ama calismasi zorlanmiyor — agent "kor" basliyor
- Kurallar 8+ kaynaga dagilmis — agent hangisini ne zaman yukleyecegini bilmiyor
- Domain-spesifik profil yok — frontend/backend/database yazarken ayni generic context
- Drift fix'i 6 kez tekrarlandi — yapisal cozum yok, yama bazli
- Context health reaktif — saglik kotuyken bile agent calisabiliyor
- Scope creep korumasiz — 3 dosya istendi 26 dosya yazildi
- Self-updating mekanizma yok — kurallar statik
- Profile resolver bug'li: `status` okuyor, `overall_status` degil (L46)
- rule_packet.v1.json paylasimli yol — multi-agent race condition
- Codex enforcement ayri kod yolunda — parity yok

**Hedef:** Her agent, her oturumda, dogru profil + dogru domain + dogru kurallar + dogru scope ile calisan, kendi kendini guncelleyen, drift-proof bir context sistemi.

## Codex Istisare Sonucu (Revizyonlar)

| # | Revizyon | Karar |
|---|---|---|
| R1 | context_compiler.py hem Claude hem Codex icin TEK assembly katmani | enforcement_pre_write + codex_enforcement_bridge tek compiler'i cagirsin |
| R2 | rule_packet → agent-scoped artifact | `rule_packet.{agent_id}.{hash}.v1.json` formatinda |
| R3 | Yeni dosya yerine mevcut overlap'leri genislet | bootstrap→check_context_bootstrap, quality→check_context_health, evolution→fact_evolution |
| R4 | Domain rule dosyalari `{domain}.md` formatinda | Mevcut loader `.claude/rules/{domain}.md` bekliyor; buna uyacagiz |
| R5 | policy_domain_conventions icin schema ekle | domain-conventions.schema.v1.json |
| R6 | constants.py + standards.lock birlikte guncelle | check_standards_lock_parts/constants.py da update |
| R7 | Profile resolver bug fix (overall_status + manual_request.kind) | Phase 0 prerequisite |
| R8 | context_engine_cmds.py yeni modul | context_cmds=863L, maintenance=962L dolmak uzere |
| R9 | ai-entry-pack-build komutunu manage.py'a register et | Mevcut eksik |

---

## PHASE 0: Prerequisite Bug Fixes (R7 + R9)
**Amac:** Diger phase'lerin ustune insa edecegi temeli saglamak.

### 0.1 Profile Resolver Bug Fix

**Dosya:** `src/ops/context_profile_resolver.py`

Bug (L46): `status.get("status", "OK")` → olmasi gereken: `status.get("overall_status") or status.get("status", "OK")`

Ek fix: `_gather_context_signals()` icine `manual_request.kind` yuklemesi ekle (su an hic yuklenmiyor; REVIEW/ASSESSMENT/PLANNING auto-resolution guvenilir degil).

**Degisiklik:** ~15 satir

### 0.2 ai-entry-pack-build Register

**Dosya:** `src/ops/manage.py`

`ai-entry-pack-build` komutu `src/ops/execution_target_ops.py:195`'te tanimli ama manage.py'a hic register edilmemis. Register ekle.

**Degisiklik:** ~3 satir

### 0.3 Tests

- `tests/contract/test_profile_resolver_signals.py` — overall_status dogru okunuyor, manual_request.kind yukleniyor

### 0.4 DoD

- [x] Profile resolver `overall_status` field'ini okuyor
- [x] `manual_request.kind` signal'i gather ediliyor
- [x] `ai-entry-pack-build` komutu manage.py'dan calistiriliyor
- [x] Contract test yesil (9/9 PASS)

---

## PHASE 1: Context Compiler & Bootstrap Gate
**Amac:** Agent calismayi baslatmadan once saglik kontrolu + derlenmmis kural paketi zorunlu hale gelsin.

### 1.1 Bootstrap Gate (Mevcut Dosya Genisletme — R3)

**Dosya:** `ci/check_context_bootstrap.py` (mevcut, ~160 lines → ~220 lines)

Mevcut yapi: 3 tier'li (STATUS, STRUCTURAL, PROJECT) dosya varlik/freshness/schema kontrolu.

Eklenecekler:
1. **Health gate**: `_compute_context_health_lens()` cagir, score >= 0.8 kontrol et
2. **Profile gate**: `resolve_profile()` cagir, profil cozumlenebiliyor mu kontrol et
3. **Gate result**: Her tier + health + profile sonuclarini birlestir
4. **Grace mode**: Ilk 2 cagrida WARN (agent calismaya devam), sonra BLOCK
5. **Session cache**: PASS sonucu `.cache/reports/bootstrap_evidence.v1.json`'a yazilir; ayni session icinde tekrar kontrol gerekmez

Yeni fonksiyonlar:
```python
def _check_health_gate(workspace_root: Path) -> dict:
    """Health score >= 0.8 required."""

def _check_profile_gate(workspace_root: Path) -> dict:
    """Profile resolution must succeed."""

def run_bootstrap_gate(repo_root, workspace_root, grace_count=2) -> dict:
    """Full gate: tiers + health + profile. Returns PASS/WARN/BLOCKED."""
```

Hook entegrasyonu (`.claude/settings.json`):
```json
{"matcher": "Bash", "hooks": [
  {"type": "preToolUse", "command": "python3 ci/check_context_bootstrap.py --gate --workspace-root .cache/ws_customer_default"}
]}
```

### 1.2 Context Compiler (Yeni — R1 TEK Assembly Katmani)

**Yeni dosya:** `src/ops/context_compiler.py` (~350 lines)

Her iki agent (Claude + Codex) icin TEK derleme noktasi. Mevcut `compile_rule_packet()` (enforcement_pre_write.py:53) ve `_compile_preflight()` (codex_enforcement_bridge.py:39) mantigi buraya tasinir.

```python
def compile_enforcement_context(
    *,
    workspace_root: Path,
    target_path: str,
    agent_id: str = "claude",  # "claude" | "codex"
    request_hash: str = "",    # R2: agent-scoped artifact
) -> dict:
    """Unified enforcement compiler for all agents."""
    # 1. Profile resolution (zorunlu, fallback yok)
    profile = resolve_profile(workspace_root)
    profile_id = profile["profile_id"]

    # 2. Rules digest (domain detection dahil)
    digest = compile_rules_digest(workspace_root=workspace_root, target_path=target_path)

    # 3. Write authorization
    auth = write_authorize(workspace_root=workspace_root, target_path=target_path)

    # 4. Provenance tracking — her kural icin kaynak + neden
    rules_with_provenance = _build_provenance(digest, profile_id)

    # 5. Agent-scoped artifact yolu (R2)
    artifact_path = _agent_scoped_path(workspace_root, agent_id, request_hash)

    # 6. Compile + write atomic
    result = {
        "version": "v1",
        "compiled_at": now_iso8601(),
        "agent_id": agent_id,
        "target_path": target_path,
        "profile": {"id": profile_id, "resolution_method": profile.get("resolution_method")},
        "authorization": auth,
        "rules": digest,
        "rules_with_provenance": rules_with_provenance,
        "compilation_sources": _list_sources(workspace_root),
    }
    write_json_atomic(artifact_path, result)
    return result
```

Agent-scoped artifact path (R2):
```
.cache/reports/rule_packet.{agent_id}.{hash8}.v1.json
Ornek: .cache/reports/rule_packet.claude.a1b2c3d4.v1.json
```

Provenance kaydi:
```json
{
  "rule_id": "R-src-ops-001",
  "text": "Use src.shared.utils for all JSON I/O",
  "source": ".claude/rules/src-ops.md:7",
  "domain": "src-ops",
  "why": "Prevents duplicate utility implementations, ensures atomic writes",
  "priority": "MUST"
}
```

### 1.3 Mevcut Pipeline Entegrasyonu (R1)

**Dosya:** `scripts/enforcement_pre_write.py` (~30 satir degisiklik)
- `compile_rule_packet()` (L53) icindeki dogrudan `resolve_profile + compile_rules_digest + write_authorize` cagrisi → `context_compiler.compile_enforcement_context()` ile degistirilir
- Eski fonksiyon backward-compat wrapper olarak kalir (deprecation notice)

**Dosya:** `scripts/codex_enforcement_bridge.py` (~20 satir degisiklik)
- `_compile_preflight()` (L39) → `context_compiler.compile_enforcement_context(agent_id="codex")` ile degistirilir
- `_build_enforcement_prompt_prefix()` compiler ciktisini kullanir

**Dosya:** `scripts/enforcement_post_write.py` (~5 satir degisiklik)
- `_PACKET_PATH` → agent-scoped path okumak icin guncellenir (en son yazilan packet'i bulur)

### 1.4 Command Registration (R8)

**Yeni dosya:** `src/ops/commands/context_engine_cmds.py` (~80 lines)
- `compile-context` komutu: `context_compiler.compile_enforcement_context()` CLI wrapper
- `bootstrap-gate` komutu: `check_context_bootstrap.run_bootstrap_gate()` CLI wrapper

**Dosya:** `src/ops/manage.py` — `register_context_engine_subcommands` import + register (~3 satir)

### 1.5 Schema

**Yeni schema:** `schemas/compiled-context.schema.v1.json` (~80 lines)
- Mevcut `rule-packet.schema.v1.json` ustune insa eder (superset)
- Ek field'lar: `agent_id`, `profile`, `rules_with_provenance[]`, `compilation_sources[]`

**Yeni schema:** `schemas/bootstrap-evidence.schema.v1.json` (~40 lines)
- `gate_result` (PASS/WARN/BLOCKED), `health_score`, `profile_id`, `tier_results[]`, `grace_count`

**Mevcut policy degisikligi:** `policies/policy_context_orchestration.v1.json`
- `bootstrap_gate_enabled: true`, `min_health_score: 0.8`, `grace_invocations: 2` ekle

### 1.6 Tests

- `tests/contract/test_context_compiler.py` — 8 kaynak derlenir, provenance kaydi, agent-scoped cikti
- `tests/contract/test_bootstrap_gate.py` — health >= 0.8 PASS, < 0.8 WARN(grace)/BLOCKED
- `tests/contract/test_compiled_context_schema.py` — schema validation

### 1.7 DoD

- [x] Bootstrap gate calisiyor: health < 0.8 → grace mode → BLOCKED
- [x] context_compiler.py TEK assembly katmani: Claude + Codex ayni fonksiyonu cagiriyor
- [x] Agent-scoped artifact: race condition yok (paralel test ile dogrulanmis — test_parallel_race_condition.py)
- [x] Her kural'da provenance: source + why + domain + priority
- [x] Schema validation geciyor
- [x] Mevcut enforcement_pre_write + codex_enforcement_bridge compiler uzerinden calisiyor
- [x] Contract testler yesil (3 dosya + 2 e2e)

### 1.8 Riskler

| Risk | Etki | Mitigation |
|------|------|-----------|
| Bootstrap gate agent'i bloklayabilir | Agent hic calismaz | Grace mode: ilk 2 cagrida WARN |
| Compilation suresi uzun | Her write oncesi yavaslama | Fingerprint cache: ayni input = ayni cikti |
| Python 3.9 uyumsuzlugu (worktree) | tomllib import hatasi | `try: import tomllib except: import tomli` |
| Manage.py eager import zinciri | Yeni komut kaydi patlayabilir | Lazy import pattern (context_engine_cmds icinde) |

---

## PHASE 2: Domain Scope Engine
**Amac:** Dosya path'inden ve icerikten otomatik domain tespiti + domain-spesifik konvansiyon yukleme.

### 2.1 Domain Scope Detector

**Yeni dosya:** `src/ops/domain_scope_engine.py` (~250 lines)

6 domain:
```python
DOMAIN_SCOPES = {
    "frontend": {
        "globs": ["**/*.tsx", "**/*.jsx", "**/*.vue", "**/*.css", "**/*.scss",
                  "web/**", "apps/**", "**/components/**", "**/pages/**"],
        "keywords": ["import React", "from 'react'", "defineComponent", "@mfe/design-system"],
        "rules_domain": "frontend"  # → .claude/rules/frontend.md
    },
    "backend": {
        "globs": ["**/*.py", "src/**", "services/**"],
        "keywords": ["import flask", "import fastapi", "from src."],
        "rules_domain": "backend"
    },
    "database": {
        "globs": ["**/*.sql", "db/**", "migrations/**"],
        "keywords": ["SELECT", "CREATE TABLE", "ALTER TABLE", "INSERT INTO"],
        "rules_domain": "database"
    },
    "accounting": {
        "globs": ["**/account*", "**/budget*", "**/muhasebe*", "**/hesap*"],
        "keywords": ["ACCOUNT_PLAN", "ACCOUNT_CARD", "BUDGET_PLAN"],
        "rules_domain": "accounting"
    },
    "api": {
        "globs": ["**/api/**", "**/routes/**", "**/endpoints/**"],
        "keywords": ["@app.route", "router.get", "openapi"],
        "rules_domain": "api"
    },
    "infra": {
        "globs": ["ci/**", "scripts/**", ".github/**", "docker*"],
        "keywords": ["workflow", "deploy", "pipeline"],
        "rules_domain": "infra"
    }
}
```

Detection:
1. Path-based: fnmatch ile glob eslestir
2. Content-based: keyword scan (opsiyonel, dosya mevcutsa)
3. Confidence scoring: 0.0-1.0; threshold >= 0.7 icin domain kurallarini yukle

Cikti: `{"detected_domains": ["frontend"], "primary_domain": "frontend", "confidence": 0.92}`

### 2.2 Domain Rule Dosyalari (R4: `{domain}.md` formati)

Mevcut loader `.claude/rules/{domain}.md` bekliyor. Yeni domain'ler ayni formatta:

- `.claude/rules/frontend.md` (~80 lines)
  - @mfe/design-system zorunlu, external dep yasak (antd, @mui, recharts, chart.js, d3)
  - Vite bundler (webpack degil), i18n pre-bundle yasagi
  - AG Grid 34.3.1 pattern'lari
  - Component export pattern'lari (PageLayout, DetailDrawer, FormDrawer)
  - **Dev repo'dan cikarilacak:** package.json deps, vite.config.ts, tsconfig paths

- `.claude/rules/backend.md` (~50 lines)
  - Python type hints zorunlu, src.shared.utils import zorunlu
  - Keycloak = login only, authorization via OpenFGA (permission-service)
  - Script budget (soft 1200, hard 2000)
  - **Dev repo'dan cikarilacak:** service yapi, middleware, auth akisi

- `.claude/rules/database.md` (~50 lines)
  - Workcube 3-tier: shared > company > yearly
  - DashboardQueryEngine: no alias on source, qualify ambiguous columns
  - SchemaLens API (port 8096) table discovery
  - **Dev repo'dan cikarilacak:** aktif tablo listesi, connection pattern'lari

- `.claude/rules/accounting.md` (~40 lines)
  - Tekduzen Hesap Plani, ACCOUNT_PLAN/CARD/CARD_ROWS, BUDGET_PLAN_ROW
  - Mali yil partition kurallari
  - **Dev repo'dan cikarilacak:** hesap hierarchi, muhasebe akisi

- `.claude/rules/api.md` (~40 lines)
  - REST conventions, versioning, OpenAPI uyumu
  - **Dev repo'dan cikarilacak:** endpoint listesi, middleware chain

### 2.3 compile_rules_digest Entegrasyonu (R4)

**Dosya:** `src/ops/compile_rules_digest.py` (~40 satir degisiklik)

`_DOMAIN_MAP` genisletme (mevcut domain ID'ler korunur, yeniler eklenir):
```python
# Mevcut: (korunuyor)
(re.compile(r"^src/ops/"), "src-ops"),
(re.compile(r"^schemas/"), "schemas"),
...

# Yeni domain scope ekleme (R4):
(re.compile(r"^web/"), "frontend"),
(re.compile(r"^apps/"), "frontend"),
(re.compile(r".*\.tsx$"), "frontend"),
(re.compile(r".*\.jsx$"), "frontend"),
(re.compile(r"^services/"), "backend"),
(re.compile(r"^db/"), "database"),
(re.compile(r"^migrations/"), "database"),
(re.compile(r".*\.sql$"), "database"),
(re.compile(r".*account.*"), "accounting"),
(re.compile(r"^api/"), "api"),
```

Onemli: Mevcut testler `src-ops` ve `cross-repo` bekliyor — bu degerleri KORUYOR olacagiz.

`_load_domain_rules()` (L99-116) zaten `.claude/rules/{domain}.md` yukluyor — yeni dosyalar otomatik yuklenecek.

### 2.4 Domain Convention Policy + Schema (R5)

**Yeni policy:** `policies/policy_domain_conventions.v1.json` (~100 lines)
```json
{
  "version": "v1",
  "domains": {
    "frontend": {
      "forbidden_imports": ["antd", "@ant-design/icons", "@mui/material", "recharts"],
      "required_package": "@mfe/design-system",
      "bundler": "vite",
      "rules_file": ".claude/rules/frontend.md"
    },
    "backend": {
      "required_imports": ["src.shared.utils"],
      "forbidden_patterns": ["print()", "open(.*json.*)"],
      "rules_file": ".claude/rules/backend.md"
    },
    "database": {
      "query_rules": {"no_alias_source": true, "qualify_ambiguous": true},
      "tier_model": "shared > company > yearly",
      "rules_file": ".claude/rules/database.md"
    }
  },
  "detection": {
    "confidence_threshold": 0.7,
    "max_rules_per_domain": 20
  }
}
```

**Yeni schema:** `schemas/domain-conventions.schema.v1.json` (~60 lines)
**Yeni schema:** `schemas/domain-scope-result.schema.v1.json` (~50 lines)

### 2.5 Context Compiler Entegrasyonu

**Dosya:** `src/ops/context_compiler.py` (Phase 1)
- `compile_enforcement_context()` icine domain detection cagir
- Domain-spesifik kurallar `rules_with_provenance[]`'a dahil et
- Ciktiya `domain_scope` section'i ekle

### 2.6 Dev Repo Analiz Adimi (Phase 2 oncesi)

Dev repo (`/Users/halilkocoglu/Documents/dev`) analiz edilecek dosyalar:
- `package.json` — dependencies, scripts
- `vite.config.ts` — bundler config
- `tsconfig.json` — TypeScript paths
- `web/apps/mfe-shell/` — shell architecture
- `services/` — backend service yapisi
- `db/` veya `migrations/` — database schema pattern'lari

### 2.7 Tests

- `tests/contract/test_domain_scope_engine.py` — 6 domain path detection, confidence scoring
- `tests/contract/test_domain_conventions_policy.py` — policy schema validation
- `tests/contract/test_domain_rules_loading.py` — .claude/rules/{domain}.md yukleme

### 2.8 DoD

- [x] 6 domain otomatik tespit ediliyor (frontend, backend, database, accounting, api, infra)
- [x] Mevcut domain ID'ler korunuyor (src-ops, schemas, policies, ci, ...)
- [x] Confidence >= 0.7 icin domain kurallar yukleniyor
- [x] 6 domain convention dosyasi `.claude/rules/{domain}.md` formatinda (infra dahil)
- [x] policy_domain_conventions.v1.json schema-valid (R5)
- [x] compile_rules_digest genisletilmis domain map calisiyor
- [x] Mevcut testler kirilmadan geciyor
- [x] Yeni contract testler yesil (26/26)

### 2.9 Riskler

| Risk | Etki | Mitigation |
|------|------|-----------|
| Yanlis domain tespiti | Yanlis kurallar | Confidence threshold (0.7) + multi-domain |
| Dev repo path'leri farkli | Glob'lar eslesmez | DOMAIN_SCOPES policy'den configure edilebilir |
| Mevcut testler kirilir | Regression | Mevcut domain ID'leri korumak zorunlu |

---

## PHASE 3: Enhanced Pre-Write Pipeline
**Amac:** Scope korumasi, domain konvansiyon enjeksiyonu, etki analizi.

### 3.1 Scope Guard

**Yeni dosya:** `src/ops/scope_guard.py` (~200 lines)

```python
def init_scope(session_id: str, declared_files: list[str], max_files: int = 5) -> dict:
    """Oturum baslangicinda scope bildir."""

def check_scope(session_id: str, new_file: str) -> dict:
    """Her write oncesi scope kontrol et. WITHIN/WARN/BLOCK dondur."""

def expand_scope(session_id: str, reason: str) -> dict:
    """Kullanici onayi ile scope genislet."""
```

Threshold'lar:
- files_count > declared * 2 → WARN
- files_count > declared * 3 → BLOCK (kullanici onay gerekli)
- Yeni domain'e gecis → WARN ("Frontend'e de dokunuyorsunuz")

State: `.cache/reports/scope_guard_state.v1.json`

### 3.2 Impact Analyzer

**Yeni dosya:** `src/ops/impact_analyzer.py` (~200 lines)

```python
def analyze_impact(workspace_root: Path, target_path: str, max_depth: int = 3) -> dict:
    """Basit grep-based import chain traversal. Embedding yok."""
```

Cikti:
```json
{
  "target": "src/ops/context_compiler.py",
  "direct_importers": ["scripts/enforcement_pre_write.py"],
  "direct_imports": ["src.ops.compile_rules_digest"],
  "affected_tests": ["tests/contract/test_context_compiler.py"],
  "affected_count": 3,
  "risk_level": "LOW"
}
```

Risk: LOW (0-3), MEDIUM (4-8), HIGH (9+), CRITICAL (20+)

### 3.3 Convention Injection + Compiler Entegrasyonu

**Dosya:** `src/ops/context_compiler.py` — `compile_enforcement_context()` ciktisina ekleme:
```json
{
  "conventions": [
    {"id": "CONV-FE-001", "text": "@mfe/design-system ONLY", "domain": "frontend"}
  ],
  "scope_check": {"status": "WITHIN_SCOPE", "files_remaining": 3},
  "impact": {"affected_count": 2, "risk_level": "LOW"}
}
```

**Dosya:** `scripts/enforcement_pre_write.py` — compiler ciktisindaki scope_check ve impact'i hook response'a dahil et

### 3.4 Schema & Policy

**Yeni schema:** `schemas/scope-guard-state.schema.v1.json` (~50 lines)
**Yeni schema:** `schemas/impact-analysis.schema.v1.json` (~40 lines)
**Yeni policy:** `policies/policy_scope_guard.v1.json` (~40 lines)

### 3.5 Tests

- `tests/contract/test_scope_guard.py` — scope exceed WARN/BLOCK
- `tests/contract/test_impact_analyzer.py` — import chain traversal
- `tests/contract/test_convention_injection.py` — domain-correct conventions

### 3.6 DoD

- [x] Scope guard: 3x asimda BLOCK, domain degisimde WARN
- [x] Impact analizi: max_depth=3 grep-based traversal
- [x] Convention injection: domain-dogru conventions rule_packet'te
- [x] Compiler ciktisi tam: rules + conventions + scope + impact
- [x] Contract testler yesil (25/25)

---

## PHASE 4: Context Quality & Observability
**Amac:** Bagam kalitesini olcmek, izlemek, erken uyari vermek.

### 4.1 Context Quality Scorer (Mevcut Genisletme — R3)

**Dosya:** `scripts/check_context_health.py` + `src/benchmark/eval_runner_runtime.py`

Mevcut 6 component'e 3 yeni eklenir:

7. **Rule Relevance** (0-20): Yuklenen kurallardan kaci uygulanma/violation gosterdi?
8. **Token Efficiency** (0-20): compiled_context boyutu / max_context_pack_bytes
9. **Cache Hit Rate** (0-20): Session boyunca compilation cache hit orani

`_compute_context_health_lens()` genisletilir → 9 component, max 180 puan, 0-1'e normalize.

### 4.2 Session Metrics Aggregator

**Yeni dosya:** `src/ops/context_session_metrics.py` (~200 lines)

```python
def record_metric(workspace_root: Path, metric_type: str, value: Any) -> None:
    """Tek metrik kaydet (append-only JSONL)."""

def aggregate_session_metrics(workspace_root: Path, session_id: str) -> dict:
    """Oturum sonu metrik ozeti."""
```

Toplanan metrikler:
- total_writes, rules_applied, rules_violated, rules_never_used
- scope_warnings, scope_blocks, domain_switches
- cache_hits, cache_misses, cache_hit_rate
- avg_compilation_ms, health_score_start/end
- quality_trend: IMPROVING / STABLE / DEGRADING

State: `.cache/reports/context_session_metrics.v1.jsonl` (append-only)

### 4.3 Drift Early Warning

**Dosya:** `src/ops/context_drift.py` — mevcut genisletme (~30 satir)
- cache_hit_rate < 0.5 → WARN
- cache_hit_rate < 0.3 → ALERT + auto re-compilation tetikle
- quality_trend == DEGRADING → uyari

### 4.4 Schema & Policy

**Yeni schema:** `schemas/context-session-metrics.schema.v1.json` (~60 lines)
**Yeni policy:** `policies/policy_context_quality.v1.json` (~40 lines)

### 4.5 Tests

- `tests/contract/test_context_quality_scorer.py` — 9 component hesaplama
- `tests/contract/test_session_metrics.py` — metrik aggregation
- `tests/contract/test_drift_early_warning.py` — threshold alerts

### 4.6 DoD

- [x] 9 component health score (mevcut 6 + 3 yeni)
- [x] Session metrikleri JSONL olarak toplaniyoir
- [x] Cache hit rate tracking aktif
- [x] Drift early warning: DEGRADING trend tetikliyor
- [x] Contract testler yesil (12/12)

---

## PHASE 5: Self-Evolving Context (ACE Pattern)
**Amac:** Context'in kendi kendini iyilestirmesi — tam otonom.

### 5.1 Rule Effectiveness Tracker

**Yeni dosya:** `src/ops/rule_effectiveness.py` (~200 lines)

```python
def track_rule_usage(workspace_root: Path, rule_id: str, action: str) -> None:
    """Kural kullanim kaydi: 'loaded', 'applied', 'violated', 'ignored'."""

def compute_effectiveness(workspace_root: Path) -> list[dict]:
    """Tum kurallar icin effectiveness score hesapla."""
```

Classification:
- HOT (effectiveness >= 0.7): Her zaman yukle
- WARM (0.3-0.7): Domain/profile eslestiginde yukle
- COLD (< 0.3): Prune adayi
- DEAD (0 usage in 30+ sessions): Otomatik arsivle

State: `.cache/reports/rule_effectiveness.v1.json`

### 5.2 Context Evolution Engine (Mevcut Genisletme — R3)

**Dosya:** `src/ops/fact_evolution.py` (mevcut, ~93 lines → ~250 lines)

Mevcut: decision regression detection + change frequency.
Eklenecek: ACE produce-reflect-curate dongusu.

```python
def run_evolution_cycle(workspace_root: Path) -> dict:
    """ACE dongusu: produce → reflect → curate."""

def auto_apply_proposal(workspace_root: Path, proposal: dict) -> dict:
    """Confidence >= 0.9 olan proposal'lari otomatik uygula."""
```

Otomasyon kurali (TAM OTONOM):
- confidence >= 0.9 → otomatik uygula (prune/promote/demote) + evidence log
- confidence 0.7-0.9 → otomatik uygula + geri alinabilir evidence
- confidence < 0.7 → insan onayina sun (CHG sureci)
- Yeni kural (add): confidence >= 0.9 VE 3+ session tekrarlayan violation → otomatik

Evolution proposal:
```json
{
  "proposal_id": "EVO-20260404-001",
  "type": "prune|add|modify|promote|demote",
  "target_rule": "R-src-ops-001",
  "reason": "Applied 0 times in 20 sessions",
  "confidence": 0.92,
  "auto_applied": true,
  "rollback_ref": "EVO-20260404-001.rollback.v1.json"
}
```

### 5.3 Hot/Warm/Cold Memory Tiers

**Yeni policy:** `policies/policy_context_memory_tiers.v1.json` (~60 lines)
```json
{
  "tiers": {
    "hot": {"always_load": true, "max_rules": 30, "min_effectiveness": 0.7},
    "warm": {"load_on_match": true, "max_rules": 50, "min_effectiveness": 0.3},
    "cold": {"load_on_demand": true, "archive_after_sessions": 30}
  },
  "auto_evolution": {
    "enabled": true,
    "auto_apply_threshold": 0.9,
    "auto_apply_with_rollback_threshold": 0.7,
    "manual_review_below": 0.7
  }
}
```

### 5.4 Schema

**Yeni schema:** `schemas/rule-effectiveness.schema.v1.json` (~50 lines)
**Yeni schema:** `schemas/context-evolution-proposal.schema.v1.json` (~50 lines)

### 5.5 Tests

- `tests/contract/test_rule_effectiveness.py` — scoring, HOT/WARM/COLD/DEAD classification
- `tests/contract/test_context_evolution.py` — ACE cycle, auto-apply, rollback
- `tests/contract/test_memory_tiers.py` — tier policy enforcement

### 5.6 DoD

- [x] Rule effectiveness tracking: load/apply/violate/ignore sayaci
- [x] HOT/WARM/COLD/DEAD classification calisiyor
- [x] Evolution proposal uretiliyor
- [x] confidence >= 0.9 otomatik uygulaniyor + rollback ref
- [x] DEAD kurallar otomatik arsiveleniyor
- [x] fact_evolution.py mevcut testler hala geciyor
- [x] Contract testler yesil (19/19)

---

## PHASE 6: Cross-Agent Context Continuity
**Amac:** Agent'lar arasi context el degistirme, consultation aktif hale getirme.

### 6.1 Enhanced AI Entry Pack (R9 register + enhancement)

**Dosya:** `src/ops/ai_entry_pack_build.py` (~40 satir ekleme)

Yeni field'lar:
```json
{
  "compiled_context_ref": ".cache/reports/rule_packet.claude.latest.v1.json",
  "active_profile": {"id": "TASK_EXECUTION", "resolution_method": "auto"},
  "pending_consultations": [],
  "last_session_decisions": [...],
  "scope_state": {"status": "WITHIN_SCOPE"},
  "quality_snapshot": {"score": 0.87, "grade": "B", "trend": "IMPROVING"}
}
```

### 6.2 Consultation Protocol Wiring

**Dosya:** `ci/check_context_bootstrap.py` (Phase 1'de genisletilmis)
- Bootstrap sirasinda consultation queue kontrol et (AGENTS.md Step 0.5 uyumu)
- Acik consultation varsa ve `to_agent == current_agent` → cevap hazirlanmasi gerektigi rapor et

### 6.3 Context Snapshot for Handoff

**Yeni dosya:** `src/ops/context_snapshot.py` (~150 lines)

```python
def create_snapshot(workspace_root: Path, from_agent: str, to_agent: str) -> dict:
    """Agent handoff icin context snapshot olustur."""
```

Snapshot:
```json
{
  "snapshot_id": "SNAP-20260404-001",
  "from_agent": "claude",
  "to_agent": "codex",
  "compiled_context_hash": "a1b2c3d4",
  "active_profile": "TASK_EXECUTION",
  "domain_scope": {"primary": "frontend"},
  "key_decisions": [...],
  "scope_state": {...},
  "quality_metrics": {...},
  "pending_work": [...]
}
```

### 6.4 Schema

**Yeni schema:** `schemas/context-snapshot.schema.v1.json` (~60 lines)

### 6.5 Tests

- `tests/contract/test_ai_entry_pack_v2.py` — enhanced fields mevcut
- `tests/contract/test_consultation_wiring.py` — bootstrap'ta queue kontrol
- `tests/contract/test_context_snapshot.py` — handoff snapshot

### 6.6 DoD

- [x] AI entry pack enhanced: profile + consultations + quality (context_continuity section)
- [x] Consultation queue bootstrap'ta kontrol ediliyor (context_snapshot._find_pending_consultations)
- [x] Context snapshot handoff sirasinda uretiliyor
- [x] Cross-agent context kaybi yok (snapshot + entry pack + agent-scoped artifacts)
- [x] Contract testler yesil (6/6)

---

## PHASE X: Standards Lock & CI Update (R6 — Her Phase Sonunda)

Her phase sonunda:

### Standards Lock

**Dosya:** `standards.lock` — `required_files` ve `required_commands` guncelle
**Dosya:** `ci/check_standards_lock_parts/constants.py` — `REQUIRED_FILES`, `REQUIRED_COMMANDS`, `REQUIRED_GATES` guncelle

### CI Workflow

**Dosya:** `.github/workflows/gate-enforcement-check.yml` — yeni step'ler:
- Phase 1 sonrasi: `bootstrap-gate` step
- Phase 2 sonrasi: `domain-scope-validation` step
- Phase 4 sonrasi: `context-quality-report` step

**Dosya:** `.github/workflows/gate-contract-tests.yml` — yeni test suite'ler ekleme

### Policy Dry-Run Fixtures

**Dosya:** `fixtures/envelopes/` — domain_conventions policy icin test envelope'lari

---

## Implementation Siralama

```
Phase 0 ←── prerequisite bug fixes (profile resolver + ai-entry-pack register)
  ↓
Phase 1 ←── bootstrap gate + compiler (TEK assembly katmani)
  ↓
Phase 2 ←── domain scope engine (compiler'a domain ekler)
  ↓
Phase 3 ←── scope guard + impact analyzer (compiler ciktisini genisletir)
  ↓
Phase 4 ←── quality scorer + metrics (Phase 1-3 ciktilarini olcer)
  ↓
Phase 5 ←── self-evolving context (Phase 4 metriklerini kullanir)
  ↓
Phase 6 ←── cross-agent continuity (tum Phase'leri paketler)
```

Her phase bagimsiz deploy edilebilir. Phase X (standards + CI) her phase sonunda uygulanir.

---

## Toplam Deliverables

### Yeni Dosyalar (12)
| Dosya | Phase | ~Lines |
|-------|-------|--------|
| `src/ops/context_compiler.py` | 1 | 350 |
| `src/ops/commands/context_engine_cmds.py` | 1 | 80 |
| `schemas/compiled-context.schema.v1.json` | 1 | 80 |
| `schemas/bootstrap-evidence.schema.v1.json` | 1 | 40 |
| `src/ops/domain_scope_engine.py` | 2 | 250 |
| `policies/policy_domain_conventions.v1.json` | 2 | 100 |
| `schemas/domain-conventions.schema.v1.json` | 2 | 60 |
| `schemas/domain-scope-result.schema.v1.json` | 2 | 50 |
| `.claude/rules/frontend.md` | 2 | 80 |
| `.claude/rules/backend.md` | 2 | 50 |
| `.claude/rules/database.md` | 2 | 50 |
| `.claude/rules/accounting.md` | 2 | 40 |
| `.claude/rules/api.md` | 2 | 40 |
| `src/ops/scope_guard.py` | 3 | 200 |
| `src/ops/impact_analyzer.py` | 3 | 200 |
| `schemas/scope-guard-state.schema.v1.json` | 3 | 50 |
| `schemas/impact-analysis.schema.v1.json` | 3 | 40 |
| `policies/policy_scope_guard.v1.json` | 3 | 40 |
| `src/ops/context_session_metrics.py` | 4 | 200 |
| `schemas/context-session-metrics.schema.v1.json` | 4 | 60 |
| `policies/policy_context_quality.v1.json` | 4 | 40 |
| `src/ops/rule_effectiveness.py` | 5 | 200 |
| `schemas/rule-effectiveness.schema.v1.json` | 5 | 50 |
| `schemas/context-evolution-proposal.schema.v1.json` | 5 | 50 |
| `policies/policy_context_memory_tiers.v1.json` | 5 | 60 |
| `src/ops/context_snapshot.py` | 6 | 150 |
| `schemas/context-snapshot.schema.v1.json` | 6 | 60 |

### Mevcut Dosya Degisiklikleri (14)
| Dosya | Phase | Degisiklik |
|-------|-------|-----------|
| `src/ops/context_profile_resolver.py` | 0 | Bug fix: overall_status + manual_request.kind |
| `src/ops/manage.py` | 0,1 | ai-entry-pack register + context_engine_cmds register |
| `ci/check_context_bootstrap.py` | 1 | Health gate + profile gate + grace mode |
| `scripts/enforcement_pre_write.py` | 1,3 | Compiler entegrasyonu + scope/impact |
| `scripts/codex_enforcement_bridge.py` | 1 | Compiler entegrasyonu |
| `scripts/enforcement_post_write.py` | 1 | Agent-scoped packet path |
| `.claude/settings.json` | 1 | Bootstrap hook |
| `policies/policy_context_orchestration.v1.json` | 1 | bootstrap_gate_enabled |
| `src/ops/compile_rules_digest.py` | 2 | Domain map genisletme |
| `src/ops/context_drift.py` | 4 | Metric-driven early warning |
| `src/benchmark/eval_runner_runtime.py` | 4 | 3 yeni health component |
| `src/ops/fact_evolution.py` | 5 | ACE cycle + auto-evolution |
| `src/ops/ai_entry_pack_build.py` | 6 | Enhanced fields |
| `standards.lock` + `constants.py` | X | Her phase sonunda |

### Test Dosyalari (21)
| Phase | Testler |
|-------|---------|
| 0 | test_profile_resolver_signals.py |
| 1 | test_context_compiler.py, test_bootstrap_gate.py, test_compiled_context_schema.py |
| 2 | test_domain_scope_engine.py, test_domain_conventions_policy.py, test_domain_rules_loading.py |
| 3 | test_scope_guard.py, test_impact_analyzer.py, test_convention_injection.py |
| 4 | test_context_quality_scorer.py, test_session_metrics.py, test_drift_early_warning.py |
| 5 | test_rule_effectiveness.py, test_context_evolution.py, test_memory_tiers.py |
| 6 | test_ai_entry_pack_v2.py, test_consultation_wiring.py, test_context_snapshot.py |

---

## Verification Plan

Her phase sonunda:
1. `python3 ci/validate_schemas.py` — yeni schemalar valid
2. `pytest tests/contract/ -x` — tum contract testler yesil
3. `python3 -m src.ops.manage compile-context --workspace-root .cache/ws_customer_default` — compiler calisiyor
4. `python3 ci/check_context_bootstrap.py --gate --workspace-root .cache/ws_customer_default` — gate calisiyor
5. `python3 -m src.ops.manage enforcement-check --profile default` — regression yok

End-to-end (Phase 3 sonrasi):
1. Bir dosya yaz → rule_packet'te domain + conventions + scope + impact
2. Scope asimi → WARN/BLOCK
3. Health < 0.8 → bootstrap gate BLOCKED (grace sonrasi)
4. Paralel agent yazimi → agent-scoped artifact, corruption yok

## Rakiplerden Alinan Best Practices

| Best Practice | Kaynak | Phase |
|---|---|---|
| Glob-based rule auto-attach | Cursor .mdc | 2 (domain globs) |
| Hot/warm/cold memory | Codified Context paper | 5 (memory tiers) |
| KV-cache hit rate tracking | Manus | 4 (cache metrics) |
| ACE produce-reflect-curate | ACE paper | 5 (evolution engine) |
| Spec-driven development | Kiro | 1 (schema-first) |
| Repo-map lightweight indexing | Aider | 3 (impact analyzer) |
| Self-improving rules | Cursor | 5 (rule effectiveness) |
| Single compiled context | Augment Code | 1 (context compiler) |
| Agent-scoped artifacts | Devin 2.0 | 1 (race condition fix) |
