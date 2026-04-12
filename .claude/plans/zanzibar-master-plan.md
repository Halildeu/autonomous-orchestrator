# Zanzibar Master Plan — Rev 17 (Konsolide Final)

**Tarih:** 2026-04-13
**Kaynak:** Claude analizi + Codex istisaresi (CNS-20260413-001, 150K token)
**Worktree:** claude/festive-golick
**Base:** main @ 5b18297a

---

## 0. DOGRULAMA OZETI

Onceki session notlari guncel repo ile capraz dogrulandi. Duzeltmeler:

| Onceki Not | Gercek Durum | Karar |
|------------|-------------|-------|
| 2 test @Disabled | Testler aktif (fix yapilmis) | Listeden cikarildi |
| PageLayout export eksik | Zaten export ediliyor | Listeden cikarildi |
| Outbox'ta sadece SQL var | Java siniflar da var (branch'te) | PR #350 hardening olarak guncellendi |
| Playwright secret yok | Secret CI'da tanimli | Listeden cikarildi |
| M-04 Playwright E2E | CI-entegre, calisiyor | Tamamlandi |

---

## 1. MEVCUT DURUM

### Derin (Saglam) Katmanlar
- OpenFGA model (model.fga): 9 tip, deny-wins, hiyerarsik miras
- OpenFgaAuthzService: fail-closed, 10s cache, batch, audit log, explain
- TupleSyncService: deny-wins resolution, batch ops, version-based invalidation
- ScopeContext + @Filter + PostgreSQL RLS: 3 katmanli data enforcement
- Frontend @mfe/auth: 3-katman (me cache -> check -> UI gate)
- Decision registry: 12 FINAL karar, 5 constraint, revision tracking
- Playwright authz E2E: CI-entegre, restricted user deny senaryosu

### Acik PR'lar
- PR #349 (ADR-0012 Phase 3): OPEN, MERGEABLE, 28/28 check PASS
- PR #350 (Faz 4-a outbox): OPEN, 3 check FAILING

### Guvenlik Bulgulari (Codex Dogruladi)

**permitAll catch-all — FIILI ACIK (teorik degil):**

| Servis | Profil | Korunmayan Endpoint Ornekleri |
|--------|--------|-------------------------------|
| report-service | !local & !dev & !conntest | AlertController, ScheduleController, ContextHealthController |
| user-service | !local & !dev | /api/audit/events |
| api-gateway | !local & !dev | non-API path'ler acik |
| variant-service | !local & !dev | risk dusuk (tum controller /api/v1/ altinda) |
| auth-service | !local & !dev | catch-all mevcut ama kasitli public path'ler var |
| schema-service | PROFIL YOK | AUTH_MODE=permitAll -> FULL BYPASS |

**Guvenli:** permission-service, core-data-service (authenticated() catch-all)

**ERP_OPENFGA_ENABLED=false default:** Fail-open — disabled modda tum check() -> true.

### PR #350 Detay (Codex Tespiti)
- V11 SQL migration + Java (Entity/Repository/Poller): MEVCUT
- @EnableScheduling YOK -> poller inert (KRITIK BUG)
- .claude/worktrees gitlink kazara commit edilmis
- Test: YOK, Row-level locking: YOK
- CI: enforcement + delivery-contract + delivery-gate FAILING

---

## 2. ONCELIK SIRASI (Claude + Codex Uzlasi)

### PR-A: PR #349 Merge (5 dk)

- [ ] gh pr merge 349 --squash
- [ ] Merge sonrasi main smoke check

### PR-B: Prod Auth Surface Hardening (1 gun)

**report-service (EN KRITIK):**
- [ ] SecurityConfig.java:53 — anyRequest().permitAll() -> anyRequest().authenticated()
- [ ] Tum controller path'lerin /api/v1/** altinda oldugunu dogrula
- [ ] AlertController, ScheduleController, ContextHealthController korunmali

