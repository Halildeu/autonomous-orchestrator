from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.orchestrator.memory.adapters import resolve_memory_port
from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, deterministic_record_id
from src.prj_kernel_api.dotenv_loader import resolve_env_value
from search_adapter_core import _atomic_write_json, _iter_files, _now_iso, _safe_int


SEMANTIC_NAMESPACE_BASE = "codex_search_semantic_v1"
SEMANTIC_CHUNK_SIZE = 1200
SEMANTIC_MAX_FILES = 600
SEMANTIC_MAX_BYTES = 6_000_000
SEMANTIC_EXPECTED_ADAPTER = "pgvector_driver"
_SEMANTIC_ENV_LOCK = RLock()


def _env_value(*, workspace_root: Path, key: str, default: str = "") -> str:
    present, value = resolve_env_value(key, str(workspace_root), env_mode="dotenv")
    if present and isinstance(value, str) and value.strip():
        return value.strip()
    raw = os.environ.get(key, default)
    return str(raw).strip() if isinstance(raw, str) else str(default)


@contextmanager
def _with_env(overrides: dict[str, str]):
    # Semantic runtime env overrides use global process env; serialize to avoid threaded races.
    with _SEMANTIC_ENV_LOCK:
        before = {k: os.environ.get(k) for k in overrides}
        for key, value in overrides.items():
            if value is None:
                continue
            os.environ[str(key)] = str(value)
        try:
            yield
        finally:
            for key, value in before.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _semantic_env_overrides(workspace_root: Path) -> dict[str, str]:
    adapter = _env_value(workspace_root=workspace_root, key="ORCH_MEMORY_ADAPTER", default="pgvector_driver")
    fallback = _env_value(workspace_root=workspace_root, key="ORCH_MEMORY_FALLBACK", default="local_first")
    network_mode = _env_value(workspace_root=workspace_root, key="ORCH_NETWORK_MODE", default="ON")
    vector_enable = _env_value(workspace_root=workspace_root, key="VECTOR_BACKEND_ENABLE", default="1")
    pgvector_dsn = _env_value(workspace_root=workspace_root, key="ORCH_PGVECTOR_DSN", default="")
    pgvector_password = _env_value(workspace_root=workspace_root, key="PGVECTOR_POSTGRES_PASSWORD", default="")
    return {
        "ORCH_MEMORY_ADAPTER": adapter or "pgvector_driver",
        "ORCH_MEMORY_FALLBACK": fallback or "local_first",
        "ORCH_NETWORK_MODE": network_mode or "ON",
        "VECTOR_BACKEND_ENABLE": vector_enable or "1",
        "ORCH_PGVECTOR_DSN": pgvector_dsn,
        "PGVECTOR_POSTGRES_PASSWORD": pgvector_password,
    }


def _semantic_manifest_path(manager: Any, scope: str) -> Path:
    scope_norm = str(scope or "ssot").strip().lower()
    return manager.workspace_root / ".cache" / "state" / "keyword_search" / f"semantic_index.{scope_norm}.v1.json"


def _semantic_namespace(scope: str) -> str:
    scope_norm = str(scope or "ssot").strip().lower()
    return f"{SEMANTIC_NAMESPACE_BASE}_{scope_norm}"


def _adapter_name(raw: Any, default: str = "") -> str:
    value = str(raw or default).strip().lower()
    return value or str(default or "").strip().lower()


def _adapter_required_reason(expected: str, resolved: str) -> str:
    exp = _adapter_name(expected, SEMANTIC_EXPECTED_ADAPTER)
    got = _adapter_name(resolved, "none") or "none"
    if exp == "pgvector_driver":
        return f"PGVECTOR_REQUIRED (resolved={got})"
    return f"{exp.upper()}_REQUIRED (resolved={got})"


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []
    if len(raw) <= chunk_size:
        return [raw]
    return [raw[i : i + chunk_size] for i in range(0, len(raw), chunk_size)]


def _shorten_text(text: str, limit: int = 200) -> str:
    raw = str(text or "")
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 3)] + "..."


def _normalize_hit_preview(text: str, limit: int = 320) -> str:
    return _shorten_text(str(text or "").replace("\n", " ").strip(), limit=limit)


