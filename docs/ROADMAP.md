# SSOT Yol Haritası (Kilitli) — v1.0.0 sonrası
## “ISO Sırası Çekirdek + Genel Platform + Katalog‑Temelli Üretim + Learning (Suggest‑Only) + Autopilot (İnsansız)”

> **CANONICAL:** Bu dosya tek SSOT yol haritasıdır. Legacy arşiv: `ROADMAP_v2.7_legacy.md` (archive only).

> Bu doküman artık **tek doğru** (SSOT) yol haritamızdır.  
> Amaç: Mevcut v1.0.0 çekirdeğimizden sapmadan, ürünün “genel platform” kimliğini tamamlamak ve insansız otomasyonu sürdürülebilir şekilde büyütmek.

### Değişiklik yönetimi (kilit)
- Bu dosyadaki yol haritası “kilitli” kabul edilir; değişiklikler PR ile ve gerekçelendirilerek yapılır.
- Yol haritasını etkileyen her SSOT değişikliği için **policy-check** çalıştırılır: `python -m src.ops.manage policy-check --source both`
- İlke: SSOT = Git; indeks/cache = rebuildable (`.cache/`).
- Customer-friendly mode: kullanıcı komut yazmaz, agent ops’u çalıştırır (bkz. `docs/OPERATIONS/CODEX-UX.md`).
- Tek mantık + katman modeli SSOT: `docs/LAYER-MODEL-LOCK.v1.md`.

### Plan‑only placeholders (repo dışında, bilerek yok)
Bu listede yer alan referanslar **PLAN‑ONLY PLACEHOLDER** olarak işaretlenmiştir ve repo’da bulunmaması normaldir.
- [PLAN-ONLY PLACEHOLDER] ci/validate_format_contracts.py
- [PLAN-ONLY PLACEHOLDER] ci/validate_iso_core_presence.py
- [PLAN-ONLY PLACEHOLDER] ci/validate_tenant_consistency.py
- [PLAN-ONLY PLACEHOLDER] schemas/format-contract.schema.json
- [PLAN-ONLY PLACEHOLDER] formats/format-code-gen.v1.json
- [PLAN-ONLY PLACEHOLDER] formats/format-decision-proposal.v1.json
- [PLAN-ONLY PLACEHOLDER] formats/format-procedure-iso.v1.json
- [PLAN-ONLY PLACEHOLDER] formats/format-recommendation.v1.json
- [PLAN-ONLY PLACEHOLDER] docs/OPERATIONS/roadmap-runner-demo.md
- [PLAN-ONLY PLACEHOLDER] packs/pack-demo
- [PLAN-ONLY PLACEHOLDER] packs/pack-demo/manifest.v1.json
- [PLAN-ONLY PLACEHOLDER] packs/bp-*
- [PLAN-ONLY PLACEHOLDER] packs/formats/learning/autopilot
- [PLAN-ONLY PLACEHOLDER] docs/specs
- [PLAN-ONLY PLACEHOLDER] workflows/formatlar/paketler/standartlar/kontrol
- [PLAN-ONLY PLACEHOLDER] workflows/templates/policy
- [PLAN-ONLY PLACEHOLDER] governor/budget/quota
- [PLAN-ONLY PLACEHOLDER] governor/budget/quota/tool-capability
- [PLAN-ONLY PLACEHOLDER] governor/report_only

---

## Mevcut durum (program‑led özet)
- Doc‑nav “tek kapı” ölçümü: broken_refs=1, ambiguity=0, critical_nav_gaps=0 (strict rapor cockpit’i etkilemez).
- M10.2 Assessment: DONE (blok kalktı, index‑first çalışıyor).
- M10.3 Gap register: DONE (gap_register + gap_summary mevcut).
- M10.4 Cockpit benchmark: DONE (system_status sections.benchmark mevcut).
- Portfolio tracking: portfolio-status + system_status sections.projects (program‑led tek kapı).
- Next focus: **M0 Maintainability** (SCRIPT_BUDGET borçları; davranış değişmeden refactor planı).

