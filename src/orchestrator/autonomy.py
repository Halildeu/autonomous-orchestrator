from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.utils.jsonio import load_json


def autonomy_cfg_for_intent(policy: dict[str, Any], intent: str) -> dict[str, Any]:
    defaults = policy.get("defaults") if isinstance(policy.get("defaults"), dict) else {}
    intents = policy.get("intents") if isinstance(policy.get("intents"), dict) else {}
    cfg = intents.get(intent) if isinstance(intents.get(intent), dict) else {}

    mode = cfg.get("mode", defaults.get("mode", "human_review"))
    success_threshold = cfg.get("success_threshold", defaults.get("success_threshold", 0.8))
    min_samples = cfg.get("min_samples", defaults.get("min_samples", 5))

    return {
        "mode": mode,
        "success_threshold": float(success_threshold),
        "min_samples": int(min_samples),
    }


def load_autonomy_store(store_path: Path) -> dict[str, Any]:
    if not store_path.exists():
        return {}
    try:
        raw = load_json(store_path)
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def save_autonomy_store(store_path: Path, store: dict[str, Any]) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def autonomy_record_for_intent(store: dict[str, Any], intent: str, *, initial_mode: str) -> dict[str, Any]:
    raw = store.get(intent) if isinstance(store.get(intent), dict) else {}
    samples_raw = raw.get("samples", 0) if isinstance(raw, dict) else 0
    successes_raw = raw.get("successes", 0) if isinstance(raw, dict) else 0
    mode_raw = raw.get("mode", initial_mode) if isinstance(raw, dict) else initial_mode
    recent_raw = raw.get("recent", []) if isinstance(raw, dict) else []

    try:
        samples = int(samples_raw)
    except Exception:
        samples = 0
    try:
        successes = int(successes_raw)
    except Exception:
        successes = 0
    if samples < 0:
        samples = 0
    if successes < 0:
        successes = 0

    allowed_modes = {"manual_only", "human_review", "full_auto"}
    mode = mode_raw if isinstance(mode_raw, str) and mode_raw in allowed_modes else initial_mode

    recent: list[str] = []
    if isinstance(recent_raw, list):
        for v in recent_raw[-3:]:
            if isinstance(v, str) and v in {"SUCCESS", "FAIL"}:
                recent.append(v)

    return {"samples": samples, "successes": successes, "mode": mode, "recent": recent}


def update_autonomy_record(
    record: dict[str, Any],
    *,
    outcome: str,
    cfg_mode: str,
    success_threshold: float,
    min_samples: int,
) -> dict[str, Any]:
    samples = int(record.get("samples", 0)) if isinstance(record.get("samples"), int) else int(record.get("samples", 0) or 0)
    successes = int(record.get("successes", 0)) if isinstance(record.get("successes"), int) else int(record.get("successes", 0) or 0)
    mode = record.get("mode", cfg_mode) if isinstance(record.get("mode"), str) else cfg_mode

    recent_raw = record.get("recent", [])
    recent: list[str] = []
    if isinstance(recent_raw, list):
        for v in recent_raw[-3:]:
            if isinstance(v, str) and v in {"SUCCESS", "FAIL"}:
                recent.append(v)

    if outcome not in {"SUCCESS", "FAIL"}:
        return {"samples": samples, "successes": successes, "mode": mode, "recent": recent}

    samples += 1
    if outcome == "SUCCESS":
        successes += 1
    recent.append(outcome)
    recent = recent[-3:]

    if cfg_mode != "manual_only" and mode != "manual_only":
        if samples >= int(min_samples) and samples > 0:
            ratio = float(successes) / float(samples)
            if ratio >= float(success_threshold):
                mode = "full_auto"

    if mode != "manual_only" and len(recent) == 3:
        fails = sum(1 for v in recent if v == "FAIL")
        if fails >= 2:
            mode = "human_review"

    return {"samples": samples, "successes": successes, "mode": mode, "recent": recent}


def autonomy_gate_triggered(*, autonomy_mode_used: str, dry_run: bool, side_effect_policy: str) -> str | None:
    if autonomy_mode_used == "manual_only":
        return "AUTONOMY_MANUAL_ONLY"
    if autonomy_mode_used == "human_review":
        if (not dry_run) and side_effect_policy != "none":
            return "AUTONOMY_HUMAN_REVIEW"
    return None

