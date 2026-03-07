# Same-File Conflict Arbitration (v1)

Status: ACTIVE
Mode: documented safe default

## Amaç
Ayni dosyaya iki agent'in ayni anda yazmaya calismasi durumunda fail-closed davranisi tek SSOT metinde toplamak.

## Mevcut mekanizmalar
- work_item_claims: `.cache/index/work_item_claims.v1.json`
- execution_leases: `.cache/index/work_item_leases.v1.json`
- governor_lock: `.cache/governor_lock`

## Safe default kurallari
1. Ayni dosya icin ayni anda tek aktif writer kabul edilir.
2. Acik handoff yoksa aktif claim/lease sahibi yazma onceligini korur.
3. Stale claim/lease ancak stale evidence ile temizlenebilir.
4. Handoff owner_tag + owner_session + evidence_paths olmadan tamamlanmis sayilmaz.

## Residual gap
File-level arbitration su an dogrudan engine tarafinda enforce edilmiyor. Bu nedenle mevcut claim/lease/governor mekanizmalari disinda ayni dosya riskinde varsayilan davranis BLOCK + ESCALATE olmaya devam eder.
