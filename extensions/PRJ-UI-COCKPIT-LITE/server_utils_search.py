from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.orchestrator.memory.adapters import resolve_memory_port
from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, deterministic_record_id
from src.prj_kernel_api.dotenv_loader import resolve_env_value

from server_utils import (
    RG_MAX_FILESIZE,
    SEARCH_ALLOWED_EXTS,
    SEARCH_INDEX_DIR_REL,
    SEARCH_NAMESPACE_BASE,
    SEARCH_SKIP_DIRS,
    SSOT_SEARCH_ROOTS,
    WS_SEARCH_ROOTS_REL,
    _sanitize_text,
    _shorten_text,
)


def _classify_search_mode(query: str, mode_hint: str | None) -> str:
    hint = str(mode_hint or "").strip().lower()
    if hint in {"semantic", "keyword"}:
        return hint
    q = str(query or "").strip()
    if q.lower().startswith("semantic:") or q.lower().startswith("sem:"):
        return "semantic"
    if q.lower().startswith("keyword:") or q.lower().startswith("key:"):
        return "keyword"
    if any(ch in q for ch in ['"', "'", "=", ":", "/", "\\", ".", "*", "(", ")", "[", "]", "{", "}", "|"]):
        return "keyword"
    tokens = [t for t in re.split(r"\\W+", q) if t]
    if len(tokens) >= 4 or "?" in q:
        return "semantic"
    return "keyword"


def _normalize_search_scope(scope: str | None) -> str:
    raw = str(scope or "").strip().lower()
    if raw in {"repo", "ssot"}:
        return raw
    return "repo"


def _search_namespace(scope: str | None) -> str:
    normalized = _normalize_search_scope(scope)
    return f"{SEARCH_NAMESPACE_BASE}_{normalized}"


def _search_index_manifest_path(ws_root: Path, scope: str | None) -> Path:
    normalized = _normalize_search_scope(scope)
    # Backward-compatible: older versions wrote to semantic_index.v1.json (no scope suffix).
    # We still prefer the scoped filenames to avoid collisions between different index scopes.
    return ws_root / SEARCH_INDEX_DIR_REL / f"semantic_index.{normalized}.v1.json"


def _workspace_search_roots(ws_root: Path) -> list[Path]:
    roots: list[Path] = []
    for rel in WS_SEARCH_ROOTS_REL:
        path = (ws_root / rel).resolve()
        if path.exists():
            roots.append(path)
    return roots


def _search_roots(repo_root: Path, ws_root: Path, scope: str | None) -> list[Path]:
    normalized = _normalize_search_scope(scope)
    ws_roots = _workspace_search_roots(ws_root)
    if normalized != "ssot":
        return [repo_root] + ws_roots
    roots: list[Path] = []
    for rel in SSOT_SEARCH_ROOTS:
        path = (repo_root / rel).resolve()
        if path.exists():
            roots.append(path)
    if not roots:
        roots = [repo_root]
    return roots + ws_roots


def _iter_index_files(repo_root: Path, roots: list[Path], max_files: int, max_bytes: int) -> tuple[list[Path], int]:
    files: list[Path] = []
    total_bytes = 0
    for base in roots:
        if len(files) >= max_files or total_bytes >= max_bytes:
            return files, total_bytes
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SEARCH_SKIP_DIRS]
        for filename in sorted(filenames):
            if len(files) >= max_files or total_bytes >= max_bytes:
                return files, total_bytes
            path = Path(dirpath) / filename
            if path.suffix.lower() not in SEARCH_ALLOWED_EXTS:
                continue
            try:
                size = path.stat().st_size
            except Exception:
                continue
            if size <= 0:
                continue
            if total_bytes + size > max_bytes:
                continue
            files.append(path)
            total_bytes += size
    return files, total_bytes


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []
    if len(raw) <= chunk_size:
        return [raw]
    return [raw[i : i + chunk_size] for i in range(0, len(raw), chunk_size)]


