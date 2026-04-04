#!/usr/bin/env python3
"""Memory sweep — automated memory hygiene for Claude Code sessions.

Triggers:
  --trigger merge       Full sweep after git merge (PostToolUse hook)
  --trigger pull        Full sweep after git pull (PostToolUse hook)
  --trigger compaction  Lightweight check after context compaction (PostCompact)
  --trigger bootstrap   Freshness check during bootstrap gate

Full sweep: index sync + stale detection + smart archive detection + duplicate check
Lightweight: index sync + stale count only (< 2 seconds)

Hook integration (.claude/settings.json):
  PostToolUse: Bash(git merge*) → python3 scripts/memory_sweep.py --trigger merge
  PostToolUse: Bash(git pull*)  → python3 scripts/memory_sweep.py --trigger pull
  PostCompact:                  → python3 scripts/memory_sweep.py --trigger compaction --lightweight
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.shared.memory_parser import (
    find_orphaned_files,
    detect_stale_projects,
    list_memory_files,
    parse_memory_index,
)
from src.shared.utils import now_iso8601


def _resolve_memory_dir() -> Path | None:
    """Resolve memory directory — env-based (R1), then fallback."""
    # 1. CLAUDE_PROJECT_DIR env var
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidate = Path(project_dir) / "memory"
        if candidate.is_dir():
            return candidate

    # 2. Standard Claude Code project path convention
    home = Path.home()
    for projects_dir in [
        home / ".claude" / "projects",
    ]:
        if projects_dir.is_dir():
            # Find project matching our repo
            for proj in projects_dir.iterdir():
                if proj.is_dir() and "autonomous-orchestrator" in proj.name:
                    mem = proj / "memory"
                    if mem.is_dir():
                        return mem

    return None


def _smart_archive_candidates(memory_dir: Path) -> list[dict[str, Any]]:
    """Detect projects that should be archived (R8 — 3 conditions).

    Conditions (ALL must be true):
    1. Memory body contains done indicators (ALL DONE, DONE, MERGED, ARCHIVED)
    2. File not modified in last 7 days
    3. Not already archived
    """
    import time

    candidates: list[dict[str, Any]] = []
    now = time.time()
    seven_days = 7 * 86400

    done_patterns = ["ALL DONE", "all done", "DONE", "MERGED", "ARCHIVED", "tamamlandı", "tamamlandi"]

    for f in sorted(memory_dir.glob("project_*.md")):
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        # Skip already archived
        if "[ARCHIVED]" in content:
            continue

        # Condition 1: Done indicators in body
        has_done = any(p in content for p in done_patterns)
        if not has_done:
            continue

        # Condition 2: Not modified recently
        try:
            age_seconds = int(now - f.stat().st_mtime)
            recent = age_seconds < seven_days
        except Exception:
            recent = True

        if recent:
            # Recently modified — might still be in progress
            continue

        # All 3 conditions met
        candidates.append({
            "filename": f.name,
            "reason": "done_indicators_found + not_recently_modified",
            "age_days": age_seconds // 86400,
        })

    return candidates


def run_sweep(
    *,
    memory_dir: Path,
    lightweight: bool = False,
    trigger: str = "manual",
) -> dict[str, Any]:
    """Run memory sweep. Returns structured report."""
    report: dict[str, Any] = {
        "version": "v1",
        "generated_at": now_iso8601(),
        "trigger": trigger,
        "lightweight": lightweight,
        "memory_dir": str(memory_dir),
    }

    # Index sync (always)
    orphaned, missing = find_orphaned_files(memory_dir)
    report["index_sync"] = {
        "orphaned_files": orphaned,
        "missing_files": missing,
        "in_sync": len(orphaned) == 0 and len(missing) == 0,
    }

    # Stale detection (always)
    stale = detect_stale_projects(memory_dir)
    report["stale_projects"] = {
        "count": len(stale),
        "projects": stale,
    }

    if lightweight:
        report["status"] = "OK" if not stale else "WARN"
        return report

    # Full sweep — archive candidates + file count
    archive_candidates = _smart_archive_candidates(memory_dir)
    all_files = list_memory_files(memory_dir)
    index_entries = parse_memory_index(memory_dir)

    report["archive_candidates"] = {
        "count": len(archive_candidates),
        "candidates": archive_candidates,
    }
    report["summary"] = {
        "total_files": len(all_files),
        "index_entries": len(index_entries),
        "active_projects": len([f for f in all_files if f["type"] == "project" and "[ARCHIVED]" not in f.get("body", "")]),
        "archived_projects": len([f for f in all_files if "[ARCHIVED]" in f.get("body", "")]),
        "feedback_entries": len([f for f in all_files if f["type"] == "feedback"]),
        "reference_entries": len([f for f in all_files if f["type"] == "reference"]),
    }

    has_issues = bool(orphaned or missing or stale or archive_candidates)
    report["status"] = "WARN" if has_issues else "OK"

    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Memory sweep — automated hygiene")
    parser.add_argument("--trigger", default="manual", choices=["merge", "pull", "compaction", "bootstrap", "manual"])
    parser.add_argument("--lightweight", action="store_true", help="Index sync + stale count only")
    parser.add_argument("--memory-dir", default=None, help="Override memory directory path")
    args = parser.parse_args()

    if args.memory_dir:
        memory_dir = Path(args.memory_dir)
    else:
        memory_dir = _resolve_memory_dir()

    if not memory_dir or not memory_dir.is_dir():
        print(json.dumps({"status": "SKIP", "reason": "memory directory not found"}))
        return 0

    lightweight = args.lightweight or args.trigger == "compaction"

    report = run_sweep(
        memory_dir=memory_dir,
        lightweight=lightweight,
        trigger=args.trigger,
    )

    # Write report
    report_path = _REPO_ROOT / ".cache" / "ws_customer_default" / ".cache" / "reports" / "memory_sweep_report.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"status": report["status"], "trigger": args.trigger, "stale": report["stale_projects"]["count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
