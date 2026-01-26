from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.orchestrator.memory.adapters.local_first import _embed
from src.orchestrator.memory.memory_port import MemoryQueryResult, MemoryRecord, deterministic_record_id


def _env_flag(name: str) -> bool:
    raw = os.environ.get(name, "0")
    v = str(raw).strip().lower() if isinstance(raw, str) else "0"
    return v in {"1", "true", "yes", "on"}


def _is_localhost_dsn(dsn: str) -> bool:
    s = str(dsn or "").strip()
    if not s:
        return False
    if s.startswith(("postgres://", "postgresql://")):
        try:
            p = urlparse(s)
        except Exception:
            return False
        host = str(p.hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1", "::1"}
    lowered = s.lower()
    return "host=localhost" in lowered or "host=127.0.0.1" in lowered or "host=::1" in lowered


def _load_runtime_config(workspace: Path) -> dict[str, Any]:
    path = workspace / ".cache" / "runtime" / "memory_backends.local.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _pgvector_dsn(workspace: Path) -> str | None:
    override = os.environ.get("ORCH_PGVECTOR_DSN")
    if isinstance(override, str) and override.strip():
        return override.strip()

    cfg = _load_runtime_config(workspace).get("pgvector")
    dsn_template = cfg.get("dsn_template") if isinstance(cfg, dict) else None
    if not isinstance(dsn_template, str) or not dsn_template.strip():
        return None

    pw = os.environ.get("PGVECTOR_POSTGRES_PASSWORD")
    if not isinstance(pw, str) or not pw.strip():
        return None
    return dsn_template.replace("${PGVECTOR_POSTGRES_PASSWORD}", pw.strip())


def _vector_size() -> int:
    return 64


@dataclass(frozen=True)
class PgvectorDriverMemoryPort:
    workspace: Path
    adapter_id: str = "pgvector_driver"

    def is_available(self, *, network_mode: str) -> bool:
        if not _env_flag("VECTOR_BACKEND_ENABLE"):
            return False
        if str(network_mode or "").strip().upper() != "ON":
            return False
        if importlib.util.find_spec("psycopg") is None:
            return False
        if importlib.util.find_spec("pgvector") is None:
            return False
        dsn = _pgvector_dsn(self.workspace)
        if not isinstance(dsn, str) or not dsn.strip():
            return False
        return _is_localhost_dsn(dsn)

    def why_unavailable(self, *, network_mode: str) -> str:
        if not _env_flag("VECTOR_BACKEND_ENABLE"):
            return "pgvector_driver unavailable: VECTOR_BACKEND_ENABLE must be 1 (explicit opt-in)."
        if str(network_mode or "").strip().upper() != "ON":
            return "pgvector_driver unavailable: ORCH_NETWORK_MODE must be ON (offline-first; no auto-connect under OFF)."
        dsn = _pgvector_dsn(self.workspace)
        if not isinstance(dsn, str) or not dsn.strip():
            return "pgvector_driver unavailable: DSN is missing (set ORCH_PGVECTOR_DSN or PGVECTOR_POSTGRES_PASSWORD for local config)."
        if not _is_localhost_dsn(dsn):
            return "pgvector_driver unavailable: endpoint must be localhost-only (DSN host must be localhost)."
        if importlib.util.find_spec("psycopg") is None:
            return "pgvector_driver unavailable: postgres driver psycopg is not installed."
        if importlib.util.find_spec("pgvector") is None:
            return "pgvector_driver unavailable: dependency pgvector is not installed."
        return "pgvector_driver unavailable: UNKNOWN"

    def _connect(self):
        if importlib.util.find_spec("psycopg") is None:
            raise RuntimeError("psycopg is not installed")
        if importlib.util.find_spec("pgvector") is None:
            raise RuntimeError("pgvector is not installed")
        dsn = _pgvector_dsn(self.workspace)
        if not dsn:
            raise RuntimeError("pgvector DSN is missing")

        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
        from pgvector.psycopg import register_vector  # type: ignore

        conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        register_vector(conn)
        return conn

    def _ensure_schema(self, conn) -> None:
        dim = _vector_size()
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.execute(
            f"""
CREATE TABLE IF NOT EXISTS memory_records_v1 (
  namespace text NOT NULL,
  record_id text NOT NULL,
  text text NOT NULL,
  vector vector({dim}) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{{}}'::jsonb,
  PRIMARY KEY (namespace, record_id)
);
"""
        )

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

        dim = _vector_size()
        vec = _embed(text, dim=dim)

        conn = self._connect()
        try:
            self._ensure_schema(conn)

            from pgvector import Vector  # type: ignore

            conn.execute(
                """
INSERT INTO memory_records_v1 (namespace, record_id, text, vector, metadata)
VALUES (%s, %s, %s, %s, %s::jsonb)
ON CONFLICT (namespace, record_id)
DO UPDATE SET text = EXCLUDED.text, vector = EXCLUDED.vector, metadata = EXCLUDED.metadata
""",
                (ns, rid, str(text or ""), Vector(vec), json.dumps(meta, ensure_ascii=False, sort_keys=True)),
            )
        finally:
            conn.close()

        return MemoryRecord(record_id=rid, text=str(text or ""), vector=[float(x) for x in vec], metadata=dict(meta))

    def query_text(self, *, namespace: str, query: str, top_k: int = 5) -> list[MemoryQueryResult]:
        ns = str(namespace or "").strip() or "default"
        dim = _vector_size()
        qv = _embed(query, dim=dim)

        conn = self._connect()
        try:
            self._ensure_schema(conn)
            from pgvector import Vector  # type: ignore

            rows = conn.execute(
                """
SELECT record_id, text, vector, metadata, (1 - (vector <=> %s)) AS score
FROM memory_records_v1
WHERE namespace = %s
ORDER BY vector <=> %s
LIMIT %s
""",
                (Vector(qv), ns, Vector(qv), int(top_k) if isinstance(top_k, int) else 5),
            ).fetchall()
        finally:
            conn.close()

        results: list[MemoryQueryResult] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("record_id") or "")
            text = str(row.get("text") or "")
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            raw_vec = row.get("vector")
            if hasattr(raw_vec, "to_list"):
                vec = raw_vec.to_list()  # type: ignore[no-any-return]
            elif isinstance(raw_vec, list):
                vec = raw_vec
            else:
                vec = _embed(text, dim=dim)

            results.append(
                MemoryQueryResult(
                    record=MemoryRecord(
                        record_id=rid,
                        text=text,
                        vector=[float(x) for x in vec],
                        metadata=dict(meta),
                    ),
                    score=float(row.get("score") or 0.0),
                )
            )
        return results

    def delete(self, *, namespace: str, record_ids: list[str]) -> int:
        ns = str(namespace or "").strip() or "default"
        ids = [str(rid or "").strip() for rid in (record_ids or []) if str(rid or "").strip()]
        if not ids:
            return 0

        conn = self._connect()
        try:
            self._ensure_schema(conn)
            cur = conn.execute(
                "DELETE FROM memory_records_v1 WHERE namespace = %s AND record_id = ANY(%s)",
                (ns, ids),
            )
            removed = int(getattr(cur, "rowcount", 0) or 0)
        finally:
            conn.close()
        return removed
