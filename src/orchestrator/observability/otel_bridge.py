from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from src.ops.trace_meta import build_trace_meta
from src.orchestrator.runner_utils import hash_json_dir

logger = logging.getLogger(__name__)

# ── OTEL Span Export (opt-in, graceful fallback) ──────────────────────
# Enable by setting OTEL_EXPORT_ENABLED=1. Requires opentelemetry-sdk.
# Falls back to console log silently when SDK is not installed.

_otel_available = False
_span_exporter = None

try:
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore

    _otel_available = True
    _tracer_provider: Any = None

    def _get_tracer_provider() -> Any:
        global _tracer_provider
        if _tracer_provider is None and os.environ.get("OTEL_EXPORT_ENABLED") == "1":
            _tracer_provider = TracerProvider()
            _tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        return _tracer_provider

except ImportError:
    def _get_tracer_provider() -> Any:  # type: ignore[misc]
        return None


def export_run_span(*, run_id: str, intent: str, status: str, duration_ms: int = 0) -> None:
    """Export a run span via OTEL ConsoleSpanExporter if OTEL_EXPORT_ENABLED=1.

    No-op when opentelemetry-sdk is not installed or feature flag is off.
    """
    provider = _get_tracer_provider()
    if provider is None:
        logger.debug("OTEL export skipped (disabled or sdk unavailable) run_id=%s", run_id)
        return
    tracer = provider.get_tracer("ao.runner")
    with tracer.start_as_current_span("runner.run") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("intent", intent)
        span.set_attribute("status", status)
        span.set_attribute("duration_ms", duration_ms)
    logger.info("OTEL span exported run_id=%s intent=%s status=%s", run_id, intent, status)


def _rel_to_workspace(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _default_evidence_paths(*, workspace: Path, out_dir: Path, run_id: str) -> list[str]:
    base_rel = _rel_to_workspace(out_dir, workspace)
    prefix = run_id if base_rel in {"", "."} else f"{base_rel}/{run_id}"
    return [
        f"{prefix}/request.json",
        f"{prefix}/summary.json",
        f"{prefix}/provenance.v1.json",
        f"{prefix}/integrity.manifest.v1.json",
    ]


def attach_trace_meta(
    summary: dict[str, Any],
    *,
    workspace: Path,
    out_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    existing = summary.get("trace_meta")
    if isinstance(existing, dict) and str(existing.get("run_id") or "") == str(run_id or ""):
        return existing

    policy_hash = None
    try:
        policy_hash = hash_json_dir(workspace, "policies")
    except Exception:
        policy_hash = None

    trace_meta = build_trace_meta(
        work_item_id=str(run_id or ""),
        work_item_kind="RUN",
        run_id=str(run_id or ""),
        policy_hash=policy_hash,
        evidence_paths=_default_evidence_paths(workspace=workspace, out_dir=out_dir, run_id=str(run_id or "")),
        workspace_root=str(workspace),
    )
    summary["trace_meta"] = trace_meta
    return trace_meta
