# Side Effects & Capabilities (v0.1)

Bu doküman, sistemin **bugün (v0.1.x)** hangi side effect’leri (dosya write, PR açma vb.) desteklediğini ve nasıl güvenli açıldığını anlatır.

SSOT (single source of truth) olarak şu manifest’i kullan:
- `docs/OPERATIONS/side-effects-manifest.v1.json`

## Side-effect policy durumu

Manifest’teki kavramlar:
- `side_effect_policies`: kavramsal policy isimleri (örn. `none`, `draft`, `pr`, `merge`, `deploy`)
- `supported_now`: bugün gerçekten kullanılan/izin verilenler
- `blocked_now`: bugün **fail-closed** engellenenler (örn. schema veya gate ile)

Pratik:
- `none`: side effect yok (write/PR yok).
- `draft`: local dosya write side effect’i için (MOD_B file write yolu).
- `pr`: GitHub PR creation side effect’i (integration-only; gerçek HTTP ancak explicit enable).
- `merge`, `deploy`: **reserved** ve bugün bloklu (fail-closed).

## PR side effect (integration-only, fail-closed)

PR açma side effect’i sadece şu koşullarda *gerçek* network çağrısı yapabilir:
- `side_effect_policy == "pr"` ve `dry_run == false`
- APPROVAL gate geçilmiş olmalı (SUSPENDED ise `--resume ... --approve true`)
- `ORCH_INTEGRATION_MODE=1` set edilmeli (aksi halde `INTEGRATION_MODE_REQUIRED` ile fail-closed)
- `policies/policy_security.v1.json`:
  - `network_access: true`
  - `network_allowlist` içinde `api.github.com`
- `policies/policy_secrets.v1.json`:
  - `allowed_secret_ids` içinde `GITHUB_TOKEN`
  - secret runtime’da mevcut olmalı (env veya `vault_stub`)

En güvenli manuel test (evidence üretmez):
- Runbook’a bak: `docs/OPERATIONS/runbook-day1.md` → “GitHub PR side effect” bölümü.

## Capabilities (Tool Gateway)

Side effect’ler tool bazında enforced edilir:
- Tool capability allowlist’i `registry/registry.v1.json` içindeki `modules[].allowed_tools` alanından gelir.
- Runner, Tool Gateway üzerinden çağrılmayan yan etkileri kabul etmez (deny-by-default).

Güncel matrix için:
- `docs/OPERATIONS/side-effects-manifest.v1.json` → `capabilities_matrix`

