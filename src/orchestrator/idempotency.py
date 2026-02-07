from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from src.utils.jsonio import load_json


def timestamp_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{secrets.token_hex(3)}"


def deterministic_run_id(
    *,
    tenant_id: str,
    idempotency_key: str,
    workflow_id: str,
    workflow_fingerprint: str,
) -> str:
    raw = f"{tenant_id}:{idempotency_key}:{workflow_id}:{workflow_fingerprint}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_idempotency_store(store_path: Path) -> tuple[dict[str, str], bool]:
    if not store_path.exists():
        return ({}, False)
    try:
        raw = load_json(store_path)
    except Exception:
        return ({}, False)

    if isinstance(raw, dict) and isinstance(raw.get("mappings"), dict):
        src = raw["mappings"]
    elif isinstance(raw, dict):
        src = {k: v for k, v in raw.items() if k != "version"}
    else:
        return ({}, False)

    loaded = {str(k): str(v) for k, v in src.items()}

    migrated = False
    migrated_map: dict[str, str] = {}
    for k, v in loaded.items():
        if ":" in k:
            migrated = True
            migrated_map[sha256(k.encode("utf-8")).hexdigest()[:24]] = v
        else:
            migrated_map[k] = v

    return (migrated_map, migrated)


def save_idempotency_store(store_path: Path, mappings: dict[str, str]) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "v1", "mappings": dict(sorted(mappings.items()))}
    store_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_result_state(summary_path: Path) -> str | None:
    if not summary_path.exists():
        return None
    try:
        summary = load_json(summary_path)
    except Exception:
        return None
    if not isinstance(summary, dict):
        return None
    rs = summary.get("result_state")
    if isinstance(rs, str) and rs:
        return rs
    st = summary.get("status")
    if isinstance(st, str) and st:
        return st
    return None

