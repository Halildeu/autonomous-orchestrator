# AGENTS.md

Bu repo “JSON‑first” bir orchestrator iskeleti (WWV) olarak tasarlanır.

## Çalışma kuralları

- JSON artefact’lar: `schemas/`, `policies/`, `registry/`, `workflows/`, `orchestrator/` altında tutulur.
- Versiyonlu dosyalar: `*.v1.json` gibi adlandırılır. JSON Schema dosyaları: `*.schema.json`.
- JSON formatı: 2 boşluk indent, UTF‑8, gereksiz trailing whitespace yok.
- Secrets: credential / token / private key commit edilmez. CI’da env/secret ile geçilir.

## Doğrulama

- Şema kontrolü: `python ci/validate_schemas.py`
- Dry-run simülasyon: `python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json`
