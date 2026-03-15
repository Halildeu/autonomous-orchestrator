#!/usr/bin/env python3
"""Initialize context bootstrap structure for managed repos.

Creates the 3-tier context bootstrap directory structure and seed files
so that AI agents can immediately begin context loading in managed repos.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


# Tier 1: Status context — workspace-relative cache structure
TIER_1_DIRS = [
    ".cache/ws_customer_default/.cache/reports",
]

# Tier 2: Structural context — repo-root files that must exist
TIER_2_FILES = [
    "AGENTS.md",
]

# Tier 3: Governance context — synced from core repo
TIER_3_DIRS = [
    "docs/OPERATIONS",
]


def _seed_system_status(workspace_reports: Path) -> dict[str, Any]:
    """Create minimal system_status.v1.json seed if missing."""
    status_path = workspace_reports / "system_status.v1.json"
    if status_path.exists():
        return {"path": str(status_path), "action": "exists"}

    seed = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": "BOOTSTRAP",
        "summary": "Managed repo initialized — awaiting first system-status run.",
        "subsystems": [],
        "errors": [],
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(status_path), "action": "created"}


def _seed_portfolio_status(workspace_reports: Path) -> dict[str, Any]:
    """Create minimal portfolio_status.v1.json seed if missing."""
    port_path = workspace_reports / "portfolio_status.v1.json"
    if port_path.exists():
        return {"path": str(port_path), "action": "exists"}

    seed = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": "BOOTSTRAP",
        "summary": "Managed repo initialized — awaiting first portfolio-status run.",
        "projects": [],
    }
    port_path.parent.mkdir(parents=True, exist_ok=True)
    port_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(port_path), "action": "created"}


def init_bootstrap(
    *,
    target_root: Path,
    apply: bool = False,
) -> dict[str, Any]:
    """Initialize context bootstrap structure for a managed repo."""
    actions: list[dict[str, Any]] = []

    # Tier 1: Create workspace cache directories
    for rel_dir in TIER_1_DIRS:
        dir_path = target_root / rel_dir
        if dir_path.exists():
            actions.append({"path": rel_dir, "action": "exists", "tier": 1})
        elif apply:
            dir_path.mkdir(parents=True, exist_ok=True)
            actions.append({"path": rel_dir, "action": "created", "tier": 1})
        else:
            actions.append({"path": rel_dir, "action": "would_create", "tier": 1})

    # Tier 1: Seed status files
    reports_dir = target_root / ".cache" / "ws_customer_default" / ".cache" / "reports"
    if apply:
        reports_dir.mkdir(parents=True, exist_ok=True)
        actions.append({"tier": 1, **_seed_system_status(reports_dir)})
        actions.append({"tier": 1, **_seed_portfolio_status(reports_dir)})
    else:
        for name in ["system_status.v1.json", "portfolio_status.v1.json"]:
            p = reports_dir / name
            if p.exists():
                actions.append({"path": str(p), "action": "exists", "tier": 1})
            else:
                actions.append({"path": str(p), "action": "would_create", "tier": 1})

    # Tier 2: Check structural files
    for rel_file in TIER_2_FILES:
        file_path = target_root / rel_file
        if file_path.exists():
            actions.append({"path": rel_file, "action": "exists", "tier": 2})
        else:
            actions.append({"path": rel_file, "action": "missing", "tier": 2})

    # Tier 3: Create governance directories
    for rel_dir in TIER_3_DIRS:
        dir_path = target_root / rel_dir
        if dir_path.exists():
            actions.append({"path": rel_dir, "action": "exists", "tier": 3})
        elif apply:
            dir_path.mkdir(parents=True, exist_ok=True)
            actions.append({"path": rel_dir, "action": "created", "tier": 3})
        else:
            actions.append({"path": rel_dir, "action": "would_create", "tier": 3})

    # Generate bootstrap report
    report_path = target_root / ".cache" / "reports" / "context_bootstrap_init.v1.json"
    report = {
        "version": "v1",
        "kind": "context-bootstrap-init-report",
        "generated_at": _now_iso(),
        "target_root": str(target_root),
        "mode": "apply" if apply else "dry-run",
        "actions": actions,
    }
    if apply:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return report


def init_for_manifest(
    *,
    manifest_path: Path,
    apply: bool = False,
) -> dict[str, Any]:
    """Initialize bootstrap for all managed repos in a manifest."""
    manifest = _load_json(manifest_path)
    repos = manifest.get("repos")
    if not isinstance(repos, list):
        return {"status": "FAIL", "error": "INVALID_MANIFEST", "results": []}

    results: list[dict[str, Any]] = []
    for item in repos:
        if not isinstance(item, dict):
            continue
        repo_root = item.get("repo_root")
        if not isinstance(repo_root, str) or not repo_root.strip():
            continue
        target = Path(repo_root.strip()).expanduser().resolve()
        result = init_bootstrap(target_root=target, apply=apply)
        results.append(result)

    return {
        "status": "OK",
        "mode": "apply" if apply else "dry-run",
        "total": len(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize context bootstrap for managed repos")
    parser.add_argument("--target-repo-root", action="append", default=[], help="Target repo (repeatable)")
    parser.add_argument("--manifest-path", default="", help="Managed repos manifest path")
    parser.add_argument("--apply", action="store_true", help="Apply (create dirs/seeds)")
    args = parser.parse_args(argv)

    if args.manifest_path:
        manifest = Path(args.manifest_path).expanduser().resolve()
        result = init_for_manifest(manifest_path=manifest, apply=bool(args.apply))
    elif args.target_repo_root:
        results = []
        for raw in args.target_repo_root:
            target = Path(raw.strip()).expanduser().resolve()
            r = init_bootstrap(target_root=target, apply=bool(args.apply))
            results.append(r)
        result = {
            "status": "OK",
            "mode": "apply" if args.apply else "dry-run",
            "total": len(results),
            "results": results,
        }
    else:
        result = {"status": "FAIL", "error": "TARGET_REQUIRED"}

    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("status") != "FAIL" else 2


if __name__ == "__main__":
    sys.exit(main())