---

## Kilitlenen ana kararlar (işletim sistemi kuralı)

Bu bölüm “tek mantık + katmanlar” kararını SSOT seviyesinde kilitler.  
Tamamlanmayan kısımlar legacy değildir; yol haritası burada kilitli kalır.

### 0.1 Tek Mantık Zinciri (her işte aynı)
Her iş şu zincirden geçer (yöntem değil, ürün davranışı):

Bağlam → Paydaş → Kapsam → Kriter → Risk → Kanıt → Üretim → Recheck

### 0.2 Katmanlar “görev” değil, “izin/sahiplik”
- **L0 CORE:** motor + kapılar + doğrulamalar. Varsayılan kilitli.
- **L1 CATALOG:** workflows/formatlar/paketler/standartlar/kontrol noktaları. “Kütüphane”.
- **L2 WORKSPACE:** türev indeksler/raporlar/incubator/CHG taslakları/session RAM. “Çalışma masası”.
- **L3 EXTERNAL:** müşterinin gerçek işi (kod/doküman/proje çıktısı). “Teslimat alanı”.

Kural: Aynı mantık zinciri her yerde aynı; katman sadece nereye yazabileceğimizi belirler.

### 0.3 Tek katalog görünümü (bakım kolaylığı)
- Tek mantıksal katalog (tek derived index)
- İki kaynak olabilir:
  - Global (L1) → core tarafından sağlanan
  - Customer‑owned (L2’de saklanır, katalog entry olarak etiketlenir)
- Derived index bu ikisini deterministik birleştirir (origin/owner/priority/conflict kurallarıyla).

### 0.4 Core dokunulmazlığı (müşteri güveni)
- Core‑lock default ENABLED.
- Müşteri modunda core’a yazma denemesi fail‑closed + kanıtlı BLOCKED.
- Core’a dokunulacaksa bilinçli akış: “unlock + gerekçe + CHG + review”.

---

## 1) “Bir yazılım yaz” dediğinde hangi seviyede yazılır?
Varsayılan: **L3 EXTERNAL** (müşteri projesi / gerçek çıktı).  
Eş zamanlı olarak:
- **L2 WORKSPACE:** sentez + kararlar + format/kanıt pointer’ları + recheck sonucu
- **L1 CATALOG:** genellenebilir akış/format varsa, önce customer‑owned entry olarak üretilir (origin=CUSTOMER)

L0 CORE’a bu istekle dokunulmaz. Core davranış değişikliği istenirse ayrı kilit açma protokolü uygulanır.

---

## 2) Yol haritası (mevcut sistemle uyumlu “kilitli plan”)
Mevcut çekirdekle uyumlu ve core‑lock açıkken çalışacak şekilde kilitlenmiştir.

### Faz A — Davranış kilidi ve sınırlar (hemen, kalıcı)
**A1 — Tek Mantık sözleşmesi (CAPABILITY spec‑core)**
- Tüm katalog entry tipleri için meta alanlar (id/purpose/inputs/outputs/guardrails/iso_refs/evidence/risk/layer) standarttır.
- Eksik/yanlış layer, core_lock_required ihlali, evidence boşluğu → fail‑closed.

**A2 — Core‑lock: müşteri için dokunulmaz**
- Core yazımı sadece açık kilit + CHG + review ile.
- Müşteri modunda core dokunuşu → BLOCKED + kanıt.

**A3 — Tek katalog görünümü**
- Hard conflict → FAIL (katalog build iptal; stabil index korunur).
- Soft conflict → WARN + deterministik seçim.

DoD: Aynı girdi → aynı index hash; müşteri core’a dokunamaz; conflict raporu cockpit’te görünür.

