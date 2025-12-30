# Constitution (v0)

## Amaç

Bu doküman, orchestrator’un temel ilkelerini ve sınırlarını tanımlar.

## İlkeler

- Varsayılan güvenli: side‑effect yoksa `dry_run` ile çalıştır.
- Açık intent sözleşmesi: intent → workflow eşleşmesi kayıt altında olmalı.
- İzlenebilirlik: her isteğin `request_id` ve `idempotency_key` alanları olmalı.

