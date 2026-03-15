"""Context enrichment: hot files, import graph, and file ownership signals.

Enriches agent context with:
1. Hot files — most frequently changed files in recent git history
2. Import graph — lightweight regex-based dependency mapping
3. File ownership — dominant author per file via git blame aggregate
"""
from __future__ import annotations

import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_OUTPUT_REL = ".cache/index/context_enrichment.v1.json"

# Import patterns per language
_IMPORT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    ".java": [
        re.compile(r"^\s*import\s+([\w.]+)\s*;", re.MULTILINE),
    ],
    ".ts": [
        re.compile(r"""from\s+['"]([^'"]+)['"]""", re.MULTILINE),
        re.compile(r"""import\s+['"]([^'"]+)['"]""", re.MULTILINE),
    ],
    ".tsx": [
        re.compile(r"""from\s+['"]([^'"]+)['"]""", re.MULTILINE),
        re.compile(r"""import\s+['"]([^'"]+)['"]""", re.MULTILINE),
    ],
    ".py": [
        re.compile(r"^\s*from\s+([\w.]+)\s+import", re.MULTILINE),
        re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE),
    ],
    ".js": [
        re.compile(r"""from\s+['"]([^'"]+)['"]""", re.MULTILINE),
        re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]""", re.MULTILINE),
    ],
}


def _run_git(args: list[str], cwd: Path, timeout: int = 30) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 1. Hot Files
# ---------------------------------------------------------------------------

def compute_hot_files(
    *,
    repo_root: Path,
    days: int = 7,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Return the top_n most changed files in the last `days` days."""
    repo_root = repo_root.resolve()
    since = f"--since={days} days ago"
    output = _run_git(["log", since, "--name-only", "--pretty=format:"], repo_root)

    if not output.strip():
        return []

    counter: Counter[str] = Counter()
    for line in output.splitlines():
        line = line.strip()
        if line and not line.startswith("commit "):
            counter[line] += 1

    result: list[dict[str, Any]] = []
    for path, count in counter.most_common(top_n):
        full = repo_root / path
        result.append({
            "path": path,
            "change_count": count,
            "exists": full.exists(),
        })
    return result


# ---------------------------------------------------------------------------
# 2. Hot Tests
# ---------------------------------------------------------------------------

