# AI Multi-Repo Operating Contract (v1)

Amaç: Çok repolu ERP ürün ailesinde standardizasyon drift'ini engellemek, AI destekli geliştirme akışını ölçülebilir ve denetlenebilir hale getirmek.

## Kapsam
- Web, mobil, backend, SQL, API, tasarım sistemi ve ortak servis repoları.
- Bu kontrat, core/control-plane kurallarını ve execution repo zorunluluklarını tanımlar.

## Zorunlu İlkeler (MUST)
1. SSOT-first: Mimari/policy/gate kararları core SSOT'ta tutulur, execution repolar bu kararları tüketir.
2. Control-plane / execution ayrımı korunur: Core karar verir, execution repo uygular.
3. `standards.lock` zorunludur: Her PR ve push'ta geçerli JSON + zorunlu anahtarlar doğrulanır.
4. CODEOWNERS zorunludur: Core yolları (`policies/`, `schemas/`, `.github/workflows/`, `ci/`, `docs/OPERATIONS/`) sahip onayı olmadan merge edilemez.
5. PR gate'leri blocking olmalıdır: enforcement, schema, policy dry-run, secrets taraması geçmeden merge yoktur.
6. AI governance fail-closed çalışır: allowlist dışı provider/model çağrısı engellenir; canlı çağrılar explicit flag ile açılır.
7. Audit zorunludur: LLM çağrıları redacted audit izi bırakır; secret/token değerleri asla loglanmaz.
8. Reasoning lane fallback kurallıdır: `reasoning -> fast reasoning -> chat` sıralaması policy ile yönetilir.

## Zorunlu Kontroller
- Teknik kontrol dosyası: `standards.lock`
- Sahiplik: `.github/CODEOWNERS`
- PR enforcement: `.github/workflows/gate-enforcement-check.yml`
- Module delivery lane workflow: `.github/workflows/module-delivery-lanes.yml`
- LLM live policy: `policies/policy_llm_live.v1.json`
- Provider guardrails: `policies/policy_llm_providers_guardrails.v1.json`
- Kernel API gate policy: `policies/policy_kernel_api_guardrails.v1.json`
- UI design system policy: `policies/policy_ui_design_system.v1.json`
- Managed repo sync scripti: `scripts/sync_managed_repo_standards.py`
- Teknik baseline (AI-yorumlanabilir canonical format): `registry/technical_baseline.aistd.v1.json`
- Legacy standards archive manifest: `registry/archives/legacy_standards_archive.aistd.v1.json`
- Solo branch policy guard: `scripts/check_branch_protection_solo_policy.py`
- Lane config + runner: `ci/module_delivery_lanes.v1.json`, `ci/run_module_delivery_lane.py`, `ci/check_module_delivery_lanes.py`

## Standart Kaynakları (Neye Göre Kontrol Eder?)
Bu kontrat `standards.lock` içindeki `standard_sources` haritasını canonical kabul eder:
- Teknik baseline (normatif, tek kaynak): `registry/technical_baseline.aistd.v1.json`
- Katman sınırı: `policies/policy_layer_boundary.v1.json`
- LLM canlı çağrı standardı: `policies/policy_llm_live.v1.json`
- LLM provider guardrail standardı: `policies/policy_llm_providers_guardrails.v1.json`
- Kernel API guardrail standardı: `policies/policy_kernel_api_guardrails.v1.json`
- UI design system standardı (tek UI kit + token chain + modüler sayfa + parametrik veri): `policies/policy_ui_design_system.v1.json`
- Network/security standardı: `policies/policy_security.v1.json`
- Secret allowlist standardı: `policies/policy_secrets.v1.json`
- PM execution bridge standardı: `policies/policy_pm_suite.v1.json`, `policies/policy_feature_execution_bridge.v1.json`

Not (Hard Cutover v2):
- Legacy doc tabanlı standart bağımlılıkları `standard_sources` dışına alınmıştır.
- Legacy dosyalar yalnız `registry/archives/legacy_standards_archive.aistd.v1.json` manifesti ile read-only arşiv olarak tutulur.

