from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.orchestrator.dlq import iso_utc_now
from src.tools.gateway import PolicyViolation
from src.utils.jsonio import load_json


def load_governor(workspace: Path) -> dict[str, Any]:
    default = {
        "version": "v1",
        "global_mode": "normal",
        "quarantine": {"intents": [], "workflows": []},
        "concurrency": {"max_parallel_runs": 1},
        "_path": str(workspace / "governor" / "health_brain.v1.json"),
        "_loaded": False,
    }

    path = workspace / "governor" / "health_brain.v1.json"
    if not path.exists():
        return default

    try:
        raw = load_json(path)
    except Exception:
        return default

    if not isinstance(raw, dict):
        return default

    mode = raw.get("global_mode")
    global_mode = mode if isinstance(mode, str) and mode in {"normal", "report_only"} else "normal"

    quarantine_raw = raw.get("quarantine")
    quarantine = quarantine_raw if isinstance(quarantine_raw, dict) else {}
    intents_raw = quarantine.get("intents", [])
    workflows_raw = quarantine.get("workflows", [])
    intents = [x for x in intents_raw if isinstance(x, str) and x] if isinstance(intents_raw, list) else []
    workflows = [x for x in workflows_raw if isinstance(x, str) and x] if isinstance(workflows_raw, list) else []

    conc_raw = raw.get("concurrency")
    conc = conc_raw if isinstance(conc_raw, dict) else {}
    max_parallel_raw = conc.get("max_parallel_runs", 1)
    try:
        max_parallel = int(max_parallel_raw)
    except Exception:
        max_parallel = 1
    if max_parallel < 1:
        max_parallel = 1

    return {
        "version": "v1",
        "global_mode": global_mode,
        "quarantine": {"intents": intents, "workflows": workflows},
        "concurrency": {"max_parallel_runs": max_parallel},
        "_path": str(path),
        "_loaded": True,
    }


def acquire_governor_lock(workspace: Path, *, max_parallel_runs: int) -> tuple[Path, bool]:
    lock_path = workspace / ".cache" / "governor_lock"
    if int(max_parallel_runs) > 1:
        return (lock_path, False)

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as e:
        raise PolicyViolation("CONCURRENCY_LIMIT", "Concurrency limit reached (governor lock exists).") from e

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{iso_utc_now()} lock\n")
    except Exception:
        try:
            lock_path.unlink()
        except Exception:
            pass
        raise

    return (lock_path, True)


def release_governor_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def load_quota_policy(workspace: Path) -> dict[str, Any]:
    default = {
        "version": "v1",
        "default": {"max_runs_per_day": 2, "max_est_tokens_per_day": 8000},
        "overrides": {},
        "_path": str(workspace / "policies" / "policy_quota.v1.json"),
        "_loaded": False,
    }

    path = workspace / "policies" / "policy_quota.v1.json"
    if not path.exists():
        return default

    try:
        raw = load_json(path)
    except Exception:
        return default

    if not isinstance(raw, dict):
        return default

    def_raw = raw.get("default")
    overrides_raw = raw.get("overrides")

    def_cfg = def_raw if isinstance(def_raw, dict) else {}
    ov_cfg = overrides_raw if isinstance(overrides_raw, dict) else {}

    def _coerce_int(v: Any, fallback: int) -> int:
        try:
            n = int(v)
        except Exception:
            return fallback
        if n < 1:
            return fallback
        return n

    default_runs = _coerce_int(def_cfg.get("max_runs_per_day"), default["default"]["max_runs_per_day"])
    default_tokens = _coerce_int(def_cfg.get("max_est_tokens_per_day"), default["default"]["max_est_tokens_per_day"])

    overrides: dict[str, dict[str, int]] = {}
    for tenant, cfg in ov_cfg.items():
        if not isinstance(tenant, str) or not tenant:
            continue
        if not isinstance(cfg, dict):
            continue
        overrides[tenant] = {
            "max_runs_per_day": _coerce_int(cfg.get("max_runs_per_day"), default_runs),
            "max_est_tokens_per_day": _coerce_int(cfg.get("max_est_tokens_per_day"), default_tokens),
        }

    return {
        "version": "v1",
        "default": {"max_runs_per_day": default_runs, "max_est_tokens_per_day": default_tokens},
        "overrides": overrides,
        "_path": str(path),
        "_loaded": True,
    }


def load_autonomy_policy(workspace: Path) -> dict[str, Any]:
    default = {
        "version": "v1",
        "defaults": {"mode": "human_review", "success_threshold": 0.8, "min_samples": 5},
        "intents": {},
        "_path": str(workspace / "policies" / "policy_autonomy.v1.json"),
        "_loaded": False,
    }

    path = workspace / "policies" / "policy_autonomy.v1.json"
    if not path.exists():
        return default

    try:
        raw = load_json(path)
    except Exception:
        return default

    if not isinstance(raw, dict):
        return default

    allowed_modes = {"manual_only", "human_review", "full_auto"}

    def _coerce_mode(v: Any, fallback: str) -> str:
        return v if isinstance(v, str) and v in allowed_modes else fallback

    def _coerce_float_0_1(v: Any, fallback: float) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return fallback
        if f < 0 or f > 1:
            return fallback
        return f

    def _coerce_int_min1(v: Any, fallback: int) -> int:
        try:
            n = int(v)
        except Exception:
            return fallback
        if n < 1:
            return fallback
        return n

    defaults_raw = raw.get("defaults")
    defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    default_mode = _coerce_mode(defaults.get("mode"), default["defaults"]["mode"])
    default_threshold = _coerce_float_0_1(defaults.get("success_threshold"), float(default["defaults"]["success_threshold"]))
    default_min_samples = _coerce_int_min1(defaults.get("min_samples"), int(default["defaults"]["min_samples"]))

    intents_raw = raw.get("intents")
    intents_cfg = intents_raw if isinstance(intents_raw, dict) else {}

    intents: dict[str, dict[str, Any]] = {}
    for intent, cfg_raw in intents_cfg.items():
        if not isinstance(intent, str) or not intent:
            continue
        cfg = cfg_raw if isinstance(cfg_raw, dict) else {}
        intents[intent] = {
            "mode": _coerce_mode(cfg.get("mode"), default_mode),
            "success_threshold": _coerce_float_0_1(cfg.get("success_threshold"), default_threshold),
            "min_samples": _coerce_int_min1(cfg.get("min_samples"), default_min_samples),
        }

    return {
        "version": "v1",
        "defaults": {"mode": default_mode, "success_threshold": default_threshold, "min_samples": default_min_samples},
        "intents": intents,
        "_path": str(path),
        "_loaded": True,
    }

