from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PgvectorOptionalMemoryPort:
    workspace: Path
    adapter_id: str = "pgvector_optional"

    def is_available(self, *, network_mode: str) -> bool:
        if str(network_mode or "").strip().upper() != "ON":
            return False
        # pgvector requires a postgres driver; keep optional and dependency-free by default.
        return importlib.util.find_spec("psycopg") is not None or importlib.util.find_spec("psycopg2") is not None

    def why_unavailable(self, *, network_mode: str) -> str:
        if str(network_mode or "").strip().upper() != "ON":
            return "pgvector_optional unavailable: network_mode must be ON (offline-first; no auto-connect under OFF)."
        return "pgvector_optional unavailable: postgres driver is not installed (deps governance forbids adding it)."

    def upsert_text(self, *, namespace: str, text: str, metadata: dict[str, Any] | None = None, record_id: str | None = None):
        raise RuntimeError(self.why_unavailable(network_mode="OFF"))

    def query_text(self, *, namespace: str, query: str, top_k: int = 5):
        raise RuntimeError(self.why_unavailable(network_mode="OFF"))

    def delete(self, *, namespace: str, record_ids: list[str]):
        raise RuntimeError(self.why_unavailable(network_mode="OFF"))
