# Observability Rules

- Logger: use `src.shared.logger.get_logger(__name__)` — never use `print()` for structured output
- Log level: controlled by `AO_LOG_LEVEL` env var (default INFO); DEBUG only in development
- OTEL spans: `src.orchestrator.observability.otel_bridge.export_run_span()` for run-level traces
- OTEL export: behind `OTEL_EXPORT_ENABLED=1` feature flag — graceful ImportError fallback required
- Quality gate metrics: `src.orchestrator.quality_gate.get_gate_metrics()` returns Counter snapshot
- Gate counter key format: `{gate_id}:{action}` (e.g. `schema_valid:pass`, `output_not_empty:reject`)
- Secrets MUST NOT appear in spans, logs, or metrics — scrub before emitting
- Observability coverage matrix: `docs/OPERATIONS/OBSERVABILITY-COVERAGE-MATRIX.v1.json`
- New observable components must be added to coverage matrix
- No blocking calls in span export — wrap in try/except, log warning on failure
