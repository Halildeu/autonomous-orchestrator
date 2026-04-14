# Zanzibar Master Plan — Rev 19 (Claude + Codex Uzlasi)

**Tarih:** 2026-04-14
**Kaynak:** Rev 18 + CNS-20260414-001 (482K token, gpt-5.4) + CNS-20260414-002 (212K token, gpt-5.4) + Claude (Opus 4.6) degerlendirme
**Base:** main @ e9fadc13
**Uzlasi:** 5 BLOCKER + 1 FIX tespit edildi; Dalga 0 eklendi

---

## 0. REV 18 -> REV 19 DEGISIKLIK OZETI

Rev 18'de "Canary Rollout" ilk dalga idi. Codex istisaresi 6 bulgu ortaya cikardi;
Claude degerlendirmesi ve Codex Round 2 dogrulamasiyla 5 tanesi BLOCKER olarak
kesinlesti. Dalga 0 (Canary Readiness) eklendi.

| Bulgu | Aciklama | R1 Claude | R2 Codex | Uzlasi |
|-------|----------|-----------|----------|--------|
| #1 | `/authz/check` + `/batch-check` core-data'da, route permission-service'e gidiyor | Dogrulamam lazim | BLOCKER (kanitla) | **BLOCKER** |
| #2 | JWT fallback: /authz/me hata -> 200+bos body -> 5dk sticky 403 | Dalga 4'e ertele | YUKSEK RISK (canary tetikler) | **BLOCKER** |
| #3 | Deny rate metrigi HTTP 403 bazli, /authz/check 200+allowed:false donuyor | BLOCKER | BLOCKER | **BLOCKER** |
| #4 | Phantom alert: outbox_failed + circuit_breaker Micrometer uretici yok | BLOCKER | BLOCKER | **BLOCKER** |
| #5 | variant + core-data compose'da PERMISSION_SERVICE_BASE_URL yok | BLOCKER | BLOCKER | **BLOCKER** |
| #6 | Runbook drift: Stage 1 "flags OFF" ama compose default=true | Non-blocker | Non-blocker | **FIX** |

### Ek Codex Bulgulari (Rev 18'de yoktu)
- `/api/v1/authz/explain` iki serviste farkli semantikle mevcut (permission-service: legacy, core-data: OpenFGA)
- Runbook + alert metni "fail-closed = check true" diyor; kod `false`/empty donuyor
- variant-service bos authz response'u 5dk cache'liyor (sticky deny)

---

## 1. MEVCUT DURUM (2026-04-14)

### Tamamlanan Katmanlar

| Katman | Durum |
|--------|-------|
| OpenFGA Altyapi (model.fga, Docker v1.11.2, PG datastore) | Prod-ready |
| Backend Core (OpenFgaAuthzService, ScopeContextFilter, @RequireModule) | Prod-ready |
| Tuple Sync (TupleSyncService, Outbox + SKIP LOCKED + @EnableScheduling) | Prod-ready |
| Data Enforcement (Hibernate @Filter + PostgreSQL RLS + ScopeContext) | Prod-ready |
| Frontend Auth (@mfe/auth: PermissionProvider, useZanzibarAccess, ZanzibarGate) | Prod-ready |
| Frontend UI (mfe-access RoleDrawer, mfe-users multi-role, tabbed scope) | Prod-ready |
| Guvenlik (7/7 servis authenticated() catch-all) | Hardened |
| Hardening (MF singleton, CORS, CB, rate-limit, Grafana alerts) | Prod-ready |
| E2E Test (Playwright authz, doctor-zanzibar.sh 47 check) | CI-entegre |
| Explain UX (403 sayfasinda "Neden?" butonu + useExplainPermission + i18n) | Kismi |
| k6 (zanzibar-check.js, SK-2/SK-11 esikleri) | Tamamlandi |
| ERP_OPENFGA_ENABLED default=true (compose + .env.example) | Tamamlandi |
| Grafana alert kurallari (authz-zanzibar-rules.yml) | Tamamlandi |

### BLOCKER'lar (Canary Oncesi Duzeltilmeli)

