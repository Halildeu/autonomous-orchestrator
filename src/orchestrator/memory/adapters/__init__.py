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

def _backend_enable() -> bool:
    raw = os.environ.get("VECTOR_BACKEND_ENABLE", "0")
    v = str(raw).strip().lower() if isinstance(raw, str) else "0"
    return v in {"1", "true", "yes", "on"}


def resolve_memory_port(*, workspace: Path) -> MemoryPort:
    raw = os.environ.get("ORCH_MEMORY_ADAPTER", "local_first")
    adapter = str(raw).strip().lower() if isinstance(raw, str) else "local_first"

    if adapter in {"local_first", "local-first", "local"}:
        return LocalFirstMemoryPort(workspace=workspace)

    net = _network_mode()
    if adapter in {"qdrant_driver", "qdrant-driver"}:
        if not _backend_enable() or net != "ON":
            return LocalFirstMemoryPort(workspace=workspace)
        port = QdrantDriverMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            return LocalFirstMemoryPort(workspace=workspace)
        return port

    if adapter in {"qdrant_optional", "qdrant"}:
        port = QdrantOptionalMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    if adapter in {"pgvector_driver", "pgvector-driver"}:
        if not _backend_enable() or net != "ON":
            return LocalFirstMemoryPort(workspace=workspace)
        port = PgvectorDriverMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            return LocalFirstMemoryPort(workspace=workspace)
        return port

    if adapter in {"pgvector_optional", "pgvector"}:
        port = PgvectorOptionalMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    raise MemoryAdapterUnavailable(f"Unknown memory adapter: {adapter}")
