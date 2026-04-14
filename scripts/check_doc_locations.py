#!/usr/bin/env python3
"""
Dokümanların "doğru klasörde" oluşturulup oluşturulmadığını denetler.

Problem:
- Aynı tip dokümanlar (PB/PRD/STORY/AC/TP/RB/ADR, *.api.md, *.template.md)
  bazen farklı dizinlere yazılabiliyor ve ekip/agent bunları bulmakta zorlanıyor.

Çözüm:
- Repo genelinde dosya adlarına bakarak bu dokümanların yanlış yere düşmesini
  yakalar ve hata üretir (CI gate olarak kullanılabilir).

Not:
- `.claude/` altındaki dosyalar (plans, memory, worktrees) canonical doc
  konumu değildir ve kontrol dışıdır. Worktree'ler git worktree manager
  tarafından yönetilen izole kopyalardır; canonical repo'nun SSOT kuralları
  worktree içeriğine uygulanmaz.

Kullanım:
  python3 scripts/check_doc_locations.py
  python3 scripts/check_doc_locations.py --include-legacy
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional


ROOT = Path(__file__).resolve().parents[1]

LEGACY_ROOTS = [
    ROOT / "backend" / "docs" / "legacy",
]
SKIP_DIRS = {"node_modules", ".git", ".claude", "dist", "build", "coverage", "storybook-static", "playwright-report", "test-results"}


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def is_under_any(path: Path, roots: List[Path]) -> bool:
    return any(is_under(path, r) for r in roots if r.exists())


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: str
    allowed_root: Path
    extra_allowed: Optional[Callable[[Path], bool]] = None

    def is_allowed(self, path: Path) -> bool:
        if not is_under(path, self.allowed_root):
            return False
        if self.extra_allowed is None:
            return True
        return self.extra_allowed(path)

    @property
    def expected(self) -> str:
        return f"{self.allowed_root.relative_to(ROOT)}/"


def adr_allowed(path: Path) -> bool:
    # docs/02-architecture/services/<servis>/ADR/ADR-*.md
    return path.parent.name == "ADR"


RULES: List[Rule] = [
    Rule(
        name="PB",
        pattern="PB-*.md",
        allowed_root=ROOT / "docs" / "01-product" / "PROBLEM-BRIEFS",
    ),
    Rule(
        name="PRD",
        pattern="PRD-*.md",
        allowed_root=ROOT / "docs" / "01-product" / "PRD",
    ),
    Rule(
        name="STORY",
        pattern="STORY-*.md",
        allowed_root=ROOT / "docs" / "03-delivery" / "STORIES",
    ),
    Rule(
        name="ACCEPTANCE",
        pattern="AC-*.md",
        allowed_root=ROOT / "docs" / "03-delivery" / "ACCEPTANCE",
    ),
    Rule(
        name="TEST-PLAN",
        pattern="TP-*.md",
        allowed_root=ROOT / "docs" / "03-delivery" / "TEST-PLANS",
    ),
    Rule(
        name="ADR",
        pattern="ADR-*.md",
        allowed_root=ROOT / "docs" / "02-architecture" / "services",
        extra_allowed=adr_allowed,
    ),
    Rule(
        name="RUNBOOK",
        pattern="RB-*.md",
        allowed_root=ROOT / "docs" / "04-operations" / "RUNBOOKS",
    ),
    Rule(
        name="API-DOC",
        pattern="*.api.md",
        allowed_root=ROOT / "docs" / "03-delivery" / "api",
    ),
    Rule(
        name="TEMPLATE",
        pattern="*.template.md",
        allowed_root=ROOT / "docs" / "99-templates",
    ),
]


def iter_matches(pattern: str) -> List[Path]:
    return sorted(
        p
        for p in ROOT.rglob(pattern)
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
    )


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="backend/docs/legacy altını da tarar (varsayılan: ignore).",
    )
    args = parser.parse_args(argv[1:])

    errors: List[str] = []

    for rule in RULES:
        matches = iter_matches(rule.pattern)
        for path in matches:
            if not args.include_legacy and is_under_any(path, LEGACY_ROOTS):
                continue
            if rule.is_allowed(path):
                continue
            rel = path.relative_to(ROOT)
            errors.append(f"{rule.name}: {rel} (beklenen: {rule.expected})")

    if errors:
        print("[check_doc_locations] HATA: Yanlış klasöre yazılmış dokümanlar bulundu:")
        for e in errors:
            print(f"- {e}")
        print("\nNot: Bu kontrol, dokümanların tek kaynak/tek yerde tutulmasını sağlar.")
        return 1

    print("[check_doc_locations] OK: Doküman konumları doğru ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
