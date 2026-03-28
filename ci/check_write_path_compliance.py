"""CI gate: verify all file writes in src/ use canonical atomic write functions.

Scans Python files in src/ for direct file write calls (path.write_text,
path.write_bytes, open(..., "w")) that bypass the canonical wrappers in
src/shared/utils.py. Excludes the wrappers themselves and known safe patterns.

Exit codes:
    0 — compliant
    1 — violations found
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

# Files that ARE the canonical wrappers (allowed to use direct writes)
ALLOWLIST_FILES: set[str] = {
    str(SRC_DIR / "shared" / "utils.py"),
    str(SRC_DIR / "tenant" / "build_catalog.py"),
    str(SRC_DIR / "artifacts" / "store.py"),
}

# Patterns that indicate a direct (non-atomic) file write
VIOLATION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("path.write_text()", re.compile(r"\.\s*write_text\s*\(")),
    ("path.write_bytes()", re.compile(r"\.\s*write_bytes\s*\(")),
    ("open(..., 'w')", re.compile(r"open\s*\([^)]*['\"]w['\"]")),
]


def _scan_file(path: Path) -> list[dict[str, str | int]]:
    """Return list of violations in a single Python file."""
    violations: list[dict[str, str | int]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return violations

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern_name, pattern in VIOLATION_PATTERNS:
            if pattern.search(line):
                violations.append({
                    "file": str(path.relative_to(REPO_ROOT)),
                    "line": line_no,
                    "pattern": pattern_name,
                    "text": stripped[:120],
                })
    return violations


_DEFAULT_MAX_VIOLATIONS = 348  # Ratchet baseline — reduce this as call sites are migrated


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Check write path compliance in src/")
    parser.add_argument(
        "--max-violations",
        type=int,
        default=_DEFAULT_MAX_VIOLATIONS,
        help=f"Maximum allowed violations before gate fails (default: {_DEFAULT_MAX_VIOLATIONS}). "
             "Set to 0 to block all violations.",
    )
    parser.add_argument("--warn-only", action="store_true", help="Never exit 1 (legacy WARN mode)")
    args = parser.parse_args(argv)

    all_violations: list[dict[str, str | int]] = []

    for py_file in sorted(SRC_DIR.rglob("*.py")):
        if str(py_file) in ALLOWLIST_FILES:
            continue
        if "_contract_test" in py_file.name or "_test.py" in py_file.name:
            continue
        violations = _scan_file(py_file)
        all_violations.extend(violations)

    count = len(all_violations)
    exceeded = count > args.max_violations
    status = "OK" if not exceeded else "FAIL"

    report = {
        "status": status,
        "violations_count": count,
        "max_violations": args.max_violations,
        "gate": "BLOCK" if not args.warn_only else "WARN",
        "violations": all_violations[:50],
        "note": (
            f"Ratchet gate: fail if violations > {args.max_violations}. "
            "Reduce --max-violations as call sites are migrated to write_json_atomic/write_text_atomic."
        ),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if exceeded and not args.warn_only:
        print(
            f"\nFAIL: {count} direct write(s) found (max allowed: {args.max_violations}). "
            f"New violations introduced. Migrate to src.shared.utils atomic write helpers.",
            file=sys.stderr,
        )
        return 1

    if count:
        print(
            f"\nWARN: {count} direct write(s) found (within ratchet limit of {args.max_violations}).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
