from __future__ import annotations

import os
from pathlib import Path

from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, MemoryPort

from src.orchestrator.memory.adapters.local_first import LocalFirstMemoryPort
from src.orchestrator.memory.adapters.pgvector_optional import PgvectorOptionalMemoryPort
from src.orchestrator.memory.adapters.qdrant_optional import QdrantOptionalMemoryPort


def _network_mode() -> str:
    v = os.environ.get("ORCH_NETWORK_MODE", "OFF")
    return str(v).strip().upper() if isinstance(v, str) else "OFF"


def resolve_memory_port(*, workspace: Path) -> MemoryPort:
    raw = os.environ.get("ORCH_MEMORY_ADAPTER", "local_first")
    adapter = str(raw).strip().lower() if isinstance(raw, str) else "local_first"

    if adapter in {"local_first", "local-first", "local"}:
        return LocalFirstMemoryPort(workspace=workspace)

    net = _network_mode()
    if adapter in {"qdrant_optional", "qdrant"}:
        port = QdrantOptionalMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    if adapter in {"pgvector_optional", "pgvector"}:
        port = PgvectorOptionalMemoryPort(workspace=workspace)
        if not port.is_available(network_mode=net):
            raise MemoryAdapterUnavailable(port.why_unavailable(network_mode=net))
        return port

    raise MemoryAdapterUnavailable(f"Unknown memory adapter: {adapter}")