| # | Blocker | Kanit |
|---|---------|-------|
| B1 | `/authz/check` + `/batch-check` endpoint core-data'da; gateway+Vite permission-service'e yonlendiriyor | `AuthzExplainController.java:45,71` vs `vite.config.ts:281`, `gateway:76` |
| B2 | `/authz/me` hata -> 200+bos fallback body -> variant 5dk sticky 403 | `AuthorizationControllerV1.java:150`, `VariantAuthorizationServiceImpl.java:23` |
| B3 | Deny rate metrigi HTTP 403 bazli; `/authz/check` 200+`allowed:false` donuyor | `zanzibar-guardrails.json:25` |
| B4 | `tuple_sync_outbox_failed_total` + `openfga_circuit_breaker_state` alert var, Micrometer uretici yok | `authz-zanzibar-rules.yml:217,246` vs `AuthzCacheMetricsConfig.java` (sadece cache gauge) |
| B5 | variant + core-data compose'da `PERMISSION_SERVICE_BASE_URL` yok -> authzVersion polling kendine gidiyor | `OpenFgaAuthzConfig.java:40` (her iki servis), `docker-compose.yml:128,171` |

### Kalan Legacy Borc (TB-11)

| Kategori | Dosya |
|----------|-------|
| PermissionServiceClient | 8 dosya (auth, user, report-service) |
| PermissionCodes | 15 dosya (common-auth + tuketiciler) |
| /api/permissions eski route | Gateway + client |
| Deprecated PermissionType | PAGE, FIELD enum |
| **Toplam** | **~23 dosya, ~56 referans** |

---

## 2. YOL HARITASI

### DALGA 0: Canary Readiness (2-3 gun) — BLOCKER FIX

**B1: /authz/check route duzeltmesi**
- [ ] `/authz/check` ve `/batch-check` endpoint'lerini permission-service `AuthorizationControllerV1`'a tasi
  - En dusuk maliyetli yol: core-data'daki mantigi permission-service'e kopyala (ayni OpenFgaAuthzService kullanilacak)
  - core-data'daki duplicate endpoint'i `@Deprecated` isaretle veya sil
- [ ] Gateway + Vite route'larinin tutarliligini dogrula
- [ ] Frontend `api.ts` call path'lerini dogrula (degisiklik gerekmemeli)
- Kanit: `AuthzExplainController.java:45,71`, `AuthorizationControllerV1.java`, `vite.config.ts:281`

**B2: JWT fallback mitigasyonu**
- [ ] `AuthorizationControllerV1.java` top-level catch: 200+bos body yerine 503 don
  - Alternatif: fallback body'de `degraded: true` flag ekle, client'lar bunu kontrol etsin
- [ ] variant-service `PermissionServiceAuthzClient`: bos response'u cache'leme (null don)
- [ ] variant-service cache TTL'i 5dk -> hata durumunda 0 (veya skip cache)
- Kanit: `AuthorizationControllerV1.java:150`, `VariantAuthorizationServiceImpl.java:23`, `AuthorizationContextCache.java:29`

**B3: Deny rate metrigi duzeltmesi**
- [ ] `authz_decisions_total` Micrometer Counter ekle (tag: `allowed=true|false`, `reason=*`)
  - Yer: `OpenFgaAuthzService.check()` ve `checkWithReason()` icinde
- [ ] `zanzibar-guardrails.json` deny_rate sorgusunu guncelle: HTTP 403 -> `authz_decisions_total{allowed="false"}`
- [ ] Grafana alert kuralini guncelle
- Kanit: `zanzibar-guardrails.json:25`, `authz-zanzibar-rules.yml:88`

**B4: Phantom alert'lere metric uretici ekle**
- [ ] `tuple_sync_outbox_failed_total` Counter: `TupleSyncOutboxPoller` icerisinde FAILED entry islendiginde increment
- [ ] `openfga_circuit_breaker_state` Gauge: `OpenFgaCircuitBreaker` state degistiginde guncelle (0=closed, 1=open, 2=half-open)
- [ ] Mevcut `AuthzCacheMetricsConfig` pattern'ini kullan (MeterRegistry injection)
- Kanit: `authz-zanzibar-rules.yml:217,246`, `AuthzCacheMetricsConfig.java:22`

