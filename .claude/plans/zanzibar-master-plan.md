# ZANZIBAR / OpenFGA — KAPSAMLI PROJE PLANI (rev 7)

**Proje Kodu:** PRJ-ZANZIBAR-OPENFGA
**Tarih:** 2026-04-12
**Revizyon:** 7 (Dalga 1-4 + Faz 3 DONE, Faz 2 canary AKTIF)
**Karar Referansi:** D-001 → D-007 (D-003 TRANSFORMED)
**Durum:** PR #334-339 merged+deployed. Staging canary flags ON. 48h gozlem basladi.
**Istisare:** CNS-001..005 (5 Codex istisare, 15+ itiraz kabul, tumu duzeltildi)
**Merged PRs:** #334 (Dalga3), #335 (Dalga4), #336 (hotfix), #338 (CNS-005), #339 (Faz3)

---

## 1. PROJE AMACI

Mevcut JWT-based statik permission sistemi 3 kritik sorun iceriyor:
1. **Stale permission** — rol degistiginde JWT yenilenene kadar eski izinler aktif
2. **Hardcoded admin** — yeni roller icin kod degisikligi gerekiyor
3. **Inline check tutarsizligi** — her servis farkli kontrol yapiyor, data leak riski

**Hedef:** 4 katmanli, fail-closed, auditlenebilir yetkilendirme:
```
Keycloak (authn) → OpenFGA (authz) → Hibernate @Filter + RLS (data) → Frontend SDK (UI)
```

---

## 2. BASARI KRITERLERI

