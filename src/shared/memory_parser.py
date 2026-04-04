"""Memory file parser — reads Claude memory files with YAML frontmatter.

Parses memory files from ~/.claude/projects/*/memory/ directory.
Each file has YAML frontmatter (---name/description/type---) followed by markdown body.
MEMORY.md is a plain markdown index (no frontmatter).

Usage:
    from src.shared.memory_parser import parse_memory_file, list_memory_files, update_memory_index
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_memory_file(path: Path) -> dict[str, Any]:
    """Parse a single Claude memory file with YAML frontmatter.

    Returns: {name, description, type, body, path, filename}
    """
    result: dict[str, Any] = {
        "path": str(path),
        "filename": path.name,
        "name": "",
        "description": "",
        "type": "",
        "body": "",
    }

    if not path.exists():
        result["error"] = "file_not_found"
        return result

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        result["error"] = f"read_error: {exc}"
        return result

    # Parse YAML frontmatter (between --- markers)
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if fm_match:
        frontmatter_raw = fm_match.group(1)
        result["body"] = fm_match.group(2).strip()

        # Simple key: value parsing (no full YAML needed)
        for line in frontmatter_raw.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key in ("name", "description", "type"):
                    result[key] = value
    else:
        # No frontmatter — treat as plain body
        result["body"] = content.strip()

    return result


def list_memory_files(memory_dir: Path) -> list[dict[str, Any]]:
    """List all memory files with parsed metadata.

    Skips MEMORY.md (index file, not a memory entry).
    """
    if not memory_dir.is_dir():
        return []

    files: list[dict[str, Any]] = []
    for f in sorted(memory_dir.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        parsed = parse_memory_file(f)
        files.append(parsed)

    return files


def parse_memory_index(memory_dir: Path) -> list[dict[str, str]]:
    """Parse MEMORY.md index — extract file references and categories.

    Returns list of {filename, title, category} entries.
    """
    index_path = memory_dir / "MEMORY.md"
    if not index_path.exists():
        return []

    entries: list[dict[str, str]] = []
    current_category = ""

    for line in index_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        # Category headers: ## User, ## Feedback, ## Project — Active, etc.
        if line.startswith("## "):
            current_category = line[3:].strip()
            continue

        # Entry: - [title](filename) — description
        link_match = re.match(r"^- \[(.+?)\]\((.+?)\)", line)
        if link_match:
            title = link_match.group(1)
            filename = link_match.group(2)
            entries.append({
                "filename": filename,
                "title": title,
                "category": current_category,
            })

    return entries


def find_orphaned_files(memory_dir: Path) -> tuple[list[str], list[str]]:
    """Find orphaned files (in dir but not in index) and missing files (in index but not in dir).

    Returns: (orphaned_filenames, missing_filenames)
    """
    index_entries = parse_memory_index(memory_dir)
    indexed_files = {e["filename"] for e in index_entries}

    actual_files = set()
    if memory_dir.is_dir():
        for f in memory_dir.glob("*.md"):
            if f.name != "MEMORY.md":
                actual_files.add(f.name)

    orphaned = sorted(actual_files - indexed_files)
    missing = sorted(indexed_files - actual_files)
    return orphaned, missing


def detect_stale_projects(
    memory_dir: Path,
    *,
    stale_days: int = 30,
) -> list[dict[str, Any]]:
    """Detect active project memories that haven't been updated in stale_days.

    Uses file mtime as proxy for last update.
    """
    import time

    stale: list[dict[str, Any]] = []
    now = time.time()
    threshold = stale_days * 86400

    for f in sorted(memory_dir.glob("project_*.md")):
        if f.name == "MEMORY.md":
            continue
        parsed = parse_memory_file(f)
        if "[ARCHIVED]" in parsed.get("body", ""):
            continue  # Skip already archived

        try:
            age_seconds = int(now - f.stat().st_mtime)
            if age_seconds > threshold:
                stale.append({
                    "filename": f.name,
                    "name": parsed.get("name", ""),
                    "age_days": age_seconds // 86400,
                    "stale_threshold": stale_days,
                })
        except Exception:
            pass

    return stale
