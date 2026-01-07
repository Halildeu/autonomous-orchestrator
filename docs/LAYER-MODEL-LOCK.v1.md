# Layer Model Lock (SSOT) — v1

Bu doküman, “tek mantık” zincirini ve katman modelini SSOT olarak kilitler.
Amaç: CORE dokunulmazlığını korurken, proje işlerini güvenli ve deterministik biçimde yürütmek.

## 1) Tek Mantık zinciri (ürün davranışı)
Bağlam → Paydaş → Kapsam → Kriter → Risk → Kanıt → Üretim → Recheck

Kural:
- İşe başlamadan önce Bağlam/Paydaş/Kapsam/Kriter ya SSOT’tan okunur ya da session RAM’de geçici tutulur.
- Bu bilgiler yoksa fail-closed: `report_only` / `no side-effect` / conservative mode.

## 2) Katmanlar ve yazma izinleri
- **L0 CORE (kilitli):** Ürünün SSOT’u. Varsayılan **core_lock=ENABLED**. Core’a yazım yalnızca açıkça kilit açılırsa mümkündür.
- **L1 CATALOG (kütüphane):** Paylaşılabilir şablonlar ve tanımlar. CORE tarafından yönetilir.
- **L2 WORKSPACE (çalışma masası):** Tenant/ISO dokümanları, derived index, raporlar.
- **L3 EXTERNAL (müşteri işi):** Müşteriye teslim edilecek artefact’ler.

Kural:
- Proje akışları core’a yazamaz. Yazım yalnızca `workspace_root` ve (varsa) `external_root` altında yapılır.

## 3) Tek katalog görünümü (deterministik)
Global SSOT + customer‑owned kayıtlar tek bir derived index’te birleşir.
Index **cache**’tir; kaynak SSOT **Git**’tir.

## 4) Customer‑owned kayıtlar (etiket mantığı)
Her kayıt aşağıdaki alanlarla izlenir:
- `origin`
- `owner_tenant`
- `promotion_state`
- `override_ref`

## 5) Conflict politikası
- **Hard conflict:** FAIL (fail‑closed).
- **Soft conflict:** WARN + deterministik seçim (ör. pack_id lexicographic).

## 6) “Bir yazılım yaz” isteğinde çıktı dağılımı
- Çıktı (artefact): **L3 EXTERNAL**
- Sentez/kanıt: **L2 WORKSPACE**
- Genellenebilir akış: **L1 CATALOG** (yalnızca promotion lane ile)

## 7) Core’a dokunma protokolü
Core’a yazım yalnızca aşağıdaki koşullarda mümkün:
- core_lock açılır (CORE_UNLOCK=1)
- gerekçe + CHG + review kayıt altına alınır
- evidence/provenance ile izlenir

## 8) Extension Model Lock
Extension modeli kilidi:
- PRJ-* = extension
- extension manifest SSOT (JSON + strict schema)
- program-led extension registry (workspace index)
- UI yakıtı JSON (system-status + portfolio-status)