### Faz B — Katalog yaşam döngüsü (müşteri özelleştirir ama global’i bozmaz)
**B1 — Customer‑owned katalog entry standardı**
- Zorunlu etiketler: origin, owner_tenant, promotion_state, override_ref.

**B2 — Promotion disiplini**
- customer‑owned → candidate → promoted
- promoted sadece core‑lock açıkken, manual review ile.

### Faz C — Benchmark/Gap Engine “kalp projesi” (M10.*)
Hedef: her işte aynı zinciri otomatikleştirmek (O(delta), pointer‑only).

**C1 — North Star (Standards catalog)**  
Controls + Metrics + Maturity (0–5) deterministik kriterlerle (pointer + schema + index sinyali).

**C2 — Assessment (O(delta))**  
system_status + pack index + quality + repo hygiene + harvest sinyallerini okur.

**C2b — Eval Lenses (Trend / Integrity & Compatibility / AI‑Ops Fit)**  
M10.2b eval çıktısında üç lens deterministik sinyal üretir; gap ve intake’e pointer‑only bağlanır.

**C3 — Gap register + Closure map**  
safe‑only → incubator taslak/uygula; plan‑only → draft.

**C4 — Cockpit**  
benchmark_scorecard + top_actions + regression; “Top 5 Next Actions” deterministik sıralama.

### Faz D — Otomatik iyileştirme döngüsü (PDCA)
**D1 — Recheck loop:** safe‑only apply sonrası otomatik recheck  
**D2 — Öneri patlaması kontrolü:** quota + quality_score + cooldown  
**D3 — Sürdürülebilirlik:** O(delta) + cursor + retention
**D4 — M10.5 PDCA Recheck + Regression + Quota/Cooldown + Retention/Cursor:** recheck sonrası regression_flag + severity escalation + cooldown + deterministik top_actions

### Faz E — M0 Maintainability (çekirdek borçlarını yönetilebilir kılma)
Davranış değiştirmeden yapılır:
- `local_runner.py` / `manage.py` / `smoke_test.py` borçlarını plan‑only CHG’lerle bölmek
- script budget borcunu azaltmak (hard 0 kalsın, warn sayısı düşsün)

DoD: SMOKE_OK aynı kalır; CLI çıktıları/evidence şekli değişmez; yapı daha bakımı kolay olur.

---

## 3) Yol haritası “yaşayan” olacak: güncelleme protokolü
- Yeni ihtiyaç → Action Register
- Çözüm → CHG taslağı (safe‑only ise incubator, değilse plan‑only)
- Kabul → promotion bundle (global’e geçecekse)
- Kanıt → evidence; özet → project‑status

---

## 4) M0 Maintainability Sprint: çekirdek mi katalog mu?
Bu açıkça **L0 CORE bakımıdır** (davranışı değiştirmeden).  
Çıktılar (plan/CHG) **L2 WORKSPACE**’te tutulur; core‑lock gevşetilmez.

---

## 0) Bizim çekirdeğimiz (diğerlerinden ayrıştığımız yer)

### 0.1 ISO mantık sırası: aktif devrede (iş yapılırken)
Bu bir “doküman sırası” değil, **ürün davranışı**:
1) **Bağlam analizi** (context)
2) **Paydaş analizi** (stakeholders)
3) **Kapsam** (scope)
4) **Kriterler / risk iştahı** (criteria)
5) **Kontroller / standart çıktılar** (controls + output standards)
6) **Ölçüm** (measure)
7) **İyileştirme** (improvement)

Kural:
- Ürün, bir işi “yapmadan önce” bağlam/paydaş/kapsam/kriterleri ya **SSOT’tan** okur ya da **session RAM**’de (ephemeral) geçici olarak tutar.
- Bunlar yoksa **fail-closed**: `report_only` / `no side-effect` / conservative mode.

### 0.2 “Genel platform” ilkesi: kullanıcı profil seçmez, sistem filtreler
Kullanıcı sohbetten iş ister:  
**amaç → domain → artifact türü → stack → izinler → format**

