# ZANZIBAR / OpenFGA — KAPSAMLI PROJE PLANI

**Proje Kodu:** PRJ-ZANZIBAR-OPENFGA
**Tarih:** 2026-04-12
**Revizyon:** 13 (CNS-007 denetim + CNS-008 kalan iş istişaresi entegre)
**Karar Referansı:** D-001 → D-007 (tümü FINAL)
**Durum:** Faz 0-3.5 DONE, Faz 4 kısmen, Faz 5 devam ediyor

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
| SK-6 | Legacy permission-service | Transformed (D-002) | TRANSFORMED | ✅ PASS |
| SK-7 | Test coverage (authz kodu) | >= %80 | common-auth 51.9%, report-service 13.4% | ❌ GAP |
| SK-8 | Frontend permission gate | 0 broken gate | 0 | ✅ PASS |
| SK-9 | @Filter/RLS kapsamı | Tüm company-scoped tablolar | 4/4 entity, 4/4 tablo | ✅ PASS |
| SK-10 | Prod geçiş downtime | 0 dakika | PENDING (canary aşaması) | ⏳ PENDING |
| SK-11 | Batch check p95 | < 50ms | 29-30ms | ✅ PASS |
| SK-12 | Design Lab senaryoları | 3+ senaryo | 4 senaryo | ✅ PASS |

**Skor: 10 PASS + 1 GAP + 1 PENDING = %83**

**NOT:** SK-6 referansı D-002'dir (permission-service deprecation). Manifest'teki `legacy_transformed_d003` YANLIŞ — düzeltilecek.

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
| 4-c | Audit hardening (deny log var, alert mekanizması YOK) | ⚠️ KISMEN | — |
| 4-a | propagateRoleChange (senkron — async/durable gerekli) | ❌ YAPILMADI | — |
| 4-b | Legacy permission-service kaldır (D-002 scope netleşmeli) | ❌ YAPILMADI | — |
| 5 | Test altyapısı (devam ediyor) | 🔄 DEVAM | — |
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

## 5. KALAN İŞLER — 41 MADDE (CNS-007 + CNS-008 uzlaşısı)

*Codex CNS-008 istişaresi sonucu mükerrerler elendi, eforlar düzeltildi, öncelikler revize edildi.*
*Eski S-06/S-07/S-08/S-09/E-02/E-03 merge paketi içinde kapandı.*

### P0-S: SSOT Yapısal Düzeltmeler (5 iş — merge paketi)

| # | İş | Ref | Efor | Durum |
|---|-----|-----|------|-------|
| S-01 | Commit + PR (plan, roadmap, extension, decisions, rules, manifest) | D-01..D-09 | XS | ✅ Dosyalar hazır |
| S-02 | Decision drift closure (orch vs dev D-002/D-003 yorum hizala) | CNS-008 | 0.5 gün | AÇIK |
| S-03 | Extension typo temizliği (zanbibar→zanzibar, docs_ref doldur) | CNS-008 | XS | AÇIK |
| S-04 | Worktree birleştirme (quirky-bohr kalan parçaları al) | CNS-008 | XS | AÇIK |
| S-05 | Cross-repo sync çalıştır (dev repo drift ölç) | D-15 | 0.5 gün | AÇIK |

*NOT: Eski S-06 (SK-6 fix), S-07 (faz hizala), S-08 (consultation ref), S-09 (stale memory), E-02 (SK hizala), E-03 (rules fix) bu oturumda S-01 merge paketi içinde çözüldü.*

### P0-R: Rollout (3 iş — production, scope düzeltildi per CNS-008)

| # | İş | Efor | Not |
|---|-----|------|-----|
| R-01 | Mevcut flag promotion + runbook operationalize (greenfield DEĞİL) | 0.5 gün | Dev repo'da `RB-zanzibar-canary.md` mevcut |
| R-02 | Monitoring wiring doğrulama (mevcut dashboard threshold check) | 0.5 gün | Prometheus/Loki zaten var, efor daraltıldı |
| R-03 | Stage 3 gate-based rollout %10→%25→%50→%100 | 5-10 gün gözlem | |

### P1: SK-7 Coverage + Enforcement (10 iş — eforlar CNS-008 ile düzeltildi)

