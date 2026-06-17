# AGENTS.md (SSOT)

Bu repo "JSON‑first" bir orchestrator iskeleti (WWV) olarak tasarlanır.

## Customer-friendly mode (MUST)

- Kullanıcı asla shell komutu yazmaz; kullanıcı yalnızca doğal dille ister ("Devam et", "Duraklat", "Rapor üret").
- Agent, işi **ops komutları** üzerinden yürütür (ör. `roadmap-status/finish/pause/resume`, `policy-check`, `script-budget`) ve kullanıcıdan komut istemez.
- Varsayılan workspace root: `.cache/ws_customer_default` (yoksa agent `workspace-bootstrap` ile oluşturur).
- Agent her cevapta **AUTOPILOT CHAT** formatını kullanır: `PREVIEW / RESULT / EVIDENCE / ACTIONS / NEXT`.
- Fail-closed: şüphede dur, `report_only`/no-side-effect yönünde davran; network default kapalıdır.
- Secrets asla log'a/evidence'a yazılmaz; token/anahtar basılmaz.
- Core vs workspace sınırı: core repo yazımı varsayılan olarak kapalıdır (fail-closed). Yalnızca CORE_UNLOCK=1 ve CORE_UNLOCK_REASON set ise, allowlist SSOT yollarına (schemas/, policies/, extensions/, `vendor_packs` altı semgrep klasörü, docs/OPERATIONS/, docs/ROADMAP.md, roadmaps/SSOT/roadmap.v1.json, docs/LAYER-MODEL-LOCK.v1.md, docs/OPERATIONS/SSOT-MAP.md, docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md, `.github` altı `gate-enforcement-check.yml`, `.github` altı `module-delivery-lanes.yml`, `.github` altı `board-pr-merge-evidence.yml`, `.github/CODEOWNERS`, standards.lock, `scripts/sync_managed_repo_standards.py`, `ci/check_standards_lock.py`, `ci/check_standards_lock_parts/`, `ci/check_module_delivery_lanes.py`, `ci/run_module_delivery_lane.py`, `ci/module_delivery_lanes.v1.json`, `pyproject.toml`, .pre-commit-config.yaml, AGENTS.md) kanıt üreterek yazılabilir; aksi halde BLOCKED. src/** yazımı normalde YASAKTIR; istisna olarak ONE_SHOT_SRC_WINDOW aktifken sadece allow_paths + ttl_seconds içinde yazılabilir ve pencere sonunda restore kanıtı zorunludur.
- Living roadmap değişikliği: açık istenmedikçe sessizce SSOT edit yapmak yok; gerekiyorsa **Change Proposal (CHG)** üret.

## SSOT Entrypoint Map / Router (AGENTS-only entrypoint)

Bu repo'da fallback yalnızca **AGENTS.md** olduğu için, aşağıdaki liste **tek canonical yönlendirme rotasıdır**.
Agent, navigasyon ve karar bağlamı için önce bu listedeki dokümanları kullanır. Bu liste dışındaki linkler yardımcıdır; canonical değildir.

### SSOT & Navigation (canonical)
- docs/OPERATIONS/CODEX-UX.md (customer-friendly ops akışı)
- docs/OPERATIONS/CODEX-CONFIG-CONTRACT.v1.md (Codex config contract)
- schemas/policy-codex-runtime.schema.v1.json (Codex runtime overlay schema)
- policies/policy_codex_runtime.v1.json (Codex runtime overlay policy)
- docs/OPERATIONS/CODING-STANDARDS.md (zorunlu coding standartları ve shared utilities)
- docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md (multi-repo operasyon kontratı)
- scripts/sync_managed_repo_standards.py (taşeron repo standart senkronizasyonu)
- .github/workflows/module-delivery-lanes.yml (modüler lane CI template + gate)
- ci/check_module_delivery_lanes.py (lane kontrat check)
- docs/LAYER-MODEL-LOCK.v1.md (L0/L1/L2/L3 + core_lock protokolü)
- docs/ROADMAP.md (MIRROR human summary; canonical is `roadmaps/SSOT/roadmap.v1.json` — RM-SSOT-001)
- `docs/ROADMAP_v2.7_legacy.md` (archive only; do not follow)
- docs/OPERATIONS/repo-layout.md
- docs/OPERATIONS/repo-layout.v1.json
- docs/OPERATIONS/spec-core.md (CAPABILITY/KABİLİYET spec-core)
- docs/OPERATIONS/tags-registry.md (AUTOPILOT CHAT + status/action registry)
- docs/OPERATIONS/SSOT-MAP.md (kritik SSOT haritası)
- docs/OPERATIONS/EXTENSIONS.md (extension canonical doküman)
- docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md (Governance Board Capability v1 ürün özelliği)
- docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md (Governance Board Capability managed repo rollout kontratı)
- docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md (GitHub Project board çalışma modeli; board SSOT değildir)
- docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md (trackable board governance adoption plan)
- docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md (Status/Faz/Track/Priority/Kind + label kontratı)
- docs/OPERATIONS/BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md (agent-state ve evidence issue body kontratı)
- docs/OPERATIONS/BOARD-PR-TEMPLATE-CONTRACT.v1.md (`Tracked by` varsayılan PR kontratı)
- docs/OPERATIONS/BOARD-PROJECTION-MANIFEST.v1.md (board_projection.v1 desired/observed/drift kontratı)
- docs/OPERATIONS/BOARD-LIVE-SYNC-VALIDATION-EVIDENCE.v1.md (live ProjectV2 metadata/sync evidence)
- schemas/board-projection.schema.v1.json (board projection schema)
- policies/policy_board_governance.v1.json (board governance policy)
- .github/workflows/board-pr-merge-evidence.yml (merged PR `Tracked by` evidence workflow)
- roadmaps/SSOT/roadmap.v1.json (CANONICAL roadmap — RM-SSOT-001)
- roadmaps/PROJECTS/README.md (project roadmaps)
- roadmaps/PROJECTS/project-roadmap.template.v1.json (project template)
- roadmaps/PROJECTS/PRJ-KERNEL-API/contract.v1.md (project contract)
- policies/policy_test_quality.v1.json (test quality enforcement — fake test prevention)
- schemas/policy-test-quality.schema.v1.json (test quality policy schema)
- schemas/test-quality-rules.schema.v1.json (test quality rules definition schema)
- schemas/system-status.schema.json
- policies/policy_system_status.v1.json
- src/ops/system_status_report.py
- src/ops/manage.py (ops entrypoint; project-status/system-status burada)
- src/ops/roadmap_cli.py (varsa: project-status / navigator wrapper)
- schemas/context-profile-registry.schema.v1.json (profile-based context registry contract)
- schemas/active-context-profile.schema.v1.json (per-workspace active profile artifact)
- schemas/agent-consultation.schema.v1.json (agent-to-agent async consultation)
- policies/policy_context_profile_registry.v1.json (6 profile SSOT: STARTUP/EMERGENCY/TASK_EXECUTION/REVIEW/ASSESSMENT/PLANNING)
- policies/policy_agent_consultation.v1.json (consultation protocol: paths, state_machine, single_writer)
- policies/policy_multi_agent_coordination.v1.json (multi-agent git coordination — branch lease, file write arbitration)
- schemas/policy-multi-agent-coordination.schema.v1.json (multi-agent coordination schema)
- policies/policy_context_orchestration.v1.json (context orchestration + profile registry ref)
- policies/policy_maturity_assessment.v1.json (maturity rubric L0-L4 scoring)
- policies/policy_risk_scoring.v1.json (multi-factor risk thresholds)
- policies/policy_human_approval_request.v1.json (human approval workflow)
- policies/policy_quality_gates.v1.json (AI output quality gates)
- policies/policy_decision_boundaries.v1.json (decision boundary enforcement)

### Operating rule (MUST)
- Program ops/gate/runner ile yönlendirir; agent yalnız plan/analiz/rapor üretir.
- Kullanıcı komut yazmaz.
- "Neredeyiz?" sorusunda tek kapı: **project-status** (yoksa **system-status** fallback).
- Doc navigation için tek kapı: doc-nav-check (summary default; detail/strict on-demand).
- Kullanıcıya yönelik arama (keyword/semantic) için ortak kanal: `scripts/codex-search` (altında `ops-search` → `/api/search`); böylece Cockpit ve agent'lar aynı arama hattını kullanır.
- GitHub Project Board governance için board repo SSOT'un yerine geçmez; `project-roadmap` label board ingestion gate'idir, `Tracked by #N` varsayılandır, `Needs Verify` kabul kuyruğudur, `Done`/issue close yalnız gerçek kabul kanıtı ve ayrı kasıtlı gate ile yapılır.
- Board drift/sync işlerinde güvenli sıra: `board-projection-live` → `board-metadata-live` → `board-sync --mode dry-run`; apply yalnız accepted digest + explicit target board id + confirmation + token env ile yapılır.
- Governance Board Capability managed repo rollout için canonical yol: `BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md` + `standards.lock` + `scripts/sync_managed_repo_standards.py`; dağıtım registered manifest hedefleriyle sınırlıdır, canlı GitHub mutation yine per-target gate ister.
- **Decision Registry (MUST):** Mimari karar gerektiren konuya (auth, DB, UI, altyapı) dokunmadan önce `decisions/registry.v1.json` kontrol et. ACTIVE kararları takip et. Karar değiştirmek istiyorsan **Decision Change Proposal (DCP)** üret — sessizce değiştirme. `rejected_alternatives` listesindeki yaklaşımları tekrar önerme.

## Multi-Agent (shared context)

Bu repo birden fazla agent tarafından yönetilir. Tüm agent'lar **bu AGENTS.md dosyasını** tek canonical instruction kaynağı olarak kullanır.

### Aktif Agent'lar
| Agent | Provider | Config | Çalışma Modu | Durum |
|---|---|---|---|---|
| **Codex** | OpenAI (gpt-5.3-codex effective runtime overlay) | `.codex/config.toml` | Sandbox (workspace-write) | Aktif |
| **Antigravity** | Google DeepMind (Gemini) | `.gemini/settings.json` | IDE (yerel dosya sistemi) | Askıya alındı (kısa vadede kullanılmayacak) |

### Ortak Kurallar
- Tüm agent'lar aynı ops komut setini kullanır.
- Tüm agent'lar aynı SSOT router'ı (bu dosya) takip eder.
- Tüm agent'lar aynı bağlam kaynaklarını okur (aşağıdaki Context Bootstrap).
- Core_lock, fail-closed, secrets kuralları tüm agent'lar için geçerlidir.
- Agent çıktıları AUTOPILOT CHAT formatındadır: `PREVIEW / RESULT / EVIDENCE / ACTIONS / NEXT`.

### Consultation Protocol (async istişare)

Agent'lar birbirine async soru sorabilir. Git repo transport layer'dır.
- Schema: `schemas/agent-consultation.schema.v1.json`
- Policy: `policies/policy_agent_consultation.v1.json` (paths, state_machine, single_writer kuralları burada)

### Branch / Worktree Awareness (MUST)
- Agent çalıştığı branch/worktree'yi bilmeli; `git rev-parse --abbrev-ref HEAD` + `--short HEAD` ile alır.
- Cross-agent karşılaştırmada aynı branch ZORUNLU.

### Maturity Assessment Protocol (MUST)
- Rubric: `policies/policy_maturity_assessment.v1.json`. `evidence_commands` çalıştırılması ZORUNLU; salt dosya okuma ile skor verilmez.
- Scoring: L0=0%, L1=25%, L2=50%, L3=75%, L4=100%.
- **Branch-local** vs **canonical** maturity ayrımı: canonical skor yalnızca main branch'te. PR merge + CI gate geçişi olmadan canonical skor ARTMAZ.

## Context Bootstrap (her konuşma başında)

Agent çalışmaya başladığında, **Profile Resolution → Bootstrap** sırasını takip eder.

### 0. Profile Resolution (ÖNCE yap)

`policies/policy_context_profile_registry.v1.json` içindeki 6 profil arasından aktif profili belirle:

| Profil | Ne zaman aktif? |
|---|---|
| **EMERGENCY** | system_status=FAIL veya integrity violation var |
| **ASSESSMENT** | Olgunluk/gap/PDCA değerlendirmesi isteniyorsa |
| **PLANNING** | Roadmap/mimari/strateji planlaması |
| **REVIEW** | Kod/PR/rapor incelemesi |
| **TASK_EXECUTION** | Belirli bir ops komutu veya work item (varsayılan) |
| **STARTUP** | İlk oturum, hiç bağlam yok |

Aktif profil artefaktı: `.cache/index/active_context_profile.v1.json`

### 0.5 Consultation Check (varsa cevapla)

Agent bootstrap'ta workspace'teki consultation queue'yu kontrol eder:
- Requests: `.cache/index/consultations/requests/CNS-*.request.v1.json`
- State: `.cache/index/consultations/state/CNS-*.state.v1.json`
- Responses: `.cache/reports/consultations/CNS-*.{agent}.response.v1.json`

Davranış:
- Açık request varsa ve `to_agent` kendi agent_id'sine eşitse → cevap ver (stdout JSON)
- State `ANSWERED` ise ve kendi başlattığı ise → response'u oku
- Boşsa → devam et

**Not:** Agent dosya yazmaz. Dispatcher tek yazar. Agent yalnızca structured JSON stdout döner.

### 1. Durum Bağlamı (en güncel hal)
- `.cache/ws_customer_default/.cache/reports/system_status.v1.json` — sistem durumu
- `.cache/ws_customer_default/.cache/reports/portfolio_status.v1.json` — portföy durumu
- `.cache/ws_customer_default/.cache/roadmap_state.v1.json` — roadmap ilerleme durumu

### 2. Yapısal Bağlam (SSOT)
- `AGENTS.md` — canonical instruction + router (bu dosya)
- `docs/OPERATIONS/CODEX-UX.md` — customer-friendly ops akışı
- `docs/LAYER-MODEL-LOCK.v1.md` — katman modeli

### 3. Proje Bağlamı (yalnızca ASSESSMENT veya PLANNING profilinde)
- `roadmaps/PROJECTS/*/project.manifest.v1.json` — proje manifestleri
- `roadmaps/SSOT/roadmap.v1.json` — canonical roadmap

### Bootstrap komutu (agent çalıştırır)
```
python3 -m src.ops.manage system-status --workspace-root .cache/ws_customer_default
python3 -m src.ops.manage portfolio-status --workspace-root .cache/ws_customer_default
```

Profil `required_files` ve `bootstrap_commands` alanları profile-specific ek yüklemeleri tanımlar.

## Repo conventions

Detay: `docs/OPERATIONS/CODING-STANDARDS.md`. Özet: `*.v1.json`, `*.schema.json`, 2-space indent, UTF-8. Secrets commit edilmez.

## Doğrulama (agent tarafından çalıştırılır)

- Şema kontrolü: `python3 ci/validate_schemas.py`
- Dry-run simülasyon: `python3 ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json`
- Policy-check: `python3 -m src.ops.manage policy-check --source both`
