from __future__ import annotations

import os
from pathlib import Path

from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, MemoryPort

from src.orchestrator.memory.adapters.local_first import LocalFirstMemoryPort
from src.orchestrator.memory.adapters.pgvector_driver import PgvectorDriverMemoryPort
from src.orchestrator.memory.adapters.pgvector_optional import PgvectorOptionalMemoryPort
from src.orchestrator.memory.adapters.qdrant_driver import QdrantDriverMemoryPort
from src.orchestrator.memory.adapters.qdrant_optional import QdrantOptionalMemoryPort


def _network_mode() -> str:
    v = os.environ.get("ORCH_NETWORK_MODE", "OFF")
    return str(v).strip().upper() if isinstance(v, str) else "OFF"


def _normalize_adapter(raw: str | None) -> str:
    return str(raw).strip().lower() if isinstance(raw, str) and raw.strip() else ""


def _resolve_adapter(*, adapter: str, workspace: Path, net: str) -> MemoryPort:
    if adapter in {"local_first", "local-first", "local"}:
        return LocalFirstMemoryPort(workspace=workspace)

    if adapter in {"qdrant_driver", "qdrant-driver"}:
        port = QdrantDriverMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    if adapter in {"qdrant_optional", "qdrant"}:
        port = QdrantOptionalMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    if adapter in {"pgvector_driver", "pgvector-driver"}:
        port = PgvectorDriverMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    if adapter in {"pgvector_optional", "pgvector"}:
        port = PgvectorOptionalMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    raise MemoryAdapterUnavailable(f"Unknown memory adapter: {adapter}")


def resolve_memory_port(*, workspace: Path) -> MemoryPort:
    adapter = _normalize_adapter(os.environ.get("ORCH_MEMORY_ADAPTER", "local_first")) or "local_first"
    fallback = _normalize_adapter(os.environ.get("ORCH_MEMORY_FALLBACK", "")) or ""
    net = _network_mode()
    try:
        return _resolve_adapter(adapter=adapter, workspace=workspace, net=net)
    except MemoryAdapterUnavailable as primary_err:
        if fallback:
            try:
                return _resolve_adapter(adapter=fallback, workspace=workspace, net=net)
            except MemoryAdapterUnavailable as fallback_err:
                raise MemoryAdapterUnavailable(
                    f"{primary_err}; fallback={fallback} failed: {fallback_err}"
                ) from fallback_err
        raise