**B5: Compose PERMISSION_SERVICE_BASE_URL**
- [ ] `docker-compose.yml` variant-service env'ine `PERMISSION_SERVICE_BASE_URL: ${PERMISSION_SERVICE_BASE_URL:-http://permission-service}` ekle
- [ ] `docker-compose.yml` core-data-service env'ine ayni satiri ekle
- [ ] `RemoteAuthzVersionProvider` default port'u dogrula (127.0.0.1:8091 -> 8084 veya compose override yeterli)
- Kanit: `docker-compose.yml:128,171`, `OpenFgaAuthzConfig.java:40`

**FIX: Runbook + alert text drift**
- [ ] `RB-zanzibar-canary.md` Stage 1 metnini guncelle: compose default=true ile uyumla
- [ ] Fail-closed aciklamasini duzelt: "check -> true" degil "check -> false (deny-all)"
- [ ] Alert summary'de ayni duzeltme
- Kanit: `RB-zanzibar-canary.md:38,88`, `OpenFgaAuthzService.java:79`

**Dogrulama:**
- [ ] `doctor-zanzibar.sh --quick` PASS
- [ ] Tum servisler icin `mvn test` PASS
- [ ] Frontend `npm test` PASS

---

### DALGA 1: Canary Rollout (3-5 gun)

**On kosul:** Dalga 0 tamamlandi.

**Canary Asamalari (RB-zanzibar-canary runbook):**

| Asama | Gun | Bayraklar | Basari Kriteri |
|-------|-----|-----------|----------------|
| Stage 1: Deploy | Gun 1 | Compose default (true) | Tum container'lar healthy |
| Stage 2: Canary | Gun 2-4 | ON (admin + restricted) | p95 <50ms, error <0.5%, deny <10% |
| Stage 3: Full | Gun 5+ | ON (tum kullanicilar) | 48h stabil, 0 regression |

**Ek guardrail'ler (Codex onerisi):**
- [ ] `/authz/me` latency + error rate
- [ ] `tuple_sync_outbox_pending` + `oldest_age`
- [ ] `openfga_up`, `permission_service_up`
- [ ] Object-level `/authz/check` deny senaryosu restricted probe'a ekle
- [ ] Scope/RLS deny senaryosu restricted probe'a ekle

**Ciktilar:**
- [ ] Canary 48h stable raporu
- [ ] doctor-zanzibar.sh runtime (B bolumu) PASS
- [ ] Restricted smoke user deny senaryosu PASS

---

### DALGA 2: Explain UX Polish (2-3 gun, Dalga 1 sonrasi)

**Mevcut (zaten tamamlanan):**
- 403 sayfasinda "Neden erisiemiyorum?" butonu + useExplainPermission hook + i18n (15 anahtar)
- Backend `/v1/authz/explain` (permission-service + core-data)

**Kalan is (Dalga 0 B1 sonrasi netlesecek):**
- [ ] `/authz/explain` route sahipligini birlestir (iki servis -> tek canonical)
- [ ] ExplainDrawer bileseni (mfe-access) — opsiyonel, 403 sayfasi zaten calisiyor
- [ ] ZanzibarGate `disabled` -> explain tooltip
- [ ] Playwright test

---

### DALGA 3: Legacy Temizlik (3-4 gun, Dalga 1 ile paralel calisabilir)

**PR Sirasi (TB-11):**

| PR | Kapsam | Dosya |
|----|--------|-------|
| PR6-prereq | auth-service PermissionServiceClient -> OpenFGA | ~6 dosya |
| PR6 | PermissionCodes sil + tuketici migration | ~20 dosya |
| PR8 | report-service migration | ~3 dosya |

---

### DALGA 4: Backlog

| # | Is | Oncelik |
|---|-----|---------|
| 1 | Scope reconciliation (scheduled + on-demand hibrit) | ORTA |
| 2 | OpenFGA model version management | ORTA |
| 3 | k6 CI workflow (regression gate) | ORTA |
| 4 | Circuit breaker for writes | DUSUK |
| 5 | EP-016 enforcement rule (legacy auth import ban) | DUSUK |
| 6 | JaCoCo coverage | DUSUK |

**Scope Reconciliation Stratejisi (Codex onerisi, karar bekliyor):**
- Hibrit: saatlik incremental + gece full sweep + incident icin manuel tetikleme
- Yer: sadece permission-service (C-005 hub kisiti)
- Hedef: drift detect + repair + metric + audit

