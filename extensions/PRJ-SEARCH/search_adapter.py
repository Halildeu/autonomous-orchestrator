from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

# NOTE: This module is loaded both as a normal import and via spec_from_file_location.
# Keep sibling imports robust by ensuring this directory is importable.
_MODULE_DIR = Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

import search_adapter_capabilities as _capabilities
import search_adapter_index as _index
import search_adapter_query as _query
import search_adapter_semantic as _semantic
from search_adapter_core import (
    SEARCH_ADAPTER_CONTRACT_ID,
    SEARCH_ADAPTER_KEYWORD_FTS5_RG,
    SEARCH_ADAPTER_KEYWORD_PYTHON,
    SEARCH_ADAPTER_SEMANTIC_PGVECTOR,
    ScopeSpec,
)


class KeywordIndexManager:
    def __init__(self, repo_root: Path, workspace_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.workspace_root = workspace_root.resolve()
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    # Backward-compatible internal API retained for existing callers.
    def _paths(self, scope: str) -> dict[str, Path]:
        return _index.paths(self, scope)

    def _scope_spec(self, scope: str, *, max_file_bytes: int) -> ScopeSpec:
        return _index.scope_spec(self, scope, max_file_bytes=max_file_bytes)

    def _read_json_if_exists(self, path: Path) -> dict[str, Any] | None:
        return _index.read_json_if_exists(path)

    def _update_history(self, history_path: Path, *, manifest: dict[str, Any]) -> dict[str, Any]:
        return _index.update_history(history_path, manifest=manifest)

    def _predict_eta_seconds(self, *, manifest: dict[str, Any] | None, history: dict[str, Any] | None) -> int | None:
        return _index.predict_eta_seconds(manifest=manifest, history=history)

    # Sub-module boundaries: index, capabilities, query.
    def status(self, scope: str) -> dict[str, Any]:
        return _index.status(self, scope)

    def capabilities(self, scope: str = "ssot") -> dict[str, Any]:
        return _capabilities.capabilities(self, scope=scope)

    def start_build(
        self,
        scope: str,
        *,
        force: bool = False,
        max_files: int = 0,
        max_file_bytes: int = 524288,
    ) -> dict[str, Any]:
        return _index.start_build(
            self,
            scope,
            force=force,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
        )

    def search(
        self,
        query: str,
        *,
        scope: str = "ssot",
        search_mode: str = "auto",
        pattern_mode: str = "auto",
        limit: int = 80,
        auto_build: bool = True,
    ) -> dict[str, Any]:
        return _query.search(
            self,
            query,
            scope=scope,
            search_mode=search_mode,
            pattern_mode=pattern_mode,
            limit=limit,
            auto_build=auto_build,
        )

    def semantic_index_status(self, scope: str = "ssot") -> dict[str, Any]:
        return _semantic.semantic_index_status(self, scope=scope)

    def semantic_index_build(
        self,
        *,
        scope: str = "ssot",
        rebuild: bool = False,
        chunk_size: int = 1200,
        max_files: int = 600,
        max_bytes: int = 6_000_000,
        max_file_bytes: int = 524288,
    ) -> dict[str, Any]:
        return _semantic.semantic_index_build(
            self,
            scope=scope,
            rebuild=rebuild,
            chunk_size=chunk_size,
            max_files=max_files,
            max_bytes=max_bytes,
            max_file_bytes=max_file_bytes,
        )


__all__ = [
    "KeywordIndexManager",
    "SEARCH_ADAPTER_CONTRACT_ID",
    "SEARCH_ADAPTER_KEYWORD_FTS5_RG",
    "SEARCH_ADAPTER_KEYWORD_PYTHON",
    "SEARCH_ADAPTER_SEMANTIC_PGVECTOR",
]