Sistem discovery ile kategorik filtre uygular ve en uygun workflow/modül/formatı seçer.

Kural:
- UI’da “profil seç” yok; ama arkada kalıcı kararlar var: **Tenant Decision Bundle (SSOT)**.

### 0.3 Learning karar vermez
Learning plane sadece **öneri üretir** (suggest-only).  
Control plane (policy/gates/governor/budget/quota) karar verir. Asla bypass yok.

### 0.4 SSOT = Git; Index = cache
- Kalıcı kararlar/kurallar/formatlar: Git repo’da deklaratif SSOT.
- Discovery/Learning index: rebuildable cache (drift engeli).

### 0.5 Standart ürün çıktısı üretme
Ürün “ne yaparsa yapsın”, çıktılar **format contract**’lara uyar:
- Kod üretimi formatı
- Prosedür formatı
- Karar/öneri formatı
- Autopilot chat formatı

Bunların hepsi katalogda ve schema’lıdır.

### 0.6 CAPABILITY (KABİLİYET) spec-core meta sözleşmesi (Hybrid)
Amaç: “tek mantık” ile hem keşif (discovery) hem yürütme (execution) hem de denetimi (evidence/risk) aynı sözleşmeye bağlamak.

Neden:
- **Tek sözleşme**: `capability` / `pack` / `format` / `roadmap` / `policy` gibi artefact türleri aynı “meta çekirdek” ile tanımlanır.
- **ISO sırası aktif**: ISO bağlamı uzun metin olarak tekrar edilmez; `iso_refs` ile tenant ISO çekirdek dosyalarına referans verilir (M1).
- **Evidence + risk birleşik**: her tanım kendi kanıt beklentisini (evidence) ve risk/guardrail sınırlarını taşır.

Nedir (spec-core meta alanları, v0.1):
- `id`: tekil kimlik (CAPABILITY id’si dahil)
- `purpose`: kısa amaç/capsule
- `inputs`: beklenen girişler (schema id/paths)
- `steps`: yüksek seviye adımlar (DAG değil; “ne olur” tanımı)
- `outputs`: beklenen çıktı türü + format contract referansı
- `guardrails`: policy/gate/governor/budget/quota/tool-capability sınırları
- `iso_refs`: `tenant/<TENANT>/{context,stakeholders,scope,criteria}.v1.md` referansları (içerik kopyalanmaz)
- `evidence`: beklenen evidence dosyaları/izler (integrity/provenance dahil)
- `risk`: risk sınıfı + side-effect beklentisi (fail-closed)

Nasıl (hybrid meta+body):
- Meta: strict JSON (schema ile) → makine tarafından doğrulanabilir.
- Body: opsiyonel açıklama/şablon metni (markdown) → insan tarafından okunabilir.
- Kural: CAPABILITY tanımları için **MUST** (meta zorunlu). Pack/format/roadmap/policy için **MAY** (kademeli).

Terminology lock:
- Canonical (code): **CAPABILITY**
- Doküman (TR): **KABİLİYET**
- Yasak terim: eski terminoloji (repo docs/specs içinde kullanılmaz; yerine CAPABILITY/KABİLİYET)

---

## 1) Mevcut durum (v1.0.0 çekirdek kapasite)
Elimizdeki çekirdek zaten şunları sağlıyor:
- `policy-check` (schema validate + dry-run + diff + markdown report + supply-chain gates)
- evidence: integrity + provenance + replay + export
- tool gateway + capabilities + limits + network allowlist + secrets provider
- side-effect: `none`/`draft`/`pr` (merge/deploy blocked; SSOT manifest var)
- ops: `src.ops.manage` + reaper + runbook
- gerçek workflow: `policy_review` + `dlq_triage`
- PR side-effect: integration-only gate ile gerçek PR açma (ops command dahil)

