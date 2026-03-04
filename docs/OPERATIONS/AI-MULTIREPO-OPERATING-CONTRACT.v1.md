# AI Multi-Repo Operating Contract (v1)

Amaç: Çok repolu ERP ürün ailesinde standardizasyon drift'ini engellemek, AI destekli geliştirme akışını ölçülebilir ve denetlenebilir hale getirmek.

## Kapsam
- Web, mobil, backend, SQL, API, tasarım sistemi ve ortak servis repoları.
- Bu kontrat, core/control-plane kurallarını ve execution repo zorunluluklarını tanımlar.

## Zorunlu İlkeler (MUST)
1. SSOT-first: Mimari/policy/gate kararları core SSOT'ta tutulur, execution repolar bu kararları tüketir.
2. Control-plane / execution ayrımı korunur: Core karar verir, execution repo uygular.
3. `standards.lock` zorunludur: Her PR ve push'ta geçerli JSON + zorunlu anahtarlar doğrulanır.
4. CODEOWNERS zorunludur: Core yolları (policies/schemas/workflows/ci/docs-operasyon) sahip onayı olmadan merge edilemez.
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
- Managed repo sync scripti: `scripts/sync_managed_repo_standards.py`
- Solo branch policy guard: `scripts/check_branch_protection_solo_policy.py`
- Lane config + runner: `ci/module_delivery_lanes.v1.json`, `ci/run_module_delivery_lane.py`, `ci/check_module_delivery_lanes.py`

## Standart Kaynakları (Neye Göre Kontrol Eder?)
Bu kontrat `standards.lock` içindeki `standard_sources` haritasını canonical kabul eder:
- Kod standardı: `docs/OPERATIONS/CODING-STANDARDS.md`
- Repo yerleşimi: `docs/OPERATIONS/repo-layout.v1.json`
- Katman sınırı: `policies/policy_layer_boundary.v1.json`
- LLM canlı çağrı standardı: `policies/policy_llm_live.v1.json`
- LLM provider guardrail standardı: `policies/policy_llm_providers_guardrails.v1.json`
- Kernel API guardrail standardı: `policies/policy_kernel_api_guardrails.v1.json`
- Network/security standardı: `policies/policy_security.v1.json`
- Secret allowlist standardı: `policies/policy_secrets.v1.json`

## Uyum Kanıtı
- PR başına gate artefact'ları saklanır.
- Uyum doğrulama komutu: `python3 ci/check_standards_lock.py`
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
4. Delivery lane: Backend, frontend, database ve API scope'ları ayrı geliştirilir; lane mapping `backend->unit`, `frontend->contract`, `integration->integration`, `e2e_gate->e2e` olarak uygulanır. CI sırası `backend -> frontend -> integration -> e2e` zorunludur ve `module-delivery-gate` geçmeden merge olmaz.
5. Observability: Sync çıktısı `system_status` ve `portfolio_status` içinde `managed_repo_standards` section’ında taşeron repo bazında drift olarak görünür.
6. Drift scoreboard: `system_status` + `portfolio_status` akışları `.cache/reports/drift_scoreboard.v1.json` üretir; lane override matrisi (`repo -> unit/contract/integration/e2e command`) ve preserve tabanlı rollout önerisi tek JSON'da izlenir.
7. Branch protection policy: `standards.lock.branch_protection.required_checks` içinde `module-delivery-gate` zorunludur; canlı doğrulama kanıtı yoksa durum `UNVERIFIED` olarak raporlanır.
8. Solo developer policy: write yetkili collaborator sayısı `<=1` ise `required_approving_review_count=0` ve `require_code_owner_reviews=false` zorunludur; `>1` olduğunda minimum `1` review ve code-owner review zorunludur.

## Değişiklik Yönetimi
- Bu kontratta değişiklik sessiz yapılmaz; CHG süreci ve gate kanıtı gerekir.
- Kontrat ve `standards.lock` birlikte güncellenir.
