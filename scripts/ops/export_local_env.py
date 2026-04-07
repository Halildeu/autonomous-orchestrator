#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SHARED_FALLBACK_FILES = [
    ROOT.parent / "autonomous-orchestrator" / ".env.local",
    ROOT.parent / "autonomous-orchestrator" / ".env",
]
DEFAULT_FILES = [
    ROOT / ".env.local",
    ROOT / ".env",
    ROOT / "backend" / ".env.local",
    ROOT / "backend" / ".env",
    ROOT / "web" / ".env.local",
    ROOT / "web" / ".env",
    *SHARED_FALLBACK_FILES,
]

ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def parse_value(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if text[0] in {"'", '"'} and text[-1] == text[0]:
        return text[1:-1]
    if " #" in text:
        text = text.split(" #", 1)[0].rstrip()
    return text


def load_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return values

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        values[key] = parse_value(raw_value)
    return values


def iter_env_files() -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for path in DEFAULT_FILES:
        resolved = path.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            files.append(resolved)

    raw_extra = (os.environ.get("LOCAL_ENV_FALLBACK_FILES") or "").strip()
    if raw_extra:
        for item in raw_extra.split(os.pathsep):
            candidate = Path(item).expanduser()
            if candidate not in seen:
                seen.add(candidate)
                files.append(candidate)

    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="+")
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()

    merged: dict[str, str] = {}
    for env_file in iter_env_files():
        merged.update(load_file(env_file))

    exports: list[str] = []
    for key in args.keys:
        value = os.environ.get(key)
        if value is None:
            value = merged.get(key)
        if value is None:
            continue
        if value == "" and not args.allow_empty:
            continue
        exports.append(f"export {key}={shlex.quote(value)}")

    print("\n".join(exports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