Not:
- Bundan sonra “yeni ürün” yazmıyoruz; çekirdeğe **SSOT katmanları ve katalog** ekleyip autopilot + learning’i bu zemine oturtuyoruz.

---

## 2) Ürün yapısı (SSOT katmanları)

### 2.1 Kalıcı SSOT (repo içinde)

#### A) Tenant Decision Bundle (kalıcı karar demeti)
Kullanıcı “backend dili Java” gibi sabit kararlar aldıkça buraya yazılır:
- stack seçimleri
- allowed tools
- network allowlist
- side_effect sınırları
- output standards
- enabled packs
- risk criteria / eşikler

#### B) ISO Çekirdek Dokümanları (kalıcı)
- `tenant/<TENANT>/context.v1.md`
- `tenant/<TENANT>/stakeholders.v1.md`
- `tenant/<TENANT>/scope.v1.md`
- `tenant/<TENANT>/criteria.v1.md`

Kural:
- Bunlar “iş yapılırken” referans alınır.
- Yoksa conservative mode.

#### C) Packs Catalog (kalıcı)
Hazır kategorik setler:
- workflows + templates + policy overlays + constraints

#### D) Format & Conversation Contract Catalog (kalıcı)
“Bu tür işte chat nasıl yazacak / çıktı formatı ne olacak” SSOT’u.

#### E) Best Practice & Trend Library (kalıcı)
Sektörel lider pratikler / checklists / standard hooks.
“Aktif devrede”: quality gate olarak çalışır.

### 2.2 Ephemeral SSOT (session RAM, geçici)
Kullanıcı sohbet içinde küçük kararlar ekler:
- “bu işte React kullan”
- “bu raporu şu formatta yaz”

Bu kararlar TTL ile yaşar, sonra düşer. Evidence/provenance’a hash olarak işlenir.

### 2.3 Derived index (cache, rebuildable)
- composite catalog index (tenant bundle + packs + formats + best practices birleşimi)
- learning index (flaky/strategy stats)
- autopilot state cache

---

## 3) Katalog-temelli “iş yapma” akışı (runtime)

### 3.1 Intent → filters → selection
1) Kullanıcı isteği → `intent` + `domain` + `artifact_type` çıkarımı
2) ISO sırası:
   - context/stakeholder/scope/criteria çekilir (SSOT veya session RAM)
3) Composite catalog’dan filtre:
   - allowed_tools, stack, output formats, policy constraints
4) Workflow seçimi
5) Format contract seçimi
6) Execution (tool gateway)
7) Evidence + integrity + provenance + (gerekirse) export
8) Learning event log (öneri üretimi)

### 3.2 “Chat formatı” standardı
Her çıktı, seçilen format contract’a göre:
- neyi nasıl anlatacağını,
- hangi bölümler zorunlu,
- hangi dil ve şablon
olacağını bilir.

---

## 4) Kilitli yol haritası (milestone bazlı)

### M0 — Maintainability Guardrails (Script Budget) + Core↔Workspace boundary
Amaç: Kritik script’lerin kontrolsüz büyümesini önlemek ve bakım/refactor borcunu CI’da görünür kılmak.

Deliverables:
- Script budget SSOT: `ci/script_budget.v1.json` (+ `schemas/script-budget.schema.json`)
- Checker: `ci/check_script_budget.py` (soft=warn, hard=fail)
- CI: `gate-schema` içinde script budget step + artifact raporu
- Dokümantasyon: `docs/OPERATIONS/maintainability-guardrails.md`

DoD:
- Soft aşım: CI geçer ama `WARN` raporlar.
- Hard aşım: CI fail olur (refactor zorunlu).

### M1 — ISO Çekirdeği SSOT (Context/Stakeholder/Scope/Criteria) + aktif gate
Amaç: İş yapılırken ISO sırasını aktif hale getirmek.