## Uyum Kanıtı
- PR başına gate artefact'ları saklanır.
- Uyum doğrulama komutu: `python3 ci/check_standards_lock.py`
- Feature preflight teknik checklist komutu: `python3 scripts/ops_technical_baseline_checklist.py --repo-root .`
- Feature execution bridge komutu: `python3 extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py --repo-root .`
- Dashboard export komutu (taşeron standart envanteri + bilinmeyen sinyaller): `python3 scripts/export_managed_repo_standards_dashboard.py --workspace-root .`
- Taşeron repo sync doğrulama komutu: `python3 ci/check_standards_lock.py --repo-root <repo_root>`
- Lane kontrat doğrulama komutu: `python3 ci/check_module_delivery_lanes.py --strict`
- Solo branch policy doğrulama komutu: `python3 scripts/check_branch_protection_solo_policy.py --repo-slug <owner/repo>`
- System summary kaynakları:
  - `.cache/reports/system_status.v1.json`
  - `.cache/reports/portfolio_status.v1.json`
  - `.cache/reports/drift_scoreboard.v1.json`

## Taşeron Repo İşletim Akışı (MUST)
1. Onboarding: Repo, managed manifest (`.cache/managed_repos.v1.json`) içine alınır.
2. Sync: `scripts/sync_managed_repo_standards.py` dry-run ile drift ölçer; `--apply` ile standart dosyaları hedef repoya taşır.
3. Verify: Sync sonrası hedef repoda `ci/check_standards_lock.py --repo-root <repo_root>` çalışır; FAIL ise merge/promotion durur.
4. Feature execution contract: Kod degisikligi baslamadan once `extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json` guncellenir. Business hedefi, kapsam globs, UX theme/subtheme karari ve lane planinin tek JSON kontratta toplanmasi zorunludur.
5. Delivery lane: Backend, database, API ve frontend scope'lari ayri gelistirilir; lane mapping `backend->unit`, `database->database`, `api->api`, `frontend->contract`, `integration->integration`, `e2e_gate->e2e` olarak uygulanir. CI sirasi `backend -> database -> api -> frontend -> integration -> e2e` zorunludur ve `module-delivery-gate` gecmeden merge olmaz.
6. Observability: Sync ciktisi `system_status` ve `portfolio_status` icinde `managed_repo_standards` section'inda taseron repo bazinda drift olarak gorunur.
7. Drift scoreboard: `system_status` + `portfolio_status` akislar `.cache/reports/drift_scoreboard.v1.json` uretir; lane override matrisi (`repo -> unit/database/api/contract/integration/e2e command`) ve preserve tabanli rollout onerisi tek JSON'da izlenir.
8. Branch protection policy: `standards.lock.branch_protection.required_checks` icinde `module-delivery-gate` zorunludur; canli dogrulama kaniti yoksa durum `UNVERIFIED` olarak raporlanir.
9. Solo developer policy: write yetkili collaborator sayisi `<=1` ise `required_approving_review_count=0` ve `require_code_owner_reviews=false` zorunludur; `>1` oldugunda minimum `1` review ve code-owner review zorunludur.
10. Legacy format yonetimi: Eski markdown/json standart kaynaklari yalnizca archive/snapshot amacli tutulur; normatif teknik kararlar `technical_baseline.aistd.v1.json` uzerinden yorumlanir.

## Context Health & Self-Healing (v0.2)
11. Context health: Her sync döngüsünde `scripts/check_context_health.py` managed repo workspace'ini kontrol eder; score 0-100, grade A-F üretir.
12. Context drift detection: Artifact, session ve policy hash'leri orchestrator ile karşılaştırılır; drift tespit edilirse gap üretilir.
13. Reconciliation: `--sync-context` flag'i ile sync script context artifact'larını push eder, session'ı yeniler, parent decision'larını child'a aktarır.
14. Parent-child session: Orchestrator session parent, managed repo session child olarak bağlanır; decision inheritance SSOT-first kuralına uyar (parent wins on conflict).
15. Portfolio health: Tüm managed repo'ların context health score'ları aggregate edilir; portfolio_context_health.v1.json üretilir.
16. Self-healing döngüsü: Health score drop → GAP-EVAL-LENS-context_health → work_intake ticket → PDCA regression check → otomatik fix at next sync.

## Değişiklik Yönetimi
- Bu kontratta değişiklik sessiz yapılmaz; CHG süreci ve gate kanıtı gerekir.
- Kontrat ve `standards.lock` birlikte güncellenir.
