# spec-core (CAPABILITY/KABİLİYET) — SSOT meta sözleşmesi v0.1

Amaç: Ürünün “tek mantık” sözleşmesini, artefact türleri arasında ortak bir meta çekirdekle standardize etmek.

Bu sözleşme:
- Fail-closed davranışı destekler (belirsizlikte: plan-only / report_only).
- SSOT = Git, derived index = rebuildable cache ilkesine uyar.
- ISO sırasını “aktif referans” olarak kullanır (uzun metin kopyalamaz).
- Evidence / risk / guardrails alanlarını aynı meta içinde taşır.

## İki SSOT katmanı

1) Project SSOT (Roadmap)
- Yol haritası: `roadmaps/SSOT/roadmap.v1.json`
- Milestone’lar: M0..Mn (dotted id’ler dahil)

2) Operational SSOT (ISO çekirdek)
- Tenant ISO çekirdek dosyaları (M1 ile workspace’te oluşturulur):
  - `tenant/<TENANT>/context.v1.md`
  - `tenant/<TENANT>/stakeholders.v1.md`
  - `tenant/<TENANT>/scope.v1.md`
  - `tenant/<TENANT>/criteria.v1.md`

Kural: spec-core meta içindeki `iso_refs` bu dosyalara **referans** verir; içerik kopyalanmaz.

## Hybrid meta + body yapısı

Her spec dosyası iki bölümden oluşur:

1) `meta` (schema-validated, strict)
- Makine tarafından doğrulanabilir alanlar: kimlik, amaç, guardrails, risk, evidence, ISO referansları.
- Bu repo için SSOT schema’lar:
  - `schemas/spec-core.schema.json`
  - `schemas/spec-capability.schema.json`

2) `body` (tür-özelleştirilebilir)
- İnsan tarafından okunur; tür-specific alanlar taşır.
- CAPABILITY (KABİLİYET) için `body.type == "capability"` ve `implementation_ref` zorunludur.

## Meta alanları (özet)

- `id`, `version`, `kind`, `purpose`: tanım kimliği ve niyet
- `inputs[]`, `steps[]`, `outputs[]`: yüksek seviye sözleşme
- `guardrails[]`: policy, gate, governor, tool-capability sınırları (metinsel, kısa)
- `iso_refs`: ISO çekirdek dokümanlarına referanslar + gate seviyesi (warn/block)
- `evidence`: beklenen evidence dosyaları + verify-on-read beklentisi
- `risk`: risk sınıfı + default mod + tetikleyiciler
- `sustainability`: intent bağlamı + ölçüm hedefleri (ops/finops için)
- `continuity`: resume/idempotency/checkpointing sinyalleri

## Workspace-bound / external pointer standardı (SSOT)

`implementation_ref` core repo’da yoksa bu **missing_file** olarak değil **external_pointer** veya **workspace_bound** olarak değerlendirilir.
ISO core refs (`tenant/.../*.v1.md`) **workspace_bound** kabul edilir; içerik core’da kopyalanmaz.
Doc‑graph ve navigasyon bu standardı temel alır.

## Terminology lock

- Canonical (code): **CAPABILITY**
- Doküman (TR): **KABİLİYET**
- Eski terminoloji repo SSOT dokümanlarında kullanılmaz.

## Örnek CAPABILITY

Örnek SSOT dosyası:
- `capabilities/CAP-PR-PACKAGER.v1.json`