Deliverables:
- `tenant/<TENANT>/context.v1.md`
- `tenant/<TENANT>/stakeholders.v1.md`
- `tenant/<TENANT>/scope.v1.md`
- `tenant/<TENANT>/criteria.v1.md`
- `ci/validate_iso_core_presence.py` (fail-closed kural):
  - Bu dosyalar yoksa: `autopilot/report_only`, side_effect blocked.
- `src.ops.policy_report` içine “ISO core status” bölümü.

DoD:
- ISO core yoksa system “conservative mode”u açık şekilde raporlar.
- ISO core varsa üretimde referans olarak kullanılır.

### M2 — Tenant Decision Bundle SSOT v0.1 + Consistency Gate (en kritik)
Amaç: Kullanıcı kararları çelişmesin; discovery doğru filtrelesin.

Dosya yapısı:
- `tenant/<TENANT>/decision-bundle.v1.json`
- `schemas/tenant-decision-bundle.schema.json` [PLAN-ONLY PLACEHOLDER]
- `ci/validate_tenant_consistency.py` (FAIL-closed)

Bundle içeriği (minimal v0.1):
- tenant_id
- stack defaults (backend/frontend/procedure/decision-support)
- enabled packs
- side_effect_policy limits
- allowed tools (high-level)
- network allowlist defaults (integration-only)
- output standards (format ids)
- risk criteria (eşikler)

Consistency Gate (conflict matrix):
- stack_type ↔ required packs
- side_effect_policy=pr ↔ github tool + api.github.com allowlist + GITHUB_TOKEN allowlist
- merge/deploy blocked ↔ bundle’da enabled olamaz
- format id ↔ artifact_type uyumu
- forbidden_paths ↔ tool capabilities

DoD:
- CI’da tenant consistency FAIL → merge yok.
- policy-check raporunda “Tenant Decision Summary” görünür.

### M3 — Packs Catalog v0.1 + Composite Catalog Builder
Amaç: Kullanıcı amaçlarına göre hazır setleri aktive edip standart çıktı üretmek.

Packs:
- `packs/<pack_id>/manifest.v1.json` (+ schema)
- içerik: intents/workflows/templates/policy overlays/constraints

Composite catalog builder:
- `src/tenant/build_catalog.py`
  - input: decision bundle + enabled packs + tenant modules + format contracts
  - output: `.cache/index/catalog.v1.json` (derived)
- discovery bu catalog’dan beslenecek.

DoD:
- Catalog filtreleme deterministik ve explainable.

### M4 — Format & Conversation Contract SSOT (M2.5 olarak da düşünülebilir)
Amaç: Ürünün her çıktısı standart formata uysun; chat formatı da katalogdan gelsin.

Deliverables:
- `formats/` katalog
  - `formats/format-code-gen.v1.json`
  - `formats/format-procedure-iso.v1.json`
  - `formats/format-decision-proposal.v1.json`
  - `formats/format-recommendation.v1.json`
  - `formats/format-autopilot-chat.v1.json`
- `schemas/format-contract.schema.json` (strict)
- `ci/validate_format_contracts.py`
- discovery: intent+artifact_type+audience→format selection
- policy-check raporu: “selected format” bölümü

DoD:
- Her output zorunlu başlık/bölüm setini üretir.
- Format drift olursa gate yakalar.

### M5 — Session RAM (Ephemeral mini-SSOT) v0.1
Amaç: Sohbette eklenen küçük kararları TTL ile yönetmek ve evidence’a bağlamak.

Deliverables:
- `.cache/sessions/<session_id>/session_context.v1.json` (git-ignored)
  - ephemeral_decisions[], ttl, last_updated
- `session_context_hash` → provenance’a yazılır
- “SSOT override” kuralı:
  - SSOT kararlar > session kararlar (öncelik)
  - session kararlar TTL sonrası düşer

DoD:
- Kullanıcı sohbetle geçici karar eklediğinde çıktı buna uyar.
- TTL bitince sistem SSOT’a döner.

