#!/usr/bin/env python3
"""
Theme override allowlist/bypass guardrail.

Amaç:
- Theme Registry contract'ı bypass eden (hardcoded) apply/mapping yaklaşımlarını engellemek.
- Özellikle "surface.default.bg" için UI tarafında hardcoded cssVar listesi/LocalStorage hack'leri olmamalı.

Not:
Bu script "schema validate" yapmaz; yalnızca repo içi yasak pattern taraması yapar.

Kullanım:
  python3 scripts/check_theme_override_allowlist.py
"""

from __future__ import annotations

from pathlib import Path
import os
import re
import sys
from typing import Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]


SKIP_DIRS = {"node_modules", "dist", "build", "coverage", "test-results", ".git", ".next", ".claude"}
ALLOWED_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs"}


BANNED_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("SURFACE_COLOR_STORAGE_KEY", re.compile(r"\bSURFACE_COLOR_STORAGE_KEY\b")),
    ("mfe.surfaceColor", re.compile(r"mfe\.surfaceColor")),
    ("applySurfaceColorOverride", re.compile(r"\bapplySurfaceColorOverride\b")),
]


def iter_web_source_files() -> Iterable[Path]:
    web_root = ROOT / "web"
    if not web_root.exists():
        return []

    for dirpath, dirnames, filenames in os.walk(web_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix not in ALLOWED_EXT:
                continue
            rel = p.relative_to(ROOT)
            if str(rel).startswith("web/design-tokens/"):
                continue
            if str(rel).startswith("web/tests/"):
                continue
            yield p


def main() -> int:
    hits: List[str] = []
    for path in iter_web_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for label, pattern in BANNED_PATTERNS:
            if not pattern.search(text):
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    hits.append(f"{label}: {path.relative_to(ROOT)}:{idx}")
                    if len(hits) >= 50:
                        break
            if len(hits) >= 50:
                break
        if len(hits) >= 50:
            break

    if hits:
        print("[check_theme_override_allowlist] FAIL: registry bypass/hardcode pattern bulundu (ilk 20):")
        for h in hits[:20]:
            print(f"- {h}")
        if len(hits) > 20:
            print(f"- ... (+{len(hits) - 20})")
        return 1

    print("[check_theme_override_allowlist] OK ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

