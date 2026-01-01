from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any

from src.orchestrator.workflow_exec import BudgetSpec, BudgetTracker


def duration_ms_from_started(started_at: Any, finished_at: str, *, fallback: Any = None) -> int:
    try:
        if isinstance(started_at, str) and started_at:
            s = datetime.fromisoformat(started_at)
            f = datetime.fromisoformat(finished_at)
            return int((f - s).total_seconds() * 1000)
    except Exception:
        pass

    if isinstance(fallback, int):
        return fallback
    try:
        return int(fallback)
    except Exception:
        return 0


def parse_budget(envelope: Any) -> BudgetSpec:
    defaults = BudgetSpec(max_attempts=2, max_time_ms=20_000, max_tokens=4000)
    if not isinstance(envelope, dict):
        return defaults

    raw = envelope.get("budget")
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        raise ValueError("budget must be an object.")

    max_attempts_raw = raw.get("max_attempts", defaults.max_attempts)
    max_time_ms_raw = raw.get("max_time_ms", defaults.max_time_ms)
    max_tokens_raw = raw.get("max_tokens", defaults.max_tokens)

    try:
        max_attempts = int(max_attempts_raw)
    except Exception as e:
        raise ValueError("budget.max_attempts must be an integer.") from e
    try:
        max_time_ms = int(max_time_ms_raw)
    except Exception as e:
        raise ValueError("budget.max_time_ms must be an integer.") from e
    try:
        max_tokens = int(max_tokens_raw)
    except Exception as e:
        raise ValueError("budget.max_tokens must be an integer.") from e

    if max_attempts < 1 or max_attempts > 100:
        raise ValueError("budget.max_attempts out of bounds (1..100).")
    if max_time_ms < 1 or max_time_ms > 600_000:
        raise ValueError("budget.max_time_ms out of bounds (1..600000).")
    if max_tokens < 1 or max_tokens > 1_000_000:
        raise ValueError("budget.max_tokens out of bounds (1..1000000).")

    return BudgetSpec(max_attempts=max_attempts, max_time_ms=max_time_ms, max_tokens=max_tokens)


def budget_hit_from_policy_violation(code: str | None) -> str | None:
    if code == "BUDGET_TOKENS_EXCEEDED":
        return "TOKENS"
    if code == "BUDGET_TIME_EXCEEDED":
        return "TIME"
    if code == "BUDGET_ATTEMPTS_EXCEEDED":
        return "ATTEMPTS"
    return None


def is_budget_policy_violation(code: str | None) -> bool:
    return code in {"BUDGET_TOKENS_EXCEEDED", "BUDGET_TIME_EXCEEDED", "BUDGET_ATTEMPTS_EXCEEDED"}


def budget_spec_dict(spec: BudgetSpec) -> dict[str, int]:
    return {
        "max_attempts": int(spec.max_attempts),
        "max_time_ms": int(spec.max_time_ms),
        "max_tokens": int(spec.max_tokens),
    }


def budget_usage_dict(tracker: BudgetTracker | None, *, fallback_elapsed_ms: int = 0) -> dict[str, int]:
    if tracker is None:
        return {"attempts_used": 0, "elapsed_ms": int(fallback_elapsed_ms), "est_tokens_used": 0}
    tracker.update_elapsed()
    return {
        "attempts_used": int(tracker.usage.attempts_used),
        "elapsed_ms": int(tracker.usage.elapsed_ms),
        "est_tokens_used": int(tracker.usage.est_tokens_used),
    }


def parse_bool(text: str) -> bool:
    v = text.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean: true/false")

