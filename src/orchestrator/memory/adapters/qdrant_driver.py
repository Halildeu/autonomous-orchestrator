from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.orchestrator.memory.adapters.local_first import _embed, _namespace_key
from src.orchestrator.memory.memory_port import MemoryQueryResult, MemoryRecord, deterministic_record_id


def _env_flag(name: str) -> bool:
    raw = os.environ.get(name, "0")
    v = str(raw).strip().lower() if isinstance(raw, str) else "0"
    return v in {"1", "true", "yes", "on"}


def _load_runtime_config(workspace: Path) -> dict[str, Any]:
    path = workspace / ".cache" / "runtime" / "memory_backends.local.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _is_localhost_url(url: str) -> bool:
    try:
        p = urlparse(str(url or ""))
    except Exception:
        return False
    host = str(p.hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _qdrant_url(workspace: Path) -> str:
    override = os.environ.get("ORCH_QDRANT_URL")
    if isinstance(override, str) and override.strip():
        return override.strip()
    cfg = _load_runtime_config(workspace).get("qdrant")
    if isinstance(cfg, dict) and isinstance(cfg.get("url"), str) and cfg["url"].strip():
        return str(cfg["url"]).strip()
    return "http://localhost:6333"


def _vector_size(workspace: Path) -> int:
    cfg = _load_runtime_config(workspace).get("qdrant")
    collections = cfg.get("collections") if isinstance(cfg, dict) else None
    raw = collections.get("vector_size") if isinstance(collections, dict) else None
    if isinstance(raw, int) and raw > 0:
        return raw
    return 64


def _collection_base(workspace: Path) -> str:
    cfg = _load_runtime_config(workspace).get("qdrant")
    collections = cfg.get("collections") if isinstance(cfg, dict) else None
    raw = collections.get("smoke_collection") if isinstance(collections, dict) else None
    name = str(raw).strip() if isinstance(raw, str) else ""
    return name or "codex_smoke"


def _collection_name(workspace: Path, namespace: str) -> str:
    suffix = _namespace_key(namespace).replace(".", "_").replace("-", "_")
    base = _collection_base(workspace)
    return f"{base}_{suffix}"


@dataclass(frozen=True)
class QdrantDriverMemoryPort:
    workspace: Path
    adapter_id: str = "qdrant_driver"

    def is_available(self, *, network_mode: str) -> bool:
        if not _env_flag("VECTOR_BACKEND_ENABLE"):
            return False
        if str(network_mode or "").strip().upper() != "ON":
            return False
        if importlib.util.find_spec("qdrant_client") is None:
            return False
        return _is_localhost_url(_qdrant_url(self.workspace))

    def why_unavailable(self, *, network_mode: str) -> str:
        if not _env_flag("VECTOR_BACKEND_ENABLE"):
            return "qdrant_driver unavailable: VECTOR_BACKEND_ENABLE must be 1 (explicit opt-in)."
        if str(network_mode or "").strip().upper() != "ON":
            return "qdrant_driver unavailable: ORCH_NETWORK_MODE must be ON (offline-first; no auto-connect under OFF)."
        url = _qdrant_url(self.workspace)
        if not _is_localhost_url(url):
            return f"qdrant_driver unavailable: endpoint must be localhost-only; got url={url!r}."
        if importlib.util.find_spec("qdrant_client") is None:
            return "qdrant_driver unavailable: dependency qdrant-client is not installed."
        return "qdrant_driver unavailable: UNKNOWN"

    def _client(self):
        if importlib.util.find_spec("qdrant_client") is None:
            raise RuntimeError("qdrant-client is not installed")
        from qdrant_client import QdrantClient  # type: ignore

        return QdrantClient(url=_qdrant_url(self.workspace), prefer_grpc=False)

    def _models(self):
        try:
            from qdrant_client import models  # type: ignore

            return models
        except Exception:  # pragma: no cover
            from qdrant_client.http import models  # type: ignore

            return models

    def _ensure_collection(self, *, namespace: str) -> str:
        models = self._models()
        client = self._client()

        collection_name = _collection_name(self.workspace, namespace)
        try:
            exists = bool(client.collection_exists(collection_name))  # type: ignore[attr-defined]
        except Exception:
            try:
                client.get_collection(collection_name=collection_name)  # type: ignore[attr-defined]
                exists = True
            except Exception:
                exists = False

        if not exists:
            dim = _vector_size(self.workspace)
            client.create_collection(  # type: ignore[attr-defined]
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )
        return collection_name

    def upsert_text(
        self,
        *,
        namespace: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        ns = str(namespace or "").strip() or "default"
        meta = metadata if isinstance(metadata, dict) else {}
        rid = str(record_id or "").strip() or deterministic_record_id(namespace=ns, text=text, metadata=meta)

        dim = _vector_size(self.workspace)
        vec = _embed(text, dim=dim)
        payload = {"namespace": ns, "text": str(text or ""), "metadata": meta}

        models = self._models()
        client = self._client()
        collection = self._ensure_collection(namespace=ns)
        point = models.PointStruct(id=rid, vector=vec, payload=payload)
        client.upsert(collection_name=collection, points=[point])  # type: ignore[attr-defined]
        return MemoryRecord(record_id=rid, text=payload["text"], vector=[float(x) for x in vec], metadata=dict(meta))

    def query_text(self, *, namespace: str, query: str, top_k: int = 5) -> list[MemoryQueryResult]:
        ns = str(namespace or "").strip() or "default"
        dim = _vector_size(self.workspace)
        qv = _embed(query, dim=dim)

        client = self._client()
        collection = self._ensure_collection(namespace=ns)
        hits = client.search(  # type: ignore[attr-defined]
            collection_name=collection,
            query_vector=qv,
            limit=int(top_k) if isinstance(top_k, int) else 5,
            with_payload=True,
            with_vectors=True,
        )

        results: list[MemoryQueryResult] = []
        for hit in hits or []:
            payload = getattr(hit, "payload", None)
            raw = payload if isinstance(payload, dict) else {}
            text = str(raw.get("text") or "")
            meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}

            hv = getattr(hit, "vector", None)
            vec = hv if isinstance(hv, list) and all(isinstance(x, (int, float)) for x in hv) else _embed(text, dim=dim)
            score = float(getattr(hit, "score", 0.0) or 0.0)
            rid = str(getattr(hit, "id", "") or "")
            results.append(
                MemoryQueryResult(
                    record=MemoryRecord(record_id=rid, text=text, vector=[float(x) for x in vec], metadata=dict(meta)),
                    score=score,
                )
            )
        return results

    def delete(self, *, namespace: str, record_ids: list[str]) -> int:
        ns = str(namespace or "").strip() or "default"
        ids = [str(rid or "").strip() for rid in (record_ids or []) if str(rid or "").strip()]
        if not ids:
            return 0

        models = self._models()
        client = self._client()
        collection = self._ensure_collection(namespace=ns)
        client.delete(collection_name=collection, points_selector=models.PointIdsList(points=ids))  # type: ignore[attr-defined]
        return len(ids)