### M6 — Best Practice & Trend Library (aktif gate) v0.1
Amaç: “lider pratikler” sadece doküman değil; üretimde aktif kontrol olsun.

Deliverables:
- `best_practices/` veya `packs/bp-*`
- `policies/policy_quality.v1.json`
- quality gate:
  - seçilen formatın zorunlu bölümleri var mı?
  - ISO sırası uygulanmış mı?
  - side_effect risk uyumu var mı?
- ops: `ops best-practice-status`

DoD:
- Üretim sırasında kalite check otomatik devrede.
- Yeni trendler ADR ile eklenip pack olarak sürülür.

### M7 — Learning Plane v0.1 (Offline Advisor / Suggest-only)
Amaç: Autopilot’u verimli yapacak öneri indeksi.

Deliverables:
- `learning/events.jsonl` (append-only)
- `learning/flaky_index.v1.json`
- `learning/strategy_stats.v1.json`
- `learning_snapshot_hash` provenance’a
- ops: learning-status/learning-export
- poison/drift:
  - only merged outcomes positive
  - anomaly → governor learning disable/report_only

DoD:
- Rerun vs fix önerisi ve fix strateji sırası üretilir.
- Karar control plane’de kalır.

### M8 — Autopilot MVP v0.1 (İnsansız PR Loop)
Amaç: PR lifecycle tamamen otomatik.

Deliverables (özet):
- PR discovery
- checks monitor
- retry/backoff
- local reproduce + fix loop (frenler ile)
- merge engine (PAT→GitHub App)
- kill switches
- ops autopilot-status + metrics

DoD:
- Fail→fix→push→green→merge loop en az 1 gerçek senaryoda çalışır.
- Runaway yok: loop cap, budget, quota, governor.

### M9 — Pack Ecosystem v0.1 (Selection + Advisor)
Amaç: Pack manifest SSOT + deterministik seçim izi + pack‑aware öneri zenginleştirme.

Deliverables (özet):
- M9.1: Pack manifest SSOT + conflict gate (hard fail, soft warn)
- M9.2: Pack index build (O(delta))
- M9.3: Pack selection trace (shortlist + tie-break)
- M9.4: Pack‑aware advisor suggestions (bounded, suggest‑only)
- M9.5: Auto‑heal pack‑derived artefact rebuild, conflict gate ile koşullu (hard conflict → block)

---

## 5) Non‑negotiable maddeler (sapmama listesi)
1) Learning karar vermez, önerir.
2) SSOT = Git; index = cache.
3) ISO sırası aktif devrede (yoksa conservative mode).
4) Secrets asla log/evidence’a düşmez.
5) Network default kapalı, integration-only açılır.
6) merge/deploy side effects blocked (şimdilik; SSOT manifest ile).
7) Her adım evidence + integrity + provenance ile izlenebilir.
8) Her SSOT değişikliği sim/diff/policy-check’den geçer.

---

## 6) v1.0.0 ile uyum değerlendirmesi (durum matrisi)

### 6.1 “Bugün elimizde ne var?” (kanıtlı çekirdek)
Bu repo şu an (v1.0.0 çekirdeğiyle) yol haritasının “güvenli platform” zeminiyle uyumlu:
- Deterministik kontrol düzlemi: `schemas/`, `policies/`, `registry/`, `orchestrator/`, `workflows/`
- Denetim hattı: `python -m src.ops.manage policy-check --source both` (dry-run + diff + markdown rapor)
- Evidence paketi + integrity/provenance: `src/evidence/*`, `python -m src.evidence.integrity_verify --run evidence/<run_id>`
- Side-effect SSOT: `docs/OPERATIONS/side-effects-manifest.v1.json` ve `docs/OPERATIONS/side-effects.md`
- Tool gateway + capability enforcement + limits: `src/tools/gateway.py`
- Network allowlist & secrets: `policies/policy_security.v1.json`, `policies/policy_secrets.v1.json`
- Ops: `python -m src.ops.manage runs|dlq|suspends`, `python -m src.ops.reaper --dry-run true --out ...`

