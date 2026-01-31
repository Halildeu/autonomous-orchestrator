from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.orchestrator.memory.adapters import resolve_memory_port
from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, deterministic_record_id
from src.prj_kernel_api.dotenv_loader import resolve_env_value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(workspace_root))
    except Exception:
        return str(path)


def _env_value(*, workspace_root: Path, key: str, default: str) -> str:
    present, value = resolve_env_value(key, str(workspace_root), env_mode="dotenv")
    if present and isinstance(value, str) and value.strip():
        return value
    return str(os.environ.get(key, default))


@contextmanager
def _with_env(overrides: dict[str, str]):
    before = {k: os.environ.get(k) for k in overrides}
    for k, v in overrides.items():
        if v is None:
            continue
        os.environ[str(k)] = str(v)
    try:
        yield
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_memory_healthcheck(*, workspace_root: Path | str) -> dict[str, Any]:
    workspace_root = Path(workspace_root)
    out_json = workspace_root / ".cache" / "reports" / "memory_health.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "memory_health.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    requested_adapter = _env_value(workspace_root=workspace_root, key="ORCH_MEMORY_ADAPTER", default="local_first")
    fallback_adapter = _env_value(workspace_root=workspace_root, key="ORCH_MEMORY_FALLBACK", default="")
    network_mode = _env_value(workspace_root=workspace_root, key="ORCH_NETWORK_MODE", default="OFF")
    vector_enable = _env_value(workspace_root=workspace_root, key="VECTOR_BACKEND_ENABLE", default="0")
    pgvector_password = _env_value(workspace_root=workspace_root, key="PGVECTOR_POSTGRES_PASSWORD", default="")
    pgvector_dsn = _env_value(workspace_root=workspace_root, key="ORCH_PGVECTOR_DSN", default="")
    qdrant_url = _env_value(workspace_root=workspace_root, key="ORCH_QDRANT_URL", default="")

    status = "OK"
    resolved_adapter = None
    availability_ok = False
    reason = None
    notes: list[str] = []

    overrides = {
        "ORCH_MEMORY_ADAPTER": requested_adapter,
        "ORCH_MEMORY_FALLBACK": fallback_adapter,
        "ORCH_NETWORK_MODE": network_mode,
        "VECTOR_BACKEND_ENABLE": vector_enable,
        "PGVECTOR_POSTGRES_PASSWORD": pgvector_password,
        "ORCH_PGVECTOR_DSN": pgvector_dsn,
        "ORCH_QDRANT_URL": qdrant_url,
    }
    try:
        with _with_env(overrides):
            port = resolve_memory_port(workspace=workspace_root)
        resolved_adapter = getattr(port, "adapter_id", None)
        availability_ok = True
        notes.append("resolve_memory_port=ok")
    except MemoryAdapterUnavailable as exc:
        status = "WARN"
        availability_ok = False
        reason = str(exc)
        notes.append("resolve_memory_port=unavailable")
    except Exception as exc:
        status = "FAIL"
        availability_ok = False
        reason = f"unexpected_error:{type(exc).__name__}"
        notes.append("resolve_memory_port=error")

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "requested_adapter": requested_adapter,
        "fallback_adapter": fallback_adapter,
        "resolved_adapter": resolved_adapter,
        "network_mode": network_mode,
        "availability": {
            "ok": availability_ok,
            "reason": reason,
        },
        "status": status,
        "notes": notes,
    }
    out_json.write_text(_dump_json(payload), encoding="utf-8")
    md_lines = [
        "# Memory Health",
        f"- generated_at: {payload['generated_at']}",
        f"- status: {payload['status']}",
        f"- requested_adapter: {requested_adapter}",
        f"- fallback_adapter: {fallback_adapter or 'none'}",
        f"- resolved_adapter: {resolved_adapter or 'none'}",
        f"- network_mode: {network_mode}",
        f"- availability_ok: {availability_ok}",
    ]
    if reason:
        md_lines.append(f"- reason: {reason}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    payload["report_path"] = _rel_path(workspace_root, out_json)
    payload["report_md_path"] = _rel_path(workspace_root, out_md)
    return payload


def run_memory_smoke(*, workspace_root: Path | str) -> dict[str, Any]:
    workspace_root = Path(workspace_root)
    out_json = workspace_root / ".cache" / "reports" / "memory_smoke.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "memory_smoke.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    requested_adapter = _env_value(workspace_root=workspace_root, key="ORCH_MEMORY_ADAPTER", default="local_first")
    fallback_adapter = _env_value(workspace_root=workspace_root, key="ORCH_MEMORY_FALLBACK", default="")
    network_mode = _env_value(workspace_root=workspace_root, key="ORCH_NETWORK_MODE", default="OFF")
    vector_enable = _env_value(workspace_root=workspace_root, key="VECTOR_BACKEND_ENABLE", default="0")
    pgvector_password = _env_value(workspace_root=workspace_root, key="PGVECTOR_POSTGRES_PASSWORD", default="")
    pgvector_dsn = _env_value(workspace_root=workspace_root, key="ORCH_PGVECTOR_DSN", default="")
    qdrant_url = _env_value(workspace_root=workspace_root, key="ORCH_QDRANT_URL", default="")

    status = "OK"
    resolved_adapter = None
    reason = None
    notes: list[str] = []
    smoke_details: dict[str, Any] = {}

    overrides = {
        "ORCH_MEMORY_ADAPTER": requested_adapter,
        "ORCH_MEMORY_FALLBACK": fallback_adapter,
        "ORCH_NETWORK_MODE": network_mode,
        "VECTOR_BACKEND_ENABLE": vector_enable,
        "PGVECTOR_POSTGRES_PASSWORD": pgvector_password,
        "ORCH_PGVECTOR_DSN": pgvector_dsn,
        "ORCH_QDRANT_URL": qdrant_url,
    }
    try:
        with _with_env(overrides):
            port = resolve_memory_port(workspace=workspace_root)
            resolved_adapter = getattr(port, "adapter_id", None)
            notes.append("resolve_memory_port=ok")

            namespace = "memory_smoke"
            text = f"memory_smoke_ping::{int(time.time())}"
            record_id = deterministic_record_id(namespace=namespace, text=text, metadata={"kind": "smoke"})
            record = port.upsert_text(namespace=namespace, text=text, metadata={"kind": "smoke"}, record_id=record_id)
            hits = port.query_text(namespace=namespace, query="memory_smoke", top_k=3)
            deleted = port.delete(namespace=namespace, record_ids=[record.record_id])
            smoke_details = {
                "record_id": record.record_id,
                "query_hits": len(hits),
                "deleted": deleted,
            }
            notes.append("smoke_ok")
    except Exception as exc:
        status = "FAIL"
        reason = f"smoke_error:{type(exc).__name__}"
        notes.append("smoke_fail")

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "requested_adapter": requested_adapter,
        "fallback_adapter": fallback_adapter,
        "resolved_adapter": resolved_adapter,
        "network_mode": network_mode,
        "status": status,
        "reason": reason,
        "notes": notes,
        "smoke": smoke_details,
    }
    out_json.write_text(_dump_json(payload), encoding="utf-8")
    md_lines = [
        "# Memory Smoke",
        f"- generated_at: {payload['generated_at']}",
        f"- status: {payload['status']}",
        f"- requested_adapter: {requested_adapter}",
        f"- fallback_adapter: {fallback_adapter or 'none'}",
        f"- resolved_adapter: {resolved_adapter or 'none'}",
        f"- network_mode: {network_mode}",
    ]
    if reason:
        md_lines.append(f"- reason: {reason}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    payload["report_path"] = _rel_path(workspace_root, out_json)
    payload["report_md_path"] = _rel_path(workspace_root, out_md)
    return payload
