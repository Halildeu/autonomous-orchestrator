# AGENTS.md (Managed Repo — SSOT)

Bu repo, **ana orchestrator repo** tarafından yönetilen (taşeron) bir repodur.
Canonical instruction kaynağı: ana repo'daki `AGENTS.md` + bu dosya.

## Customer-friendly mode (MUST)

- Kullanıcı asla shell komutu yazmaz; doğal dille ister.
- Agent, işi **ops komutları** üzerinden yürütür.
- Varsayılan workspace root: `.cache/ws_customer_default` (yoksa agent `workspace-bootstrap` ile oluşturur).
- Agent her cevapta **AUTOPILOT CHAT** formatını kullanır: `PREVIEW / RESULT / EVIDENCE / ACTIONS / NEXT`.
- Fail-closed: şüphede dur, `report_only`/no-side-effect yönünde davran; network default kapalıdır.
- Secrets asla log'a/evidence'a yazılmaz; token/anahtar basılmaz.

## SSOT Entrypoint Map / Router

### Standards & Governance (ana repo'dan sync)
- `standards.lock` — sync edilen standart dosya listesi
- `docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md` — multi-repo operasyon kontratı
- `docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md` — mimari kısıtlar
- `policies/` — policy dosyaları (ana repo'dan sync)
- `schemas/` — JSON Schema dosyaları (ana repo'dan sync)
- `registry/technical_baseline.aistd.v1.json` — teknik standart baseline

### Module Delivery (repo-specific)
- `ci/module_delivery_lanes.v1.json` — bu repo'ya özel lane konfigürasyonu
- `.github/workflows/module-delivery-lanes.yml` — CI pipeline
- `.github/workflows/gate-enforcement-check.yml` — enforcement gate

### Extension Contracts (ana repo'dan sync)
- `extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json` — feature execution
- `extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json` — UX katalogu lock

## Multi-Agent (shared context)

Bu repo birden fazla agent tarafından yönetilir. Tüm agent'lar **bu AGENTS.md dosyasını** tek canonical instruction kaynağı olarak kullanır.

### Aktif Agent'lar
| Agent | Provider | Config | Çalışma Modu |
|---|---|---|---|
| **Codex** | OpenAI (gpt-5.3-codex effective runtime overlay) | `.codex/config.toml` | Sandbox (workspace-write) |
| **Antigravity** | Google DeepMind (Gemini) | `.gemini/settings.json` | IDE (yerel dosya sistemi) |

### Ortak Kurallar
- Tüm agent'lar aynı ops komut setini kullanır.
- Tüm agent'lar aynı SSOT router'ı (bu dosya) takip eder.
- Tüm agent'lar aynı bağlam kaynaklarını okur (aşağıdaki Context Bootstrap).
- Core_lock, fail-closed, secrets kuralları tüm agent'lar için geçerlidir.
- Agent çıktıları AUTOPILOT CHAT formatındadır: `PREVIEW / RESULT / EVIDENCE / ACTIONS / NEXT`.

## Context Bootstrap (her konuşma başında)

Agent çalışmaya başladığında, aşağıdaki bağlam dosyalarını sırasıyla yükler:

### 1. Durum Bağlamı (en güncel hal)
- `.cache/ws_customer_default/.cache/reports/system_status.v1.json` — sistem durumu
- `.cache/ws_customer_default/.cache/reports/portfolio_status.v1.json` — portföy durumu

### 2. Yapısal Bağlam (SSOT)
- `AGENTS.md` — canonical instruction + router (bu dosya)
- `standards.lock` — governance standartları

### 3. Governance Bağlamı (ana repo'dan sync)
- `docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md` — multi-repo kontrat
- `docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md` — mimari kısıtlar

## Doğrulama (agent tarafından çalıştırılır)

- Şema kontrolü: `python ci/validate_schemas.py`
- Standards lock: `python3 ci/check_standards_lock.py --repo-root .`
- Module delivery: `python3 ci/check_module_delivery_lanes.py --strict`

## Repo conventions

- JSON artefact'lar: `schemas/`, `policies/`, `registry/` altında tutulur.
- Versiyonlu dosyalar: `*.v1.json` gibi adlandırılır. JSON Schema dosyaları: `*.schema.json`.
- JSON formatı: 2 boşluk indent, UTF-8, gereksiz trailing whitespace yok.
- Secrets: credential / token / private key commit edilmez. CI'da env/secret ile geçilir.

## Sync Metadata

- **Source**: Ana orchestrator repo (`standards.lock`)
- **Sync script**: `scripts/sync_managed_repo_standards.py`
- **Sync mode**: dry-run (default), `--apply` ile uygula