### 6.2 Milestone uyumu (özet)
Bu yol haritası mevcut çekirdekle çelişmiyor; tam tersine, şu anki çekirdeği “SSOT katmanları + katalog” ile ürünleştirmeyi hedefliyor.

En büyük fark:
- v1.0.0 çekirdeği “guardrail + evidence + ops” omurgasını kurdu.
- Bu plan ise “tenant‑bazlı kararlar + katalog + format sözleşmeleri + öğrenme/otopilot” katmanını SSOT olarak ekliyor.

### 6.3 Milestone bazında durum
| Milestone | Durum | Bugün repo’da karşılığı | Not / sonraki minimal adım |
|---|---|---|---|
| Doc‑nav “tek kapı” | WARN | doc‑nav‑check summary/strict (strict isolated) | broken_refs=1; strict only broken gerçekleri sayar |
| M10.2 Assessment | DONE | `.cache/index/assessment.v1.json`, `.cache/reports/benchmark_scorecard.v1.json` | O(delta) assessment çalışıyor |
| M10.3 Gap register | DONE | `.cache/index/gap_register.v1.json`, `.cache/reports/gap_summary.v1.md` | safe‑only/plan‑only ayrımı aktif |
| M10.4 Cockpit benchmark | DONE | system_status `sections.benchmark` + top_next_actions | cockpit deterministik özet veriyor |
| M10.5 PDCA recheck + regression | Plan | Faz D altında kilitli | recheck + regression + cooldown + retention/cursor |
| M0 Maintainability | Next | SCRIPT_BUDGET WARN | davranış değiştirmeden refactor planı |
| M1 ISO core SSOT + gate | Eksik | governor/report_only ve side-effect gating mevcut | `tenant/<TENANT>/*` ISO dosyaları + CI presence gate + policy_report ISO status |
| M2 Tenant Decision Bundle + consistency | Eksik (kısmi benzerlik: quota override) | `tenant_id` var; `policy_quota` tenant override var | `tenant/<TENANT>/decision-bundle.v1.json` + schema + CI conflict matrix + policy_report summary |
| M3 Packs + composite catalog builder | Eksik | workflow/modül katalog parçaları var (workflows/, templates/) | `packs/*` + schema + `.cache/index/catalog.v1.json` builder |
| M4 Format & chat contracts | Eksik | bazı çıktılar markdown üretiyor (policy_report, dlq_triage) | `formats/*` + strict schema + selection + validate gate |
| M5 Session RAM mini‑SSOT | Eksik | `.cache` kullanımı var; provenance alanları var | `.cache/sessions/*` + TTL + provenance hash |
| M6 Best practice gate | Eksik | schema validation + smoke gates var | `policy_quality.v1.json` + output section checks |
| M7 Learning suggest-only | Eksik (hazır zemin var) | autonomy store deterministik; replay/diff altyapısı var | events.jsonl + stats + governor kill switch |
| M8 Autopilot PR loop | Kısmi (temel side-effect var) | `github_pr_create` integration-only; ops komutu var | PR lifecycle orchestration + caps/budget/kill switch ile loop |

### 6.4 Net sonuç (ve bir sonraki adım)
- Bu SSOT yol haritası mevcut sistemle uyumludur; çekirdekteki fail-closed, evidence, supply-chain, policy-check bileşenlerini “platform”a taşıma planıdır.
- Sıralama açısından **M2** (Tenant Decision Bundle + Consistency Gate) en yüksek kaldıraçtır; discovery/packs/formats/learning/autopilot katmanlarının tamamı buna dayanır.

---

## Ek: Eski yol haritası (arşiv)
v1.0.0 öncesi “çekirdek kurulum” yol haritası arşivlendi: `ROADMAP_v2.7_legacy.md` (archive only)
