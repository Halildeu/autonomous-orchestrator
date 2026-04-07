# STORY-0318: Zanzibar Uyumlu Yetki Sistemi — Final İstişare Dokümanı

ID: STORY-0318

1. AMAÇ

Mevcut yetki sistemini Zanzibar (OpenFGA) tabanlı tam yetki yönetimine dönüştürmek:
rol paketleri, DENY, çoklu rol, scope UI, izin kataloğu ve explain sistemi.

2. TANIM

Bu doküman, eski OpenFGA altyapı migration (Faz 0-5, PR #168) üzerine inşa edilecek
tam yetki yeniden tasarımının istişare dokümanıdır. 12 karar, 5 fazlı plan içerir.

3. KAPSAM VE SINIRLAR

Kapsam: OpenFGA model, backend API (catalog, assignments, /me, explain),
frontend (mfe-users çoklu rol, mfe-access rol drawer, explain panel).
Sınır: Keycloak sadece login. SaaS ürünü değil. SOC2 ertelendi.

4. ACCEPTANCE KRİTERLERİ

- Çoklu rol atanabilir, DENY ile izin engellenebilir
- Scope UI sekmeli çalışır, explain endpoint aktif
- Tüm mevcut testler geçer

5. BAĞIMLILIKLAR

- OpenFGA altyapı migration (PR #168 — DONE)
- Keycloak realm, permission-service, user-service, core-data-service

6. ÖZET

12 kararla şekillenen, 5 fazlı Zanzibar uyumlu yetki yeniden tasarımı.

7. LİNKLER (İSTEĞE BAĞLI)

- decisions/registry.v1.json (zanzibar-openfga topic)

---

# İSTİŞARE DETAYLARI

## 1. Kararlar

| # | Karar | Tercih |
|---|---|---|
| K1 | EDIT seviyesi | Kaldırılacak — sadece VIEW ve MANAGE |
| K2 | Çoklu rol | Evet — kullanıcıya birden fazla rol atanabilir |
| K3 | Yerleşik roller | Süper Admin + Salt Okunur (silinemez) |
| K4 | Custom roller | Sınırsız — admin oluşturur |
| K5 | Veri izolasyonu | Zorunlu — şirket atanmadan hiçbir veri görülmez |
| K6 | Özellik yetkisi | Global — buton/sayfa erişimi şirket bağımsız |
| K7 | Scope atama UI | Sekmeli — Şirketler / Projeler / Depolar / Şubeler |
| K8 | İki yönlü atama | Evet — kullanıcıdan role ve rolden kullanıcıya |
| K9 | Rol tanımı | İzin paketi — modül + aksiyon + rapor + sayfa + alan |
| K10 | Engelleme (deny) | Evet — tam yetki ver, birkaçını engelle |
| K11 | Modül listesi kaynağı | Tek endpoint — /v1/modules |
| K12 | Hata tespiti | Kullanıcı dostu — neden erişemediğini anlayabilmeli |

---

## 2. İki Yetki Katmanı

### Katman 1: Veri Yetkisi (Data-Level)

Ne kontrol eder: Kullanıcı hangi şirket/proje/depo/şube verisini görebilir?

Kural: Scope atanmadan hiçbir veri görülmez.

```
user:ahmet → viewer → company:1          (Serban verilerini görebilir)
user:ahmet → viewer → project:5          (Proje Alpha verilerini görebilir)
user:ahmet → operator → warehouse:3      (İstanbul Depo verilerini görebilir)
user:ahmet → member → branch:7           (Ankara Şube verilerini görebilir)
```

Enforcement: ScopeContextFilter → OpenFGA listObjects → Hibernate @Filter → PostgreSQL RLS

### Katman 2: Özellik Yetkisi (Feature-Level)

Ne kontrol eder: Kullanıcı hangi modül/buton/sayfa/rapor/ikona erişebilir?

Kural: Scope gerekmez — global. Rol atanmışsa ilgili özellikler açılır.

```
user:ahmet → can_manage → module:PURCHASE         (satın alma modülü)
user:ahmet → allowed → action:APPROVE_PURCHASE     (onay butonu)
user:ahmet → can_view → report:PURCHASE_SUMMARY    (rapor erişimi)
user:ahmet → blocked → action:DELETE_PURCHASE_ORDER (engelleme!)
```

### İkisi Birlikte

Ahmet Serban'da satın alma yapabilir, Acme'de yapamaz:
- Özellik: PURCHASE modülü açık (ROL'den)
- Veri: Sadece Serban verileri (SCOPE'tan)
- Engel: Sipariş silme engelli (DENY'dan)

---

## 3. OpenFGA Model (Final)

```fga
model
  schema 1.1

type user

type organization
  relations
    define admin: [user]
    define member: [user] or admin

type company
  relations
    define org: [organization]
    define admin: [user] or admin from org
    define manager: [user]
    define member: [user] or manager or admin
    define viewer: [user] or member

type project
  relations
    define company: [company]
    define admin: [user] or admin from company
    define manager: [user]
    define viewer: [user] or manager or admin

type warehouse
  relations
    define company: [company]
    define admin: [user] or admin from company
    define manager: [user]
    define operator: [user] or manager or admin
    define viewer: [user] or operator

type branch
  relations
    define company: [company]
    define admin: [user] or admin from company
    define manager: [user]
    define member: [user] or manager or admin

type module
  relations
    define can_manage: [user] but not blocked
    define can_view: [user] or can_manage but not blocked
    define blocked: [user]

type action
  relations
    define allowed: [user] but not blocked
    define blocked: [user]

type report
  relations
    define can_view: [user] but not blocked
    define blocked: [user]

type page
  relations
    define can_access: [user] but not blocked
    define blocked: [user]

type field
  relations
    define can_view: [user] but not blocked
    define blocked: [user]
```

Her type'ta `blocked` ilişkisi var — engelleme her seviyede çalışır.

---

## 4. Rol Sistemi

### 4.1 Yerleşik Roller (silinemez)

| Rol | OpenFGA | Açıklama |
|---|---|---|
| Süper Admin | admin → organization:default | Her şeye erişim |
| Salt Okunur | Tüm modüller can_view | Hiçbir şeyi değiştiremez |

### 4.2 Rol = İzin Paketi

Rol sadece modül değil, her türlü yetki parçacığını gruplar:

```
"Satın Alma Müdürü" rolü:
  İZİN VER:
    module:PURCHASE         → MANAGE
    module:WAREHOUSE        → VIEW
    module:REPORT           → VIEW
    action:APPROVE_PURCHASE → ALLOWED
    action:CREATE_PO        → ALLOWED
    report:PURCHASE_SUMMARY → ALLOWED
    page:PURCHASE_SETTINGS  → ALLOWED

  ENGELLE:
    action:DELETE_PO        → BLOCKED
```

### 4.3 DB Şeması

```sql
role_permissions:
  role_id          | permission_type | permission_key        | grant_type
  3 (Satın Alma M.)| module          | PURCHASE              | MANAGE
  3                | module          | WAREHOUSE             | VIEW
  3                | action          | APPROVE_PURCHASE      | ALLOW
  3                | action          | CREATE_PO             | ALLOW
  3                | action          | DELETE_PO             | DENY
  3                | report          | PURCHASE_SUMMARY      | ALLOW
  3                | page            | PURCHASE_SETTINGS     | ALLOW
```

`grant_type`: MANAGE / VIEW / ALLOW / DENY

### 4.4 Çoklu Rol Birleşimi

Ahmet'e 2 rol atanmış:
- Satın Alma Müdürü: PURCHASE=MANAGE, action:DELETE_PO=DENY
- Raporlama Okuyucu: REPORT=VIEW

Sonuç tuple'ları (union):
```
can_manage → module:PURCHASE
can_view → module:WAREHOUSE
can_view → module:REPORT
allowed → action:APPROVE_PURCHASE
allowed → action:CREATE_PO
blocked → action:DELETE_PO         ← engelleme!
can_view → report:PURCHASE_SUMMARY
can_access → page:PURCHASE_SETTINGS
```

Kural: DENY her zaman ALLOW'u yener (deny-wins). Birden fazla rolde çakışma varsa engelleme kazanır.

---

## 5. Atama Akışı

### 5.1 Rol Oluşturma (/access/roles)

```
POST /v1/roles
{
  "name": "Satın Alma Müdürü",
  "description": "Satın alma ve depo yetkisi",
  "permissions": [
    { "type": "module", "key": "PURCHASE", "grant": "MANAGE" },
    { "type": "module", "key": "WAREHOUSE", "grant": "VIEW" },
    { "type": "module", "key": "REPORT", "grant": "VIEW" },
    { "type": "action", "key": "APPROVE_PURCHASE", "grant": "ALLOW" },
    { "type": "action", "key": "CREATE_PO", "grant": "ALLOW" },
    { "type": "action", "key": "DELETE_PO", "grant": "DENY" },
    { "type": "report", "key": "PURCHASE_SUMMARY", "grant": "ALLOW" },
    { "type": "page", "key": "PURCHASE_SETTINGS", "grant": "ALLOW" }
  ]
}
```

### 5.2 Kullanıcıya Rol + Scope Atama (/admin/users)

```
POST /v1/users/{userId}/assignments
{
  "roleIds": [3, 7],
  "scopes": {
    "companyIds": [1],
    "projectIds": [5],
    "warehouseIds": [3],
    "branchIds": [7]
  }
}

→ OpenFGA tuple'ları:
  // Özellik (rollerden):
  can_manage → module:PURCHASE
  can_view → module:WAREHOUSE
  can_view → module:REPORT
  allowed → action:APPROVE_PURCHASE
  allowed → action:CREATE_PO
  blocked → action:DELETE_PO
  can_view → report:PURCHASE_SUMMARY
  can_access → page:PURCHASE_SETTINGS

  // Veri scope:
  viewer → company:1
  viewer → project:5
  operator → warehouse:3
  member → branch:7
```

### 5.3 Rol İzni Değiştiğinde

```
PUT /v1/roles/3/permissions
{ "permissions": [...yeni liste...] }

→ Atanmış kullanıcıları bul (10 kişi)
→ Her kullanıcı için:
    1. Eski tuple'ları sil
    2. Yeni tuple'ları yaz
→ 10 kullanıcı anında güncellenir
```

### 5.4 İki Yönlü Atama

```
Yol A: Kullanıcıdan role
  /admin/users → Ahmet → Drawer → ROLLER checkbox → Kaydet

Yol B: Rolden kullanıcıya
  /access/roles → Satın Alma Müdürü → Drawer → + Kişi Ekle → Kaydet

İkisi aynı endpoint'i çağırır: POST /v1/users/{userId}/assignments
```

---

## 6. Hata Tespiti (Kullanıcı Dostu)

### 6.1 "Neden Erişemiyorum?" Sistemi

Kullanıcı bir sayfaya/butona erişemediğinde net mesaj görmeli:

```
┌──────────────────────────────────────────┐
│ ⚠ Bu sayfaya erişiminiz yok              │
│                                          │
│ Neden:                                   │
│ • "Denetim" modülü rolünüzde tanımlı değil│
│ • Gerekli: module:AUDIT → can_view       │
│ • Mevcut rolleriniz: Satın Alma Müdürü   │
│                                          │
│ [Yetki Talep Et]    [Yöneticiye Bildir]  │
└──────────────────────────────────────────┘
```

Veri yoksa:

```
┌──────────────────────────────────────────┐
│ ℹ Gösterilecek veri yok                  │
│                                          │
│ Neden:                                   │
│ • "Acme Corp" şirketine erişiminiz yok   │
│ • Erişiminiz olan şirketler: Serban      │
│                                          │
│ [Farklı Şirket Seç]                     │
└──────────────────────────────────────────┘
```

Engelleme varsa:

```
┌──────────────────────────────────────────┐
│ ⛔ Bu işlem engellenmiş                   │
│                                          │
│ Neden:                                   │
│ • "Sipariş Silme" rolünüzde engellenmiş  │
│ • Kaynak: Satın Alma Müdürü rolü         │
│ • Engel türü: DENY                       │
│                                          │
│ [Yöneticiye Bildir]                      │
└──────────────────────────────────────────┘
```

### 6.2 Backend Explain API

```
POST /v1/authz/explain
{
  "userId": "ahmet",
  "permissionType": "action",
  "permissionKey": "DELETE_PO"
}

Response:
{
  "allowed": false,
  "reason": "DENIED_BY_ROLE",
  "details": {
    "roleName": "Satın Alma Müdürü",
    "grantType": "DENY",
    "permissionType": "action",
    "permissionKey": "DELETE_PO"
  },
  "userRoles": ["Satın Alma Müdürü", "Raporlama Okuyucu"],
  "userScopes": {
    "companies": ["Serban Holding"],
    "projects": ["Proje Alpha"]
  }
}
```

### 6.3 Frontend Hook

```typescript
const { allowed, reason, details } = useCheckPermission("action", "DELETE_PO");

if (!allowed) {
  showDeniedMessage(reason, details);
}
```

---

## 7. /v1/authz/me Response (Final)

```json
{
  "userId": "ahmet",
  "superAdmin": false,
  "roles": ["Satın Alma Müdürü", "Raporlama Okuyucu"],
  "modules": {
    "PURCHASE": "MANAGE",
    "WAREHOUSE": "VIEW",
    "REPORT": "VIEW"
  },
  "actions": {
    "APPROVE_PURCHASE": "ALLOW",
    "CREATE_PO": "ALLOW",
    "DELETE_PO": "DENY"
  },
  "reports": {
    "PURCHASE_SUMMARY": "ALLOW"
  },
  "pages": {
    "PURCHASE_SETTINGS": "ALLOW"
  },
  "scopes": {
    "companyIds": [1],
    "projectIds": [5],
    "warehouseIds": [3],
    "branchIds": [7]
  }
}
```

Frontend bu response'u cache'ler (60s TTL) ve her yetki kontrolü bu objeden yapılır.

---

## 8. UI Tasarımı (Final)

### 8.1 mfe-users — Kullanıcı Drawer

```
┌──────────────────────────────┐
│ Ahmet Yılmaz            [×]  │
│ ahmet@serban.com             │
│ ──────────────────────────── │
│                              │
│ ROLLER                       │
│ ☑ Satın Alma Müdürü          │
│ ☑ Depo Sorumlusu             │
│ ☐ İK Yöneticisi              │
│ ☐ Raporlama Okuyucu          │
│ ☐ Salt Okunur                │
│                              │
│ VERİ ERİŞİMİ                 │
│ ┌────────────────────────┐   │
│ │Şirketler│Projeler│Depolar│Şubeler│
│ ├────────────────────────┤   │
│ │ ☑ Serban Holding       │   │
│ │ ☐ Acme Corp            │   │
│ │ ☐ Beta Ltd             │   │
│ └────────────────────────┘   │
│                              │
│ [Kaydet]          [Vazgeç]   │
└──────────────────────────────┘
```

### 8.2 mfe-access — Rol Drawer

```
┌──────────────────────────────┐
│ Satın Alma Müdürü       [×]  │
│ ──────────────────────────── │
│                              │
│ MODÜLLER                     │
│ Kullanıcı Yönetimi    [—] ▼  │
│ Satın Alma        [Yönet] ▼  │
│ Depo                [Oku] ▼  │
│ Raporlama           [Oku] ▼  │
│                              │
│ AKSİYONLAR                   │
│ ☑ Satın Alma Onay            │
│ ☑ Sipariş Oluştur            │
│ ☒ Sipariş Sil (ENGEL)        │
│                              │
│ RAPORLAR                     │
│ ☑ Satın Alma Özeti           │
│                              │
│ SAYFALAR                     │
│ ☑ Satın Alma Ayarları        │
│                              │
│ ATANMIŞ KİŞİLER (2)         │
│ ● Ahmet Yılmaz               │
│ ● Mehmet Kaya                 │
│              [+ Kişi Ekle]   │
│                              │
│ [Kaydet]          [Vazgeç]   │
└──────────────────────────────┘

Semboller:
  ☑ = İzin verilmiş (ALLOW)
  ☒ = Engellenmiş (DENY) — kırmızı/üstü çizili
  [—] = Yetki yok
  [Oku] = VIEW
  [Yönet] = MANAGE
```

---

## 9. İzin Kataloğu

Tüm izin parçacıkları tek endpoint'ten gelir:

```
GET /v1/permissions/catalog

Response:
{
  "modules": [
    { "key": "USER_MANAGEMENT", "label": "Kullanıcı Yönetimi", "levels": ["VIEW", "MANAGE"] },
    { "key": "PURCHASE", "label": "Satın Alma", "levels": ["VIEW", "MANAGE"] },
    { "key": "WAREHOUSE", "label": "Depo", "levels": ["VIEW", "MANAGE"] },
    { "key": "AUDIT", "label": "Denetim", "levels": ["VIEW", "MANAGE"] },
    { "key": "REPORT", "label": "Raporlama", "levels": ["VIEW", "MANAGE"] },
    { "key": "THEME", "label": "Tema", "levels": ["VIEW", "MANAGE"] },
    { "key": "ACCESS", "label": "Erişim Yönetimi", "levels": ["VIEW", "MANAGE"] }
  ],
  "actions": [
    { "key": "APPROVE_PURCHASE", "label": "Satın Alma Onay", "module": "PURCHASE", "deniable": true },
    { "key": "CREATE_PO", "label": "Sipariş Oluştur", "module": "PURCHASE", "deniable": true },
    { "key": "DELETE_PO", "label": "Sipariş Sil", "module": "PURCHASE", "deniable": true },
    { "key": "RESET_PASSWORD", "label": "Parola Sıfırla", "module": "USER_MANAGEMENT", "deniable": true },
    { "key": "DELETE_USER", "label": "Kullanıcı Sil", "module": "USER_MANAGEMENT", "deniable": true },
    { "key": "TOGGLE_STATUS", "label": "Durum Değiştir", "module": "USER_MANAGEMENT", "deniable": true }
  ],
  "reports": [
    { "key": "PURCHASE_SUMMARY", "label": "Satın Alma Özeti", "module": "PURCHASE" },
    { "key": "HR_COMPENSATION", "label": "İK Maaş Raporu", "module": "USER_MANAGEMENT" },
    { "key": "WAREHOUSE_STOCK", "label": "Stok Raporu", "module": "WAREHOUSE" }
  ],
  "pages": [
    { "key": "ADMIN_SETTINGS", "label": "Yönetici Ayarları", "module": "ACCESS" },
    { "key": "PURCHASE_SETTINGS", "label": "Satın Alma Ayarları", "module": "PURCHASE" }
  ]
}
```

Bu endpoint:
- Rol drawer'da izin seçimi için kullanılır
- Frontend'de hardcode modül listesi kalmaz
- Yeni izin eklemek sadece bu kataloğa eklemek demek

---

## 10. Yapılacak İşler

### Faz 1: OpenFGA Model + Backend Altyapı
- model.fga güncelle (branch, action, report, page, field type'ları + blocked ilişkisi)
- role_permissions DB şeması (permission_type + permission_key + grant_type)
- /v1/permissions/catalog endpoint
- /v1/modules endpoint
- /v1/users/{id}/assignments endpoint (rol + scope birlikte)
- Rol izni değişince tuple yenileme (tüm atanmış kullanıcılar)
- /v1/authz/me genişlet (modules, actions, reports, pages, scopes)
- /v1/authz/explain endpoint (neden erişemiyorum)
- EDIT seviyesini kaldır

### Faz 2: Frontend mfe-users
- Modül level dropdown kaldır
- Rol checkbox listesi (çoklu seçim)
- Sekmeli scope atama (Şirketler/Projeler/Depolar/Şubeler)
- Kaydet → rol tuple + scope tuple birlikte yaz

### Faz 3: Frontend mfe-access
- Rol drawer: modül + aksiyon + rapor + sayfa izin seçimi (katalogdan)
- DENY desteği (☒ engelleme checkbox)
- "Atanmış Kişiler" + "Kişi Ekle" (iki yönlü atama)
- Modül/aksiyon/rapor/sayfa listesini katalog endpoint'ten çek

### Faz 4: Erişim Engeli UX
- "Neden erişemiyorum?" mesajları (modül/scope/deny bazlı)
- useCheckPermission hook (frontend)
- Explain drawer/modal

### Faz 5: Temizlik
- Hardcode modül listeleri kaldır (5 yer)
- Deprecated endpoint'ler kaldır
- Decision topic güncelle
- i18n güncelle
- doctor-zanzibar.sh güncelle

---

## 11. Doğrulama Kriterleri

- [ ] Şirket atanmadan kullanıcı hiçbir veri görememeli
- [ ] Rol atanmadan kullanıcı hiçbir modüle erişememeli
- [ ] DENY her zaman ALLOW'u yenmeli
- [ ] Rol izni değişince atanmış kullanıcılar anında güncellenmeli
- [ ] Birden fazla rol atanabilmeli
- [ ] İki yönden atama yapılabilmeli (kullanıcı→rol, rol→kullanıcı)
- [ ] Erişim engeli nedenini kullanıcı anlayabilmeli
- [ ] EDIT hiçbir yerde görünmemeli
- [ ] İzin kataloğu tek endpoint'ten gelmeli
- [ ] Aksiyon/rapor/sayfa/alan seviyesinde izin atanabilmeli
- [ ] OpenFGA Playground'da tuple'lar doğrulanabilmeli
