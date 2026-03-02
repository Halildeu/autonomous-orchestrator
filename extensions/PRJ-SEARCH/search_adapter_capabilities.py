from __future__ import annotations

import shutil
from typing import Any

from search_adapter_core import (
    SEARCH_ADAPTER_CONTRACT_ID,
    SEARCH_ADAPTER_KEYWORD_FTS5_RG,
    SEARCH_ADAPTER_KEYWORD_PYTHON,
    SEARCH_ADAPTER_SEMANTIC_PGVECTOR,
    _safe_int,
)
from search_adapter_semantic import semantic_capability


def capabilities(manager: Any, scope: str = "ssot") -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    if scope_norm not in {"ssot", "repo"}:
        scope_norm = "ssot"

    status_payload = manager.status(scope_norm)
    index_status = str(status_payload.get("status") or "UNKNOWN")
    index_obj = status_payload.get("index") if isinstance(status_payload.get("index"), dict) else {}

    rg_available = shutil.which("rg") is not None
    keyword_primary = SEARCH_ADAPTER_KEYWORD_FTS5_RG if rg_available else SEARCH_ADAPTER_KEYWORD_PYTHON
    sem_live = semantic_capability(manager, scope=scope_norm)
    sem_status = str(sem_live.get("status") or "UNAVAILABLE").strip().upper()
    sem_reason = str(sem_live.get("reason") or "").strip()
    sem_resolved = str(sem_live.get("resolved_adapter") or "").strip()
    sem_reason_out = sem_reason if sem_status != "READY" else ""

    adapters = [
        {
            "adapter_id": SEARCH_ADAPTER_KEYWORD_FTS5_RG,
            "engine": "keyword",
            "status": "READY" if rg_available else "UNAVAILABLE",
            "reason": "" if rg_available else "RG_NOT_FOUND",
            "supports_scopes": ["ssot", "repo"],
            "requires_index": True,
            "pattern_modes": ["fixed", "regex", "auto"],
            "auto_build": True,
            "tooling": {"primary": "rg", "fallback": "python"},
        },
        {
            "adapter_id": SEARCH_ADAPTER_KEYWORD_PYTHON,
            "engine": "keyword",
            "status": "READY",
            "reason": "",
            "supports_scopes": ["ssot", "repo"],
            "requires_index": True,
            "pattern_modes": ["fixed", "regex", "auto"],
            "auto_build": True,
            "tooling": {"primary": "python"},
        },
        {
            "adapter_id": SEARCH_ADAPTER_SEMANTIC_PGVECTOR,
            "engine": "semantic",
            "status": sem_status or "UNAVAILABLE",
            "reason": sem_reason_out,
            "supports_scopes": ["ssot", "repo"],
            "requires_index": False,
            "pattern_modes": [],
            "auto_build": False,
            "tooling": {
                "primary": "pgvector",
                "resolved_adapter": sem_resolved or "",
            },
        },
    ]

    return {
        "status": "OK",
        "contract_id": SEARCH_ADAPTER_CONTRACT_ID,
        "contract_version": "v1",
        "scope": scope_norm,
        "routing": {
            "default_mode": "auto",
            "supported_modes": ["auto", "keyword", "semantic"],
            "auto_mode_primary": keyword_primary,
            "auto_mode_fallback_chain": [
                SEARCH_ADAPTER_KEYWORD_FTS5_RG,
                SEARCH_ADAPTER_KEYWORD_PYTHON,
            ],
        },
        "selection": {
            "keyword_primary": keyword_primary,
            "semantic_primary": SEARCH_ADAPTER_SEMANTIC_PGVECTOR,
            "semantic_fallback": keyword_primary,
        },
        "fallback_chain": {
            "keyword": [SEARCH_ADAPTER_KEYWORD_FTS5_RG, SEARCH_ADAPTER_KEYWORD_PYTHON],
            "semantic": [
                SEARCH_ADAPTER_SEMANTIC_PGVECTOR,
                SEARCH_ADAPTER_KEYWORD_FTS5_RG,
                SEARCH_ADAPTER_KEYWORD_PYTHON,
            ],
        },
        "adapters": adapters,
        "index": {
            "status": index_status,
            "adapter_id": str(index_obj.get("adapter_id") or ""),
            "indexed_at": str(index_obj.get("indexed_at") or ""),
            "file_count": _safe_int(index_obj.get("file_count"), 0, min_value=0),
            "record_count": _safe_int(index_obj.get("record_count"), 0, min_value=0),
            "stale": bool(index_obj.get("stale")),
        },
    }