| # | İş | Efor | Not |
|---|-----|------|-----|
| C-01 | ScopeContextFilter MockMvc (12-15 test) | 1.5 gün | ↑ CNS-008: MockMvc tarafı pahalı |
| C-02 | OpenFgaAuthzService mock (20-25 test) | 2 gün | ↑ CNS-008: 393 LOC, branch yoğun |
| C-03 | SqlBuilder pure unit (10-12 test) — EN HIZLI KAZANÇ | 0.5 gün | = değişmedi |
| C-04 | DashboardQueryEngine testi (15-20 test) | 1.5 gün | ↑ CNS-008: boyut/branch yoğunluğu |
| C-05 | QueryEngine testi (8-10 test) | 0.5 gün | = değişmedi |
| C-06 | Registry testleri (12-16 test) | 1 gün | ↑ CNS-008: 2 registry + fixture yükü |
| C-07 | Rollback playbook staging testi | 0.5 gün | |
| E-01 | Consultation kararlarını plana yansıt (CNS-001/002 actions) | XS | |
| M-07 | Zanzibar enforcement policy (D-003 katman, D-007 tenant) | 1 gün | ↑ P2'den yükseltildi per CNS-008 |
| M-08 | Cross-repo sync Zanzibar izi (standards.lock + feature exec) | 0.5 gün | ↑ P2'den yükseltildi per CNS-008 |

### P2: Orta Vade (12 iş — L-02 eklendi, eforlar düzeltildi)

| # | İş | Efor | Not |
|---|-----|------|-----|
| M-01 | 6 dependabot PR triage | 0.5 gün | |
| M-02 | report-service export/repository testleri | 1.5 gün | ↑ CNS-008 |
| M-03 | ContextHealth modül testleri (1146 LOC, 0%) | 2 gün | ↑ CNS-008: birden fazla servis |
| M-04 | Playwright E2E staging çalıştırma | 0.5 gün | |
| M-05 | ADR-0012 Phase 3: JWT claim removal, @PreAuthorize→OpenFGA | 3-5 gün | |
| M-06 | k6 CI entegrasyonu | 0.5-1 gün | ↑ CNS-008: CI wiring + gate |
| M-09 | T-01..T-13, Risk, TB → machine-readable JSON | 0.5 gün | |
| M-10 | EP-016 legacy auth import ban implement et | 0.5 gün | |
| M-11 | EP-012 severity WARN→BLOCKED (Faz 4-b sonrası) | XS | |
| L-02 | SecurityConfig testi (Spring Security chain) | 1-2 gün | ↑ P3'ten yükseltildi, güvenlik kritik |
| M-12 | Extension/test kontrat temizliği (typo, boş ref) | 0.5 gün | YENİ per CNS-008 |
| M-13 | Portfolio kalıcılık doğrulaması | XS | YENİ per CNS-008 |

### P3: Uzun Vade (4 iş)

| # | İş |
|---|-----|
| L-01 | Stale branch temizliği (claude/theme-axis-tokens) |
| L-03 | Managed repo contract hardening / sync completion | 
| L-04 | SSOT roadmap milestone güncelle (roadmaps/SSOT/roadmap.v1.json) |
| L-05 | OpenFGA model version management (otomatik migration) |

*NOT: L-02 SecurityConfig P2'ye yükseltildi. L-03 "onboarding" → "contract hardening" olarak yeniden yazıldı per CNS-008.*

### DEFERRED (7 iş — SaaS kararına / geleceğe bağımlı)

| # | İş | Neden |
|---|-----|-------|
| F-01 | Faz 6 SaaS features (condition, event-driven, Redis) | D-005 |
| F-02 | service-manager unhealthy fix | Scope dışı |
| F-03 | Playwright CI entegrasyonu (ENV secret + workflow) | CI altyapı |
| F-04 | compat.ts useAuthorization kaldırma | Migration sonrası |
| F-05 | OpenFGA HTTP/2 tuning | Performans |
| F-06 | RemoteAuthzVersionProvider WireMock testi | Nice-to-have |
| F-07 | Grafana dashboard staging doğrulama | Observability |

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
- D-002: Permission-service kaldırılacak (SK-6 referansı BU)
- D-003: Katman sorumluluk sınırı korunuyor
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