@contextmanager
def _semantic_runtime(manager: Any):
    workspace_root = Path(manager.workspace_root).resolve()
    overrides = _semantic_env_overrides(workspace_root)
    expected_adapter = _adapter_name(overrides.get("ORCH_MEMORY_ADAPTER"), SEMANTIC_EXPECTED_ADAPTER)
    probe: dict[str, Any]
    try:
        with _with_env(overrides):
            port = resolve_memory_port(workspace=workspace_root)
            resolved_adapter = str(getattr(port, "adapter_id", "") or "")
            if _adapter_name(resolved_adapter) != expected_adapter:
                probe = {
                    "status": "UNAVAILABLE",
                    "reason": _adapter_required_reason(expected_adapter, resolved_adapter),
                    "resolved_adapter": resolved_adapter,
                    "expected_adapter": expected_adapter,
                }
                yield probe, None
                return
            probe = {
                "status": "READY",
                "reason": "",
                "resolved_adapter": resolved_adapter,
                "expected_adapter": expected_adapter,
            }
            yield probe, port
            return
    except MemoryAdapterUnavailable as exc:
        probe = {
            "status": "UNAVAILABLE",
            "reason": _shorten_text(str(exc), 240),
            "resolved_adapter": "",
            "expected_adapter": expected_adapter,
        }
        yield probe, None
        return
    except Exception as exc:
        probe = {
            "status": "UNAVAILABLE",
            "reason": f"{type(exc).__name__}: {_shorten_text(str(exc), 200)}",
            "resolved_adapter": "",
            "expected_adapter": expected_adapter,
        }
        yield probe, None
        return


def _semantic_probe(manager: Any) -> dict[str, Any]:
    with _semantic_runtime(manager) as runtime:
        probe, _port = runtime
        return probe


def semantic_capability(manager: Any, scope: str = "ssot") -> dict[str, Any]:
    probe = _semantic_probe(manager)
    out = dict(probe)
    out["scope"] = str(scope or "ssot").strip().lower()
    out["adapter_id"] = "semantic_pgvector"
    return out


def _build_semantic_index(
    manager: Any,
    *,
    port: Any,
    scope: str,
    resolved_adapter: str,
    chunk_size: int,
    max_files: int,
    max_bytes: int,
    max_file_bytes: int,
    rebuild: bool,
) -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    spec = manager._scope_spec(scope_norm, max_file_bytes=max_file_bytes)
    namespace = _semantic_namespace(scope_norm)
    manifest_path = _semantic_manifest_path(manager, scope_norm)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    existing_record_ids: list[str] = []
    if rebuild and manifest_path.exists():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
        if isinstance(previous, dict) and str(previous.get("namespace") or "") == namespace:
            ids = previous.get("record_ids")
            if isinstance(ids, list):
                existing_record_ids = [str(rid) for rid in ids if isinstance(rid, str) and rid.strip()]

    files, file_stats = _iter_files(
        spec.roots,
        allowed_exts=spec.allowed_exts,
        exclude_dir_names=spec.exclude_dir_names,
        max_file_bytes=spec.max_file_bytes,
        max_files=max_files,
    )
    selected_files: list[Path] = []
    total_bytes = 0
    for path in files:
        try:
            size = int(path.stat().st_size)
        except Exception:
            continue
        if total_bytes + size > max_bytes:
            continue
        selected_files.append(path)
        total_bytes += size

    if existing_record_ids:
        try:
            port.delete(namespace=namespace, record_ids=existing_record_ids)
        except Exception:
            pass

    record_ids: list[str] = []
    indexed_files = 0
    indexed_chunks = 0
    for path in selected_files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunks = _chunk_text(content, chunk_size)
        if not chunks:
            continue
        try:
            rel_path = str(path.resolve().relative_to(manager.repo_root).as_posix())
        except Exception:
            rel_path = str(path)
        for chunk_idx, chunk in enumerate(chunks):
            meta = {"path": rel_path, "chunk": chunk_idx, "bytes": len(chunk)}
            record_id = deterministic_record_id(namespace=namespace, text=chunk, metadata=meta)
            port.upsert_text(namespace=namespace, text=chunk, metadata=meta, record_id=record_id)
            record_ids.append(record_id)
            indexed_chunks += 1
        indexed_files += 1

    duration_ms = int((time.monotonic() - started) * 1000)
    manifest = {
        "version": "v1",
        "scope": scope_norm,
        "namespace": namespace,
        "indexed_at": _now_iso(),
        "adapter_id": "semantic_pgvector",
        "resolved_adapter": str(resolved_adapter or ""),
        "file_count": int(indexed_files),
        "record_count": int(indexed_chunks),
        "indexed_bytes": int(total_bytes),
        "duration_ms": int(duration_ms),
        "chunk_size": int(chunk_size),
        "max_files": int(max_files),
        "max_bytes": int(max_bytes),
        "max_file_bytes": int(max_file_bytes),
        "record_ids": record_ids,
        "file_stats": file_stats,
    }
    _atomic_write_json(manifest_path, manifest)
    return manifest


