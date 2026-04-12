# ZANZIBAR / OpenFGA — KAPSAMLI PROJE PLANI

**Proje Kodu:** PRJ-ZANZIBAR-OPENFGA
**Tarih:** 2026-04-12
**Revizyon:** 16 (Stage 3 %100 rollout + ADR-0012 Phase 3 + durable outbox)
**Karar Referansı:** D-001 → D-007 (tümü FINAL)
**Durum:** Faz 0-3.5 DONE, Faz 4 büyük kısmı DONE (4-b kaldı), Faz 5 devam

---

## 0. DENETİM BULGULARI VE DÜZELTMELER (rev 12, 2026-04-12)

Bu revizyon Claude + Codex bağımsız denetim (CNS-007) sonuçlarını içerir.

### Tespit Edilen Yapısal Sorunlar

| # | Bulgu | Kaynak | Durum |
|---|-------|--------|-------|
| D-01 | Plan dosyası untracked (`??`) — version control dışında | Codex | **AÇIK** |
| D-02 | `roadmaps/PROJECTS/PRJ-ZANZIBAR-OPENFGA/roadmap.v1.json` yok | İkisi | **AÇIK** |
| D-03 | `extensions/PRJ-ZANZIBAR-OPENFGA/` main'de yok (branch `329299d`'de var) | İkisi | **AÇIK** |
| D-04 | Extension manifest'te typo: `zanbibar-openfga.v1.json` | Codex | **AÇIK** |
| D-05 | Portfolio status'ta PRJ-ZANZIBAR-OPENFGA girişi yok | Codex | **AÇIK** |
| D-06 | Decision registry stale: rev 3, 2026-03-28 (15 gün eski) | İkisi | **AÇIK** |
| D-07 | SK-6 referansı: manifest `legacy_transformed_d003` — YANLIŞ, doğrusu D-002 | İkisi | **AÇIK** |
| D-08 | Plan 10 SK, manifest 12 SK — SK-11 (batch p95) ve SK-12 (design lab) plan'da eksik | İkisi | **AÇIK** |
| D-09 | Faz numaralama: plan FAZ 0-6, manifest FAZ-0/1/1.5/2/3/3.5/4/5 — tutarsız | İkisi | **AÇIK** |
| D-10 | RESOLVED consultation kararları plana yansımamış (CNS-001/002 action items) | İkisi | **AÇIK** |
| D-11 | Commit d80b17b mesajı ile diff uyuşmuyor | Codex | BİLGİ |
| D-12 | Backend/frontend rules hâlâ "permission-service" referansı — D-002'ye aykırı | Claude | **AÇIK** |
| D-13 | Zanzibar-specific enforcement policy yok (D-003/D-007 enforce edilmiyor) | İkisi | **AÇIK** |
| D-14 | T-01..T-13, RACI, Risk, TB tabloları machine-readable değil (sadece prose) | İkisi | **AÇIK** |
| D-15 | Cross-repo sync (standards.lock, feature exec contract) Zanzibar izi yok | İkisi | **AÇIK** |
| D-16 | Bozuk consultation referansları (CNS ID mismatch manifest'te) | Codex | **AÇIK** |
| D-17 | Memory `project_openfga_migration.md` stale ("PR #158 open" — eski) | Claude | **AÇIK** |

### Önceki Planla Karşılaştırma

| Konu | Eski Plan (rev 8) | Doğru Durum |
|------|-------------------|-------------|
| SK sayısı | 10 (SK-1..SK-10) | 12 (SK-11: batch p95 <50ms, SK-12: design lab 3+ senaryo) |
| Faz modeli | FAZ 0-6 (düz) | FAZ 0, 1, 1.5, 2, 3, 3.5, 4, 5, 6 (ara fazlar var) |
| SK-6 referansı | D-002 ✅ | Manifest'te D-003 ❌ — düzeltilecek |
| Plan tracking | Untracked | Git'e commit edilecek |
| Extension | Yok | Branch'te var ama typo'lu, main'e merge gerek |

---

## 1. PROJE AMACI

Mevcut JWT-based statik permission sistemi 3 kritik sorun içeriyor:
1. **Stale permission** — rol değiştiğinde JWT yenilenene kadar eski izinler aktif
2. **Hardcoded admin** — yeni roller için kod değişikliği gerekiyor
3. **Inline check tutarsızlığı** — her servis farklı kontrol yapıyor, data leak riski

**Hedef:** 4 katmanlı, fail-closed, auditlenebilir yetkilendirme:
```
Keycloak (authn) → OpenFGA (authz) → Hibernate @Filter + RLS (data) → Frontend SDK (UI)
```

---

## 2. BAŞARI KRİTERLERİ (12 adet — manifest ile hizalı)

| # | Kriter | Hedef | Mevcut | Durum |
|---|--------|-------|--------|-------|
| SK-1 | OpenFGA check başarı oranı | >= %99.9 | %100 | ✅ PASS |
| SK-2 | p95 latency artışı | < 15ms | 11-15ms | ✅ PASS |
| SK-3 | Data leak | 0 incident | 0 | ✅ PASS |
| SK-4 | Rollback süresi | < 5 dakika | < 1dk | ✅ PASS |
| SK-5 | Decision log kapsamı | %100 | Aktif | ✅ PASS |
| SK-6 | Permission-service transformed (D-003) | Hub olarak dönüştürüldü | TRANSFORMED | ✅ PASS |
| SK-7 | Test coverage (authz kodu) | >= %80 | common-auth 51.9%, report-service 13.4% | ❌ GAP |
| SK-8 | Frontend permission gate | 0 broken gate | 0 | ✅ PASS |
| SK-9 | @Filter/RLS kapsamı | Tüm company-scoped tablolar | 4/4 entity, 4/4 tablo | ✅ PASS |
| SK-10 | Prod geçiş downtime | 0 dakika | PENDING (canary aşaması) | ⏳ PENDING |
| SK-11 | Batch check p95 | < 50ms | 29-30ms | ✅ PASS |
| SK-12 | Design Lab senaryoları | 3+ senaryo | 4 senaryo | ✅ PASS |

**Skor: 10 PASS + 1 GAP + 1 PENDING = %83**

**NOT:** SK-6 referansı D-003'tür (permission-service TRANSFORMED — OpenFGA hub). Dev repo DCP (CNS-20260411-001) ile uzlaşılmış karar: kaldırma değil, dönüştürme. Manifest `legacy_permission_service_removed_d002` → düzeltilecek.

---

## 3. FAZ DURUMU (geçmiş — tamamlananlar)

| Faz | Açıklama | Durum | PR |
|-----|----------|-------|----|
| 0 | Staging flags ON test (8/8) | ✅ DONE | #305-#318 |
| 1 | @Filter/RLS (4 entity, 4 tablo, isolation test) | ✅ DONE | #314, #317 |
| 1.5 | can_edit, checkWithReason, batch-check, hooks, gates | ✅ DONE | #305 |
| 2 | Prod deploy flags ON (0% error, p95=15ms, Prometheus+Loki) | ✅ DONE | #316 |
| 3 | Report permission groups (4 group, 31 rapor, ZanzibarGate) | ✅ DONE | #346 |
| 3.5 | Design Lab (4 senaryo, playground, live demo, 14 story) | ✅ DONE | #318 |
| 4-d | Frontend mutation refresh (60s version polling + smart) | ✅ DONE | — |
| 4-c | Audit hardening (deny log + alert route + Grafana 5 rule) | ✅ DONE | PR #348 |
| 4-a | propagateRoleChange durable outbox (V11 migration + poller) | ✅ PR #350 | PR #350 AÇIK |
| 4-b | Faz 4-b scope netleştirme (D-003 TRANSFORMED) | ⏳ P3 | — |
| 5 | Test altyapısı (94 test yazıldı, SK-7 devam) | 🔄 DEVAM | PR #348 |
| 6 | P3 SaaS (DEFERRED — D-005) | 📋 DEFERRED | — |

### Dev Repo Merge Geçmişi (toplam 11 PR)
Oturum 1: #305, #307, #313, #314, #315, #316, #317, #318
Oturum 2: #346, #347
Orchestrator: #70, #71, #72, #73 (Orch #74 merge bekliyor)

---

## 4. STAGING DURUMU

| Metrik | Değer |
|--------|-------|
| Servis health | 18 healthy |
| OpenFGA | SERVING, v1.11.2 (pinli) |
| Vault | Unsealed (vault-unseal watcher + PR #347 health retry) |
| SK-2 latency | 11-15ms (parallel OpenFGA + cache enable + TTL 120s) |
| Model ID | 01KNX1PH3V4EQE4K25H8D77PHX |
| RLS | 4 tablo aktif (devops/postgres/ scripts) |

### Port Mapping (DİKKAT — localhost:8080 = Keycloak, gateway DEĞİL!)
| Servis | Host Port | Docker Internal |
|--------|-----------|-----------------|
| Keycloak | 8080 | keycloak:8080 |
| Gateway | 8082 | api-gateway:8080 |
| Permission-service | 8090 | permission-service:8084 |
| OpenFGA | 4000 | openfga:8080 |
| Eureka | 8761 | — |
| Prometheus | 9090 | — |

### Bilinen Sorunlar
1. **/authz/me boş dönüyor** — JWT audience mismatch (gateway vs servis)
2. **Vault auto-unseal** — PR #347 watcher çalışıyor ama health yetişemeyebilir
3. **JaCoCo coverage** — common-auth 51.9%, report-service 13.4% (hedef %80)

---

## 5. KALAN İŞLER — Rev 16 (2026-04-13)

### ✅ TAMAMLANAN (bu session)

| # | İş | PR / Kanıt |
|---|-----|-----------|
| P0-S | SSOT yapısal düzeltmeler (plan, roadmap, extension, decisions, rules) | Orch PR #77 MERGED |
| P0-R R-01..R-05 | Rollout wiring (runbook, metrics 4/4, prod alert, k6 env, C-004) | Dev PR #348 MERGED |
| P0-R R-06 | Stage 3 rollout %100 (4/4 servis ON) | Staging 18 healthy |
| P0-R R-07 | Audit alert notification route (Faz 4-c) | Dev PR #348 |
| P0-R R-08 | Doctor B7 D-003 alignment | Dev PR #348 |
| P1 C-01..C-06 | SK-7 authz core 94 test (SqlBuilder 12, ScopeCtxFilter 12, OpenFgaAuthz 25, DashQE 13, QueryEngine 6, Registry 15) | Dev PR #348 |
| P2 L-02 | SecurityConfig 11 test | Dev PR #348 |
| P2 M-16 | variant-service OpenFGA env var | Dev PR #348 |
| P2 M-14 | Faz 4-c audit alert route | Dev PR #348 |
| P2 M-01 | Dependabot triage (4 defer, 2 safe) | GitHub comments |
| P2 M-05 | ADR-0012 Phase 3: @PreAuthorize → @RequireModule (18/19 migrated) | Dev PR #349 AÇIK |
| P2 M-15 | Faz 4-a durable outbox (V11 migration, poller, dual-write) | Dev PR #350 AÇIK |
| — | Baseline fix (Spring 3.5, Node 22, @mfe/design-system) | Orch PR #77 + Dev PR #348 |
| — | CI fix (integration lane Java setup, work intake, schemas, checker) | Dev PR #348 |
| — | Vault re-init + unseal (backend-vault-1) | Manual staging fix |
| — | Cross-repo sync (37 dosya → 0 drift) | Orch → Dev |

### ⏳ AÇIK PR'LAR (merge bekliyor)

| PR | İş | Blocker |
|----|-----|---------|
| Dev #349 | ADR-0012 Phase 3 (@RequireModule) | 2 @WebMvcTest @Disabled — interceptor mock integration gerekli |
| Dev #350 | Faz 4-a durable outbox | Staging integration test gerekli |

### ❌ KALAN İŞLER (13 madde)

**P2 (6 iş — orta vade):**

| # | İş | Efor | Bağlam |
|---|-----|------|--------|
| H-03 | Rollback playbook staging testi | 0.5 gün | `RB-zanzibar-canary.md` Stage 2→1 rollback test |
| M-02 | Export/Repository testleri (CSV, Excel, CustomReport) | 1.5 gün | `report-service/.../export/`, `repository/` — 0% coverage |
| M-03 | ContextHealth modül testleri | 2 gün | `report-service/.../contexthealth/` — 1146 LOC, 0% coverage |
| M-04 | Playwright E2E staging çalıştırma | 0.5 gün | `web/tests/playwright/authz.zanzibar.spec.ts` — PW_REAL_USER_PASSWORD ENV gerekli |
| M-06 | k6 CI entegrasyonu | 0.5-1 gün | `scripts/perf/k6-zanzibar-check.js` — CI workflow yok |
| T-02 | Playwright CI entegrasyonu | 0.5 gün | `.github/workflows/` — ENV secret + workflow |

**P2 Orchestrator (2 iş):**

| # | İş | Efor | Bağlam |
|---|-----|------|--------|
| M-09 | Risk/TB/T-01..T-13 → machine-readable JSON | 0.5 gün | Plan prose → `roadmaps/PROJECTS/PRJ-ZANZIBAR-OPENFGA/` |
| M-10 | EP-016 legacy auth import ban | 0.5 gün | `ci/check_enforcement_rules.py` — Dalga 4 sonrası |

**P3 (5 iş — uzun vade):**

| # | İş | Bağlam |
|---|-----|--------|
| L-01 | Stale branch temizliği | `claude/theme-axis-tokens` dev repo |
| L-05 | OpenFGA model version management | Otomatik migration yok — `backend/openfga/model.fga` |
| L-06 | /authz/me audience fix | JWT gateway vs servis mismatch — `auth-service` JWT config |
| L-07 | compat.ts useAuthorization kaldırma | `web/packages/auth/src/compat.ts` — consumer audit önce |
| L-08 | Faz 4-b scope netleştirme | D-003 TRANSFORMED → tam scope tanımı `decisions/topics/` |

**DEFERRED (3 iş):**

| # | İş | Neden |
|---|-----|-------|
| F-01 | Faz 6 SaaS features | D-005 |
| F-05 | OpenFGA HTTP/2 tuning | Performans — gerek yok şu an |
| F-06 | RemoteAuthzVersionProvider WireMock testi | Nice-to-have |

### ⚠️ YARIM / SIĞ İŞLER (dikkat gerektiren)

| # | İş | Sorun | Aksiyon |
|---|-----|-------|---------|
| **PR #349** | ADR-0012 Phase 3 | 2 @WebMvcTest test @Disabled — `RequireModuleInterceptor` mock'u `@WebMvcTest` ile çalışmıyor | `@Import(WebMvcConfig.class)` + `@MockitoBean(OpenFgaAuthzService)` ile test yeniden yazılmalı |
| **PR #350** | Durable outbox | Outbox poller test yok — sadece compile + mevcut 5 test PASS | `TupleSyncOutboxPollerTest` yazılmalı (mock TupleSyncService + H2 outbox table) |
| **Vault** | backend-vault-1 | Container adı `platform-vault-1` değil `backend-vault-1` — compose project name uyumsuz | Deploy script compose project name kontrol etmeli veya `.env`'de `COMPOSE_PROJECT_NAME=platform` pin |
| **SK-7 coverage** | JaCoCo yeniden ölç | 94 test eklendi ama JaCoCo re-run yapılmadı — gerçek coverage bilinmiyor | `mvn verify -pl common-auth,report-service` ile JaCoCo raporu üret |
| **Baseline** | checklist 1 WARN | `PageLayout` design-system index'ten re-export edilmemiş | `web/packages/design-system/src/index.ts`'e PageLayout export ekle |

### DEV REPO MEVCUT ARTIFACT ENVANTERİ (agent taraması doğruladı)

| Kategori | Dosya Sayısı | Durum |
|----------|-------------|-------|
| Backend OpenFGA Java | 67 | ✅ Çalışıyor |
| Frontend @mfe/auth | 14 | ✅ Çalışıyor, 0 broken import |
| Storybook stories | 14 | ✅ |
| Backend testler | 27+ | ⚠️ Coverage yetersiz |
| Frontend testler | 5 suite | ✅ |
| ADR dokümanlar | 3 (0010, 0011, 0012) | ✅ |
| CI workflows | 3 (enforce, smoke, deploy) | ✅ |
| Doctor script | 25 check (17 kod + 8 runtime) | ✅ |
| k6 perf scripts | 3 | ✅ Script var, CI yok |
| Canary runbook + probe | 2 | ✅ |
| Grafana dashboard + alerts | 2 | ✅ Wiring doğrulanmamış |
| Docker OpenFGA + Vault | Tam config | ✅ v1.11.2 + 1.21.4 |
| Flyway migrations | V1-V10 | ✅ |
| RLS scripts | 1 (devops/postgres/) | ✅ 4 tablo aktif |

---

## 6. SK-7 DETAYLI YOL HARİTASI

### common-auth (51.9% → 80%)
| Modül | Mevcut | Test Sayısı | Öncelik |
|-------|--------|-------------|---------|
| ScopeContextFilter | 9% | 12-15 test (MockMvc + Mockito) | P1 |
| OpenFgaAuthzService | 17% | 20-25 test (Mockito OpenFgaClient mock) | P1 |
| RemoteAuthzVersionProvider | 55% | 5-8 test (WireMock) | P2 |
| AuthorizationContextBuilder | 75% | 3-5 test (edge cases) | P3 |

### report-service (13.4% → 80%)
| Modül | Mevcut | Test Sayısı | Öncelik |
|-------|--------|-------------|---------|
| SqlBuilder | 0% | 10-12 test (pure unit) | P1 ← EN HIZLI |
| Registry | 0% | 12-16 test (fixture JSON) | P1 |
| ReportController | 25% | 10-12 test (MockMvc) | P2 |
| DashboardQueryEngine | 0% | 15-20 test (Mockito) | P2 |
| QueryEngine | 0% | 8-10 test (Mockito) | P2 |
| Diğer (audit, filter, export) | — | 20-30 test | P3 |

**Toplam: 132-171 ek test, 8-12 gün efor (CNS-008 efor düzeltmesi ile)**

---

## 7. TEST PLANI

| Tip | Kapsam | Araçlar |
|-----|--------|---------|
| **Unit** | TupleSyncService, AuthzVersion, Cache, Filter | JUnit 5 + Mockito |
| **Integration** | JWT→OpenFGA→Cache→Response, RLS isolation | Testcontainers |
| **E2E** | Login→sayfa erişim, rol değişikliği→UI | Cypress/Playwright |
| **Performance** | Check latency (cold/warm), cache ratio, RLS etkisi | k6 |
| **Security** | RLS bypass, JWT tampering, IDOR, cross-company leak | Manual pentest |
| **Regression** | Mevcut CRUD, flag OFF davranış, frontend snapshot | Mevcut test suite |

---

## 8. RİSK MATRİSİ

| Risk | Olasılık × Etki | Mitigation | Durum |
|------|-----------------|-----------|-------|
| **R3** RLS sorgu kırma | 16 (Y×Y) | Entity bazında staging test | ✅ Mitigated (Faz 1 test) |
| **R8** Bus factor = 1 | 16 (Y×Y) | Dokümantasyon, runbook | ⚠️ Açık |
| **R1** OpenFGA performans | 12 (O×Y) | Cache + warm-up | ✅ Mitigated (SK-2 PASS) |
| **R2** Legacy kaldırma geri dönüş | 12 (D×K) | 2 hafta parallel | ⏳ Faz 4-b'de |
| **R4** Cache version uyumsuzluğu | 12 (O×Y) | Single source of truth | ✅ Mitigated |
| **R10** Staging-prod parity | 12 (O×Y) | IaC | ⚠️ Kısmen |
| **R11** Deploy materialization chain | — (O×Y) | CNS-001 bulgular | ⚠️ Açık (plana yansıtılmadı) |

---

## 9. TEKNİK BORÇ

| # | Borç | Öncelik | Faz | Durum |
|---|------|---------|-----|-------|
| TB-06 | Docker smoke test yok | Yüksek | Faz 5 | 🔄 Devam |
| TB-10 | @Filter CI gate kontrolü yok | Yüksek | Faz 1 | ✅ Mitigated |
| TB-11 | permission-service referans envanteri yok | Yüksek | Faz 4-b | ❌ Açık |
| TB-05 | ConditionalOnProperty kombinasyon testleri | Orta | Faz 5 | ❌ Açık |
| TB-07 | OpenFGA model version yönetimi yok | Orta | Faz 4-c | ❌ Açık |

---

## 10. KARAR UYUM KONTROLÜ

Her fazda kontrol:
- D-001: OpenFGA dışında auth engine YOK
- D-002: Keycloak = authentication ONLY (JWT'ye permission claim gömülmez)
- D-003: Permission-service = OpenFGA hub (kaldırılmayacak, SK-6 referansı BU)
- D-004: Shadow mode değil, flag ile geçiş
- D-007: Yeni endpoint'lerde tenant_id var

---

## 11. CONSULTATION GEÇMİŞİ

| CNS | Konu | Durum | Ana Karar |
|-----|------|-------|-----------|
| CNS-001 | 4-Wave Strategic Plan | RESOLVED | Wave 1 expand, restricted smoke user, deploy chain fix |
| CNS-002 | Dalga 3+4 Detay | RESOLVED | authzTarget registry, @TransactionalEventListener, auth-service prereq |
| CNS-003 | System NOT_READY→READY | OPEN | 4 wave readiness plan |
| CNS-004 | Design System Analysis | OPEN | Independent Codex analysis |
| CNS-005 | Design Lab + Zanzibar-Aware | OPEN | 3-layer ZanzibarGate önerisi |
| CNS-006/b | PRJ-DESIGN-LAB Evolution | OPEN | 6-phase plan, 10 tespit, 3 uzlaşı |
| CNS-007 | **Zanzibar Bağımsız Denetim** | RESOLVED | 17 bulgu (rev 12) |
| CNS-008 | **Kalan İş Listesi Denetimi** | RESOLVED | Efor düzeltmeleri, 4 ekleme, 6 öncelik değişikliği (rev 13) |
| CNS-009 | **Dev Repo Birleşik Backlog Denetimi** | RESOLVED | 7 itiraz (hepsi kabul), 8 ekleme, rollout wiring eksikleri (rev 15) |

---

## 12. ÖĞRENILEN DERSLER

1. CI bekleme: `sleep(150)` YAPMA, 30s'de kontrol et
2. Deploy: önce lokal test → commit → deploy (geriye dönme)
3. IMAGE_TAG: her PR merge sonrası güncellenmeli
4. enforcement-check: yeni dosyalar feature_execution_contract scope'una eklenmeli
5. UX catalog: yeni .tsx dosyaları ux_change_map.v1.json'a eklenmeli
6. FilterDef name conflict: aynı persistence unit'te unique isim zorunlu
7. ScopeFilterInterceptor: @PersistenceContext + @ConditionalOnBean gerekli
8. Flyway RLS: H2 desteklemez, devops/postgres/ scripts olarak yönet
9. **Plan version control dışı bırakılmamalı** (rev 12 bulgusu)
10. **Commit mesajı ile diff uyuşmalı** (rev 12 bulgusu)

---

## 13. BAŞLANGIÇ REHBERİ (Sonraki Oturum)

### Oku (sırasıyla)
1. **Bu plan:** `.claude/plans/zanzibar-master-plan.md` (rev 12)
2. **Memory:** `project_openfga_p0_cache.md`
3. **Staging ops:** `reference_staging_ops.md`

### Başla
1. **P0-S grubunu kapat** (9 SSOT düzeltmesi — 1-2 saat toplam)
2. **P0-R: Rollout altyapısı** (production'a giden yol)
3. **Veya P1 C-03: SqlBuilder** test (en hızlı SK-7 kazancı)

### Ortam
| Ortam | Durum |
|-------|-------|
| Dev repo main | ✅ (#346 squash, 5a1122c6) |
| Dev repo staging | ✅ 18 healthy, deploy SUCCESS |
| Orchestrator main | ✅ (#73 merged, PR #74 plan rev 11 bekliyor) |
| Vault | ✅ Unsealed (watcher + PR #347) |
| OpenFGA | ✅ SERVING, v1.11.2 |
| SK-2 | ✅ 11-15ms PASS |
