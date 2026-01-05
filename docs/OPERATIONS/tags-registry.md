# Tags & Status Registry (SSOT) — v0.1

Amaç: “tek mantık” sözleşmesinde (SSOT) terminoloji drift’ini azaltmak ve ops çıktılarının beklenen değerlerini tek yerde toplamak.

## AUTOPILOT CHAT başlıkları (SSOT)
- `PREVIEW`
- `RESULT`
- `EVIDENCE`
- `ACTIONS`
- `NEXT`

Kaynak: `formats/format-autopilot-chat.v1.json` (`FORMAT-AUTOPILOT-CHAT` / `v1`).

## Pointer standardı (SSOT)
- Workspace-bound / external pointer kuralı: `docs/OPERATIONS/spec-core.md` (Workspace-bound / external pointer standardı).

## Roadmap durumları (çıktı `status`)
Not: Bu liste tam kapsam garantisi vermez; mevcut sistemin ürettiği ana değerleri kapsar.

- `OK`: Milestone ilerledi / iterasyon başarılı.
- `DONE`: Yol haritasında kalan milestone yok ve Action Register boş.
- `DONE_WITH_DEBT`: Kalan milestone yok ama Action Register’da borç/uyarı var.
- `BLOCKED`: Quarantine/backoff/guardrail nedeniyle ilerleme durdu.
- `DISABLED`: Kill switch veya governor `report_only` gibi global engel.
- `ISO_MISSING`: ISO core dosyaları yok; fail-closed duruş.

## Action Register türleri (`type` / `source`)
Örnek (yaygın) eylem türleri:
- `PLACEHOLDER_MILESTONE`: NOTE-only milestone (henüz runnable değil) borcu.
- `MAINTAINABILITY_DEBT` / `MAINTAINABILITY_BLOCKER`: bakım/refactor borcu (örn. Script Budget).
- `SCRIPT_BUDGET`: Script Budget raporundan türeyen kaynak etiketi (debt ingest).

## Sık hata kodları (roadmap/runner)
Örnek (yaygın) error_code değerleri:
- `WORKSPACE_ROOT_VIOLATION`: workspace-root dışına yazma denemesi.
- `READONLY_MODE_VIOLATION`: readonly dry-run’da repo/workspace “kirlenmesi”.
- `CONTENT_MISMATCH`: overwrite=false iken mevcut dosya farklı içerikte (idempotency fail-closed).
- `SANITIZE_VIOLATION`: promotion/sanitize taramasında yasak token bulundu.