def semantic_search(
    manager: Any,
    *,
    scope: str,
    query: str,
    limit: int,
    auto_build: bool,
    rebuild: bool = False,
    chunk_size: int = SEMANTIC_CHUNK_SIZE,
    max_files: int = SEMANTIC_MAX_FILES,
    max_bytes: int = SEMANTIC_MAX_BYTES,
    max_file_bytes: int = 524288,
) -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    q = str(query or "").strip()
    if not q:
        return {"status": "FAIL", "error": "QUERY_REQUIRED", "mode": "semantic", "hits": []}

    manifest_path = _semantic_manifest_path(manager, scope_norm)
    manifest: dict[str, Any] | None = None
    with _semantic_runtime(manager) as runtime:
        probe, port = runtime
        if str(probe.get("status") or "").upper() != "READY" or port is None:
            return {
                "status": "FAIL",
                "error": str(probe.get("reason") or "SEMANTIC_BACKEND_UNAVAILABLE"),
                "mode": "semantic",
                "engine": "semantic/pgvector",
                "scope": scope_norm,
                "query": q,
                "hits": [],
                "adapter_status": probe,
            }

        if rebuild or (auto_build and not manifest_path.exists()):
            try:
                manifest = _build_semantic_index(
                    manager,
                    port=port,
                    scope=scope_norm,
                    resolved_adapter=str(probe.get("resolved_adapter") or ""),
                    chunk_size=chunk_size,
                    max_files=max_files,
                    max_bytes=max_bytes,
                    max_file_bytes=max_file_bytes,
                    rebuild=rebuild,
                )
            except Exception as exc:
                return {
                    "status": "FAIL",
                    "error": f"SEMANTIC_INDEX_BUILD_ERROR: {_shorten_text(str(exc), 180)}",
                    "mode": "semantic",
                    "engine": "semantic/pgvector",
                    "scope": scope_norm,
                    "query": q,
                    "hits": [],
                    "adapter_status": probe,
                }
        elif manifest_path.exists():
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = raw_manifest if isinstance(raw_manifest, dict) else None
            except Exception:
                manifest = None

        namespace = _semantic_namespace(scope_norm)
        try:
            hits = port.query_text(namespace=namespace, query=q, top_k=int(limit))
        except Exception as exc:
            return {
                "status": "FAIL",
                "error": f"SEMANTIC_QUERY_ERROR: {_shorten_text(str(exc), 180)}",
                "mode": "semantic",
                "engine": "semantic/pgvector",
                "scope": scope_norm,
                "query": q,
                "hits": [],
                "adapter_status": probe,
            }

    hits_out: list[dict[str, Any]] = []
    for item in hits or []:
        record = item.record
        meta = record.metadata if isinstance(record.metadata, dict) else {}
        hits_out.append(
            {
                "path": str(meta.get("path") or ""),
                "line": None,
                "col": None,
                "preview": _normalize_hit_preview(str(record.text or "")),
                "score": round(float(item.score), 6),
                "chunk": meta.get("chunk"),
            }
        )

    payload: dict[str, Any] = {
        "status": "OK",
        "mode": "semantic",
        "engine": "semantic/pgvector",
        "scope": scope_norm,
        "query": q,
        "hits": hits_out,
        "adapter_status": probe,
    }
    if isinstance(manifest, dict):
        payload["index"] = {
            "indexed_at": manifest.get("indexed_at"),
            "file_count": manifest.get("file_count"),
            "record_count": manifest.get("record_count"),
            "adapter_id": manifest.get("adapter_id"),
        }
    return payload


