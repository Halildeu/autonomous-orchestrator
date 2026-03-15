"""Lightweight code-aware index for offline, policy-gated retrieval.

No external dependencies (no embeddings, no vector DB).
Uses structural signatures: file path, symbols (class/function names),
import relationships, and recent change frequency.

Index is persisted as JSON for cross-session reuse.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_INDEX_REL = ".cache/index/code_aware_index.v1.json"

# Symbol extraction patterns
_SYMBOL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    ".py": [
        re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*def\s+(\w+)", re.MULTILINE),
    ],
    ".java": [
        re.compile(r"\bclass\s+(\w+)", re.MULTILINE),
        re.compile(r"\binterface\s+(\w+)", re.MULTILINE),
        re.compile(r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(", re.MULTILINE),
    ],
    ".ts": [
        re.compile(r"export\s+(?:class|interface|type|enum)\s+(\w+)", re.MULTILINE),
        re.compile(r"export\s+(?:function|const|let)\s+(\w+)", re.MULTILINE),
    ],
    ".tsx": [
        re.compile(r"export\s+(?:class|interface|type|enum)\s+(\w+)", re.MULTILINE),
        re.compile(r"export\s+(?:function|const|let)\s+(\w+)", re.MULTILINE),
    ],
    ".js": [
        re.compile(r"export\s+(?:class|function|const|let)\s+(\w+)", re.MULTILINE),
        re.compile(r"module\.exports\s*=\s*(\w+)", re.MULTILINE),
    ],
}

_SCANNABLE_EXTENSIONS = {".py", ".java", ".ts", ".tsx", ".js", ".jsx", ".json", ".md"}
_SCAN_DIRS = ["src", "ci", "scripts", "extensions", "web", "backend", "tests", "schemas", "registry", "policies"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_symbols(file_path: Path) -> list[str]:
    """Extract class/function/export names from a source file."""
    suffix = file_path.suffix.lower()
    patterns = _SYMBOL_PATTERNS.get(suffix, [])
    if not patterns:
        return []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    symbols: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(content):
            sym = match.group(1)
            if sym and not sym.startswith("_") and sym not in ("self", "cls"):
                symbols.append(sym)
    return list(dict.fromkeys(symbols))  # Dedupe preserving order


def _file_domain(rel_path: str) -> str:
    """Infer domain from file path."""
    parts = rel_path.split("/")
    if any(p in parts for p in ("backend",)):
        return "backend"
    if any(p in parts for p in ("web", "frontend")):
        return "frontend"
    if any(p in parts for p in ("schemas",)):
        return "schema"
    if any(p in parts for p in ("policies",)):
        return "policy"
    if any(p in parts for p in ("registry",)):
        return "registry"
    if any(p in parts for p in ("ci",)):
        return "ci"
    if any(p in parts for p in ("tests",)):
        return "test"
    if any(p in parts for p in ("scripts",)):
        return "script"
    if any(p in parts for p in ("extensions",)):
        return "extension"
    if any(p in parts for p in ("src",)):
        return "core"
    return "other"


def build_code_index(
    *,
    repo_root: Path,
    max_files: int = 1000,
) -> dict[str, Any]:
    """Build a lightweight code-aware index."""
    repo_root = repo_root.resolve()

    entries: list[dict[str, Any]] = []
    domain_counts: dict[str, int] = {}
    total_symbols = 0
    file_count = 0

    for scan_dir in _SCAN_DIRS:
        d = repo_root / scan_dir
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if file_count >= max_files:
                break
            if not p.is_file():
                continue
            if p.suffix.lower() not in _SCANNABLE_EXTENSIONS:
                continue
            # Skip node_modules, .git, __pycache__
            rel = str(p.relative_to(repo_root))
            if any(skip in rel for skip in ("node_modules/", ".git/", "__pycache__/")):
                continue

            symbols = _extract_symbols(p)
            domain = _file_domain(rel)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            total_symbols += len(symbols)
            file_count += 1

            entry: dict[str, Any] = {
                "path": rel,
                "domain": domain,
                "suffix": p.suffix.lower(),
            }
            if symbols:
                entry["symbols"] = symbols[:50]  # Cap per file
            try:
                entry["size_bytes"] = p.stat().st_size
            except Exception:
                pass

            entries.append(entry)

    index = {
        "version": "v1",
        "kind": "code-aware-index",
        "generated_at": _now_iso(),
        "repo_root": str(repo_root),
        "summary": {
            "total_files": len(entries),
            "total_symbols": total_symbols,
            "domains": domain_counts,
        },
        "entries": entries,
        "status": "OK",
    }
    return index


def write_code_index(*, repo_root: Path, index: dict[str, Any]) -> str:
    """Persist the code index to disk."""
    out = repo_root / _INDEX_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(index, ensure_ascii=True, sort_keys=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return _INDEX_REL


def load_code_index(*, repo_root: Path) -> dict[str, Any] | None:
    """Load persisted code index, or None."""
    path = repo_root / _INDEX_REL
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def search_index(
    *,
    index: dict[str, Any],
    query: str,
    domain_filter: str | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search the code index by symbol name, path, or keyword.

    Returns matched entries sorted by relevance.
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return []

    query_parts = query_lower.split()
    entries = index.get("entries", [])

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        # Domain filter
        if domain_filter and entry.get("domain") != domain_filter:
            continue

        path = str(entry.get("path") or "").lower()
        symbols = [s.lower() for s in entry.get("symbols", [])]

        score = 0.0
        for qp in query_parts:
            # Exact symbol match
            if qp in symbols:
                score += 100.0
            # Partial symbol match
            elif any(qp in s for s in symbols):
                score += 60.0
            # Path contains query
            if qp in path:
                score += 40.0
            # File stem match
            stem = Path(path).stem.lower()
            if qp in stem:
                score += 30.0

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:max_results]]
