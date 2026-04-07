# STORY-0317: Access Admin UX Redesign - Sifirdan Tasarim

ID: STORY-0317

1. AMAÇ

Access admin deneyimini tek ekranda yamanmis bir panel olmaktan cikarip,
rol yonetimi, yetki matrisi, iliski analizi ve audit akislarini ayri ama
birbiriyle tutarli yuzeylere bolmek.

2. TANIM

## 2.1 Problem

Mevcut access admin sayfasi (`/access/roles`) cok fazla isi tek yuzeyde
topluyor:

- Filtre bar, variant toolbar, tab bar, action butonlari ve grid ayni alanda.
- Gorsel hiyerarsi zayif; birincil ve ikincil aksiyonlar ayrismiyor.
- Permission atama mantigi policy kartlari ve checkbox listeleri yuzunden zor
  izleniyor.
- Graph, Matrix ve Explain gibi ileri ozellikler ana is akisinin icinde
  organik olmayan sekilde gorunuyor.

## 2.2 Rakip analizi ozeti

| Urun | En guclu taraf | Bu hikaye icin alinacak ders |
|------|----------------|------------------------------|
| Permit.io | Grid/matrix gorunumu | Yetki matrisi ve hucre bazli duzenleme |
| Clerk | Feature-based grouping | Modul bazli yetki gruplama |
| Linear | Minimal liste ve progressive disclosure | Hover ile aksiyon gosteren rol kartlari |
| Vercel | Uye/katilim akislarinda sadelik | Drawer tabanli rol detay ve uye gorunumu |
| Auth0 | Rol-kullanici iki yonlu gezinti | Rol drawer icinde atanmis kullanicilar |
| Stripe | Sistem rolleri vurgusu | System role badge ve sade yetki seviyesi |
| WorkOS | Stabil slug/ID mantigi | Rol kimligini slug ile koruma |

## 2.3 Onerilen bilgi mimarisi

Tek sayfa yerine dort route ve ortak drawer modeli kullanilir:

```text
/access
  /roles   -> Rol yonetimi
  /matrix  -> Yetki matrisi
  /graph   -> Iliski haritasi
  /audit   -> Yetki audit gecmisi
```

Sidebar icinde "Erisim" grubu route bazli calisir; tab bazli gecis
kullanilmaz.

## 2.4 Sayfa tanimlari

### Rol Yonetimi (`/access/roles`)

- Kart bazli rol listesi kullanilir.
- Kartta rol adi, aciklama, uye sayisi ve en yuksek yetki seviyesi gorunur.
- Hover durumunda `Klonla`, `Sil`, `Duzenle` aksiyonlari acilir.
- `+ Yeni Rol` butonu primary aksiyon olarak sag ustte yer alir.
- Kart tiklandiginda rol detay drawer'i acilir.

### Rol Detay Drawer

- Genel alan: uye sayisi, olusturma tarihi, son guncelleme, sistem rolu.
- Modul yetkileri accordion yapisinda gosterilir.
- Modul bazinda seviye secimi `Yok / Oku / Duz. / Yonet` olarak sunulur.
- Gerektiginde tekil permission override yapilabilir.
- Atanmis kullanicilar drawer icinde kisa liste olarak gorunur.
- Dirty state varken kaydet butonu aktif olur; cikista uyari verilir.

### Yetki Matrisi (`/access/matrix`)

- Roller satir, moduller sutun olacak sekilde matrix gorunumu sunulur.
- Hucreler tiklanabilir ve 4 seviyeli dropdown ile degistirilebilir.
- Renk kodlamasi kullanilir:
  - `Yonet` koyu mavi
  - `Duz.` acik mavi
  - `Oku` gri
  - `Yok` bos
- Degisiklikler batch save ile kaydedilir.

### Iliski Haritasi (`/access/graph`)

- Varsayilan gorunum agac yapisidir.
- Opsiyonel grafik gorunumu FlowBuilder tabanli olabilir.
- Ayni sayfada "Erisimi Kontrol Et" yuzeyi bulunur.
- Kullanici secimi sayfa basindan yapilir.

### Yetki Audit (`/access/audit`)

