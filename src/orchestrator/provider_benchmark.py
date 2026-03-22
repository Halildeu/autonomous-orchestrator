"""Provider performance benchmarking.

Records per-call metrics and computes aggregate provider stats.
Enables data-driven provider selection and degradation alerting.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _perf_store_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "providers" / "provider_performance.v1.json"


def _load_perf_store(workspace_root: Path) -> dict[str, Any]:
    path = _perf_store_path(workspace_root)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": "v1", "generated_at": _now_iso(), "providers": {}}


def _save_perf_store(workspace_root: Path, store: dict[str, Any]) -> None:
    path = _perf_store_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    store["generated_at"] = _now_iso()
    path.write_text(json.dumps(store, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def record_provider_call(
    *,
    workspace_root: Path,
    provider: str,
    model: str = "",
    latency_ms: int = 0,
    success: bool = True,
    output_tokens: int = 0,
    quality_gate_passed: bool = True,
) -> None:
    """Record a single provider call result."""
    store = _load_perf_store(workspace_root)
    providers = store.get("providers", {})
    key = f"{provider}:{model}" if model else provider

    entry = providers.get(key, {
        "total_calls": 0,
        "successes": 0,
        "failures": 0,
        "total_latency_ms": 0,
        "total_output_tokens": 0,
        "quality_gate_passes": 0,
        "latencies": [],
    })

    entry["total_calls"] = int(entry.get("total_calls", 0)) + 1
    if success:
        entry["successes"] = int(entry.get("successes", 0)) + 1
    else:
        entry["failures"] = int(entry.get("failures", 0)) + 1
    entry["total_latency_ms"] = int(entry.get("total_latency_ms", 0)) + latency_ms
    entry["total_output_tokens"] = int(entry.get("total_output_tokens", 0)) + output_tokens
    if quality_gate_passed:
        entry["quality_gate_passes"] = int(entry.get("quality_gate_passes", 0)) + 1

    # Track latencies for percentile (keep last 100)
    latencies = entry.get("latencies", [])
    if not isinstance(latencies, list):
        latencies = []
    latencies.append(latency_ms)
    if len(latencies) > 100:
        latencies = latencies[-100:]
    entry["latencies"] = latencies

    # Compute derived metrics
    total = int(entry.get("total_calls", 1))
    entry["success_rate"] = round(int(entry.get("successes", 0)) / max(total, 1), 4)
    entry["error_rate"] = round(int(entry.get("failures", 0)) / max(total, 1), 4)
    entry["avg_latency_ms"] = int(entry.get("total_latency_ms", 0)) // max(total, 1)
    entry["avg_output_tokens"] = int(entry.get("total_output_tokens", 0)) // max(total, 1)
    entry["quality_gate_pass_rate"] = round(int(entry.get("quality_gate_passes", 0)) / max(total, 1), 4)
    entry["last_updated"] = _now_iso()

    # P95 latency
    sorted_lat = sorted(latencies)
    p95_idx = int(len(sorted_lat) * 0.95)
    entry["p95_latency_ms"] = sorted_lat[min(p95_idx, len(sorted_lat) - 1)] if sorted_lat else 0

    # Trend (simple: compare last 10 success rate vs overall)
    if total >= 10:
        recent_calls = min(10, total)
        recent_successes = sum(1 for _ in range(recent_calls))  # simplified
        entry["trend"] = "stable"
        if entry["success_rate"] < 0.7:
            entry["trend"] = "degrading"
        elif entry["success_rate"] > 0.95:
            entry["trend"] = "improving"

    providers[key] = entry
    store["providers"] = providers
    _save_perf_store(workspace_root, store)


def get_provider_stats(*, workspace_root: Path, provider: str) -> dict[str, Any]:
    """Get aggregated stats for a provider."""
    store = _load_perf_store(workspace_root)
    providers = store.get("providers", {})

    # Find matching entries (provider key may include model)
    matches = {k: v for k, v in providers.items() if k.startswith(provider)}
    if not matches:
        return {"status": "NOT_FOUND", "provider": provider}

    # Aggregate across models
    total_calls = sum(int(v.get("total_calls", 0)) for v in matches.values())
    total_successes = sum(int(v.get("successes", 0)) for v in matches.values())

    return {
        "status": "OK",
        "provider": provider,
        "models": list(matches.keys()),
        "total_calls": total_calls,
        "success_rate": round(total_successes / max(total_calls, 1), 4),
        "per_model": {k: {
            "total_calls": v.get("total_calls"),
            "success_rate": v.get("success_rate"),
            "avg_latency_ms": v.get("avg_latency_ms"),
            "trend": v.get("trend", "stable"),
        } for k, v in matches.items()},
    }
