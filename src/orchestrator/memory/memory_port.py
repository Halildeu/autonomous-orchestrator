from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol


class MemoryPortError(RuntimeError):
    pass


class MemoryAdapterUnavailable(MemoryPortError):
    pass


class InvalidMemoryNamespace(MemoryPortError):
    pass


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), indent=None)


def deterministic_record_id(*, namespace: str, text: str, metadata: dict[str, Any] | None) -> str:
    payload = {
        "namespace": str(namespace or ""),
        "text": str(text or ""),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MemoryQueryResult:
    record: MemoryRecord
    score: float


class MemoryPort(Protocol):
    adapter_id: str

    def upsert_text(
        self,
        *,
        namespace: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord: ...

    def query_text(
        self,
        *,
        namespace: str,
        query: str,
        top_k: int = 5,
    ) -> list[MemoryQueryResult]: ...

    def delete(
        self,
        *,
        namespace: str,
        record_ids: list[str],
    ) -> int: ...
