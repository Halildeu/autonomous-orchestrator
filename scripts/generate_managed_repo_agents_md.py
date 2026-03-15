#!/usr/bin/env python3
"""Generate AGENTS.md for managed repos from template, profile-aware."""
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


def _resolve_profile(source_root: Path, profile_id: str) -> dict[str, Any] | None:
    """Load a domain profile from the registry."""
    registry_path = source_root / "registry" / "domain_profiles.v1.json"
    if not registry_path.exists():
        return None
    try:
        registry = _load_json(registry_path)
        profiles = registry.get("profiles", {})
        pid = profile_id or str(registry.get("default_profile") or "fullstack")
        return profiles.get(pid) if isinstance(profiles, dict) else None
    except Exception:
        return None


def _render_profile_section(profile: dict[str, Any]) -> str:
    """Render a profile-specific section for AGENTS.md."""
    pid = profile.get("profile_id", "unknown")
    display = profile.get("display_name", pid)
    scopes = profile.get("service_scopes", [])
    lanes = profile.get("active_lanes", [])
    seq = profile.get("execution_sequence", [])
    tech = profile.get("tech_stack", {})
    write_roots = profile.get("write_roots", [])

    lines = [
        "",
        "## Domain Profile",
        "",
        f"- **Profil**: {display} (`{pid}`)",
        f"- **Aktif scope'lar**: {', '.join(scopes)}",
        f"- **Aktif lane'ler**: {', '.join(lanes)}",
        f"- **Execution sırası**: {' → '.join(seq)}",
        f"- **Yazma izinleri**: {', '.join(f'`{r}`' for r in write_roots)}",
        "",
    ]

    if tech:
        lines.append("### Tech Stack")
        for domain, stack in tech.items():
            if isinstance(stack, dict):
                parts = [f"{k}={v}" for k, v in stack.items()]
                lines.append(f"- **{domain}**: {', '.join(parts)}")
        lines.append("")

    return "\n".join(lines)


def generate_agents_md(
    *,
    source_root: Path,
    target_root: Path,
    repo_slug: str = "",
    domain_profile: str = "",
    apply: bool = False,
) -> dict[str, Any]:
    """Generate AGENTS.md for a managed repo from the template.

    If target already has AGENTS.md, skip unless apply=True (overwrite).
    """
    template_path = source_root / "templates" / "AGENTS.managed.md"
    if not template_path.exists():
        return {
            "status": "FAIL",
            "error": "TEMPLATE_MISSING",
            "template_path": str(template_path),
        }

    target_agents = target_root / "AGENTS.md"
    target_exists = target_agents.exists()

    if target_exists and not apply:
        return {
            "status": "OK",
            "action": "skip_exists",
            "target_path": str(target_agents),
            "repo_slug": repo_slug,
        }

    template_content = template_path.read_text(encoding="utf-8")

    # Resolve and append profile section
    profile = _resolve_profile(source_root, domain_profile)
    if profile:
        template_content += _render_profile_section(profile)

    if apply:
        target_agents.parent.mkdir(parents=True, exist_ok=True)
        target_agents.write_text(template_content, encoding="utf-8")
        action = "updated" if target_exists else "created"
    else:
        action = "would_update" if target_exists else "would_create"

    return {
        "status": "OK",
        "action": action,
        "target_path": str(target_agents),
        "repo_slug": repo_slug,
        "domain_profile": domain_profile or "fullstack",
        "template_path": str(template_path),
        "generated_at": _now_iso(),
    }


def generate_for_manifest(
    *,
    source_root: Path,
    manifest_path: Path,
    apply: bool = False,
) -> dict[str, Any]:
    """Generate AGENTS.md for all managed repos in a manifest."""
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
        slug = str(item.get("repo_slug") or "")
        profile = str(item.get("domain_profile") or "fullstack")
        result = generate_agents_md(
            source_root=source_root,
            target_root=target,
            repo_slug=slug,
            domain_profile=profile,
            apply=apply,
        )
        results.append(result)

    failed = [r for r in results if r.get("status") != "OK"]
    return {
        "status": "OK" if not failed else "FAIL",
        "mode": "apply" if apply else "dry-run",
        "total": len(results),
        "failed": len(failed),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate AGENTS.md for managed repos")
    parser.add_argument("--source-root", default="", help="Source repo root")
    parser.add_argument("--target-repo-root", action="append", default=[], help="Target repo root (repeatable)")
    parser.add_argument("--manifest-path", default="", help="Managed repos manifest path")
    parser.add_argument("--domain-profile", default="fullstack", help="Domain profile ID")
    parser.add_argument("--apply", action="store_true", help="Apply (write) AGENTS.md")
    args = parser.parse_args(argv)

    source_root = (
        Path(str(args.source_root).strip()).expanduser().resolve()
        if str(args.source_root).strip()
        else Path(__file__).resolve().parents[1]
    )

    if args.manifest_path:
        manifest = Path(args.manifest_path).expanduser().resolve()
        result = generate_for_manifest(
            source_root=source_root,
            manifest_path=manifest,
            apply=bool(args.apply),
        )
    elif args.target_repo_root:
        results = []
        for raw in args.target_repo_root:
            target = Path(raw.strip()).expanduser().resolve()
            r = generate_agents_md(
                source_root=source_root,
                target_root=target,
                domain_profile=args.domain_profile,
                apply=bool(args.apply),
            )
            results.append(r)
        failed = [r for r in results if r.get("status") != "OK"]
        result = {
            "status": "OK" if not failed else "FAIL",
            "mode": "apply" if args.apply else "dry-run",
            "total": len(results),
            "results": results,
        }
    else:
        result = {"status": "FAIL", "error": "TARGET_REQUIRED"}

    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("status") == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