def compute_hot_tests(
    *,
    repo_root: Path,
    days: int = 7,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Return most changed test files in recent history."""
    repo_root = repo_root.resolve()
    since = f"--since={days} days ago"
    output = _run_git(["log", since, "--name-only", "--pretty=format:"], repo_root)

    if not output.strip():
        return []

    test_patterns = re.compile(r"(test_|_test\.|\.test\.|\.spec\.|Test\.java|Tests\.java)", re.IGNORECASE)
    counter: Counter[str] = Counter()
    for line in output.splitlines():
        line = line.strip()
        if line and test_patterns.search(line):
            counter[line] += 1

    return [{"path": p, "change_count": c} for p, c in counter.most_common(top_n)]


# ---------------------------------------------------------------------------
# 3. Import Graph (lightweight, regex-based)
# ---------------------------------------------------------------------------

def _extract_imports(file_path: Path) -> list[str]:
    """Extract import targets from a source file using regex patterns."""
    suffix = file_path.suffix.lower()
    patterns = _IMPORT_PATTERNS.get(suffix, [])
    if not patterns:
        return []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    imports: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(content):
            imports.append(match.group(1))
    return imports


def compute_import_graph(
    *,
    repo_root: Path,
    scope_paths: list[str] | None = None,
    max_files: int = 500,
) -> dict[str, list[str]]:
    """Build a lightweight import graph for source files.

    Args:
        repo_root: Repository root
        scope_paths: Glob patterns to limit scope (e.g. ["src/**/*.py", "web/**/*.ts"])
        max_files: Maximum files to scan
    """
    repo_root = repo_root.resolve()
    extensions = set(_IMPORT_PATTERNS.keys())

    files: list[Path] = []
    if scope_paths:
        import glob as glob_mod
        for pattern in scope_paths:
            for match in glob_mod.glob(str(repo_root / pattern), recursive=True):
                p = Path(match)
                if p.is_file() and p.suffix.lower() in extensions:
                    files.append(p)
    else:
        # Default: scan src/, web/, backend/, extensions/
        for scan_dir in ["src", "web", "backend", "extensions", "ci", "scripts"]:
            d = repo_root / scan_dir
            if d.is_dir():
                for p in d.rglob("*"):
                    if p.is_file() and p.suffix.lower() in extensions:
                        files.append(p)

    # Limit
    files = files[:max_files]

    graph: dict[str, list[str]] = {}
    for f in files:
        rel = str(f.relative_to(repo_root))
        imports = _extract_imports(f)
        if imports:
            graph[rel] = imports

    return graph


def compute_neighbors(
    *,
    import_graph: dict[str, list[str]],
    target_files: list[str],
    depth: int = 1,
) -> list[str]:
    """Find files connected to target_files in the import graph (up to depth hops)."""
    # Build reverse graph
    reverse: dict[str, set[str]] = defaultdict(set)
    for src, imports in import_graph.items():
        for imp in imports:
            reverse[imp].add(src)

    visited: set[str] = set()
    frontier: set[str] = set(target_files)

    for _ in range(depth):
        next_frontier: set[str] = set()
        for f in frontier:
            if f in visited:
                continue
            visited.add(f)
            # Forward: files this file imports
            for imp in import_graph.get(f, []):
                for graph_file in import_graph:
                    if imp in graph_file or graph_file.endswith(imp.replace(".", "/") + ".py"):
                        next_frontier.add(graph_file)
            # Reverse: files that import this file
            for importer in reverse.get(f, set()):
                next_frontier.add(importer)
            # Also check partial matches
            base = Path(f).stem
            for importer, imports in import_graph.items():
                for imp in imports:
                    if base in imp:
                        next_frontier.add(importer)
        frontier = next_frontier - visited

    return sorted(visited | frontier - set(target_files))


# ---------------------------------------------------------------------------
# 4. File Ownership
# ---------------------------------------------------------------------------

def compute_file_ownership(
    *,
    repo_root: Path,
    target_files: list[str] | None = None,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Compute dominant author per file using git shortlog."""
    repo_root = repo_root.resolve()

    if target_files is None:
        # Use hot files as targets
        hot = compute_hot_files(repo_root=repo_root, days=30, top_n=top_n)
        target_files = [h["path"] for h in hot if h.get("exists")]

    results: list[dict[str, Any]] = []
    for rel in target_files[:top_n]:
        output = _run_git(["shortlog", "-sne", "--", rel], repo_root)
        if not output.strip():
            continue
        authors: list[dict[str, Any]] = []
        for line in output.strip().splitlines():
            line = line.strip()
            parts = line.split("\t", 1)
            if len(parts) == 2:
                count = int(parts[0].strip())
                author = parts[1].strip()
                authors.append({"author": author, "commits": count})

        if authors:
            results.append({
                "path": rel,
                "dominant_author": authors[0]["author"],
                "total_authors": len(authors),
                "authors": authors[:3],  # Top 3
            })

    return results


# ---------------------------------------------------------------------------
# 5. Full Enrichment Report
# ---------------------------------------------------------------------------

def build_context_enrichment_report(
    *,
    repo_root: Path,
    days: int = 7,
    top_n: int = 20,
    scope_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Build a complete context enrichment report."""
    from datetime import datetime, timezone

    repo_root = repo_root.resolve()

    hot_files = compute_hot_files(repo_root=repo_root, days=days, top_n=top_n)
    hot_tests = compute_hot_tests(repo_root=repo_root, days=days, top_n=10)
    import_graph = compute_import_graph(repo_root=repo_root, scope_paths=scope_paths)
    ownership = compute_file_ownership(repo_root=repo_root, top_n=top_n)

    # Compute neighbors for hot files
    hot_paths = [h["path"] for h in hot_files[:10]]
    neighbors = compute_neighbors(import_graph=import_graph, target_files=hot_paths) if hot_paths else []

    return {
        "version": "v1",
        "kind": "context-enrichment-report",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo_root": str(repo_root),
        "config": {"days": days, "top_n": top_n},
        "hot_files": hot_files,
        "hot_tests": hot_tests,
        "import_graph_summary": {
            "total_files_scanned": len(import_graph),
            "total_edges": sum(len(v) for v in import_graph.values()),
        },
        "hot_file_neighbors": neighbors[:30],
        "file_ownership": ownership,
        "status": "OK",
    }