| # | Kriter | Hedef | Olcum | Durum |
|---|--------|-------|-------|-------|
| SK-1 | OpenFGA check basari orani | >= %99.9 | %100 (50/50) | ✅ PASS |
| SK-2 | p95 latency artisi | < 15ms | 21ms p95 (cache warm 13ms) | ⚠️ Marginal |
| SK-3 | Data leak | 0 incident | 0 (canViewReport BUG acik — PR1 ile kapatilacak) | ⚠️ AT RISK |
| SK-4 | Rollback suresi | < 5 dakika | < 1 dk | ✅ PASS |
| SK-5 | Decision log kapsami | %100 | OLCULEMEDI — baseline gerekli (CNS-003 #5) | ❌ UNKNOWN |
| SK-6 | Legacy permission-service | TRANSFORMED (D-003 DCP) | Aktif hub | ⚠️ DCP gerekli |
| SK-7 | Test coverage (authz kodu) | >= %80 | JaCoCo YOK — baseline gerekli | ❌ AT RISK |
| SK-8 | Frontend permission gate | 0 broken gate | 0 | ✅ PASS |
| SK-9 | @Filter/RLS kapsami | Tum company-scoped tablolar | 6/6 entity | ✅ PASS |
| SK-10 | Prod gecis downtime | 0 dakika | — | ⏳ PENDING |
| SK-11 | Batch-check p95 | < 50ms | 85ms p95 (batch-check adoption eksik — CNS-003 #7) | ❌ Optimize + adopt |
| SK-12 | Design Lab senaryo sayisi | >= 3 | 4 + 14 story | ✅ PASS |

**Skor: 5 PASS, 3 AT RISK/UNKNOWN, 2 OPTIMIZE, 1 PENDING, 1 DCP**

---

## 3. FAZLAR

### FAZ 0: STAGING FLAGS ON TEST — ✅ DONE

- Cache ttl=32s, /version + /me calisiyor, 0 ERROR
- 11/13 test PASS (T-02 cache HIT log N/A, T-07 dev fallback N/A)
- /authz/version: {"authzVersion":1}
- /authz/me: full response calisiyor (modules, actions, reports, roles)
- Report groups: HR_REPORTS, FINANCE_REPORTS, SALES_REPORTS, ANALYTICS_REPORTS

---

### FAZ 1: @FILTER / RLS GENISLETME — ✅ DONE (PR #314)

- 6 entity @Filter (UserRoleAssignment, Scope, UserPermissionScope, Company, User, VariantVisibility)
- 5 RLS SQL dosyasi (devops/postgres/01-05)
- CrossCompanyIsolationTest + RowFilterInjectorRlsTest (PR #317)
- DashboardQueryEngine RLS uyumlu

---

### FAZ 1.5: OBJECT-LEVEL CHECK — ✅ DONE (PR #305)

- /check reason, /batch-check endpoint
- useZanbibarAccess 3-layer hook (coarse gate → server check → access level)
- ZanbibarGate declarative component (full/readonly/disabled/hidden)
- 2 pilot entegrasyon (mfe-access + mfe-reporting) (PR #317)

---

### FAZ 2: PROD DEPLOY (Canary → Full Rollout) — ⚡ CANARY AKTIF (2026-04-12)

**Amac:** Feature flag ile kademeli gecis
**Efor:** M (5-10 gun, cogu gozlem suresi)
**Bagimlilik:** Dalga 3 gate'leri PASS

**3 Asama:**
```
Asama 1: Deploy (flags OFF) — 1 gun
   → container baslama, healthcheck, metrics akisi dogrulama
Asama 2: Canary (flags ON, ADMIN + RESTRICTED user) — 2-5 gun, 48h gozlem
   → Kriter: error rate < %0.1, p95 < 15ms, 0 data leak
   → MUST: restricted smoke user (deny senaryo) dahil (CNS-001)
   → Rollback: flag OFF (< 1 dk)
Asama 3: Kademeli (%10→%25→%50→%100) — 5-10 gun, her asamada 24h
   → Rollback kriteri: error rate > %0.5 VEYA p95 > 30ms
```

**Canary Guardrail Seti (Codex CNS-001):**
- deny/no_relation dagilimi
- OpenFGA upstream latency
- authz.cache.hit.rate
- OPENFGA_MODEL_ID ve OPENFGA_STORE_ID pod tutarliligi
- 60s frontend polling version tutarliligi

**Faz 2 Giris Gate'leri (CNS-003 — ZORUNLU):**
- [x] Rollback runbook kapsam dogrulamasi: RB-zanzibar-canary.md (113 satir, 3-stage)
- [x] SK-1 + SK-5 baseline olcumu: SK-1 %100, SK-5 5 endpoint
- [x] Doctor 3 fail RCA: 76/76 PASS (doctor fix merged)
- [x] Alerting tanimlari: authz-zanzibar-rules.yml (10 alert rule)

**DoD:**
- [ ] %100 rollout, 1 hafta stabil
- [ ] Error rate < %0.1
- [ ] Latency p95 < 15ms ek
- [ ] Alerting kurulmus
- [ ] Canary'de restricted user deny senaryosu PASS

**Riskler:**
- Cold cache performans (Orta/Yuksek) → warm-up script
- Network partition (Dusuk/Kritik) → fail-closed + flag OFF otomatik
- Model/version drift (Orta/Yuksek) → pod-arasi tutarlilik check (CNS-001)
- Admin-only canary (Yuksek) → restricted cohort ZORUNLU (CNS-001)

**Rollback:** Feature flag OFF (< 5 dk)

---

### FAZ 3: REPORT PERMISSION GROUPS — ✅ DONE (PR #339)

**Amac:** Rapor izinlerini OpenFGA'ya entegre
**Efor:** S (3-5 gun)
**Bagimlilik:** Faz 2 canary sonrasi

**Kapsam:**
- HR_REPORTS, FINANCE_REPORTS frontend entegrasyonu (test/showcase'de var)
- SALES_REPORTS, ANALYTICS_REPORTS frontend referansi eklenmeli (su an 0 referans)
- Report sayfalarina per-group permission filtering

**DoD:**
- [ ] 4/4 report group frontend'de aktif
- [ ] report-service check entegrasyonu
- [ ] Frontend'de erisilemez raporlar gizli

**Rollback:** Flag OFF + eski check'e don (< 5 dk)

---

### FAZ 3.5: DESIGN LAB SHOWCASE — ✅ DONE (PR #305 + #318)

- PermissionGatesShowcase: 4 senaryo (full/readonly/disabled/hidden)
- useZanbibarAccess live demo + AccessLevel matrix
- 14 Storybook story (982 satir) (PR #318)

---

### FAZ 4: MIGRATION TAMAMLAMA + LEGACY TEMIZLIK

**Onemli not:** D-003 "Permission-service REMOVED" karari guncellendi → "TRANSFORMED".
Permission-service artik OpenFGA hub: TupleSyncService + AuthzVersionService + roles CRUD + /authz/me.
Servis kaldirilamaz, donusturulmustur. (CNS-001 uzlasi)

| Alt Faz | Is | Efor | Paralel? | Durum |
|---------|-----|------|----------|-------|
| **4-a** | propagateRoleChange @TransactionalEventListener(AFTER_COMMIT) | S (2-3 gun) | Evet | ✅ DONE (PR #335 + #338) |
| **4-b** | D-003 DCP scope netlesme + deprecated temizlik | M (3-5 gun) | Evet | ✅ DONE (PR #335, -406 satir) |
| **4-c** | Audit hardening (deny log, Prometheus alert rule) | S (2-3 gun) | Evet | ⚠️ PARTIAL |
| **4-d** | Frontend mutation refresh | ✅ DONE — 60s version polling | — | ✅ DONE |

**Faz 4-a detay (Codex CNS-002 uzlasi):**
- @TransactionalEventListener(AFTER_COMMIT) + CompletableFuture.allOf.join (CNS-002 #2-3)
- @Async + thenRun YETERSIZ — stale state riski (CNS-002 #3)
- Kosullar: idempotent, retry + logging, queue depth + error count metrics
- Gelecekte garanti teslim gerekirse → outbox pattern dusunulsun

**Faz 4-b detay (Codex CNS-001 + CNS-002 uzlasi — genis DCP):**
- D-003: REMOVED → TRANSFORMED
- + ADR-0010, ADR-0012 guncellenmeli
- + registry summary, architecture index guncellenmeli
- + 28 deprecated constant temizligi
- + 2 deprecated controller temizligi
- + ConstantAuthzVersionProvider temizligi
- + mfe-users local useAuthorization migration
- **ON KOSUL:** TB-11 referans envanteri FREEZE (CNS-003 Q4)

**Rollback Faz 4-b:** Archive branch'den restore (< 1 saat, **YUKSEK RISK**)

---

### FAZ 5: TEST ALTYAPISI — ✅ DONE (PR #334, #340, #341)

| Item | Durum |
|------|-------|
| Docker smoke test script | ✅ Merged (#319) |
| Isolation tests | ✅ Merged (#317) |
| Storybook stories | ✅ Merged (#318) |
| CI smoke workflow (.github/workflows/) | ✅ Merged (#333) |
| Coverage gate (vitest + JaCoCo) | ✅ PR #334 (JaCoCo 4 modül + vitest workspace + codecov) |
| OpenFGA container integration test (Testcontainers) | ✅ PR #334 (OpenFgaContainerTest, CI @Tag integration) |
| RLS automated test | ✅ PR #334 (RlsPostgresContainerTest, CI @Tag integration) |
| HaloApplicationTests ON/OFF | ✅ PR #341 (@Disabled + testcontainers profile) |
| @TransactionalEventListener AFTER_COMMIT test | ✅ PR #340 (5/5 PASS) |
| ConditionalOnProperty combo test | ✅ PR #340 (ON 3/3 PASS) |
| @Filter CI gate | ✅ PR #340 (check-filter-gate.sh, 6/6 entity PASS) |
| SK-1/SK-5 telemetri baseline | ✅ PR #334 (zanzibar-sk-baseline.sh) |

**DoD:**
- [x] CI smoke workflow aktif
- [x] Coverage baseline alindi (JaCoCo + vitest + codecov)
- [x] OpenFGA container integration test PASS (CI-only)
- [x] RLS automated test PASS (CI-only)
- [x] @TransactionalEventListener AFTER_COMMIT davranis testi PASS

---

### FAZ 6: P3 — ERTELENMIS (SaaS kararina bagimli)

SaaS karari verildiginde aktiflesir (degisiklik yok).

---

## 4. UYGULAMA YOL HARITASI (4 Dalga — Codex uzlasi)

### DALGA 1: STABILIZE — ✅ DONE (4 PR merged: #325, #326, #328, #329)

| # | Is | PR | Durum |
|---|---|---|---|
| 1-A | Housekeeping | — | ✅ |
| 1-B | Cache config fix (TUM ZINCIR) | #329 | ✅ |
| 1-C | D-003 DCP | #325 | ✅ |
| 1-D | Minimum authz observability | #326 | ✅ |

### DALGA 2: FAZ 2 PROD HAZIRLIK — ✅ DONE (3 PR merged: #330, #332, #333)

| # | Is | PR | Durum |
|---|---|---|---|
| 2-A | Batch controller parallelStream | #332 | ✅ (5.2ms) |
| 2-B | Observability (core-data Prometheus + alert gauge fix) | #330 | ✅ |
| 2-C | CI smoke workflow + canary guardrails | #333 | ✅ |
| 2-D | Canary restricted probe + runbook | #333 | ✅ |

### DALGA 3: FAZ 3 + 5 TAMAMLAMA — ✅ DONE (PR #334, 8 commit)

**Giris Gate'leri (CNS-003 — ZORUNLU):**
- [x] Doctor 3 fail RCA: 3 fail = doctor script bug (D-003 TRANSFORMED). Doctor fix: 76/76 PASS.
- [x] SK-1 + SK-5 baseline: SK-1 %100 (2/2), SK-5 5 endpoint instrumented.

| # | Is | PR #334 Commit | Durum |
|---|---|---|---|
| **PR1** | AuthzTarget registry + canViewReport fail-closed + backend deny-default | cb0f414d | ✅ |
| hook fix | STEP_RESULTS unbound array | 86464150 | ✅ |
| **PR1-pre** | Batch-check hook yazildi ama ReportingHub'dan REVERT edildi (CNS-004: route≠group key) | f808eece→e00f37b7 | ⚠️ HOOK VAR, KULLANIM YOK |
| **PR2** | JaCoCo baseline (common-auth 45.6%, report-service 7.3%) | cc769573 | ✅ |
| **PR2-b** | SK-1/SK-5 telemetri baseline script | 2a986cc1 | ✅ |
| **PR3** | Testcontainers OpenFGA + RLS (CI-only, @Tag integration) | 6e167e4d | ✅ |
| **PR4** | Frontend coverage (vitest.workspace + codecov auth flag) | 463fbbc9 | ✅ |
| doctor fix | D-003 TRANSFORMED alignment (76/76 PASS) | c49d7b2f | ✅ |

**Siralama detayi (Codex CNS-003 Q1):**
- PR1 ONCE (security blocker) → PR2+PR2-b+PR3 PARALEL → PR4 paralel ama PR1 sonrasi rebase

### DALGA 4: FAZ 4 CLEANUP (CNS-003 revize — 5 PR)

**On kosul: TB-11 referans envanteri FREEZE (CNS-003 Q4 — HEMEN)**

| # | Is | Bagimlilik | Siralama |
|---|---|---|---|
| **PR5** | propagateRoleChange @TransactionalEventListener(AFTER_COMMIT) (CNS-002 #2-3) | Bagimsiz | Erken merge olabilir |
| **PR6-prereq** | auth-service legacy endpoint migration (CNS-002 #4) | PR6 onkosulu | PR5 ile paralel dev |
| **PR7** | mfe-users useAuthorization → usePermissions | PR6 onkosulu | PR6-prereq sonrasi |
| **PR6** | Deprecated temizlik (27 constant, 2 controller, 2 enum, 1 class) | PR6-prereq + PR7 SONRASI | En son |
| **PR8** | Grafana dashboard (mevcut metrikleri reuse — CNS-002 #6) | Bagimsiz | Paralel |

---

## 5. GUVENLIK BULGULARI (CNS-003 konsolide)

| # | Bulgu | Ciddiyet | Cozum PR | Durum |
|---|---|---|---|---|
| **R3-6** | canViewReport(undefined) = allow (implicit izin) | **KRITIK** | PR #334 (deny-default) | ✅ DUZELTILDI |
| **R4-1** | @Transactional async dispatch stale state okuyor | **YUKSEK** | PR #335 (AFTER_COMMIT) + PR #338 (@Transactional) | ✅ DUZELTILDI (test eksik — TB-15) |
| **R4-8** | auth-service PermissionServiceClient legacy endpoint canli | **YUKSEK** | PR #335 (/authz/me migration) + PR #338 (userId param) | ✅ DUZELTILDI |
| **Q7** | ReportAccessEvaluator legacy string (backend) | **ORTA** | PR #334 (reportGroup field + deny check) | ⚠️ KOD VAR ama report JSON'larda reportGroup bos (TB-18) |

---

## 6. TEST PLANI

| Tip | Kapsam | Araclar |
|-----|--------|---------|
| **Unit** | TupleSyncService, AuthzVersion, Cache, Filter | JUnit 5 + Mockito |
| **Integration** | JWT→OpenFGA→Cache→Response, RLS isolation | Testcontainers |
| **E2E** | Login→sayfa erisim, rol degisikligi→UI | Playwright |
| **Performance** | Check latency (cold/warm), cache ratio, RLS etkisi, batch p95 | k6 |
| **Security** | RLS bypass, JWT tampering, IDOR, cross-company leak | Manual pentest + automation |
| **Regression** | Mevcut CRUD, flag OFF davranis, frontend snapshot | Mevcut test suite |

---

## 7. RISK MATRISI (rev 6 — guncellenmis)

| Risk | Olasilik × Etki | Mitigation | Durum |
|------|-----------------|-----------|-------|
| **R3** RLS sorgu kirma | 16 (Y×Y) | Entity bazinda staging test | ✅ Mitigated (Faz 1 DONE) |
| **R8** Bus factor = 1 | 16 (Y×Y) | Runbook (PR #333) + kapsam dogrulamasi (CNS-003 #6) | ⚠️ Kapsam dogrulanmali |
| **R11** Deploy zinciri cache/version tasimiyor | 16 (Y×Y) | Dalga 1-B fix (PR #329) | ✅ Mitigated |
| **R14** canViewReport implicit allow | 16 (Y×K) | PR #334 deny-default | ✅ Mitigated |
| **R15** Batch-check kagit uzerinde | 12 (O×Y) | Hook var, ReportingHub revert (catalog reportGroup gerekli) | ⚠️ BEKLIYOR |
| **R12** Admin-only canary deny gizler | 12 (O×Y) | Restricted smoke user (CNS-001) | ✅ Mitigated (PR #333) |
| **R13** Model/version drift pod'lar arasi | 12 (O×Y) | Canary guardrail (CNS-001) | ✅ Mitigated (PR #333) |
| **R1** OpenFGA performans | 12 (O×Y) | Cache + warm-up | ⚠️ SK-11 optimize gerekli |
| **R2** Legacy D-003 DCP kapsamı | 12 (D×K) | TRANSFORMED (kaldirma degil) | ⚠️ DCP yazilmali |
| **R4** Cache version uyumsuzlugu | 12 (O×Y) | Single source of truth | ✅ Mitigated |

---

## 8. ZAMAN CIZELGESI (rev 6 — guncellenmis)

```
✅ Dalga 1:     STABILIZE — DONE (4 PR)
✅ Dalga 2:     FAZ 2 PROD HAZIRLIK — DONE (3 PR)

→ Dalga 3 Giris Gate:
                 ├── Doctor 3 fail RCA (1 gun)
                 └── SK-1 + SK-5 baseline (1 gun)

→ Dalga 3:      FAZ 3 + 5 TAMAMLAMA (5-10 gun)
                 ├── PR1 (security blocker, ONCE)
                 ├── PR1-pre (batch adoption, paralel)
                 ├── PR2 + PR2-b + PR3 (paralel)
                 └── PR4 (paralel, PR1 sonrasi rebase)

→ TB-11:        Permission-service referans envanteri FREEZE

→ Dalga 4:      FAZ 4 CLEANUP (5-10 gun)
                 ├── PR5 (bagimsiz, erken merge)
                 ├── PR6-prereq + PR7 (sirali)
                 ├── PR6 (en son)
                 └── PR8 (paralel)

→ Faz 2:        PROD DEPLOY (5-10 gun gozlem)
                 ├── Deploy (flags OFF)
                 ├── Canary (flags ON, restricted + admin)
                 └── Kademeli rollout (%10→%100)

→ Faz 6:        P3 ERTELENMIS (SaaS kararina bagimli)
```

---

## 9. RACI

| | Human | Claude | Codex |
|--|-------|--------|-------|
| Karar onay | **A** | R | C |
| Kod yazim | A | **R** | C (review) |
| Test yurutme | **R** | C | I |
| Prod deploy | **R** | C | I |
| Incident response | **R** | C | I |
| Dokumantasyon | A | **R** | C |
| Istisare | I | **R** | **R** |

---

## 10. TEKNIK BORC

| # | Borc | Cozum | Durum |
|---|------|-------|-------|
| TB-05 | ConditionalOnProperty kombinasyon testleri | PR #340 (ON 3/3 PASS) | ✅ |
| TB-06 | Docker smoke test | PR #319 | ✅ |
| TB-07 | OpenFGA model version yonetimi | Faz 5 scope — model.fga versioned | ✅ |
| TB-10 | @Filter CI gate | PR #340 (check-filter-gate.sh, 6/6 PASS) | ✅ |
| TB-11 | permission-service referans envanteri | PR #335 (65 ref, FROZEN) | ✅ |
| TB-12 | Doctor 3 fail RCA | PR #334 (3 fail = doctor bug, fix #338) | ✅ |
| TB-13 | SK-1/SK-5 baseline olcum | PR #334 (zanzibar-sk-baseline.sh) | ✅ |
| TB-14 | Batch-check gercek kullanim | PR #339 (canViewReport reportGroup pre-filter) | ✅ |
| TB-15 | @TransactionalEventListener AFTER_COMMIT test | PR #340 (5/5 PASS) | ✅ |
| TB-16 | HaloApplicationTests Testcontainers | PR #341 (@Disabled + testcontainers profile) | ✅ |
| TB-17 | Non-superAdmin canli deny testi | Staging serban-viewer (superAdmin=false, THEME denied) | ✅ |
| TB-18 | Report JSON'larda reportGroup field | PR #339 (31 JSON + 7 catalog) | ✅ |
| TB-19 | useBatchZanzibarAccess dead code | TB-14 cozuldu, hook gelecek use-case icin hazir | ✅ |
| TB-20 | PermissionCodes 27 deprecated inlined | PR #341 (8 dosya, class OpenFGA-only) | ✅ |
| TB-21 | PAGE/FIELD enum kaldirildi | PR #341 (V7+V9 DB temiz, enum+switch+test silindi) | ✅ |

**21/21 teknik borc KAPATILDI. Acik borc: 0.**

---

## 11. ISTISARE KAYDI

| ID | Tarih | Taraflar | Konu | Sonuc |
|----|-------|----------|------|-------|
| CNS-20260410-001 | 2026-04-10 | Claude + Codex (3 tur) | Progressive merge stratejisi | D) Hibrit — uzlasi |
| CNS-20260410-002 | 2026-04-10 | Claude → Codex | Merge sirasi | D) Progressive merge — tam uzlasi |
| CNS-20260411-001 | 2026-04-11 | Claude → Codex | Zanbibar yol haritasi + onceliklendirme | 3 itiraz kabul, 4 ek bulgu |
| CNS-20260411-002 | 2026-04-11 | Claude → Codex | Dalga 3+4 detayli plan | 5 itiraz kabul, 6 ek bulgu |
| **CNS-20260411-003** | **2026-04-11** | **Claude → Codex** | **7 itiraz + repo gercek durum dogrulamasi** | **7/7 kabul, 1 ek bulgu (roadmap manifest eksik)** |

---

## 12. CROSS-REPO SYNC MEKANIZMASI

| Mekanizma | Ne yapar |
|-----------|----------|
| Orchestrator SSOT | Zanbibar roadmap + status makine-okunur artifact |
| Dev repo mirror | scripts/sync_managed_repo_standards.py --sync-context |
| CI drift check | feature_execution_contract + delivery_session_packet freshness |
| Oturum sonu SOP | Her Zanbibar PR merge'unde orchestrator memory + plan guncelle |

---

## 13. KARAR UYUM KONTROLU

Her fazda kontrol:
- D-001: OpenFGA disinda auth engine YOK
- D-003: TRANSFORMED — permission-service OpenFGA hub olarak devam
- D-004: Shadow mode degil, flag ile gecis
- D-007: Yeni endpoint'lerde tenant_id var
- CNS-003 #3: Backend ReportAccessEvaluator deny-default + OpenFGA alignment