def semantic_index_status(manager: Any, scope: str = "ssot") -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    with _semantic_runtime(manager) as runtime:
        probe, _port = runtime
    manifest_path = _semantic_manifest_path(manager, scope_norm)
    manifest = None
    if manifest_path.exists():
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = raw_manifest if isinstance(raw_manifest, dict) else None
        except Exception:
            manifest = None

    state = "UNAVAILABLE"
    if str(probe.get("status") or "").upper() == "READY":
        state = "OK" if isinstance(manifest, dict) else "MISSING"

    index_obj = {
        "status": state,
        "adapter_id": "semantic_pgvector",
        "resolved_adapter": str(probe.get("resolved_adapter") or ""),
        "indexed_at": str((manifest or {}).get("indexed_at") or ""),
        "file_count": _safe_int((manifest or {}).get("file_count"), 0, min_value=0),
        "record_count": _safe_int((manifest or {}).get("record_count"), 0, min_value=0),
        "manifest_path": str(manifest_path),
    }
    out = {
        "status": state,
        "engine": "semantic",
        "scope": scope_norm,
        "adapter": {
            "id": "semantic_pgvector",
            "status": str(probe.get("status") or "UNAVAILABLE"),
            "reason": str(probe.get("reason") or ""),
            "resolved_adapter": str(probe.get("resolved_adapter") or ""),
        },
        "index": index_obj,
    }
    if isinstance(manifest, dict):
        out["manifest"] = manifest
    return out


def semantic_index_build(
    manager: Any,
    *,
    scope: str = "ssot",
    rebuild: bool = False,
    chunk_size: int = SEMANTIC_CHUNK_SIZE,
    max_files: int = SEMANTIC_MAX_FILES,
    max_bytes: int = SEMANTIC_MAX_BYTES,
    max_file_bytes: int = 524288,
) -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    with _semantic_runtime(manager) as runtime:
        probe, port = runtime
        if str(probe.get("status") or "").upper() != "READY" or port is None:
            return {
                "status": "UNAVAILABLE",
                "engine": "semantic",
                "scope": scope_norm,
                "adapter": {
                    "id": "semantic_pgvector",
                    "status": str(probe.get("status") or "UNAVAILABLE"),
                    "reason": str(probe.get("reason") or "SEMANTIC_BACKEND_UNAVAILABLE"),
                    "resolved_adapter": str(probe.get("resolved_adapter") or ""),
                },
                "index": {
                    "status": "UNAVAILABLE",
                    "adapter_id": "semantic_pgvector",
                    "manifest_path": str(_semantic_manifest_path(manager, scope_norm)),
                },
            }

        try:
            manifest = _build_semantic_index(
                manager,
                port=port,
                scope=scope_norm,
                resolved_adapter=str(probe.get("resolved_adapter") or ""),
                chunk_size=_safe_int(chunk_size, SEMANTIC_CHUNK_SIZE, min_value=200, max_value=4000),
                max_files=_safe_int(max_files, SEMANTIC_MAX_FILES, min_value=1, max_value=200000),
                max_bytes=_safe_int(max_bytes, SEMANTIC_MAX_BYTES, min_value=100000, max_value=500_000_000),
                max_file_bytes=_safe_int(max_file_bytes, 524288, min_value=4096, max_value=5 * 1024 * 1024),
                rebuild=bool(rebuild),
            )
        except Exception as exc:
            return {
                "status": "FAIL",
                "engine": "semantic",
                "scope": scope_norm,
                "error": f"SEMANTIC_INDEX_BUILD_ERROR: {_shorten_text(str(exc), 180)}",
                "adapter": {
                    "id": "semantic_pgvector",
                    "status": str(probe.get("status") or "UNAVAILABLE"),
                    "reason": str(probe.get("reason") or ""),
                    "resolved_adapter": str(probe.get("resolved_adapter") or ""),
                },
                "index": {"status": "FAIL", "adapter_id": "semantic_pgvector"},
            }

    return {
        "status": "OK",
        "engine": "semantic",
        "scope": scope_norm,
        "adapter": {
            "id": "semantic_pgvector",
            "status": str(probe.get("status") or "READY"),
            "reason": str(probe.get("reason") or ""),
            "resolved_adapter": str(probe.get("resolved_adapter") or ""),
        },
        "index": {
            "status": "OK",
            "adapter_id": str(manifest.get("adapter_id") or "semantic_pgvector"),
            "indexed_at": str(manifest.get("indexed_at") or ""),
            "file_count": _safe_int(manifest.get("file_count"), 0, min_value=0),
            "record_count": _safe_int(manifest.get("record_count"), 0, min_value=0),
            "manifest_path": str(_semantic_manifest_path(manager, scope_norm)),
        },
        "manifest": manifest,
    }