- Yetki degisiklikleri timeline olarak gosterilir.
- Kim, ne zaman, hangi rolu degistirdi bilgisi saklanir.
- Before/after farki okunabilir sekilde sunulur.
- Kullanici, rol ve tarih araligi filtreleri desteklenir.

3. KAPSAM VE SINIRLAR

## 3.1 Teknik yaklasim

Silinecek veya buyuk oranda yeniden yazilacak yuzeyler:

- `AccessPage.ui.tsx`
- `AccessFilterBar.ui.tsx`
- `AccessGrid.ui.tsx`
- `AccessRoleDrawer.ui.tsx`
- `PermissionMatrix.ui.tsx`
- `RelationshipGraph.ui.tsx`
- `RelationshipTreeView.ui.tsx`
- `ExplainPanel.ui.tsx`
- `ScopeAssignmentPanel.ui.tsx`

Korunacak uygulama omurgasi:

- `roles.api.ts`
- `permissions.api.ts`
- `scopes.api.ts`
- `companies.api.ts`
- `authz.api.ts`
- `use-access-roles.model.ts`
- `use-relationship-data.model.ts`
- `access.types.ts`
- mevcut backend endpoint'leri

## 3.2 Hedef dosya yapisi

```text
src/
  pages/
    roles/RolesPage.ui.tsx
    matrix/MatrixPage.ui.tsx
    graph/GraphPage.ui.tsx
    audit/AuditPage.ui.tsx
  widgets/
    role-card/RoleCard.ui.tsx
    role-drawer/RoleDrawer.ui.tsx
    matrix-cell/MatrixCell.ui.tsx
    relationship-tree/RelationshipTree.ui.tsx
    explain-check/ExplainCheck.ui.tsx
  shared/
    AccessNav.ui.tsx
```

## 3.3 Sinirlar

- Bu hikaye backend endpoint semantigini degistirmez.
- Ilk fazda odak admin deneyimidir; yeni auth modeli tanimlamaz.
- Drawer ve matrix davranisi mevcut API kontratlariyla calismalidir.

4. ACCEPTANCE KRİTERLERİ

- [ ] Rol yonetimi sayfasi kart bazli liste ile acilir.
- [ ] Yeni rol olusturma en fazla uc etkileşim adiminda tamamlanir.
- [ ] Rol drawer'inda modul bazli seviye secimi ve tekil override birlikte
  calisir.
- [ ] Yetki matrisi hucre bazli duzenleme ve toplu kaydetme sunar.
- [ ] Iliski sayfasi en az bir kullanici icin agac gorunumu ve erisim kontrolu
  yuzeyini gosterir.
- [ ] Audit sayfasi tarih/rol/kullanici filtreleri ile degisiklik kaydini listeler.
- [ ] Ham i18n key'leri son kullaniciya gosterilmez.
- [ ] Sayfalar 768px ve ustu ekranlarda kullanilabilir kalir.
- [ ] Lazy load ile ilk sayfa yukleme deneyimi hedeflenen hizda kalir.

5. BAĞIMLILIKLAR

- Access API katmani ve mevcut authz endpoint'leri
- `mfe-access` icindeki router ve drawer altyapisi
- Tasarim sistemi kart, drawer, accordion, dropdown ve badge bilesenleri
- Gerekirse iliski grafigi icin mevcut FlowBuilder entegrasyonu
- Ilgili kabul ve test plan dokumanlari

6. ÖZET

Bu hikaye access admin deneyimini tek sayfali kalabalik bir yapidan cikarip,
roller, matrix, graph ve audit olarak ayrisan daha okunabilir bir bilgi
mimarisine tasir. Teknik sinir, backend kontratlarini degistirmeden mevcut API
omurgasi uzerinde sade ve hizli bir yonetim deneyimi kurmaktir.

7. LİNKLER (İSTEĞE BAĞLI)

- `docs/03-delivery/ACCEPTANCE/AC-0316-cross-plane-auth-session-audit-foundation.md`
- `docs/03-delivery/TEST-PLANS/TP-0316-cross-plane-auth-session-audit-foundation.md`
- `docs/04-operations/RUNBOOKS/RB-mfe-access.md`
