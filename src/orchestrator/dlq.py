from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dlq_ts_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def sanitize_filename_component(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    s = "".join(keep).strip("_")
    if not s:
        return "unknown"
    return s[:80]


def dlq_min_envelope(envelope: Any, *, workflow_id: str | None = None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {
            "request_id": None,
            "tenant_id": None,
            "intent": None,
            "risk_score": None,
            "dry_run": None,
            "side_effect_policy": None,
            "idempotency_key_hash": None,
        }

    request_id = envelope.get("request_id") if isinstance(envelope.get("request_id"), str) else None
    tenant_id = envelope.get("tenant_id") if isinstance(envelope.get("tenant_id"), str) else None
    intent = envelope.get("intent") if isinstance(envelope.get("intent"), str) else None
    risk_score_raw = envelope.get("risk_score")
    try:
        risk_score = float(risk_score_raw)
    except (TypeError, ValueError):
        risk_score = None

    dry_run_value = envelope.get("dry_run")
    dry_run = dry_run_value if isinstance(dry_run_value, bool) else None

    side_effect_policy = envelope.get("side_effect_policy") if isinstance(envelope.get("side_effect_policy"), str) else None

    idempotency_key_hash = None
    idempotency_key = envelope.get("idempotency_key")
    if tenant_id and isinstance(idempotency_key, str) and idempotency_key:
        if workflow_id:
            key_plain = f"{tenant_id}:{idempotency_key}:{workflow_id}"
        else:
            key_plain = f"{tenant_id}:{idempotency_key}"
        idempotency_key_hash = sha256(key_plain.encode("utf-8")).hexdigest()

    return {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "intent": intent,
        "risk_score": risk_score,
        "dry_run": dry_run,
        "side_effect_policy": side_effect_policy,
        "idempotency_key_hash": idempotency_key_hash,
    }


def write_dlq_record(
    *,
    workspace: Path,
    stage: str,
    error_code: str,
    message: str,
    envelope: Any,
    workflow_id: str | None = None,
) -> Path:
    dlq_dir = workspace / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)

    minimal = dlq_min_envelope(envelope, workflow_id=workflow_id)
    rid = minimal.get("request_id") or "unknown"
    fname = f"{dlq_ts_filename()}_{sanitize_filename_component(str(rid))}.json"
    path = dlq_dir / fname

    record = {
        "stage": stage,
        "error_code": error_code,
        "message": message,
        "envelope": minimal,
        "ts": iso_utc_now(),
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path