---

## 3. BAGIMLILIK GRAFIGI

```
DALGA 0 (Readiness, 2-3 gun)
  ├─ B1: /authz/check route tasi
  ├─ B2: JWT fallback mitigasyonu
  ├─ B3: Deny rate metric duzelt
  ├─ B4: Phantom alert metric ekle
  ├─ B5: Compose base URL ekle
  └─ FIX: Runbook text
         │
         ▼
DALGA 1 (Canary, 3-5 gun)
         │
    ┌────┴────┐
    ▼         ▼
DALGA 2    DALGA 3
(Explain)  (Legacy)
    └────┬────┘
         ▼
      DALGA 4
     (Backlog)
```

---

## 4. RISK MATRISI

| Risk | Olasilik | Etki | Mitigasyon |
|------|----------|------|------------|
| B1 route tasimada regression | ORTA | YUKSEK | mvn test + Playwright E2E |
| B2 fallback degisikligi mevcut dev flow'u bozar | DUSUK | ORTA | local profilde farkli davranis (permitAll) |
| Canary'de yuksek deny rate | ORTA | YUKSEK | Duzeltilmis metric + flag rollback |
| Outbox backlog | DUSUK | ORTA | Yeni metric + dead letter monitoring |
| Legacy temizlikte regression | ORTA | ORTA | Servis bazli mvn test |

---

## 5. KARAR DURUMU

**7 FINAL karar:** Degisiklik yok (rev 3).
**7 Constraint:** Degisiklik yok.
**Yeni karar gerekli (Dalga 0'da):**
- [ ] B1: /authz/check permission-service'e mi tasinacak, yoksa Vite+gateway core-data'ya mi yonlendirilecek?
- [ ] B2: Fallback 503 mu donecek, yoksa `degraded:true` flag mi?

**Bekleyen karar (Dalga 4):**
- [ ] Scope reconciliation stratejisi: scheduled + on-demand hibrit (Codex onerisi)

---

## 6. ISTISARE KAYDI

| ID | Tarih | Katilimcilar | Token | Konu |
|----|-------|-------------|-------|------|
| CNS-20260413-001 | 2026-04-13 | Claude + Codex | 150K | Rev 17 gap analysis |
| CNS-20260414-001 | 2026-04-14 | Claude + Codex | 482K | Rev 18 dogrulama, 6 bulgu |
| CNS-20260414-002 | 2026-04-14 | Claude + Codex | 212K | Round 2: bulgu dogrulama, uzlasi |

---

## 7. DOGRULAMA ARACLARI

| Arac | Komut |
|------|-------|
| Doctor (quick) | `backend/scripts/doctor-zanzibar.sh --quick` |
| Doctor (full) | `backend/scripts/doctor-zanzibar.sh` |
| Canary guardrails | `backend/scripts/ci/canary/zanzibar-guardrails.json` |
| Restricted probe | `backend/scripts/ci/canary/zanzibar-restricted-probe.sh` |
| Playwright E2E | `web/tests/playwright/authz.zanzibar.spec.ts` |
| Legacy envanter | `docs/04-operations/TB-11-legacy-permission-inventory.md` |
| Canary runbook | `docs/04-operations/RUNBOOKS/RB-zanzibar-canary.md` |
| k6 perf | `backend/scripts/perf/k6-zanzibar-check.js` |

---

## 8. SESSION BASLANGIC REHBERI

```
1. Plan oku: .claude/plans/zanzibar-master-plan.md (rev 19)
2. Dalga 0: Canary Readiness (BLOCKER FIX)
   a. B1: /authz/check -> permission-service'e tasi
   b. B2: JWT fallback -> 503 veya degraded flag
   c. B3: authz_decisions_total Micrometer counter
   d. B4: outbox_failed + circuit_breaker metric
   e. B5: compose PERMISSION_SERVICE_BASE_URL
   f. FIX: runbook text
   g. Dogrulama: doctor + mvn test + npm test
3. Dalga 1: Canary rollout (3 asamali, RB-zanzibar-canary)
4. Dalga 2: Explain UX polish
5. Dalga 3: Legacy temizlik (TB-11 PR6-prereq -> PR6 -> PR8)
6. Dalga 4: Backlog (reconciliation, model versioning, k6 CI)
```
