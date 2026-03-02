"""CI gate: detect re-definition of shared utility functions in non-canonical files.

Usage:
    python ci/check_duplicate_utils.py

Exit codes:
    0 = OK (no duplicates found)
    1 = FAIL (duplicates detected)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Canonical file where these functions SHOULD live
CANONICAL_FILE = Path("src/shared/utils.py")

# Files that are explicitly allowed to contain these patterns
ALLOWED_FILES = {
    str(CANONICAL_FILE),
}

# Patterns that indicate a re-definition of a shared utility
BANNED_PATTERNS = [
    "def _load_json(",
    "def _load_json_file(",
    "def _now_iso(",
    "def _now_iso8601(",
    "def _atomic_write_text(",
    "def _atomic_write(",
    "def _write_atomic(",
    "def _sha256_file(",
    "def _sha256_text(",
    "def _parse_iso8601(",
]


def find_repo_root() -> Path:
    """Walk up from this file to find pyproject.toml."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_number, pattern, line_text) for banned patterns found."""
    hits: list[tuple[int, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return hits

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        for pattern in BANNED_PATTERNS:
            if stripped.startswith(pattern):
                hits.append((i, pattern, stripped))
    return hits


def main() -> int:
    repo_root = find_repo_root()
    src_dir = repo_root / "src"
    if not src_dir.exists():
        print("WARN: src/ directory not found, skipping check.")
        return 0

    violations: list[dict[str, object]] = []

    for py_file in sorted(src_dir.rglob("*.py")):
        rel = str(py_file.relative_to(repo_root))
        if rel in ALLOWED_FILES:
            continue
        # Skip __pycache__
        if "__pycache__" in rel:
            continue

        hits = scan_file(py_file)
        for line_no, pattern, line_text in hits:
            violations.append({
                "file": rel,
                "line": line_no,
                "pattern": pattern,
                "text": line_text,
            })

    if not violations:
        print(f"OK: No duplicate utility definitions found ({len(list(src_dir.rglob('*.py')))} files scanned).")
        return 0

    print(f"FAIL: {len(violations)} duplicate utility definition(s) found.\n")
    print("These functions should be imported from src/shared/utils.py instead:\n")

    for v in violations[:50]:  # Cap output at 50
        print(f"  {v['file']}:{v['line']}  →  {v['text']}")

    if len(violations) > 50:
        print(f"\n  ... and {len(violations) - 50} more.")

    print(f"\nFix: Replace local definitions with imports from src.shared.utils")
    print(f"See: docs/OPERATIONS/CODING-STANDARDS.md")

    # Return 0 for now (warning mode) until existing duplicates are cleaned up
    # Change to return 1 after migration is complete to enforce as hard gate
    print(f"\nMode: WARNING (existing legacy duplicates detected, hard gate disabled)")
    print(f"Total violations: {len(violations)}")
    return 0  # TODO: Change to 1 after legacy cleanup


if __name__ == "__main__":
    sys.exit(main())
