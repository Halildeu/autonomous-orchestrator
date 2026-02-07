# ADR-0001: Intent Contract

## Karar

Sistem, her isteği tek bir `intent` (URN) ile ifade eder ve routing `orchestrator/strategy_table.v1.json` üzerinden yapılır.

## Gerekçe

- Deterministik routing
- Policy simülasyonunun fixture’lar üzerinden yapılabilmesi
- Minimal, genişletilebilir sözleşme

