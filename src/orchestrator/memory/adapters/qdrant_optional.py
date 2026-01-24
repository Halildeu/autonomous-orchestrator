from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, MemoryQueryResult, MemoryRecord


@dataclass(frozen=True)
class QdrantOptionalMemoryPort:
    workspace: Path
    adapter_id: str = "qdrant_optional"

    def is_available(self, *, network_mode: str) -> bool:
        if str(network_mode or "").strip().upper() != "ON":
            return False
        return importlib.util.find_spec("qdrant_client") is not None

    def why_unavailable(self, *, network_mode: str) -> str:
        if str(network_mode or "").strip().upper() != "ON":
            return "qdrant_optional unavailable: network_mode must be ON (offline-first; no auto-connect under OFF)."
        return "qdrant_optional unavailable: dependency qdrant_client is not installed (deps governance forbids adding it)."

    def upsert_text(
        self,
        *,
        namespace: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        raise MemoryAdapterUnavailable(self.why_unavailable(network_mode="OFF"))

    def query_text(self, *, namespace: str, query: str, top_k: int = 5) -> list[MemoryQueryResult]:
        raise MemoryAdapterUnavailable(self.why_unavailable(network_mode="OFF"))

    def delete(self, *, namespace: str, record_ids: list[str]) -> int:
        raise MemoryAdapterUnavailable(self.why_unavailable(network_mode="OFF"))
