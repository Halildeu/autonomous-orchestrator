# ZANZIBAR / OpenFGA — KAPSAMLI PROJE PLANI (rev 11)

**Proje Kodu:** PRJ-ZANZIBAR-OPENFGA
**Tarih:** 2026-04-12
**Revizyon:** 11 (Deploy SUCCESS. 12/13 rev9 is kapatildi. 31 kalan is listesi.)
**Karar Referansi:** D-001 → D-007 (D-003 TRANSFORMED)
**Durum:** PR #346+#347 merged+deployed. Orch #73 merged. Staging 18 healthy. SK-2 11-15ms PASS.
**Istisare:** CNS-001..006b (7 Codex istisare, tumu uzlasi ile kapandi)
**Merged PRs:** #334-345 + #346 + #347 + Orch #71 + Orch #73

---

## OTURUM OZETI — REV 11 (2026-04-12 deploy + final audit)

Bu oturumda: cross-validation → 2 guvenlik fix → 53 test → SK-2 latency fix → vault retry → deploy SUCCESS → kapsamli kalan is audit.

### Bu Oturumda Tamamlanan (rev 9'daki 13 isten 12'si + ek isler)

| # | Is | PR | Durum |
|---|---|---|---|
| P0-1 | R16: ReportController CRUD authz | #346 | ✅ MERGED+DEPLOYED |
| P0-2 | R17: CustomReport access_config | #346 | ✅ MERGED+DEPLOYED |
| P0-3 | Playwright EPERM fix | quarantine | ✅ |
| P0-4 | PR #332 kapat | gh pr close | ✅ |
| P0-5 | Stage 3 karari (blocker'lar kapandi) | — | ✅ |
| P1-1 | SK-7: 53 yeni test | #346 | ✅ MERGED+DEPLOYED |
| P1-2 | R18: ReportingHub reportGroup | #346 | ✅ MERGED+DEPLOYED |
| P1-3 | ANALYTICS_REPORTS temizlik | #346 | ✅ MERGED+DEPLOYED |
| P1-4 | OpenFGA v1.11.2 pin | #346 | ✅ MERGED+DEPLOYED |
| P2-1 | SK-2: Parallel + cache (11-15ms) | #346 | ✅ MERGED+DEPLOYED |
| P2-2 | Deploy contract globs fix | #346 | ✅ MERGED+DEPLOYED |
| P3-1 | Vault retry health check | #347 | ✅ MERGED+DEPLOYED |
| P3-2 | Orchestrator extension + 11 test | Orch #73 | ✅ MERGED |
| EK | CNS-006 + CNS-006b Codex istisare | — | ✅ 7 tespit + 3 uzlasi |
| EK | JaCoCo gercek olcum | — | ✅ 51.9% / 13.4% |
| EK | Staging canli dogrulama | SSH | ✅ 18 healthy, SK-2 PASS |

### CNS-006 Sonuclari (Claude→Codex, dev repo taramasi)

| Madde | Codex Verdikti | Kanit |
|---|---|---|
| @Filter 6/6 | DOGRU | check-filter-gate.sh PASS |
| ANALYTICS_REPORTS | KISMI | Seed/registry var, JSON yok |
| PR #332 | KISMI | Repo icinden dogrulanamadi |
| OpenFGA latest | KISMI | Keycloak/Vault pinli, OpenFGA degil |
| Playwright | KISMI | EPERM ile FAIL, 12 Nisan artifact failed |
| @Filter eksik entity | YANLIS (eksik yok) | Gate script PASS |
| Legacy useAuthorization | DOGRU (sifir) | Sadece compat.ts |
| canViewReport deny-default | DOGRU | 11/11 test PASS |
| ReportingHub filtering | KISMI | Statik OK, dinamik/dashboard bypass |
| Ek guvenlik acigi | DOGRU — 2 YENI | ReportController + CustomReport |

### CNS-006b Uzlasi (3 anlasmazlik noktasi)

| Nokta | Claude | Codex Son Verdikt | Uzlasi |
|---|---|---|---|
| ANALYTICS_REPORTS | Orphan/tutarsiz | "Orphan degil ama tutarsiz ve temizlenmeli" | ✅ Uzlasi |
| PR #332 | Kapatilmali | "Claude'a katiliyorum, korunmali delta yok" | ✅ Uzlasi |
| OpenFGA pin | Zorunlu | "Hard zorunlu diyemem ama operasyonel olarak fiilen zorunlu hijyen" | ✅ Uzlasi |

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

## 2. BASARI KRITERLERI (rev 9 — cross-validated)

| # | Kriter | Hedef | Olcum (dogrulanmis) | Durum |
|---|--------|-------|---------------------|-------|
| SK-1 | OpenFGA check basari orani | >= %99.9 | %100 (50/50 check) | ✅ PASS |
| SK-2 | p95 latency artisi | < 15ms | 32-39ms warm (cache 10s) | ❌ FAIL |
| SK-3 | Data leak | 0 incident | 0 (deny-default aktif) | ✅ PASS |
| SK-4 | Rollback suresi | < 5 dakika | < 1 dk (flag OFF) | ✅ PASS |
| SK-5 | Decision log kapsami | %100 | authz.decision log aktif, 5 endpoint | ✅ PASS |
| SK-6 | Legacy permission-service | TRANSFORMED | D-003 DCP + ADR-0010 | ✅ PASS |
| SK-7 | Test coverage (authz kodu) | >= %80 | common-auth 45%, report-service 7% | ❌ FAIL |
| SK-8 | Frontend permission gate | 0 broken gate | 0 | ✅ PASS |
| SK-9 | @Filter/RLS kapsami | Tum company-scoped | 6/6 entity (gate script PASS) | ✅ PASS |
| SK-10 | Prod gecis downtime | 0 dakika | Canary'de, henuz prod degil | ⏳ PENDING |
| SK-11 | Batch-check p95 | < 50ms | 29-30ms warm | ✅ PASS |
| SK-12 | Design Lab senaryo sayisi | >= 3 | 4 + 14 story | ✅ PASS |

**Skor: 8 PASS, 2 FAIL, 1 PENDING = %67 (onceki %58)**

---

## 3. FAZLAR

### FAZ 0: STAGING FLAGS ON TEST — ✅ DONE

- 11/13 test PASS, 0 ERROR
- Report groups: HR_REPORTS(9), FINANCE_REPORTS(20), SALES_REPORTS(2), ANALYTICS_REPORTS(seed/registry var ama report JSON atamasi yok)

### FAZ 1: @FILTER / RLS GENISLETME — ✅ DONE (PR #314)

- 6 entity @Filter (dogrulanmis: Company, User, Scope, UPS, URA, VariantVisibility)
- 4 RLS SQL dosyasi (devops/postgres/02-05)
- check-filter-gate.sh PASS

### FAZ 1.5: OBJECT-LEVEL CHECK — ✅ DONE (PR #305)

- /check, /batch-check endpoint
- useZanbibarAccess + ZanbibarGate + 2 pilot entegrasyon

### FAZ 2: PROD DEPLOY — ⚡ CANARY 48H DOLDU, STAGE 3 KARARI GEREKLI

**Asama 2 (Canary) durumu:**
- 19/19 servis UP, batch-check 5.2ms, doctor 47/47 PASS
- Canary 48h gozlem tamamlandi (2026-04-12)

**Stage 3 giris kosullari (YENI — CNS-006):**
- [ ] ReportController guvenlik acigi KAPATILMALI (R16)
- [ ] CustomReport access_config enforce edilmeli (R17)
- [ ] OpenFGA image pinlenmeli (TB-24)
- [ ] Playwright E2E calisir hale gelmeli (TB-22)
- [x] Canary 48h doldu
- [x] Error rate < %0.1
- [x] Alerting aktif

**DoD (degismedi):**
- [ ] %100 rollout, 1 hafta stabil
- [ ] Error rate < %0.1
- [ ] Latency p95 < 15ms ek
- [ ] Canary'de restricted user deny senaryosu PASS

### FAZ 3: REPORT PERMISSION GROUPS — ⚠️ PARTIAL (CNS-006 revizyonu)

**Onceki durum:** ✅ DONE (PR #339)
**Revize durum:** ⚠️ PARTIAL — 3 sorun tespit edildi:

1. **ANALYTICS_REPORTS tutarsizligi:** Seed + registry + catalog'da tanimli, report JSON'larda atamasi yok, dashboard'larda yok
2. **ReportingHub bypass:** Dinamik rapor + dashboard `reportGroup` tasimiyor → `!item.reportGroup || canViewReport(...)` bypass
3. **DashboardController:** report-group bazli kontrol yapmiyorr

**Revize DoD:**
- [x] 3/4 report group report JSON'larda aktif (FINANCE=20, HR=9, SALES=2)
- [ ] ANALYTICS_REPORTS ya raporlara atanmali ya da temizlenmeli
- [ ] Dinamik rapor/dashboard catalog'a reportGroup eklenmeli
- [ ] DashboardController'a reportGroup check eklenmeli

### FAZ 3.5: DESIGN LAB SHOWCASE — ✅ DONE (PR #305 + #318)

### FAZ 4: MIGRATION TAMAMLAMA + LEGACY TEMIZLIK

| Alt Faz | Is | Durum |
|---------|-----|-------|
| **4-a** | AFTER_COMMIT dispatch | ✅ DONE (PR #335 + #338) |
| **4-b** | D-003 DCP + deprecated temizlik | ✅ DONE (PR #335) |
| **4-c** | Audit hardening | ⚠️ PARTIAL |
| **4-d** | Frontend mutation refresh | ✅ DONE |

### FAZ 5: TEST ALTYAPISI — ✅ DONE (PR #334, #340, #341)

(icerik degismedi — 12/12 item tamamlandi)

### FAZ 6: P3 — ERTELENMIS (SaaS kararina bagimli)

---

## 4. GUVENLIK BULGULARI (rev 9 — CNS-006 konsolide)

### Duzeltilmis Bulgular

| # | Bulgu | Ciddiyet | PR | Durum |
|---|---|---|---|---|
| R3-6 | canViewReport(undefined) = allow | KRITIK | PR #334 | ✅ DUZELTILDI |
| R4-1 | AFTER_COMMIT stale state | YUKSEK | PR #335+#338 | ✅ DUZELTILDI |
| R4-8 | auth-service legacy endpoint | YUKSEK | PR #335+#338 | ✅ DUZELTILDI |
| Q7 | ReportAccessEvaluator string | ORTA | PR #334 | ✅ DUZELTILDI (test 11/11 PASS) |

### YENI Bulgular (CNS-006 — ACIK)

| # | Bulgu | Ciddiyet | Kanit | Aksiyon |
|---|---|---|---|---|
| **R16** | ReportController CRUD/history endpoint'leri sadece `authenticated()` arkasinda — reportGroup/OpenFGA check YOK | **YUKSEK** | ReportController.java:101, SecurityConfig.java:49 | OpenFGA check ekle |
| **R17** | CustomReport `access_config` saklaniyor ama list endpoint'te UYGULANMIYOR | **ORTA** | CustomReportRepository.java:28,45 | List query'ye access_config filtresi ekle |
| **R18** | ReportingHub dinamik rapor/dashboard `reportGroup` tasimiyor → filtre bypass | **ORTA** | useCatalog.ts:63,79 — `!item.reportGroup \|\| canViewReport(...)` | Catalog map'e reportGroup ekle |

---

## 5. TEKNIK BORC (rev 9)

### Kapatilmis (21/21 — onceki oturumdan)

TB-05..TB-21 tumu KAPATILDI (degisiklik yok).

### YENI Teknik Borc (CNS-006)

| # | Borc | Ciddiyet | Kaynak |
|---|------|----------|--------|
| **TB-22** | Playwright authz.zanzibar.spec.ts EPERM ile FAIL — transform cache permission sorunu | YUKSEK | CNS-006 #5 |
| **TB-23** | ANALYTICS_REPORTS tutarsizligi — seed/registry var, JSON/dashboard atamasi yok | ORTA | CNS-006 #2, CNS-006b #1 |
| **TB-24** | OpenFGA image `latest` → `v1.11.2` pin (breaking change riski: pgxpool migration) | ORTA | CNS-006 #4, CNS-006b #3 |
| **TB-25** | PR #332 hala OPEN — #342 superseded, kapatilmali | DUSUK | CNS-006b #2 |
| **TB-26** | SK-7 test coverage 45%/7% — hedef >=80% | YUKSEK | Cross-validation |
| **TB-27** | Orchestrator entegrasyonu eksik (extension dir + SSOT roadmap + managed repo) | ORTA | Cross-validation |

**Toplam: 21 kapatilmis + 6 yeni = 27 (6 acik)**

---

## 6. RISK MATRISI (rev 9)

| Risk | Olasilik × Etki | Mitigation | Durum |
|------|-----------------|-----------|-------|
| **R16** ReportController CRUD yetki yok | 16 (Y×Y) | OpenFGA check + @PreAuthorize | ❌ ACIK — Stage 3 BLOCKER |
| **R3** RLS sorgu kirma | 16 (Y×Y) | Entity bazinda staging test | ✅ Mitigated |
| **R8** Bus factor = 1 | 16 (Y×Y) | Runbook + dokumantasyon | ⚠️ Devam |
| **R17** CustomReport access_config uygulanmiyor | 12 (O×Y) | List query filtre | ❌ ACIK |
| **R18** ReportingHub dinamik bypass | 12 (O×Y) | Catalog reportGroup | ❌ ACIK |
| **R15** Batch-check kullanim drift | 12 (O×Y) | ReportingHub adoption | ⚠️ BEKLIYOR |
| **R1** OpenFGA performans (SK-2) | 12 (O×Y) | Cache + proximity | ⚠️ SK-2 FAIL |
| **R19** OpenFGA latest image drift | 9 (O×O) | Version pin | ❌ ACIK |
| **R14** canViewReport implicit allow | 16 (Y×K) | deny-default | ✅ Mitigated |
| **R11** Deploy zinciri | 16 (Y×Y) | PR #329 | ✅ Mitigated |

---

## 7. KALAN IS LISTESI (rev 11 — 31 madde, derinlesmis)

### P0 — Rollout Oncesi (3 is)

| # | Is | Efor | Detay |
|---|---|---|---|
| K-3 | **Stage 3 kademeli rollout** | 5-10 gun gozlem | %10→%25→%50→%100, her asamada 24h |
| H-1 | **Rollout altyapisi** | 1-2 gun | Feature flag gradual mekanizmasi (user cohort secimi) |
| H-2 | **Rollout monitoring dashboard** | 1 gun | Error rate, latency, deny dagilimi, cache hit rate izleme |

### P1 — Kisa Vade (5 is)

| # | Is | Efor | Detay |
|---|---|---|---|
| K-1 | **SK-7 common-auth 51.9%→80%** | 2-3 gun | ScopeContextFilter(9%), OpenFgaAuthzService(17%) → 40-53 test |
| K-2 | **SK-7 report-service 13.4%→80%** | 4-6 gun | SqlBuilder, Registry, QueryEngine, DashboardQE → 92-118 test |
| O-1 | **ScopeContextFilter testi** | 1 gun | MockMvc + Mockito: doFilterInternal, cache HIT/MISS, fallback (12-15 test) |
| O-2 | **OpenFgaAuthzService testi** | 1.5 gun | Mockito: listObjects, check, batchCheck, timeout, dev fallback (20-25 test) |
| H-3 | **Rollback playbook staging testi** | 0.5 gun | RB-zanzibar-canary.md gercek rollback ile test |

### P2 — Orta Vade (11 is)

| # | Is | Efor | Detay |
|---|---|---|---|
| K-5 | **Dependabot PR triage** | 1-2 saat | 6 acik PR (TS 5.9, zod 4, react-router 7, vite-react 6, commons-compress) |
| O-3 | **DashboardQueryEngine testi** | 1.5 gun | Mockito: KPI/chart, time range, filter injection (15-20 test) |
| O-4 | **QueryEngine testi** | 1 gun | Mockito: SQL build, pagination, RLS injection (8-10 test) |
| O-5 | **SqlBuilder testi** | 1 gun | Pure unit: SELECT/COUNT/EXPORT, UNION ALL, schema (10-12 test) |
| O-6 | **Registry testleri** | 1 gun | Pure unit: JSON loading, validation, dangerous keyword (12-16 test) |
| O-7 | **Playwright E2E staging** | 1 gun | PW_REAL_USER_PASSWORD ENV ayari + CI entegrasyonu |
| H-4 | **ContextHealth modul testleri** | 2-3 gun | 10 dosya, 1146 LOC, file reading + chart/grid/KPI service |
| H-5 | **Export/Repository testleri** | 1-2 gun | CSV, Excel exporter + CustomReport, Schedule, Alert repo |
| H-10 | **ADR-0012 Phase 3: JWT claim removal** | 3-5 gun | @PreAuthorize→OpenFGA runtime, Keycloak mapper kaldir |
| H-11 | **k6 CI entegrasyonu** | 1 gun | k6 script var, CI'da otomatik calistirma |
| T-2 | **Playwright CI entegrasyonu** | 1 gun | ENV secret + CI workflow |

### P3 — Uzun Vade (5 is)

| # | Is | Efor | Detay |
|---|---|---|---|
| K-6 | **Stale branch temizligi** | 5 dk | claude/theme-axis-tokens sil |
| H-6 | **SecurityConfig testi** | 0.5 gun | Spring Security chain integration test |
| H-7 | **Managed repo onboarding** | 1 gun | Dev repo → managed_repos.v1.json, ilk sync dry-run |
| H-8 | **SSOT roadmap milestone** | 0.5 gun | roadmaps/SSOT/roadmap.v1.json'a Zanbibar milestone |
| H-12 | **OpenFGA model version management** | 1-2 gun | model.fga otomatik migration |

### DEFERRED (7 is — SaaS/gelecege bagimli)

| # | Is | Detay |
|---|---|---|
| H-9 | Faz 6 P3 SaaS | Condition/context, event-driven invalidation, multi-tenant, Caffeine→Redis |
| T-1 | service-manager unhealthy | Pre-existing, scope disi |
| T-3 | compat.ts useAuthorization kaldir | Consumer yok, export kaldirabilir |
| T-4 | OpenFGA HTTP/2 tuning | Client HTTP/2 multiplexing |
| T-5 | RemoteAuthzVersionProvider WireMock | 55% → WireMock testi |
| T-6 | Grafana dashboard staging dogrulama | JSON var, Grafana import dogrulanmadi |
| K-4 | Plan orchestrator main sync | Worktree conflict sonrasi plan kaybi duzeltilmeli |

**Toplam: 3 P0 + 5 P1 + 11 P2 + 5 P3 + 7 DEFERRED = 31 is (~25-40 gun)**

---

## 8. ZAMAN CIZELGESI (rev 11)

```
✅ TAMAMLANDI (bu oturum dahil):
   ├── Dalga 1-4 (14 PR)
   ├── Faz 0, 1, 1.5, 3, 3.5, 5
   ├── Canary 48h (Faz 2 Stage 2)
   ├── R16+R17+R18 guvenlik fix (PR #346)
   ├── SK-2 latency 11-15ms (PR #346)
   ├── 53 yeni test (PR #346)
   ├── OpenFGA v1.11.2 pin (PR #346)
   ├── Vault retry (PR #347)
   ├── Orchestrator extension (Orch #73)
   └── Deploy SUCCESS — 18 healthy

→ SPRINT 1 (1-2 hafta):
   ├── H-1: Rollout altyapisi (1-2 gun)
   ├── H-2: Monitoring dashboard (1 gun)
   └── K-3: Stage 3 rollout %10→%100 (5-10 gun gozlem)

→ SPRINT 2 (2-3 hafta, Stage 3 paralel):
   ├── K-1: SK-7 common-auth 80% (2-3 gun)
   ├── K-2: SK-7 report-service 80% (4-6 gun)
   └── H-3: Rollback playbook test (0.5 gun)

→ SPRINT 3 (sonrasi):
   ├── P2 isler (dependabot, Playwright CI, ADR-0012)
   ├── P3 isler (managed repo, SSOT roadmap)
   └── DEFERRED (SaaS kararina bagimli)
```

---

## 9. ISTISARE KAYDI (rev 9)

| ID | Tarih | Taraflar | Konu | Sonuc |
|----|-------|----------|------|-------|
| CNS-001 | 2026-04-11 | Claude → Codex | Dalga 1+2 roadmap | 3 itiraz kabul |
| CNS-002 | 2026-04-11 | Claude → Codex | Dalga 3+4 plan | 5 itiraz kabul |
| CNS-003 | 2026-04-11 | Claude → Codex | 7 itiraz + repo dogrulama | 7/7 kabul |
| CNS-004 | 2026-04-11 | Codex bug hunt | 5 bug bulundu | Tumu duzeltildi |
| CNS-005 | 2026-04-11 | Codex kritik bulgu | auth-service, @Transactional | Tumu duzeltildi |
| **CNS-006** | **2026-04-12** | **Claude → Codex** | **Cross-validation: 10 tespit dogrulamasi** | **2 yeni guvenlik acigi, Playwright KIRIK, ReportingHub bypass** |
| **CNS-006b** | **2026-04-12** | **Claude → Codex** | **3 anlasmazlik uzlasi** | **3/3 uzlasi: ANALYTICS tutarsiz, #332 kapat, OpenFGA pin zorunlu** |

---

## 10. RACI (degismedi)

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

## 11. CROSS-REPO SYNC (degismedi)

| Mekanizma | Ne yapar |
|-----------|----------|
| Orchestrator SSOT | Zanbibar roadmap + status artifact |
| Dev repo mirror | sync_managed_repo_standards.py |
| CI drift check | feature_execution_contract freshness |
| Oturum sonu SOP | Her PR merge'de orchestrator memory + plan guncelle |

---

## 12. KARAR UYUM KONTROLU (rev 9)

- D-001: OpenFGA disinda auth engine YOK ✅
- D-003: TRANSFORMED — permission-service OpenFGA hub ✅
- D-004: Shadow mode degil, flag ile gecis ✅
- D-007: Yeni endpoint'lerde tenant_id var ✅
- CNS-003 #3: Backend deny-default ✅
- **CNS-006 YENI:** ReportController deny-default eksik ❌ → P0-1
- **CNS-006 YENI:** CustomReport access_config enforce eksik ❌ → P0-2
