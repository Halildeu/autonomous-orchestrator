#!/usr/bin/env python3
"""Tech stack auto-discovery — parse versions from dev repo package.json.

Resolves dev repo path from .cache/managed_repos.v1.json (R2 — registry-first).
Extracts critical dependency versions and writes to:
  - .cache/reports/tech_stack_discovery.v1.json (structured artifact)
  - Updates reference_tech_stack.md memory (if writable)

Usage:
  python3 scripts/tech_stack_extract.py
  python3 scripts/tech_stack_extract.py --dev-repo /path/to/dev
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.shared.utils import load_json_or_default, now_iso8601, write_json_atomic

# Critical dependencies to extract
_CRITICAL_DEPS = [
    "react", "react-dom", "vite", "typescript",
    "ag-grid-community", "ag-grid-enterprise", "ag-grid-react",
    "@tailwindcss/vite", "vitest", "storybook",
    "react-router", "react-router-dom",
    "@reduxjs/toolkit", "react-redux",
    "@tanstack/react-query", "zod",
    "keycloak-js", "@sentry/react",
    "eslint", "prettier",
]


def _resolve_dev_repo_root(override: str | None = None) -> Path | None:
    """Resolve dev repo root from managed_repos.v1.json (R2 — registry-first)."""
    if override:
        p = Path(override)
        if p.is_dir():
            return p

    # Registry-first: .cache/managed_repos.v1.json
    managed = load_json_or_default(
        _REPO_ROOT / ".cache" / "managed_repos.v1.json", {}
    )
    for repo in managed.get("repos", []):
        if repo.get("slug") == "dev":
            local_root = repo.get("local_root")
            if local_root:
                p = Path(local_root)
                if p.is_dir():
                    return p

    # Fallback: common location
    fallback = Path.home() / "Documents" / "dev"
    if fallback.is_dir():
        return fallback

    return None


def extract_versions(dev_repo: Path) -> dict[str, Any]:
    """Extract dependency versions from dev repo package.json files."""
    versions: dict[str, str] = {}
    overrides: dict[str, str] = {}
    node_engines = ""

    # 1. Root package.json (web/ level)
    web_root = dev_repo / "web"
    root_pkg = web_root / "package.json"
    if root_pkg.exists():
        data = json.loads(root_pkg.read_text(encoding="utf-8"))
        _extract_from_pkg(data, versions)
        node_engines = data.get("engines", {}).get("node", "")

        # pnpm overrides
        pnpm = data.get("pnpm", {})
        for key, val in pnpm.get("overrides", {}).items():
            overrides[key] = val

    # 2. App package.json (mfe-shell)
    shell_pkg = web_root / "apps" / "mfe-shell" / "package.json"
    if shell_pkg.exists():
        data = json.loads(shell_pkg.read_text(encoding="utf-8"))
        _extract_from_pkg(data, versions)

    # 3. Design system package.json
    ds_pkg = web_root / "packages" / "design-system" / "package.json"
    if ds_pkg.exists():
        data = json.loads(ds_pkg.read_text(encoding="utf-8"))
        ds_version = data.get("version", "")
        if ds_version:
            versions["@mfe/design-system"] = ds_version

    return {
        "versions": versions,
        "overrides": overrides,
        "node_engines": node_engines,
    }


def _extract_from_pkg(data: dict, versions: dict[str, str]) -> None:
    """Extract critical dependency versions from a package.json."""
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section, {})
        for dep_name in _CRITICAL_DEPS:
            if dep_name in deps and dep_name not in versions:
                versions[dep_name] = deps[dep_name]


def build_discovery_report(dev_repo: Path) -> dict[str, Any]:
    """Build full tech stack discovery report."""
    extracted = extract_versions(dev_repo)

    return {
        "version": "v1",
        "generated_at": now_iso8601(),
        "dev_repo": str(dev_repo),
        "source": "managed_repos.v1.json → web/package.json",
        "versions": extracted["versions"],
        "overrides": extracted["overrides"],
        "node_engines": extracted["node_engines"],
        "critical_summary": {
            "react": extracted["versions"].get("react", "?"),
            "vite": extracted["versions"].get("vite", extracted["overrides"].get("vite", "?")),
            "typescript": extracted["versions"].get("typescript", "?"),
            "ag_grid": extracted["versions"].get("ag-grid-community", extracted["overrides"].get("ag-grid-community", "?")),
            "design_system": extracted["versions"].get("@mfe/design-system", "?"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Tech stack auto-discovery")
    parser.add_argument("--dev-repo", default=None, help="Override dev repo path")
    args = parser.parse_args()

    dev_repo = _resolve_dev_repo_root(args.dev_repo)
    if not dev_repo:
        print(json.dumps({"status": "SKIP", "reason": "dev repo not found"}))
        return 0

    report = build_discovery_report(dev_repo)

    # Write artifact
    out = _REPO_ROOT / ".cache" / "ws_customer_default" / ".cache" / "reports" / "tech_stack_discovery.v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out, report)

    print(json.dumps({
        "status": "OK",
        "react": report["critical_summary"]["react"],
        "vite": report["critical_summary"]["vite"],
        "ag_grid": report["critical_summary"]["ag_grid"],
        "versions_found": len(report["versions"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