def _apply_memory_env(ws_root: Path) -> None:
    keys = [
        "ORCH_MEMORY_ADAPTER",
        "ORCH_MEMORY_FALLBACK",
        "ORCH_NETWORK_MODE",
        "VECTOR_BACKEND_ENABLE",
        "ORCH_PGVECTOR_DSN",
        "PGVECTOR_POSTGRES_PASSWORD",
    ]
    for key in keys:
        present, value = resolve_env_value(key, str(ws_root), env_mode="dotenv")
        if present and value:
            os.environ[key] = value
    if not os.environ.get("ORCH_MEMORY_ADAPTER"):
        os.environ["ORCH_MEMORY_ADAPTER"] = "pgvector_driver"
    if not os.environ.get("ORCH_MEMORY_FALLBACK"):
        os.environ["ORCH_MEMORY_FALLBACK"] = "local_first"


def _clear_index_records(port: Any, namespace: str, record_ids: list[str]) -> int:
    if not record_ids:
        return 0
    deleted = 0
    chunk = 200
    for idx in range(0, len(record_ids), chunk):
        batch = record_ids[idx : idx + chunk]
        try:
            deleted += int(port.delete(namespace=namespace, record_ids=batch))
        except Exception:
            continue
    return deleted


def _build_semantic_index(
    *,
    repo_root: Path,
    ws_root: Path,
    port: Any,
    namespace: str,
    scope: str | None,
    max_files: int,
    max_bytes: int,
    chunk_size: int,
    rebuild: bool,
) -> dict[str, Any]:
    manifest_path = _search_index_manifest_path(ws_root, scope)
    manifest: dict[str, Any] = {}
    existing_ids: list[str] = []
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
        if rebuild and isinstance(manifest.get("record_ids"), list) and str(manifest.get("namespace") or "") == namespace:
            existing_ids = [str(rid) for rid in manifest.get("record_ids") if isinstance(rid, str)]
    if rebuild and existing_ids:
        _clear_index_records(port, namespace, existing_ids)

    roots = _search_roots(repo_root, ws_root, scope)
    files, total_bytes = _iter_index_files(repo_root, roots, max_files, max_bytes)
    record_ids: list[str] = []
    record_count = 0
    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunks = _chunk_text(content, chunk_size)
        if not chunks:
            continue
        try:
            rel = str(path.resolve().relative_to(repo_root.resolve()).as_posix())
        except Exception:
            rel = str(path)
        for idx, chunk in enumerate(chunks):
            meta = {"path": rel, "chunk": idx, "bytes": len(chunk)}
            rid = deterministic_record_id(namespace=namespace, text=chunk, metadata=meta)
            record_ids.append(rid)
            try:
                port.upsert_text(namespace=namespace, text=chunk, metadata=meta, record_id=rid)
                record_count += 1
            except Exception:
                continue

    manifest = {
        "version": "v1",
        "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "namespace": namespace,
        "scope": _normalize_search_scope(scope),
        "adapter_id": getattr(port, "adapter_id", ""),
        "file_count": len(files),
        "record_count": record_count,
        "total_bytes": total_bytes,
        "record_ids": record_ids,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def _resolve_rg_bin() -> str | None:
    rg = shutil.which("rg")
    if rg:
        return rg
    # Common macOS paths (Homebrew Intel + Apple Silicon).
    candidates = ["/opt/homebrew/bin/rg", "/usr/local/bin/rg"]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _git_grep_search(*, repo_root: Path, roots: list[Path], query: str, limit: int) -> dict[str, Any]:
    term = str(query or "").strip()
    if not term:
        return {"status": "FAIL", "error": "QUERY_REQUIRED", "mode": "keyword", "hits": []}
    # smart-case: if query contains any uppercase, keep case-sensitive, else ignore-case.
    ignore_case = term.lower() == term
    cmd = ["git", "grep", "-n", "-I", "-m", "1"]
    if ignore_case:
        cmd.append("-i")
    cmd.extend(["-F", "--", term])
    cmd.extend([str(p) for p in roots])
    try:
        proc = subprocess.Popen(cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        return {"status": "FAIL", "error": "SEARCH_TOOL_MISSING", "mode": "keyword", "hits": []}
    except Exception as exc:
        return {"status": "FAIL", "error": f"GIT_GREP_START_FAIL:{_shorten_text(exc, 80)}", "mode": "keyword", "hits": []}

    hits: list[dict[str, Any]] = []
    if proc.stdout:
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            # Format: path:line:content (content may include ':')
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path_text, line_no_text, content = parts
            try:
                line_number = int(line_no_text)
            except Exception:
                line_number = None
            hits.append(
                {
                    "path": str(path_text),
                    "line": line_number,
                    "preview": _shorten_text(_sanitize_text(str(content).strip())),
                }
            )
            if len(hits) >= limit:
                break
    try:
        if proc.poll() is None:
            proc.terminate()
    except Exception:
        pass
    return {"status": "OK", "mode": "keyword", "query": term, "hits": hits}


def _normalize_hit_path(*, repo_root: Path, ws_root: Path, raw_path: str) -> str:
    text = str(raw_path or "").strip()
    if not text:
        return ""
    try:
        path = Path(text).resolve()
    except Exception:
        return text
    for base in [repo_root.resolve(), ws_root.resolve()]:
        try:
            rel = path.relative_to(base)
            return str(rel.as_posix())
        except Exception:
            continue
    return text


def _rg_search(*, repo_root: Path, ws_root: Path, roots: list[Path], query: str, limit: int) -> dict[str, Any]:
    raw = str(query or "").strip()
    if not raw:
        return {"status": "FAIL", "error": "QUERY_REQUIRED", "mode": "keyword", "hits": []}
    # Default to literal match for speed + predictability. Enable regex with "re:" prefix.
    regex_mode = False
    term = raw
    if raw.lower().startswith("re:"):
        regex_mode = True
        term = raw[3:].strip()
    if not term:
        return {"status": "FAIL", "error": "QUERY_REQUIRED", "mode": "keyword", "hits": []}

    rg_bin = _resolve_rg_bin()
    if not rg_bin:
        return _git_grep_search(repo_root=repo_root, roots=roots, query=term, limit=limit)

    cmd = [
        rg_bin,
        "--no-config",
        "--json",
        "--no-heading",
        "--smart-case",
        "--hidden",
        "--max-count",
        "1",
        "--max-filesize",
        RG_MAX_FILESIZE,
    ]
    if not regex_mode:
        cmd.append("--fixed-strings")

    # Always skip known heavy/irrelevant paths for search UX.
    for skip in sorted(SEARCH_SKIP_DIRS):
        cmd.extend(["--glob", f"!{skip}/**"])
    for pat in ["!**/*.zip", "!**/*.gz", "!**/*.tgz", "!**/*.png", "!**/*.jpg", "!**/*.jpeg", "!**/*.gif", "!**/*.pdf"]:
        cmd.extend(["--glob", pat])

    cmd.extend(["--", term])
    cmd.extend([str(p) for p in roots])

    env = dict(os.environ)
    # Keep search behavior deterministic and avoid user-level rg defaults
    # that can unintentionally hide important workspace artifacts (e.g. .cache/**).
    env.pop("RIPGREP_CONFIG_PATH", None)
    env.pop("RIPGREP_CONFIG", None)
    hits: list[dict[str, Any]] = []
    try:
        proc = subprocess.Popen(cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    except Exception:
        # Fall back to git-grep if rg isn't runnable in this environment.
        return _git_grep_search(repo_root=repo_root, roots=roots, query=term, limit=limit)

    if proc.stdout:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") != "match":
                continue
            data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
            path_raw = data.get("path", {}).get("text") if isinstance(data.get("path"), dict) else ""
            path = _normalize_hit_path(repo_root=repo_root, ws_root=ws_root, raw_path=str(path_raw))
            line_number = data.get("line_number")
            lines = data.get("lines", {}).get("text") if isinstance(data.get("lines"), dict) else ""
            snippet = _shorten_text(_sanitize_text(str(lines).strip()))
            hits.append(
                {
                    "path": str(path),
                    "line": int(line_number) if isinstance(line_number, int) else None,
                    "preview": snippet,
                }
            )
            if len(hits) >= limit:
                break
    try:
        if proc.poll() is None:
            proc.terminate()
    except Exception:
        pass
    return {"status": "OK", "mode": "keyword", "query": term, "hits": hits}


def _semantic_search(
    *,
    repo_root: Path,
    ws_root: Path,
    scope: str | None,
    query: str,
    limit: int,
    rebuild: bool,
    max_files: int,
    max_bytes: int,
    chunk_size: int,
) -> dict[str, Any]:
    term = str(query or "").strip()
    if not term:
        return {"status": "FAIL", "error": "QUERY_REQUIRED", "mode": "semantic", "hits": []}
    namespace = _search_namespace(scope)
    _apply_memory_env(ws_root)
    try:
        port = resolve_memory_port(workspace=ws_root)
    except MemoryAdapterUnavailable as exc:
        return {"status": "FAIL", "error": _shorten_text(str(exc), 160), "mode": "semantic", "hits": []}
    except Exception as exc:
        return {"status": "FAIL", "error": _shorten_text(str(exc), 160), "mode": "semantic", "hits": []}

    manifest_path = _search_index_manifest_path(ws_root, scope)
    manifest: dict[str, Any] | None = None
    if rebuild or not manifest_path.exists():
        manifest = _build_semantic_index(
            repo_root=repo_root,
            ws_root=ws_root,
            port=port,
            namespace=namespace,
            scope=scope,
            max_files=max_files,
            max_bytes=max_bytes,
            chunk_size=chunk_size,
            rebuild=rebuild,
        )
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = None

    hits_out: list[dict[str, Any]] = []
    try:
        hits = port.query_text(namespace=namespace, query=term, top_k=limit)
    except Exception as exc:
        return {"status": "FAIL", "error": _shorten_text(str(exc), 160), "mode": "semantic", "hits": []}
    for hit in hits or []:
        record = hit.record
        meta = record.metadata if isinstance(record.metadata, dict) else {}
        path = str(meta.get("path") or "")
        snippet = _shorten_text(_sanitize_text(str(record.text or "")))
        hits_out.append(
            {
                "path": path,
                "score": round(float(hit.score), 6),
                "preview": snippet,
                "chunk": meta.get("chunk"),
            }
        )

    payload: dict[str, Any] = {"status": "OK", "mode": "semantic", "query": term, "hits": hits_out}
    if manifest:
        payload["index"] = {
            "indexed_at": manifest.get("indexed_at"),
            "file_count": manifest.get("file_count"),
            "record_count": manifest.get("record_count"),
            "adapter_id": manifest.get("adapter_id"),
        }
    return payload


def _search_router(
    *,
    repo_root: Path,
    ws_root: Path,
    query: str,
    mode_hint: str | None,
    scope: str | None,
    limit: int,
    rebuild: bool,
    max_files: int,
    max_bytes: int,
    chunk_size: int,
) -> dict[str, Any]:
    mode = _classify_search_mode(query, mode_hint)
    roots = _search_roots(repo_root, ws_root, scope)
    if mode == "semantic":
        return _semantic_search(
            repo_root=repo_root,
            ws_root=ws_root,
            scope=scope,
            query=query,
            limit=limit,
            rebuild=rebuild,
            max_files=max_files,
            max_bytes=max_bytes,
            chunk_size=chunk_size,
        )
    return _rg_search(repo_root=repo_root, ws_root=ws_root, roots=roots, query=query, limit=limit)


def _semantic_index_handle(
    *,
    repo_root: Path,
    ws_root: Path,
    scope: str | None,
    action: str | None,
    rebuild: bool,
    max_files: int,
    max_bytes: int,
    chunk_size: int,
) -> dict[str, Any]:
    mode = str(action or "").strip().lower() or "status"
    namespace = _search_namespace(scope)
    manifest_path = _search_index_manifest_path(ws_root, scope)
    if mode in {"build", "rebuild"} or rebuild:
        _apply_memory_env(ws_root)
        try:
            port = resolve_memory_port(workspace=ws_root)
        except MemoryAdapterUnavailable as exc:
            return {"status": "FAIL", "action": "build", "error": _shorten_text(str(exc), 160)}
        except Exception as exc:
            return {"status": "FAIL", "action": "build", "error": _shorten_text(str(exc), 160)}
        manifest = _build_semantic_index(
            repo_root=repo_root,
            ws_root=ws_root,
            port=port,
            namespace=namespace,
            scope=scope,
            max_files=max_files,
            max_bytes=max_bytes,
            chunk_size=chunk_size,
            rebuild=True,
        )
        return {"status": "OK", "action": "build", "index": manifest}

    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = None
        if isinstance(manifest, dict):
            return {"status": "OK", "action": "status", "index": manifest}
    return {"status": "MISSING", "action": "status", "index": None}
