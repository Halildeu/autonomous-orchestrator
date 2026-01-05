# Maintainability Guardrails (Script Budget) — v0.1

Amaç: Kritik “tek dosya” script’lerin kontrolsüz büyüyüp bakım maliyetini patlatmasını önlemek.
Bu guardrail’ler **soft/hard** limitlerle çalışır ve deterministik CI’da sürekli ölçülür.

## SSOT
- Konfigürasyon: `ci/script_budget.v1.json`
- Şema: `schemas/script-budget.schema.json`
- Checker: `ci/check_script_budget.py`
- Rapor (default): `.cache/script_budget/report.json`

## Kurallar (soft/hard)

**Dosya satır limitleri**
- `src/ops/manage.py`: soft=1200, hard=1800
- `smoke_test.py`: soft=1000, hard=1500
- `src/roadmap/executor.py`: soft=900, hard=1300
- `src/tools/gateway.py`: soft=500, hard=800

**Fonksiyon satır limitleri**
- soft=80, hard=150

## Davranış
- Soft limit aşımı: **WARN** (CI fail olmaz, rapor üretir)
- Hard limit aşımı: **FAIL** (CI fail olur)

## Lokal kullanım (copy-paste)

```bash
python ci/check_script_budget.py --out .cache/script_budget/report.json
python -m src.ops.manage script-budget
```

## “If fails” hızlı aksiyon
- `WARN`: yeni özellik eklerken önce **yeni bir modüle** ayır (ör. `src/ops/commands/*`, `ci/smoke_test.py`) ve mevcut dosyayı büyütme.
- `FAIL`: ilgili dosya/fonksiyon **refactor edilmeden merge edilmez** (hard limit).

Not: Bu guardrail’ler “kod kalitesi” için değil, **operasyonel sürdürülebilirlik** için SSOT’tur.
