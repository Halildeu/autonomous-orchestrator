# Release Checklist (v0.1)

Amaç: release öncesi “neyi, hangi komutla, hangi çıktıyı bekleyerek” kontrol edeceğimizi sabitlemek.

Not: GitHub Releases yalnızca milestone sürümlerde yayınlanır; bkz. `docs/OPERATIONS/release-strategy.md`.

## 1) Pre-release checks (copy-paste)

Repo root’ta çalıştır:

```bash
# Full end-to-end sanity
python smoke_test.py

# Policy impact review (fixtures + evidence history)
python -m src.ops.manage policy-check --source both

# Ops quick view
python -m src.ops.manage runs --limit 5
python -m src.ops.manage dlq --limit 5
python -m src.ops.manage suspends --limit 5

# Retention / disk sanity (dry-run)
python -m src.ops.manage reaper --dry-run true --out reaper_report.json

# Retention guarded cleanup (non-dry-run, pre/post snapshot gate)
python -m src.ops.manage reaper --dry-run false --out reaper_report_delete.json

# Supply chain artifacts (local dev uses DEV_KEY fallback; CI requires secret)
python supply_chain/sbom.py && python supply_chain/sign.py && python supply_chain/verify.py
python supply_chain/license_gate.py
python supply_chain/cve_gate.py
```

## 2) Expected outputs (what to look for)

### Smoke
- `SMOKE_OK` satırı görmelisin.
- `CRITICAL_*` satırları yalnızca “özet” amaçlıdır; secret / full envelope içermez.

### Policy check
- Çıktıda `POLICY_CHECK_OK ...` ve `POLICY_REPORT_WRITTEN ...` olmalı.
- `.cache/policy_check/` altında:
  - `sim_report.json` (counts + examples + threshold_used)
  - `policy_diff_report.json` (baseline varsa diff; yoksa SKIPPED)
  - `POLICY_REPORT.md` (PR review için okunabilir özet)

### Evidence + Integrity
- `evidence/<run_id>/integrity.manifest.v1.json` mevcut olmalı.
- `python -m src.evidence.integrity_verify --run evidence/<run_id>` => `status=OK`

### DLQ / Suspends
- DLQ kayıtları minimal envelope alanları içerir (tam envelope dump yok).
- Suspend varsa `evidence/<run_id>/suspend.json` bulunur ve resume komutu bellidir.

### Reaper
- `reaper_report.json` içinde candidates/deleted sayıları mantıklı olmalı.
- Dry-run’da silme olmamalı; `deleted` değerleri 0 kalır.
- Non-dry-run’da cleanup guard artifact'lari oluşmalı:
  - `.cache/reports/reaper_cleanup_pre_snapshot.v1.json`
  - `.cache/reports/reaper_cleanup_post_validate.v1.json`
- `reaper_cleanup_post_validate.v1.json.status=PASS` beklenir; `FAIL` release gate bloklar.

### Supply chain
- `supply_chain/sbom.v1.json` güncel olmalı ve `project.name/version` içermeli.
- `supply_chain/signature.v1.json` ve `python supply_chain/verify.py` => `status=OK`
- License/CVE gate => `status=OK` veya (CVE için) policy’ye göre `WARN`

## 3) If fails — quick triage

### `python smoke_test.py` fail
- Hata satırındaki stage/CRITICAL bloklarına bak; çoğu durumda:
  - `policy_violation_code` + DLQ stage ile kök neden bulunur.
  - `SMOKE_OK` yoksa CI merge bloke olur (gate-schema).

### `policy-check` fail
- `.cache/policy_check/sim_report.json` ve `POLICY_REPORT.md` üzerinden:
  - block/suspend artışı var mı?
  - `policy_diff_report.json` SKIPPED mi? (git/baseline yoksa normal)

### Supply chain verify fail (CI)
- CI’da `SUPPLY_CHAIN_SIGNING_KEY` GitHub Actions secret eksik olabilir.
- `gate-schema` log’unda “Missing SUPPLY_CHAIN_SIGNING_KEY GitHub Actions secret” görürsen secret’ı ekle.

### Reaper beklenmedik delete
- Yanlış `--dry-run false` koşmuş olabilirsin.
- `policies/policy_retention.v1.json` değerlerini kontrol et.
