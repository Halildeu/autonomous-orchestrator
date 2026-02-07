from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.jsonio import load_json


def utc_date_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def quota_limits_for_tenant(quota_policy: dict[str, Any], tenant_id: str) -> tuple[int, int]:
    default_cfg = quota_policy.get("default") if isinstance(quota_policy.get("default"), dict) else {}
    max_runs = int(default_cfg.get("max_runs_per_day", 2))
    max_tokens = int(default_cfg.get("max_est_tokens_per_day", 8000))

    overrides = quota_policy.get("overrides") if isinstance(quota_policy.get("overrides"), dict) else {}
    tenant_cfg = overrides.get(tenant_id) if isinstance(overrides.get(tenant_id), dict) else None
    if tenant_cfg:
        max_runs = int(tenant_cfg.get("max_runs_per_day", max_runs))
        max_tokens = int(tenant_cfg.get("max_est_tokens_per_day", max_tokens))

    if max_runs < 1:
        max_runs = 1
    if max_tokens < 1:
        max_tokens = 1
    return (max_runs, max_tokens)


def load_quota_store(store_path: Path) -> dict[str, Any]:
    if not store_path.exists():
        return {}
    try:
        raw = load_json(store_path)
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def save_quota_store(store_path: Path, store: dict[str, Any]) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def get_quota_usage(store: dict[str, Any], *, date_key: str, tenant_id: str) -> tuple[int, int]:
    day = store.get(date_key) if isinstance(store.get(date_key), dict) else {}
    tenant = day.get(tenant_id) if isinstance(day.get(tenant_id), dict) else {}
    try:
        runs_used = int(tenant.get("runs_used", 0))
    except Exception:
        runs_used = 0
    try:
        est_tokens_used = int(tenant.get("est_tokens_used", 0))
    except Exception:
        est_tokens_used = 0
    if runs_used < 0:
        runs_used = 0
    if est_tokens_used < 0:
        est_tokens_used = 0
    return (runs_used, est_tokens_used)


def set_quota_usage(store: dict[str, Any], *, date_key: str, tenant_id: str, runs_used: int, est_tokens_used: int) -> None:
    if date_key not in store or not isinstance(store.get(date_key), dict):
        store[date_key] = {}
    day = store[date_key]
    assert isinstance(day, dict)

    if not isinstance(tenant_id, str) or not tenant_id:
        tenant_id = "unknown"

    day[tenant_id] = {
        "runs_used": max(0, int(runs_used)),
        "est_tokens_used": max(0, int(est_tokens_used)),
    }


def quota_hit_from_policy_violation(code: str | None) -> str | None:
    if code == "QUOTA_RUNS_EXCEEDED":
        return "RUNS"
    if code == "QUOTA_TOKENS_EXCEEDED":
        return "TOKENS"
    return None


def is_quota_policy_violation(code: str | None) -> bool:
    return code in {"QUOTA_RUNS_EXCEEDED", "QUOTA_TOKENS_EXCEEDED"}

