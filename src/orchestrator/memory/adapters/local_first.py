from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.orchestrator.memory.memory_port import MemoryQueryResult, MemoryRecord, deterministic_record_id


SAFE_NAMESPACE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _namespace_key(namespace: str) -> str:
    ns = str(namespace or "").strip()
    if SAFE_NAMESPACE.match(ns):
        return ns
    return sha256(ns.encode("utf-8")).hexdigest()[:32]


def _tokenize(text: str) -> list[str]:
    raw = str(text or "").lower()
    return [t for t in re.split(r"\W+", raw) if t]


def _embed(text: str, *, dim: int = 64) -> list[float]:
    vec = [0.0] * dim
    for token in _tokenize(text):
        h = sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(h[:2], "big") % dim
        sign = 1.0 if (h[2] % 2 == 0) else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return vec
    return [round(v / norm, 6) for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class LocalFirstMemoryPort:
    workspace: Path
    adapter_id: str = "local_first"

    def _store_path(self, namespace: str) -> Path:
        key = _namespace_key(namespace)
        return self.workspace / ".cache" / "memoryport" / f"{key}.v1.json"

    def _load_records(self, namespace: str) -> dict[str, dict[str, Any]]:
        path = self._store_path(namespace)
        if not path.exists():
            return {}
        obj = _load_json(path)
        records = obj.get("records") if isinstance(obj, dict) else None
        return records if isinstance(records, dict) else {}

    def _save_records(self, namespace: str, records: dict[str, dict[str, Any]]) -> None:
        path = self._store_path(namespace)
        payload = {
            "version": "v1",
            "adapter_id": self.adapter_id,
            "namespace": str(namespace or ""),
            "records": records,
        }
        _save_json(path, payload)

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

        vec = _embed(text)
        record = {"record_id": rid, "text": str(text or ""), "vector": vec, "metadata": meta}

        records = self._load_records(ns)
        records[rid] = record
        self._save_records(ns, records)
        return MemoryRecord(record_id=rid, text=record["text"], vector=vec, metadata=dict(meta))

    def query_text(self, *, namespace: str, query: str, top_k: int = 5) -> list[MemoryQueryResult]:
        ns = str(namespace or "").strip() or "default"
        qv = _embed(query)
        records = self._load_records(ns)

        scored: list[MemoryQueryResult] = []
        for rid, raw in records.items():
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or "")
            vec = raw.get("vector")
            meta = raw.get("metadata")
            if not isinstance(vec, list) or not all(isinstance(x, (int, float)) for x in vec):
                vec = _embed(text)
            if not isinstance(meta, dict):
                meta = {}
            v = [float(x) for x in vec]
            score = _dot(qv, v)
            scored.append(
                MemoryQueryResult(
                    record=MemoryRecord(record_id=str(rid), text=text, vector=v, metadata=dict(meta)),
                    score=score,
                )
            )

        scored.sort(key=lambda r: (-float(r.score), str(r.record.record_id)))
        k = int(top_k) if isinstance(top_k, int) else 5
        if k < 1:
            k = 1
        return scored[:k]

    # ---------------------------------------------------------------
    # Code-aware secondary index
    # ---------------------------------------------------------------

    def _code_index_path(self) -> Path:
        return self.workspace / ".cache" / "memoryport" / "code_index.v1.json"

    def _load_code_index(self) -> dict[str, dict[str, Any]]:
        path = self._code_index_path()
        if not path.exists():
            return {}
        try:
            obj = _load_json(path)
            records = obj.get("records") if isinstance(obj, dict) else None
            return records if isinstance(records, dict) else {}
        except Exception:
            return {}

    def _save_code_index(self, records: dict[str, dict[str, Any]]) -> None:
        payload = {
            "version": "v1",
            "adapter_id": self.adapter_id,
            "kind": "code_aware_secondary_index",
            "records": records,
        }
        _save_json(self._code_index_path(), payload)

    def upsert_code_symbol(
        self,
        *,
        file_path: str,
        symbol: str,
        symbol_type: str = "function",
        domain: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Index a code symbol (class, function, export) for retrieval."""
        meta = metadata if isinstance(metadata, dict) else {}
        rid = sha256(f"{file_path}:{symbol}".encode("utf-8")).hexdigest()
        text = f"{symbol} {symbol_type} {file_path} {domain}"

        record = {
            "record_id": rid,
            "file_path": str(file_path),
            "symbol": str(symbol),
            "symbol_type": str(symbol_type),
            "domain": str(domain),
            "vector": _embed(text),
            "metadata": meta,
        }

        records = self._load_code_index()
        records[rid] = record
        self._save_code_index(records)
        return rid

    def query_code_symbols(
        self,
        *,
        query: str,
        top_k: int = 10,
        domain_filter: str | None = None,
        symbol_type_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query the code-aware secondary index."""
        qv = _embed(query)
        records = self._load_code_index()

        scored: list[tuple[float, dict[str, Any]]] = []
        for rid, raw in records.items():
            if not isinstance(raw, dict):
                continue
            if domain_filter and str(raw.get("domain") or "") != domain_filter:
                continue
            if symbol_type_filter and str(raw.get("symbol_type") or "") != symbol_type_filter:
                continue

            vec = raw.get("vector")
            if not isinstance(vec, list):
                continue
            v = [float(x) for x in vec]
            score = _dot(qv, v)
            scored.append((score, {
                "record_id": str(rid),
                "file_path": str(raw.get("file_path") or ""),
                "symbol": str(raw.get("symbol") or ""),
                "symbol_type": str(raw.get("symbol_type") or ""),
                "domain": str(raw.get("domain") or ""),
                "score": round(score, 4),
                "metadata": raw.get("metadata") or {},
            }))

        scored.sort(key=lambda r: -r[0])
        k = max(1, int(top_k))
        return [item for _, item in scored[:k]]

    def index_from_code_aware_index(self, *, repo_root: Path) -> int:
        """Bulk-index symbols from the code-aware index into the secondary index."""
        try:
            from src.session.code_aware_index import build_code_index
            index = build_code_index(repo_root=repo_root, max_files=500)
        except Exception:
            return 0

        count = 0
        for entry in index.get("entries", []):
            if not isinstance(entry, dict):
                continue
            fp = str(entry.get("path") or "")
            domain = str(entry.get("domain") or "")
            for sym in entry.get("symbols", []):
                self.upsert_code_symbol(
                    file_path=fp, symbol=sym, symbol_type="symbol", domain=domain,
                )
                count += 1
        return count

    def delete(self, *, namespace: str, record_ids: list[str]) -> int:
        ns = str(namespace or "").strip() or "default"
        records = self._load_records(ns)
        removed = 0
        for rid in record_ids:
            key = str(rid or "").strip()
            if not key:
                continue
            if key in records:
                records.pop(key, None)
                removed += 1
        self._save_records(ns, records)
        return removed
