from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from search_adapter_core import (
    _detect_mode_auto,
    _extract_fts_tokens,
    _fts_query_from_tokens,
    _fts_query_or_from_tokens,
    _run_rg_on_files,
    _safe_int,
)
from search_adapter_index import paths
from search_adapter_semantic import semantic_search


def _apply_context_scope(
    hits: list[dict[str, Any]],
    context_scope: list[str],
) -> list[dict[str, Any]]:
    """Boost hits matching context_scope paths to the top of results."""
    scope_set = set(context_scope)
    in_scope: list[dict[str, Any]] = []
    out_scope: list[dict[str, Any]] = []
    for hit in hits:
        path = str(hit.get("path") or "")
        matched = any(
            path == s or path.startswith(s + "/") or path.endswith("/" + s) or s in path
            for s in scope_set
        )
        if matched:
            hit["context_match"] = True
            in_scope.append(hit)
        else:
            hit["context_match"] = False
            out_scope.append(hit)
    return in_scope + out_scope


def search(
    manager: Any,
    query: str,
    *,
    scope: str = "ssot",
    search_mode: str = "auto",
    pattern_mode: str = "auto",
    limit: int = 80,
    auto_build: bool = True,
    context_scope: list[str] | None = None,
) -> dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"status": "FAIL", "error": "QUERY_REQUIRED"}

    scope_norm = str(scope or "ssot").strip().lower()
    search_mode_norm = str(search_mode or "auto").strip().lower()
    if search_mode_norm not in {"auto", "keyword", "semantic"}:
        if search_mode_norm in {"fixed", "regex"}:
            pattern_mode = search_mode_norm
            search_mode_norm = "keyword"
        else:
            search_mode_norm = "auto"
    pattern_mode_norm = str(pattern_mode or "auto").strip().lower()
    if pattern_mode_norm not in {"auto", "fixed", "regex"}:
        pattern_mode_norm = "auto"
    limit_n = _safe_int(limit, 80, min_value=1, max_value=500)

    if search_mode_norm == "semantic":
        return semantic_search(
            manager,
            scope=scope_norm,
            query=q,
            limit=limit_n,
            auto_build=bool(auto_build),
            rebuild=False,
        )

    path_map = paths(manager, scope_norm)
    if not path_map["db"].exists():
        if auto_build:
            build_status = manager.start_build(scope_norm, force=True)
            return {
                "status": "INDEX_BUILDING",
                "scope": scope_norm,
                "query": q,
                "mode": "keyword",
                "engine": "keyword/fts5+rg",
                "hits": [],
                "index": (build_status or {}).get("index") or {},
                "build": build_status,
            }
        return {
            "status": "FAIL",
            "error": "INDEX_MISSING",
            "scope": scope_norm,
            "mode": "keyword",
            "engine": "keyword/fts5+rg",
            "query": q,
            "hits": [],
        }

    started = time.monotonic()
    tokens = _extract_fts_tokens(q)
    fts_query = _fts_query_from_tokens(tokens) if tokens else ""
    fts_query_fallback = _fts_query_or_from_tokens(tokens) if len(tokens) >= 2 else ""

    candidates: list[Path] = []
    fts_used_query = ""
    fts_error = ""
    candidate_limit = 400
    try:
        con = sqlite3.connect(str(path_map["db"]))
        try:
            if fts_query:
                fts_used_query = fts_query
                cur = con.execute("SELECT path FROM docs WHERE docs MATCH ? LIMIT ?;", (fts_query, candidate_limit))
                rows = cur.fetchall()
                if not rows and fts_query_fallback:
                    fts_used_query = fts_query_fallback
                    cur = con.execute("SELECT path FROM docs WHERE docs MATCH ? LIMIT ?;", (fts_query_fallback, candidate_limit))
                    rows = cur.fetchall()
                for (path_raw,) in rows:
                    if not isinstance(path_raw, str) or not path_raw:
                        continue
                    candidates.append(Path(path_raw))
        finally:
            con.close()
    except Exception as exc:
        fts_error = str(exc)
        candidates = []

    if not candidates:
        return {
            "status": "OK",
            "scope": scope_norm,
            "query": q,
            "mode": "keyword",
            "engine": "keyword/fts5+rg",
            "hits": [],
            "index": (manager.status(scope_norm) or {}).get("index") or {},
            "error": "",
            "note": "FTS returned 0 candidates; consider broader query or rebuild index.",
            "fts_tokens": tokens,
            "fts_query": fts_query,
            "fts_query_used": fts_used_query or fts_query,
            "fts_error": fts_error,
        }

    rg_mode = pattern_mode_norm
    if rg_mode == "auto":
        rg_mode = _detect_mode_auto(q)

    candidates = [path for path in candidates if path.exists()][:candidate_limit]
    matches, rg_stats = _run_rg_on_files(q, candidates, mode=rg_mode, limit=limit_n, timeout_s=10)
    duration_ms = int((time.monotonic() - started) * 1000)

    hits = [
        {
            "path": str(match.get("path") or ""),
            "line": match.get("line"),
            "col": match.get("col"),
            "preview": str(match.get("text") or ""),
            "score": None,
        }
        for match in matches
        if isinstance(match, dict)
    ]

    engine = "keyword/fts5+rg"
    if str(rg_stats.get("backend") or "") == "python_fallback":
        engine = "keyword/fts5+python"

    context_scope_applied = False
    if context_scope:
        hits = _apply_context_scope(hits, context_scope)
        context_scope_applied = True

    return {
        "status": "OK",
        "scope": scope_norm,
        "query": q,
        "mode": "keyword",
        "engine": engine,
        "pattern_mode": rg_mode,
        "hits": hits,
        "context_scope_applied": context_scope_applied,
        "index": (manager.status(scope_norm) or {}).get("index") or {},
        "stats": {
            "duration_ms": duration_ms,
            "candidate_files": len(candidates),
            "hit_count": len(hits),
            "rg": rg_stats,
            "fts_tokens": tokens,
            "fts_query": fts_query,
        },
    }
