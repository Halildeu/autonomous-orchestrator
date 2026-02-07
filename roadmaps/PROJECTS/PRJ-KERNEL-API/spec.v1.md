# PRJ-KERNEL-API — spec.v1 (stub)

## Problem Statement
Mevcut ops/runner CLI mantığını, program-led bir API ile çağırmak; kullanıcı komut yazmadan deterministik rapor üretmek.

## User Journey (komutsuz)
İstem → program ops/gate/runner akışını yürütür → AUTOPILOT CHAT + JSON tail ile raporlar.

## API Boundary (tek kapı)
- Tek kapı: doc-nav-check summary + project-status/system-status snapshot.
- Detay/strict ayrı rapor üretir, cockpit’i bozmaz.

## Security / Isolation
- core_lock ENABLED
- workspace_root zorunlu
- sanitize + no network

## Determinism
- Aynı input → aynı output
- Evidence path’leri deterministik

## Failure Modes
- BLOCKED / WARN / DONE_WITH_DEBT semantiği
- Fail-closed; secrets yok