**user-service:**
- [ ] SecurityConfig.java:63 — anyRequest().permitAll() -> anyRequest().authenticated()
- [ ] /api/audit/events icin /api/v1/** altina tasi veya explicit matcher

**api-gateway:**
- [ ] SecurityConfig.java:51 — anyExchange().permitAll() -> anyExchange().authenticated()
- [ ] /api/auth/cookie icin explicit permitAll matcher ekle

**variant-service:**
- [ ] SecurityConfig.java:39 — anyRequest().permitAll() -> anyRequest().authenticated()

**auth-service (SecurityConfigKeycloak):**
- [ ] SecurityConfigKeycloak.java:53 — anyRequest().permitAll() -> anyRequest().authenticated()

**schema-service (KRITIK):**
- [ ] AUTH_MODE=permitAll icin @Profile("local") kisitlamasi ekle
- [ ] Non-local'da startup fail veya ignore

**Non-local startup guard (Codex onerisi):**
- [ ] Non-local profilde ERP_OPENFGA_ENABLED=false veya store/model ID bos -> WARN log
- [ ] ApplicationRunner veya @PostConstruct ile kontrol

**Vault naming fix:**
- [ ] docker-compose.yml:268 — backend-vault-1 -> platform-vault-1

**Test:**
- [ ] Her servis icin: korunan endpoint'e token'siz istek -> 401 testi

### PR-C: PR #350 Hardening (1.5 gun)

- [ ] .claude/worktrees gitlink'i branch'ten cikar
- [ ] PermissionServiceApplication.java — @EnableScheduling ekle
- [ ] TupleSyncOutboxPoller — SELECT FOR UPDATE SKIP LOCKED
- [ ] TupleSyncOutboxPoller — idempotency: ayni roleId duplicate entry onleme
- [ ] TupleSyncOutboxPollerTest yaz
- [ ] RoleChangeEventHandlerTest guncelle
- [ ] CI hatalarini coz
- [ ] Delivery dokumanlarini tamamla

### PR-D: Staged Rollout + E2E Test (2 gun)

**On kosul:** PR-B ve PR-C merged olmali.

**E2E Integration Test:**
- [ ] RoleTupleCheckIntegrationTest (Testcontainers PostgreSQL + OpenFGA)
  - Role ata -> tuple yaz -> check -> ALLOW
  - Role kaldir -> tuple sil -> check -> DENY
  - Scope ata -> data filtrele -> dogru data
- [ ] ConditionalPropertyComboTest enable et

**Staged Flag Enablement:**
- [ ] docker-compose.yml ERP_OPENFGA_ENABLED default true
- [ ] .env.example guncelle
- [ ] docker-compose.prod.yml dogrula (zaten true)

**Smoke:**
- [ ] doctor-zanzibar.sh --quick PASS
- [ ] Playwright authz.zanzibar.spec.ts PASS

### PR-E: Kalite Backlog (2-3 gun)

**Test Coverage:**
- [ ] M-02: ExcelStreamingExporter, CustomReportRepository, ScheduleRepository
- [ ] M-03: ContextHealth modulu (10 dosya, 1146 LOC)
- [ ] DENY senaryo testleri genisleti

**CI/Enforcement:**
- [ ] M-06: k6 CI workflow
- [ ] M-10: EP-016 enforcement rule (legacy auth import ban)
- [ ] JaCoCo rapor uret
- [ ] H-03: Rollback playbook staging testi

**Temizlik:**
- [ ] Gateway audience fix (variant-service -> dogru liste)
- [ ] compat.ts kaldirma (aktif consumer yok)
- [ ] Stale branch temizligi

---

## 3. UZUN VADELI (Faz 2-5, Ayri Session)

| Faz | Kapsam | Durum |
|-----|--------|-------|
| Faz 2 | Frontend mfe-users (multi-role, tabbed scope UI) | Baslamadi |
| Faz 3 | mfe-access (role drawer, DENY UI, person assignment) | Baslamadi |
| Faz 4 | Access denial UX (explain drawer/modal) | Baslamadi |
| Faz 5 | Cleanup (hardcode, deprecated, i18n) | Baslamadi |
| - | OpenFGA model version management | Backlog |
| - | Tuple reconciliation daemon | Outbox sonrasi |
| - | Circuit breaker (OpenFGA write) | Backlog |
| - | Faz 4-b scope netlestirme | Karar bekliyor |

---

## 4. KARAR SONUCLARI (2026-04-13 cozuldu)

| # | Karar | Sonuc | Constraint |
|---|-------|-------|-----------|
| K-1 | ERP_OPENFGA_ENABLED | PR-D ile staged rollout (compose default true) | - |
| K-2 | schema-service AUTH_MODE | KALDIRILDI (PR #351). Her zaman authenticated() | C-006 |
| K-3 | Korumasiz MFE'ler | Shell korumasi yeterli. Standalone auth P3'te | - |
| K-4 | Vault naming | Compose'da platform-vault-1 (PR #351) | - |

---

## 5. CODEX ISTISARE KAYDI

**ID:** CNS-20260413-001
**Katilimcilar:** Claude (Opus 4.6) + Codex (gpt-5.4)
**Token:** 150,307

**Kabul edilen Codex onerileri:**
- permitAll fiili acik tespiti (spesifik endpoint'ler)
- PR #350 @EnableScheduling eksikligi
- PR #350 gitlink kazasi
- Non-local startup guard
- schema-service profil kisitlamasi
- MFE tespitinin nuanslanmasi

**Reddedilen/nuanslanan:**
- Oncelik sirasi: PR #349 once (Codex guvenlik oncesi diyordu)
- PR #350 rework -> hardening (core tasarim saglam)
- Vault naming PR-B ile birlesme -> ayri

---

## 6. SESSION BASLANGIC REHBERI

```
1. Plan oku: .claude/plans/zanzibar-master-plan.md (rev 17)
2. PR-A: gh pr merge 349 --squash
3. PR-B: Prod auth surface hardening
4. PR-C: PR #350 hardening
5. PR-D: E2E test + staged rollout
6. PR-E: Kalite backlog
```
