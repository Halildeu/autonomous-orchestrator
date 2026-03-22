# Context Health Runbook (v1)

## Genel Bakış

Self-Healing Context Triad sistemi 3 bileşenden oluşur:
- **P0 — Reconciliation Controller**: observe→compare→act→report döngüsü
- **P1 — Context Health Score (Eval-G)**: Per-repo 0-100 sağlık puanı
- **P6 — Content Drift Detection**: SHA256 hash ile artifact/session/policy drift tespiti

## Health Score Bileşenleri

| Bileşen | Max | Ölçüm |
|---------|-----|-------|
| Session Freshness | 20 | Session context expired mı? |
| Decision Coverage | 20 | Kaç ephemeral decision populate? |
| Standards Compliance | 20 | standards.lock mevcut ve valid mi? |
| Artifact Completeness | 20 | 5 context artifact mevcut mi? |
| Drift Score | 20 | Content drift yok mu? |

**Grade Tablosu**: A (≥90) | B (≥80) | C (≥70) | D (≥50) | F (<50)

## Drift Tespiti

3 katmanlı drift kontrolü:
1. **Artifact drift**: Workspace context artifact'larının SHA256 hash karşılaştırması
2. **Session drift**: Parent-child decision uyumu (missing, stale, conflict)
3. **Policy drift**: Policy dosyalarının hash karşılaştırması

## Komutlar

```bash
# Health score kontrolü (managed repo CI'da)
python3 scripts/check_context_health.py --workspace-root .cache/ws_customer_default

# Full drift detection
python3 -c "from src.ops.context_drift import run_full_drift_detection; ..."

# Reconciliation (dry-run)
python3 scripts/sync_managed_repo_standards.py --target-repo-root /path/to/dev --sync-context

# Reconciliation (apply)
python3 scripts/sync_managed_repo_standards.py --target-repo-root /path/to/dev --apply --sync-context

# Session link
python3 -m src.ops.manage session-link-parent \
  --workspace-root /path/to/dev/.cache/ws_customer_default \
  --parent-workspace /path/to/orchestrator/.cache/ws_customer_default

# Session sync
python3 -m src.ops.manage session-sync \
  --workspace-root /path/to/dev/.cache/ws_customer_default \
  --direction both
```

## Troubleshooting

| Semptom | Olası Neden | Çözüm |
|---------|------------|-------|
| Score < 50 (F) | Session expired + artifact'lar eksik | `--sync-context --apply` çalıştır |
| Session FAIL | Child session yok veya expired | `session-link-parent` çalıştır |
| Drift WARN/FAIL | Policy/artifact hash uyumsuzluğu | `sync_managed_repo_standards --apply` |
| Decision coverage 0 | Parent'tan decision inherit edilmemiş | `session-sync --direction pull` |

## Self-Healing Akışı

```
Health score drop → gap_register (GAP-EVAL-LENS-context_health)
    → work_intake ticket (otomatik)
    → PDCA regression check (sonraki döngüde)
    → Reconciliation at next sync (otomatik fix)
```

## Çıktı Dosyaları

| Rapor | Yol |
|-------|-----|
| Drift raporu | `.cache/reports/context_drift_report.v1.json` |
| Reconciliation raporu | `.cache/reports/context_reconciliation_report.v1.json` |
| Portfolio health | `.cache/reports/portfolio_context_health.v1.json` |
| Health check (CI) | stdout JSON |
