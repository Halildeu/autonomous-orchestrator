# AGENTS.md (SSOT)

Bu repo "JSON‑first" bir orchestrator iskeleti (WWV) olarak tasarlanır.

## Customer-friendly mode (MUST)

- Kullanıcı asla shell komutu yazmaz; kullanıcı yalnızca doğal dille ister ("Devam et", "Duraklat", "Rapor üret").
- Agent, işi **ops komutları** üzerinden yürütür (ör. `roadmap-status/finish/pause/resume`, `policy-check`, `script-budget`) ve kullanıcıdan komut istemez.
- Varsayılan workspace root: `.cache/ws_customer_default` (yoksa agent `workspace-bootstrap` ile oluşturur).
- Agent her cevapta **AUTOPILOT CHAT** formatını kullanır: `PREVIEW / RESULT / EVIDENCE / ACTIONS / NEXT`.
- Fail-closed: şüphede dur, `report_only`/no-side-effect yönünde davran; network default kapalıdır.
- Secrets asla log'a/evidence'a yazılmaz; token/anahtar basılmaz.
- Core vs workspace sınırı: core repo yazımı varsayılan olarak kapalıdır (fail-closed). Yalnızca CORE_UNLOCK=1 ve CORE_UNLOCK_REASON set ise, allowlist SSOT yollarına (schemas/, policies/, extensions/, `vendor_packs` altı semgrep klasörü, docs/OPERATIONS/, docs/ROADMAP.md, roadmaps/SSOT/roadmap.v1.json, docs/LAYER-MODEL-LOCK.v1.md, docs/OPERATIONS/SSOT-MAP.md, `.github` altı `gate-enforcement-check.yml`, .pre-commit-config.yaml, AGENTS.md) kanıt üreterek yazılabilir; aksi halde BLOCKED. src/** yazımı normalde YASAKTIR; istisna olarak ONE_SHOT_SRC_WINDOW aktifken sadece allow_paths + ttl_seconds içinde yazılabilir ve pencere sonunda restore kanıtı zorunludur.
- Living roadmap değişikliği: açık istenmedikçe sessizce SSOT edit yapmak yok; gerekiyorsa **Change Proposal (CHG)** üret.

## SSOT Entrypoint Map / Router (AGENTS-only entrypoint)

Bu repo'da fallback yalnızca **AGENTS.md** olduğu için, aşağıdaki liste **tek canonical yönlendirme rotasıdır**.
Agent, navigasyon ve karar bağlamı için önce bu listedeki dokümanları kullanır. Bu liste dışındaki linkler yardımcıdır; canonical değildir.

### SSOT & Navigation (canonical)
- docs/OPERATIONS/CODEX-UX.md (customer-friendly ops akışı)
- docs/OPERATIONS/CODEX-CONFIG-CONTRACT.v1.md (Codex config contract)
- docs/OPERATIONS/CODING-STANDARDS.md (zorunlu coding standartları ve shared utilities)
- docs/LAYER-MODEL-LOCK.v1.md (L0/L1/L2/L3 + core_lock protokolü)
- docs/ROADMAP.md (MIRROR human summary; canonical is `roadmaps/SSOT/roadmap.v1.json` — RM-SSOT-001)
- `docs/ROADMAP_v2.7_legacy.md` (archive only; do not follow)
- docs/OPERATIONS/repo-layout.md
- docs/OPERATIONS/repo-layout.v1.json
- docs/OPERATIONS/spec-core.md (CAPABILITY/KABİLİYET spec-core)
- docs/OPERATIONS/tags-registry.md (AUTOPILOT CHAT + status/action registry)
- docs/OPERATIONS/SSOT-MAP.md (kritik SSOT haritası)
- docs/OPERATIONS/EXTENSIONS.md (extension canonical doküman)
- roadmaps/SSOT/roadmap.v1.json (CANONICAL roadmap — RM-SSOT-001)
- roadmaps/PROJECTS/README.md (project roadmaps)
- roadmaps/PROJECTS/project-roadmap.template.v1.json (project template)
- roadmaps/PROJECTS/PRJ-KERNEL-API/contract.v1.md (project contract)
- schemas/system-status.schema.json
- policies/policy_system_status.v1.json
- src/ops/system_status_report.py
- src/ops/manage.py (ops entrypoint; project-status/system-status burada)
- src/ops/roadmap_cli.py (varsa: project-status / navigator wrapper)

### Operations SSOT (Kalıcı)


- docs/OPERATIONS/PROJECT-SSOT.md
- docs/OPERATIONS/OPERATIONS-CHEATSHEET.md
- docs/OPERATIONS/DECISION-POLICY.md
- docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md
- docs/OPERATIONS/CHATGPT-PLANNER-INSTRUCTIONS.v1.md
- docs/OPERATIONS/RUN-CARD-TEMPLATE.v1.md
- docs/OPERATIONS/NEW-CHAT-BOOTSTRAP.v1.md
### Operating rule (MUST)
- Program ops/gate/runner ile yönlendirir; agent yalnız plan/analiz/rapor üretir.
- Kullanıcı komut yazmaz.
- "Neredeyiz?" sorusunda tek kapı: **project-status** (yoksa **system-status** fallback).
- Doc navigation için tek kapı: doc-nav-check (summary default; detail/strict on-demand).
- Kullanıcıya yönelik arama (keyword/semantic) için ortak kanal: `scripts/codex-search` (altında `ops-search` → `/api/search`); böylece Cockpit ve agent'lar aynı arama hattını kullanır.

## Multi-Agent (shared context)

Bu repo birden fazla agent tarafından yönetilir. Tüm agent'lar **bu AGENTS.md dosyasını** tek canonical instruction kaynağı olarak kullanır.

### Aktif Agent'lar
| Agent | Provider | Config | Çalışma Modu |
|---|---|---|---|
| **Codex** | OpenAI (gpt-5.2-codex) | `.codex/config.toml` | Sandbox (workspace-write) |
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
- `.cache/reports/system_status.v1.json` — sistem durumu
- `.cache/reports/portfolio_status.v1.json` — portföy durumu
- `.cache/roadmap_state.v1.json` — roadmap ilerleme durumu

### 2. Yapısal Bağlam (SSOT)
- `AGENTS.md` — canonical instruction + router (bu dosya)
- `docs/OPERATIONS/CODEX-UX.md` — customer-friendly ops akışı
- `docs/LAYER-MODEL-LOCK.v1.md` — katman modeli

### 3. Proje Bağlamı (ihtiyaç halinde)
- `roadmaps/PROJECTS/*/project.manifest.v1.json` — proje manifestleri
- `roadmaps/SSOT/roadmap.v1.json` — canonical roadmap

### Bootstrap komutu (agent çalıştırır)
```
python -m src.ops.manage system-status --workspace-root .
python -m src.ops.manage portfolio-status --workspace-root .
```

## Repo conventions

- JSON artefact'lar: `schemas/`, `policies/`, `registry/`, `workflows/`, `orchestrator/` altında tutulur.
- Versiyonlu dosyalar: `*.v1.json` gibi adlandırılır. JSON Schema dosyaları: `*.schema.json`.
- JSON formatı: 2 boşluk indent, UTF‑8, gereksiz trailing whitespace yok.
- Secrets: credential / token / private key commit edilmez. CI'da env/secret ile geçilir.

## Doğrulama (agent tarafından çalıştırılır)

- Şema kontrolü: `python ci/validate_schemas.py`
- Dry-run simülasyon: `python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json`
- Policy-check: `python -m src.ops.manage policy-check --source both`
