# AI Decision Governance Runbook (v1)

## Karar Sınıflandırması

| Seviye | Açıklama | Örnekler |
|--------|----------|----------|
| **FULL_AUTO** | AI karar verir, insan bilgilendirilir | context drift reconcile, session renew, gap→ticket, health score |
| **HUMAN_REVIEW** | AI önerir, insan onaylar | routing bucket change, policy override, side-effect execution |
| **STRICT_DENY** | AI yapamaz, insan zorunlu | production deploy, data migration, security policy, SSOT write |

## Quality Gate'ler

| Gate | Kontrol | Fail Aksiyonu |
|------|---------|---------------|
| schema_valid | Çıktı dict mi? | retry (1 kez) |
| output_not_empty | Çıktı >= 10 karakter mi? | reject |
| consistency_check | Önceki kararlarla çelişiyor mu? | warn |
| regression_check | Fact history'de revert mi? | escalate |

## Provider Benchmark

`.cache/providers/provider_performance.v1.json` dosyasında per-provider:
- success_rate, avg_latency_ms, p95_latency_ms, quality_gate_pass_rate, trend

## Komutlar

```bash
# Decision boundary kontrolü
python3 -c "from src.orchestrator.decision_boundary import resolve_decision_boundary; print(resolve_decision_boundary(operation='session_renew', risk_score=0.1))"

# Quality gate test
python3 -c "from src.orchestrator.quality_gate import run_quality_gates; print(run_quality_gates(output={'text': 'test'}))"

# Provider stats
python3 -c "from src.orchestrator.provider_benchmark import get_provider_stats; print(get_provider_stats(workspace_root=Path('.cache/ws_customer_default'), provider='claude'))"

# Decision quality score
python3 -c "from src.orchestrator.decision_quality import compute_decision_quality_score; print(compute_decision_quality_score(workspace_root=Path('.cache/ws_customer_default')))"
```

## Troubleshooting

| Semptom | Neden | Çözüm |
|---------|-------|-------|
| DECISION_BOUNDARY_STRICT_DENY | Yasak operasyon | İnsan müdahalesi gerekli |
| QUALITY_GATE_REJECT | Çıktı kalitesiz | Retry veya farklı provider |
| Provider trend=degrading | Başarı oranı düşüyor | Provider switch veya model upgrade |
| Quality score < 0.7 | Genel kalite düşük | PDCA tetiklenir, gap üretilir |
