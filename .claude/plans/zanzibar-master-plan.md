# ZANZIBAR / OpenFGA — KAPSAMLI PROJE PLANI

**Proje Kodu:** PRJ-ZANZIBAR-OPENFGA
**Tarih:** 2026-04-11
**Karar Referansi:** D-001 → D-007 (tumu FINAL)
**Durum:** 8 PR merged, staging calisiyor (flags OFF)

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

| # | Kriter | Hedef |
|---|--------|-------|
| SK-1 | OpenFGA check basari orani | >= %99.9 |
| SK-2 | p95 latency artisi | < 15ms (cache ile) |
| SK-3 | Data leak | 0 incident |
| SK-4 | Rollback suresi | < 5 dakika |
| SK-5 | Decision log kapsami | %100 |
| SK-6 | Legacy permission-service | Tamamen kaldirilmis (D-002) |
| SK-7 | Test coverage (authz kodu) | >= %80 |
| SK-8 | Frontend permission gate | 0 broken gate |
| SK-9 | @Filter/RLS kapsami | Tum company-scoped tablolar |
| SK-10 | Prod gecis downtime | 0 dakika |

---

## 3. FAZLAR

### FAZ 0: STAGING FLAGS ON TEST (BLOCKER)

**Amac:** Flags ON ile ilk gercek entegrasyon testi
**Efor:** S (2-3 gun)

**13 Test Maddesi:**

| # | Test | Oncelik |
|---|------|---------|
| T-01 | TupleSyncService bean baslatma (@ConditionalOnProperty) | P0 |
| T-02 | Batch write deny-wins sirasi | P0 |
| T-03 | Fail-closed davranis (OpenFGA baglanti kesme) | P0 |
| T-04 | AuthzVersionService counter artisi | P0 |
| T-05 | Auto-seed (bos DB) | P1 |
| T-06 | ScopeContextFilter: JWT → OpenFGA → cache | P0 |
| T-07 | Dev fallback (OpenFGA yok) | P1 |
| T-08 | Cache 30s TTL + jitter | P1 |
| T-09 | Version-keyed cache invalidation | P0 |
| T-10 | RemoteAuthzVersionProvider 3 servis | P0 |
| T-11 | Frontend 60s version polling | P1 |
| T-12 | HaloApplicationTests yesil | P0 |
| T-13 | Actuator metrics data | P1 |

**DoD:**
- [ ] 13/13 test PASSED
- [ ] 24 saat stabil (error rate < %0.1)
- [ ] Flag OFF rollback test basarili

**Riskler:**
- OpenFGA container calismama (Orta/Yuksek) → docker-compose kontrolu
- Cache version uyumsuzlugu (Orta/Yuksek) → contract test
- Frontend CORS (Dusuk/Orta) → reverse proxy config

**Rollback:** Feature flag OFF (< 1 dk)

---

### FAZ 1: @FILTER / RLS GENISLETME (Data Leak Onleme)

**Amac:** Company-scoped tum tablolara Hibernate @Filter + PostgreSQL RLS
**Efor:** M (5-8 gun)
**Bagimlilik:** Faz 0 DONE

**Kapsam:**
- Tum company-scoped entity'lere @Filter
- Karsilik gelen RLS policy migration'lari
- report-service (DashboardQueryEngine) RLS uyumu

**DoD:**
- [ ] @Filter olmayan company-scoped entity = 0
- [ ] Cross-company data isolation integration test PASSED
- [ ] DashboardQueryEngine RLS uyumlu

**Riskler:**
- Mevcut sorgu kirma (Yuksek/Yuksek → R3) → entity bazinda staging test
- JOIN conflict (Orta/Yuksek) → cross-table test onceden yazilmali
- report-service performans (Orta/Orta) → EXPLAIN ANALYZE

**Rollback:** DROP POLICY + @Filter annotation kaldir (< 30 dk)

---

### FAZ 2: PROD DEPLOY (Canary → Full Rollout)

**Amac:** D-004'e uygun feature flag ile kademeli gecis
**Efor:** M (5-10 gun, cogu gozlem suresi)
**Bagimlilik:** Faz 0 + Faz 1 DONE

**3 Asama:**
```
Asama 1: Deploy (flags OFF) — 1 gun
Asama 2: Canary (flags ON, sinirli grup) — 2-5 gun, 48h gozlem
Asama 3: Kademeli (%10→%25→%50→%100) — 5-10 gun, her asamada 24h
```

**DoD:**
- [ ] %100 rollout, 1 hafta stabil
- [ ] Error rate < %0.1
- [ ] Latency p95 < 15ms ek
- [ ] Alerting kurulmus

**Riskler:**
- Cold cache performans (Orta/Yuksek) → warm-up script
- Network partition (Dusuk/Kritik) → fail-closed + flag OFF otomatik

**Rollback:** Feature flag OFF (< 5 dk)

---

### FAZ 3: REPORT PERMISSION GROUPS (P1-C)

**Amac:** Rapor izinlerini OpenFGA'ya entegre
**Efor:** S (3-5 gun)
**Bagimlilik:** Faz 2 canary sonrasi

