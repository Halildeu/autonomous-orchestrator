# ARCHITECTURE-CONSTRAINTS (Opsiyonel ama onerilen)

## Kapsam
Bu dokuman "mimari kararlar + katman sinirlari"ni kalici olarak tutar.

## Yazim siniri
- Kalici SSOT: repo (L1)
- Gunluk run/override/kanit: workspace (L2)
- Musteri/harici repo: external (L3)

## No-wait standardi
- Uzun is: job-start -> poll
- Job kayitlari workspace altinda; kanitlar deterministik

## Uyum kapilari
- layer boundary (katman siniri)
- pack validation
- integrity_compat (North Star eval)
- operability (simplicity/sustainability/continuity)

## Docs hygiene
- docs/OPERATIONS altindaki MD artisi operability sinyalidir.
- docs_ops_md_count ve docs_ops_md_bytes deterministik olculur.
- repo_md_total_count repo geneli MD sayimini izler.
- Asimlar gap uretir ve work-intake'e duser.

## Extension-as-Model standardi
- Extension: schema/policy/ops/intake/cockpit/tests
- Tenant policy: network/side-effect/limits
