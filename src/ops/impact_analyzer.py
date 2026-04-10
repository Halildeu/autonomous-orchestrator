"""Impact analyzer — lightweight grep-based import chain traversal.

Analyzes which files import/are imported by a target file to estimate
the blast radius of a change. No embedding or AST parsing — pure grep.

Usage:
    from src.ops.impact_analyzer import analyze_impact
    result = analyze_impact(repo_root, "src/ops/context_compiler.py")
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_DEPTH = 3
_MAX_RESULTS = 50


def analyze_impact(
    repo_root: Path,
    target_path: str,
    *,
    max_depth: int = _MAX_DEPTH,
) -> dict[str, Any]:
    """Analyze import chain impact for a target file.

    Returns direct importers, direct imports, affected tests, and risk level.
    """
    target = Path(target_path)
    module_name = _path_to_module(target_path)
    basename = target.stem

    # Find direct importers (files that import this module)
    direct_importers = _find_importers(repo_root, module_name, basename, target_path)

    # Find direct imports (modules this file imports)
    direct_imports = _find_imports(repo_root, target_path)

    # Find affected tests
    affected_tests = _find_affected_tests(repo_root, module_name, basename)

    # Risk assessment
    affected_count = len(direct_importers) + len(affected_tests)
    risk_level = _assess_risk(affected_count)

    return {
        "target": target_path,
        "direct_importers": direct_importers[:_MAX_RESULTS],
        "direct_imports": direct_imports[:_MAX_RESULTS],
        "affected_tests": affected_tests[:_MAX_RESULTS],
        "affected_count": affected_count,
        "risk_level": risk_level,
    }


# ── Internal helpers ────────────────────────────────────────────


def _path_to_module(path: str) -> str:
    """Convert file path to Python module path. src/ops/foo.py → src.ops.foo"""
    clean = path.replace("/", ".").replace("\\", ".")
    if clean.endswith(".py"):
        clean = clean[:-3]
    return clean


def _find_importers(repo_root: Path, module_name: str, basename: str, target_path: str) -> list[str]:
    """Find files that import the target module (grep-based)."""
    importers: list[str] = []

    # Patterns to search for
    patterns = []
    if module_name:
        # from src.ops.context_compiler import ...
        patterns.append(re.compile(rf"from\s+{re.escape(module_name)}\s+import"))
        # import src.ops.context_compiler
        patterns.append(re.compile(rf"import\s+{re.escape(module_name)}"))
    if basename:
        # from .context_compiler import ... (relative import)
        patterns.append(re.compile(rf"from\s+\.{re.escape(basename)}\s+import"))

    # Scan Python files
    for py_file in _iter_python_files(repo_root):
        rel = str(py_file.relative_to(repo_root))
        if rel == target_path:
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if pattern.search(content):
                    importers.append(rel)
                    break
        except Exception:
            continue

    return sorted(importers)


def _find_imports(repo_root: Path, target_path: str) -> list[str]:
    """Find modules that the target file imports."""
    full_path = repo_root / target_path
    if not full_path.exists():
        return []

    imports: list[str] = []
    import_re = re.compile(r"^\s*(?:from|import)\s+([\w.]+)")

    try:
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            m = import_re.match(line)
            if m:
                mod = m.group(1)
                if mod.startswith("src.") or mod.startswith("ci."):
                    imports.append(mod)
    except Exception:
        pass

    return sorted(set(imports))


def _find_affected_tests(repo_root: Path, module_name: str, basename: str) -> list[str]:
    """Find test files that reference the target module."""
    tests: list[str] = []
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return []

    search_terms = [module_name, basename] if module_name else [basename]

    for test_file in tests_dir.rglob("test_*.py"):
        try:
            content = test_file.read_text(encoding="utf-8", errors="ignore")
            if any(term in content for term in search_terms if term):
                tests.append(str(test_file.relative_to(repo_root)))
        except Exception:
            continue

    return sorted(tests)


def _iter_python_files(repo_root: Path):
    """Iterate Python files in src/, scripts/, ci/ (skip .cache, node_modules)."""
    scan_dirs = ["src", "scripts", "ci"]
    for d in scan_dirs:
        dir_path = repo_root / d
        if dir_path.is_dir():
            yield from dir_path.rglob("*.py")


def _assess_risk(affected_count: int) -> str:
    """Assess change risk based on affected file count."""
    if affected_count <= 3:
        return "LOW"
    elif affected_count <= 8:
        return "MEDIUM"
    elif affected_count <= 20:
        return "HIGH"
    else:
        return "CRITICAL"
