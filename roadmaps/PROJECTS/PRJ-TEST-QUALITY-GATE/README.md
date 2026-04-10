# PRJ-TEST-QUALITY-GATE

Sahte Test Onleme Altyapisi — 6 katmanli savunma sistemi.

## Problem

Design Lab'da 362 sahte test tespit edildi ve silindi (139 edge + 223 depth).
Control-plane'de onleme altyapisi SIFIR. Testler post-facto temizleniyor.

## Hedef

Sahte testler olusturulamaz, commit edilemez, merge edilemez.

## Katmanlar

| # | Katman | Faz | Dosyalar |
|---|--------|-----|----------|
| 1 | SSOT Kontrat | F1 | schema + policy (6 TQ rule) |
| 2 | Statik Tespit | F2 | 4 semgrep rule (EP-006..EP-009) |
| 3 | CI Gate | F3 | ci/check_test_quality.py + contract test |
| 4 | Agent Rules | F4 | .claude/rules genisletme + AGENTS.md |
| 5 | Maturity | F5 | test_quality area + standards.lock |
| 6 | Cross-Repo | F6 | sync propagation + smoke fixture |

## Codex Consensus

- Consultation: CNS-20260410-009
- Verdict: A (plan onay, 3 iyilestirme ile)
- Parser-backed semgrep patterns (regex-only degil)
- Normalized body hash (raw SHA-256 degil)
- Post-sync semgrep smoke fixture

## Basari Metrikleri

- Zero bulk-generation markers (TQ-006)
- Shallow render ratio < 10% (TQ-001)
- Assertion density >= 2.0 per test
- Duplication ratio < 5% (TQ-003)
- CI gate blocking in managed repos
- Maturity test_quality L3
