#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(".")

# .claude (plans, memory, worktrees), legacy archives, node_modules etc.
# are NOT canonical doc locations. Worktrees especially are git-managed
# isolated copies; canonical SSOT rules do not apply to their contents.
SKIP_DIRS = {".git", ".claude", "node_modules", "dist", "build", "coverage",
             "storybook-static", "playwright-report", "test-results",
             "backend/docs/legacy"}


def _is_under_skip(p: Path) -> bool:
    parts = set(p.parts)
    if parts & SKIP_DIRS:
        return True
    # Also check multi-segment skip paths (e.g. backend/docs/legacy)
    s = p.as_posix()
    return any("/" in skip and skip in s for skip in SKIP_DIRS)


RULES = [
    ("PB", re.compile(r"^PB-\d{4}.*\.md$"), Path("docs/01-product/PROBLEM-BRIEFS")),
    ("PRD", re.compile(r"^PRD-\d{4}.*\.md$"), Path("docs/01-product/PRD")),
    ("BM", re.compile(r"^BM-\d{4}.*\.md$"), Path("docs/01-product/BUSINESS-MASTERS")),
    ("BENCH", re.compile(r"^BENCH-\d{4}.*\.md$"), Path("docs/01-product/BENCHMARKS")),
    ("SPEC", re.compile(r"^SPEC-\d{4}.*\.md$"), Path("docs/03-delivery/SPECS")),
    ("STORY", re.compile(r"^STORY-\d{4}.*\.md$"), Path("docs/03-delivery/STORIES")),
    ("AC", re.compile(r"^AC-\d{4}.*\.md$"), Path("docs/03-delivery/ACCEPTANCE")),
    ("TP", re.compile(r"^TP-\d{4}.*\.md$"), Path("docs/03-delivery/TEST-PLANS")),
    ("GUIDE", re.compile(r"^GUIDE-\d{4}.*\.md$"), Path("docs/03-delivery/guides")),
    ("RB", re.compile(r"^RB-.*\.md$"), Path("docs/04-operations/RUNBOOKS")),
    ("TRACE", re.compile(r"^TRACE-\d{4}.*\.tsv$"), Path("docs/03-delivery/TRACES")),
]

ADR_RE = re.compile(r"^ADR-\d{4}.*\.md$")


def posix_path(p: Path) -> str:
    return p.as_posix()


def main() -> int:
    bad: list[tuple[str, str, str]] = []

    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if _is_under_skip(p):
            continue

        name = p.name

        # ADR özel kural
        if ADR_RE.match(name):
            rel = posix_path(p.relative_to(ROOT))
            expected_prefix = "docs/02-architecture/services/"
            ok = rel.startswith(expected_prefix) and "/ADR/" in rel
            if not ok:
                bad.append((rel, "ADR", "expected under docs/02-architecture/services/<svc>/ADR/"))
            continue

        for key, rx, base in RULES:
            if not rx.match(name):
                continue
            rel = posix_path(p.relative_to(ROOT))
            base_prefix = posix_path(base) + "/"
            if not rel.startswith(base_prefix):
                bad.append((rel, key, f"expected under {posix_path(base)}/"))
            break

    if bad:
        print("[check_doc_routing_strict] FAIL: routing violations:")
        for path, key, exp in bad[:200]:
            print(f"- {key}: {path} -> {exp}")
        if len(bad) > 200:
            print(f"- ... ({len(bad) - 200} more)")
        return 1

    print("[check_doc_routing_strict] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
