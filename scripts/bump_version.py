from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "SemVer":
        m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", s.strip())
        if not m:
            raise ValueError("Invalid version (expected X.Y.Z).")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def bump(self, part: str) -> "SemVer":
        p = part.strip().lower()
        if p == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        if p == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if p == "major":
            return SemVer(self.major + 1, 0, 0)
        raise ValueError("Invalid part (expected patch|minor|major).")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def repo_root() -> Path:
    # scripts/bump_version.py is in a top-level folder.
    return Path(__file__).resolve().parents[1]


def utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def read_pyproject_version(pyproject_text: str) -> str:
    m = re.search(r'(?m)^\s*version\s*=\s*"(?P<v>\d+\.\d+\.\d+)"\s*$', pyproject_text)
    if not m:
        raise ValueError("Could not find version in pyproject.toml (expected: version = \"X.Y.Z\").")
    return m.group("v")


def replace_pyproject_version(pyproject_text: str, *, old: str, new: str) -> str:
    pattern = re.compile(rf'(?m)^(?P<prefix>\s*version\s*=\s*")({re.escape(old)})(")\s*$')
    updated, n = pattern.subn(rf"\g<prefix>{new}\3", pyproject_text, count=1)
    if n != 1:
        raise ValueError("Failed to update version in pyproject.toml (ambiguous or missing).")
    return updated


def insert_changelog_section(changelog_text: str, *, version: str, date_str: str) -> str:
    if f"## [{version}]" in changelog_text:
        raise ValueError(f"CHANGELOG already contains version section: {version}")

    lines = changelog_text.splitlines()
    if not lines:
        raise ValueError("CHANGELOG.md is empty.")

    # Insert after the first heading line.
    insert_at = 1
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1

    section = [
        "",
        f"## [{version}] - {date_str}",
        "- (add release notes here)",
        "",
    ]

    out = lines[:insert_at] + section + lines[insert_at:]
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/bump_version.py")
    ap.add_argument("--part", required=True, choices=["patch", "minor", "major"])
    args = ap.parse_args(argv)

    root = repo_root()
    pyproject_path = root / "pyproject.toml"
    changelog_path = root / "CHANGELOG.md"

    if not pyproject_path.exists():
        print("ERROR: Missing pyproject.toml", file=sys.stderr)
        return 2
    if not changelog_path.exists():
        print("ERROR: Missing CHANGELOG.md", file=sys.stderr)
        return 2

    py_text = pyproject_path.read_text(encoding="utf-8")
    old_v = read_pyproject_version(py_text)
    old = SemVer.parse(old_v)
    new = old.bump(str(args.part))
    new_v = str(new)

    py_updated = replace_pyproject_version(py_text, old=old_v, new=new_v)
    pyproject_path.write_text(py_updated, encoding="utf-8")

    cl_text = changelog_path.read_text(encoding="utf-8")
    cl_updated = insert_changelog_section(cl_text, version=new_v, date_str=utc_date())
    changelog_path.write_text(cl_updated, encoding="utf-8")

    print(new_v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
