# Dalga 3 Başlangıç Planı — Giriş Gate'leri + PR1

## Context

Zanzibar/OpenFGA projesi Dalga 1+2 tamamlandı (34+ PR, 19 servis UP, batch 5.2ms).
Master plan rev 6 ve roadmap manifest oluşturuldu. CNS-003'te 7/7 itiraz Codex tarafından kabul edildi.

**Şimdi yapılacak:** Dalga 3 giriş gate'lerini geçip PR1'i implement etmek.

Dev repo: `/Users/halilkocoglu/Documents/dev` (main, 561119f0)
Docker: 19/19 servis UP, healthy

---

## Adım 1: Dalga 3 Giriş Gate — Doctor 3 Fail RCA

**Ne:** Doctor-zanzibar 73/76 PASS, 3 fail'ın root cause analizi
**Araç:** `backend/scripts/doctor-zanzibar.sh`
**Eylem:**
1. `cd /Users/halilkocoglu/Documents/dev && bash backend/scripts/doctor-zanzibar.sh --json` çalıştır
2. 3 FAIL'ın hangisi olduğunu belirle (vite proxy + gateway routes claim'i doğrula)
3. Her fail için: Zanzibar mı kırdı, pre-existing mi? Git blame ile kanıtla
4. Sonuç: RCA raporu yaz (fix veya "not-zanzibar" kanıtı)

---

## Adım 2: Dalga 3 Giriş Gate — SK-1 + SK-5 Baseline

**SK-1 (OpenFGA availability):**
- `curl http://localhost:4000/healthz` ile basit availability check
- Prometheus `authz_check_total` ve `authz_check_error_total` counter'lardan availability hesapla
- Grafana endpoint: `http://localhost:3001` (observability-grafana container)

**SK-5 (Decision log coverage):**
- `authz.decision.log` özelliğini kontrol et — her check loglanıyor mu?
- `grep -r "decision.log\|auditClient.log" backend/` ile kapsam tara

---

## Adım 3: PR1 Implementation — canViewReport + authzTarget + Backend Deny-Default

### 3a. Frontend Fix (KRİTİK GÜVENLİK)

**Dosya:** `web/packages/auth/src/PermissionProvider.tsx:186`

**Mevcut (BUG):**
```typescript
canViewReport: (report: string) => {
  if (permitAll || authz?.superAdmin) return true;
  const grant = authz?.reports?.[report];
  return grant === 'ALLOW' || grant === undefined; // ← BUG: undefined = izin
}
```

**Fix:**
```typescript
canViewReport: (report: string) => {
  if (permitAll || authz?.superAdmin) return true;
  const grant = authz?.reports?.[report];
  return grant === 'ALLOW'; // deny-default: tanımsız = ret
}
```

**Etki analizi:**
- `useZanzibarAccess.ts:47` → coarse gate `!canViewReport()` → `hidden` (DOĞRU davranış)
- `Sidebar.test.tsx` → test güncellenmeli (undefined artık deny)
- Tüm report'lar `/authz/me` response'unda `reports` map'inde ALLOW olarak listelenmeliyse → backend seed kontrolü

### 3b. AuthzTarget Registry (YENİ)

**Konsept:** Her report modülü için `{objectType, objectId}` mapping
**Konum:** `web/packages/auth/src/authzTargetRegistry.ts` (yeni dosya)

```typescript
export interface AuthzTarget {
  objectType: string;
  objectId: string;
}

export const REPORT_AUTHZ_TARGETS: Record<string, AuthzTarget> = {
  'HR_REPORTS': { objectType: 'report_group', objectId: 'hr_reports' },
  'FINANCE_REPORTS': { objectType: 'report_group', objectId: 'finance_reports' },
  'SALES_REPORTS': { objectType: 'report_group', objectId: 'sales_reports' },
  'ANALYTICS_REPORTS': { objectType: 'report_group', objectId: 'analytics_reports' },
};
```

**Kullanım:** `canViewReport` OpenFGA check ile güçlendirilir (ileride batch-check adoption)

### 3c. Backend Deny-Default (ReportAccessEvaluator)

**Dosya:** `backend/report-service/src/main/java/com/example/report/access/ReportAccessEvaluator.java`

**Mevcut:** Sadece permission string kontrolü (REPORT_VIEW + custom permission)
**Eksik:** `authz.reports[reportKey]` deny-list kontrolü yok

**Fix:** `evaluate()` metoduna OpenFGA report-level check ekle:
```java
// Mevcut kontroller sonrası, return ALLOWED öncesine:
String reportKey = def.key();
if (authz.getReports() != null && authz.getReports().containsKey(reportKey)) {
    String grant = authz.getReports().get(reportKey);
    if (!"ALLOW".equals(grant)) {
        return AccessResult.DENIED_REPORT_GROUP;
    }
}
// Report tanımlı değilse ve deny-default istiyorsak:
if (authz.getReports() != null && !authz.getReports().containsKey(reportKey)) {
    return AccessResult.DENIED_REPORT_GROUP;
}
```

**Yeni AccessResult:** `DENIED_REPORT_GROUP` eklenmeli

### 3d. Test Güncellemeleri

| Dosya | Değişiklik |
|-------|-----------|
| `web/apps/mfe-shell/src/app/layout/Sidebar.test.tsx` | canViewReport undefined→deny test |
| `web/packages/auth/src/__tests__/PermissionProvider.test.tsx` | deny-default senaryoları |
| `backend/report-service/src/test/java/.../ReportAccessEvaluatorTest.java` | report group deny test |

---

## Adım 4: Dev Repo Worktree + Branch

```bash
cd /Users/halilkocoglu/Documents/dev
git checkout -b feat/zanzibar-authz-target-deny-default main
```

Commit sırası:
1. `fix(auth): canViewReport deny-default — close R3-6 security gap`
2. `feat(auth): authzTarget registry for report modules`
3. `fix(report-service): ReportAccessEvaluator deny-default + report group check`
4. `test: canViewReport deny-default + authzTarget coverage`

---

## Doğrulama

1. `bash backend/scripts/doctor-zanzibar.sh` → 73+ PASS (en az mevcut seviye)
2. Frontend test: `cd web && pnpm vitest run packages/auth`
3. Backend test: `cd backend && mvn test -pl report-service -Dtest=ReportAccessEvaluatorTest`
4. Docker smoke: `bash scripts/docker-smoke-test.sh`
5. Orchestrator sync: `python3 scripts/sync_managed_repo_standards.py --target-repo-root /Users/halilkocoglu/Documents/dev --dry-run`

---

## Risk

| Risk | Mitigation |
|------|-----------|
| deny-default mevcut kullanıcıları kilitler | SuperAdmin bypass korunuyor. Seed'de tüm report group'lar ALLOW |
| Backend report-group enum uyumsuzluğu | Mevcut 4 group ile başla (HR, FINANCE, SALES, ANALYTICS) |
| Test kırılması | Önce mevcut testleri çalıştır, sonra fix |
