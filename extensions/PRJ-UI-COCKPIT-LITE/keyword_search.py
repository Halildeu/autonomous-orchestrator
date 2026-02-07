from __future__ import annotations

# Compatibility shim: Search backend migrated to PRJ-SEARCH.
# Keep this module so existing imports in Cockpit server/tests do not break.

import importlib.util
import sys
from pathlib import Path

_ADAPTER_PATH = Path(__file__).resolve().parents[1] / "PRJ-SEARCH" / "search_adapter.py"
_SPEC = importlib.util.spec_from_file_location("prj_search.search_adapter", _ADAPTER_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"search_adapter module spec not available: {_ADAPTER_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

KeywordIndexManager = _MODULE.KeywordIndexManager
SEARCH_ADAPTER_CONTRACT_ID = _MODULE.SEARCH_ADAPTER_CONTRACT_ID
SEARCH_ADAPTER_KEYWORD_FTS5_RG = _MODULE.SEARCH_ADAPTER_KEYWORD_FTS5_RG
SEARCH_ADAPTER_KEYWORD_PYTHON = _MODULE.SEARCH_ADAPTER_KEYWORD_PYTHON
SEARCH_ADAPTER_SEMANTIC_PGVECTOR = _MODULE.SEARCH_ADAPTER_SEMANTIC_PGVECTOR

__all__ = [
    "KeywordIndexManager",
    "SEARCH_ADAPTER_CONTRACT_ID",
    "SEARCH_ADAPTER_KEYWORD_FTS5_RG",
    "SEARCH_ADAPTER_KEYWORD_PYTHON",
    "SEARCH_ADAPTER_SEMANTIC_PGVECTOR",
]
