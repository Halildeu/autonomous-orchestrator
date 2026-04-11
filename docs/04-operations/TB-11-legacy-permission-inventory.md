# TB-11: Permission-Service Legacy Reference Inventory (FROZEN)

Date: 2026-04-11
Status: FROZEN (Dalga 4 ön koşulu — bu envanterdeki itemler temizlenecek)
Ref: CNS-20260411-003 Q4, zanzibar-master-plan.md rev 6

## 1. PermissionServiceClient (3 servis, 10 referans)

| Servis | Dosya | Satır | Tür |
|--------|-------|-------|-----|
| auth-service | permission/PermissionServiceClient.java:30 | Class tanımı | KAYNAK |
| auth-service | service/AuthService.java:22,41,52 | Import + field + constructor | TÜKETİCİ |
| auth-service | service/AuthServiceTest.java:7,51 | Test mock | TEST |
| auth-service | service/AuthServiceSessionAuditTest.java:39,58 | Test mock | TEST |
| user-service | permission/PermissionServiceClient.java:21 | Class tanımı (OpenFGA wrapper) | KAYNAK |
| report-service | authz/PermissionServiceClient.java:24 | Class tanımı (WebClient) | KAYNAK |

**Eylem:** PR6-prereq — auth-service PermissionServiceClient legacy endpoint migration

## 2. PermissionCodes (1 kaynak, 37 tüketici referans)

| Servis | Dosya | Referans Sayısı | Tür |
|--------|-------|-----------------|-----|
| common-auth | PermissionCodes.java:17 | Class tanımı (27 constant) | KAYNAK |
| core-data-service | CompanyController.java | 4 referans | TÜKETİCİ |
| core-data-service | CompanyControllerSecurityTest.java | 8 referans | TEST |
| variant-service | VariantController.java | 7 referans | TÜKETİCİ |
| variant-service | VariantControllerV1.java | 8 referans | TÜKETİCİ |
| variant-service | ThemeController.java | 2 referans | TÜKETİCİ |
| variant-service | VariantAuthorizationServiceImpl.java | 4 referans | TÜKETİCİ |
| variant-service | VariantService.java | 2 referans | TÜKETİCİ |
| variant-service | VariantSecurityIntegrationTest.java | 4 referans | TEST |
| common-auth | AuthorizationContextBuilderTest.java | 1 referans | TEST |

**Eylem:** PR6 — deprecated cleanup (class silinecek, tüketiciler OpenFGA check'e migrate)

## 3. Eski /api/permissions Endpoint (3 referans)

| Dosya | Satır | Tür |
|-------|-------|-----|
| PermissionController.java:17 | @RequestMapping("/api/permissions") | KAYNAK (deprecated) |
| application.properties:39 | Gateway route /api/permissions/** | ROUTING |
| PermissionServiceClient.java:43 | /api/permissions/assignments çağrısı | TÜKETİCİ |

**Eylem:** PR6-prereq + PR6

## 4. useAuthorization (Frontend Legacy, 6 dosya)

| App | Dosya | Tür |
|-----|-------|-----|
| @mfe/auth | compat.ts:46 | Compat wrapper (KAYNAK) |
| @mfe/auth | index.ts:24 | Export | 
| mfe-users | use-authorization.model.ts:16 | Local tanım | 
| mfe-users | UserActions.ui.tsx:6,18 | TÜKETİCİ |
| mfe-users | UserDetailDrawer.ui.tsx:6,58 | TÜKETİCİ |
| mfe-shell | use-authorization.model.ts:4 | Local tanım |
| mfe-shell | use-authorization.model.test.tsx:6,23,33 | TEST |

**Eylem:** PR7 — mfe-users useAuthorization → usePermissions

## 5. Deprecated Controller'lar (2)

| Dosya | Annotation |
|-------|-----------|
| AccessController.java:18 | @Deprecated(since = "v1 endpoints added; use /api/v1/roles") |
| PermissionController.java:18 | @Deprecated(since = "v1 endpoints added; use /api/v1/permissions") |

**Eylem:** PR6 — silinecek (v1 endpoint'ler aktif)

## 6. Deprecated Enum Değerleri (2)

| Dosya | Değer |
|-------|-------|
| PermissionType.java:13 | @Deprecated PAGE |
| PermissionType.java:15 | @Deprecated FIELD |

**Eylem:** PR6

## 7. ConstantAuthzVersionProvider (1)

| Dosya | Not |
|-------|-----|
| scope/ConstantAuthzVersionProvider.java:8 | Hiç kullanılmıyor (0 tüketici) |

**Eylem:** PR6 — silinecek

## ÖZET

| Kategori | Kaynak | Tüketici | Test | Toplam |
|----------|--------|----------|------|--------|
| PermissionServiceClient | 3 | 3 | 4 | 10 |
| PermissionCodes | 1 | 27 | 13 | 41 |
| /api/permissions | 1 | 1 | 0 | 2 |
| useAuthorization | 3 | 2 | 2 | 7 |
| Deprecated controllers | 2 | 0 | 0 | 2 |
| Deprecated enums | 2 | 0 | 0 | 2 |
| ConstantAuthzVersionProvider | 1 | 0 | 0 | 1 |
| **TOPLAM** | **13** | **33** | **19** | **65** |

## PR MAPPING

| PR | Temizlenecek Kategoriler | Dosya Sayısı |
|----|-------------------------|-------------|
| PR5 | (bağımsız — propagateRoleChange) | 0 legacy |
| PR6-prereq | PermissionServiceClient (auth-service) | ~6 dosya |
| PR7 | useAuthorization (mfe-users) | ~5 dosya |
| PR6 | PermissionCodes + deprecated controllers + enums + ConstantAuthzVersionProvider | ~20 dosya |
| PR8 | (bağımsız — Grafana) | 0 legacy |