**DoD:**
- [ ] Report permission group'lari OpenFGA'da tanimli
- [ ] report-service check entegrasyonu
- [ ] Frontend'de erisilemez raporlar gizli

**Rollback:** Flag OFF + eski check'e don (< 5 dk)

---

### FAZ 4: MIGRATION TAMAMLAMA + LEGACY KALDIRMA

4 alt gorev (a/c/d paralel, b en son):

| Alt Faz | Is | Efor | Paralel? |
|---------|-----|------|----------|
| **4-a** | propagateRoleChange durable async job | S (2-3 gun) | Evet |
| **4-c** | Audit hardening (deny log, alert) | S (2-3 gun) | Evet |
| **4-d** | Frontend mutation refresh | XS (1-2 gun) | Evet |
| **4-b** | Legacy permission-service kaldir (D-002) | M (3-5 gun) | **SONRA** |

**Faz 4-b DoD (en kritik):**
- [ ] permission-service referansi 0 (`grep -r` ile)
- [ ] Archive branch'e tasinmis
- [ ] Main'den silinmis
- [ ] 2 hafta parallel calistirma tamamlanmis
- [ ] D-002 CLOSED

**Rollback Faz 4-b:** Archive branch'den restore (< 1 saat, **YUKSEK RISK**)

---

### FAZ 5: TEST ALTYAPISI

**Amac:** Eksik test coverage'i tamamla
**Efor:** M (5-7 gun)
**Paralel:** Faz 0 ile baslayabilir

**DoD:**
- [ ] HaloApplicationTests yesil (ON/OFF varyantlari)
- [ ] @ConditionalOnProperty kombinasyon testleri
- [ ] Docker smoke test (compose up → health check)
- [ ] Coverage >= %80
- [ ] CI pipeline gate

---

### FAZ 6: P3 — ERTELENMIS (D-005)

SaaS karari verildiginde aktiflesir:
- Condition/context (saate gore erisim)
- Event-driven invalidation (webhook)
- Multi-tenant izolasyon
- Caffeine → Redis

---

## 4. TEST PLANI

| Tip | Kapsam | Araclar |
|-----|--------|---------|
| **Unit** | TupleSyncService, AuthzVersion, Cache, Filter | JUnit 5 + Mockito |
| **Integration** | JWT→OpenFGA→Cache→Response, RLS isolation | Testcontainers |
| **E2E** | Login→sayfa erisim, rol degisikligi→UI | Cypress/Playwright |
| **Performance** | Check latency (cold/warm), cache ratio, RLS etkisi | k6 |
| **Security** | RLS bypass, JWT tampering, IDOR, cross-company leak | Manual pentest + automation |
| **Regression** | Mevcut CRUD, flag OFF davranis, frontend snapshot | Mevcut test suite |

---

## 5. RISK MATRISI

| Risk | Olasilik × Etki | Mitigation |
|------|-----------------|-----------|
| **R3** RLS sorgu kirma | 16 (Y×Y) | Entity bazinda staging test |
| **R8** Bus factor = 1 | 16 (Y×Y) | Dokumantasyon, runbook |
| **R1** OpenFGA performans | 12 (O×Y) | Cache + warm-up |
| **R2** Legacy kaldirma geri donus | 12 (D×K) | 2 hafta parallel |
| **R4** Cache version uyumsuzlugu | 12 (O×Y) | Single source of truth |
| **R10** Staging-prod parity | 12 (O×Y) | IaC |

---

## 6. ZAMAN CIZELGESI

```
Hafta 1-2:   FAZ 0 (staging test) ◄── BLOCKER
               ├── FAZ 5 (test altyapisi) [paralel]
Hafta 2-4:   FAZ 1 (@Filter/RLS)
Hafta 4-6:   FAZ 2 (prod deploy + canary + rollout)
Hafta 5-6:   FAZ 3 (report groups)
Hafta 7-10:  FAZ 4 (async, audit, frontend || legacy kaldir)
Hafta 11+:   FAZ 6 (P3, SaaS kararina bagimli)
```

---

## 7. RACI

| | Human | Claude | Codex |
|--|-------|--------|-------|
| Karar onay | **A** | R | C |
| Kod yazim | A | **R** | C (review) |
| Test yurutme | **R** | C | I |
| Prod deploy | **R** | C | I |
| Incident response | **R** | C | I |
| Dokumantasyon | A | **R** | C |

---

## 8. TEKNIK BORC

| # | Borc | Oncelik | Faz |
|---|------|---------|-----|
| TB-06 | Docker smoke test yok | Yuksek | Faz 5 |
| TB-10 | @Filter CI gate kontrolu yok | Yuksek | Faz 1 |
| TB-11 | permission-service referans envanteri yok | Yuksek | Faz 4-b |
| TB-05 | ConditionalOnProperty kombinasyon testleri | Orta | Faz 5 |
| TB-07 | OpenFGA model version yonetimi yok | Orta | Faz 4-c |

---

## 9. KARAR UYUM KONTROLU

Her fazda kontrol:
- D-001: OpenFGA disinda auth engine YOK
- D-003: Katman sorumluluk siniri korunuyor
- D-004: Shadow mode degil, flag ile gecis
- D-007: Yeni endpoint'lerde tenant_id var
