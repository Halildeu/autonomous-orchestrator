from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_layer_boundary.v1.json"
    core_policy = core_root / "policies" / "policy_layer_boundary.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if path.exists():
        try:
            obj = _load_json(path)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _git_status_paths(core_root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    paths: list[str] = []
    for line in (proc.stdout or "").splitlines():
        if not line:
            continue
        path_part = line[3:] if len(line) > 3 else ""
        if "->" in path_part:
            path_part = path_part.split("->", 1)[1].strip()
        path_part = path_part.strip()
        if path_part:
            paths.append(path_part)
    return sorted(set(paths))


def _normalize_roots(core_root: Path, roots: list[str]) -> list[Path]:
    results: list[Path] = []
    for root in roots:
        if not isinstance(root, str) or not root.strip():
            continue
        p = Path(root)
        if not p.is_absolute():
            p = (core_root / p).resolve()
        else:
            p = p.resolve()
        results.append(p)
    return results


def _path_under(target: Path, root: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except Exception:
        return False


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except Exception:
        return str(path)


def _allowlist_match(
    *, rel_posix: str, abs_path: Path, allowlist_abs: list[Path], allowlist_globs: list[str]
) -> bool:
    if any(_path_under(abs_path, root) for root in allowlist_abs):
        return True
    for pattern in allowlist_globs:
        if pattern.endswith("*") and rel_posix.startswith(pattern[:-1]):
            return True
        if fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


def run_layer_boundary_check(*, workspace_root: Path, mode: str = "report") -> dict[str, Any]:
    core_root = _find_repo_root(Path(__file__).resolve())
    policy = _load_policy(core_root=core_root, workspace_root=workspace_root)

    notes: list[str] = ["PROGRAM_LED=true"]
    if not policy:
        notes.append("policy_missing_or_invalid")

    defaults = {
        "enforcement_mode": "fail_closed",
        "core_roots": [
            "src",
            "docs",
            "roadmaps",
            "ci",
            ".codex",
            "AGENTS.md",
            "CHANGELOG.md",
            "README.md",
            "pyproject.toml",
            "smoke_test.py",
            ".gitignore",
            ".env.example",
        ],
        "catalog_roots": ["schemas", "policies", "registry", "workflows", "orchestrator", "packs", "capabilities"],
        "workspace_root_required": True,
        "external_write_allowlist": [".cache", "evidence", "exports", "dist", "dlq"],
    }

    enforcement_mode = str(policy.get("enforcement_mode") or defaults["enforcement_mode"])
    core_roots = policy.get("core_roots") if isinstance(policy.get("core_roots"), list) else defaults["core_roots"]
    catalog_roots = (
        policy.get("catalog_roots") if isinstance(policy.get("catalog_roots"), list) else defaults["catalog_roots"]
    )
    workspace_root_required = bool(
        policy.get("workspace_root_required", defaults["workspace_root_required"])
    )
    external_write_allowlist = (
        policy.get("external_write_allowlist")
        if isinstance(policy.get("external_write_allowlist"), list)
        else defaults["external_write_allowlist"]
    )

    core_roots_abs = _normalize_roots(core_root, [str(x) for x in core_roots])
    catalog_roots_abs = _normalize_roots(core_root, [str(x) for x in catalog_roots])
    allowlist_globs = [str(x) for x in external_write_allowlist if isinstance(x, str) and ("*" in x or "?" in x)]
    allowlist_paths = [str(x) for x in external_write_allowlist if str(x) not in allowlist_globs]
    allowlist_abs = _normalize_roots(core_root, allowlist_paths)

    core_unlock_requested = str(os.environ.get("CORE_UNLOCK", "")).strip() == "1"
    git_paths = _git_status_paths(core_root)
    if git_paths is None:
        notes.append("git_status_unavailable")
        git_paths = []

    would_block: list[dict[str, str]] = []
    allowlist_hits: list[str] = []

    for rel in git_paths:
        abs_path = (core_root / rel).resolve()
        if workspace_root_required and _path_under(abs_path, workspace_root):
            continue
        if any(_path_under(abs_path, root) for root in catalog_roots_abs):
            if core_unlock_requested:
                continue
            would_block.append({"path": rel, "layer": "catalog", "reason": "catalog_root_write_locked"})
            continue
        if any(_path_under(abs_path, root) for root in core_roots_abs):
            if core_unlock_requested:
                continue
            would_block.append({"path": rel, "layer": "core", "reason": "core_root_write_locked"})
            continue
        rel_posix = Path(rel).as_posix()
        if _allowlist_match(rel_posix=rel_posix, abs_path=abs_path, allowlist_abs=allowlist_abs, allowlist_globs=allowlist_globs):
            allowlist_hits.append(rel)
            continue
        if workspace_root_required:
            would_block.append({"path": rel, "layer": "outside_workspace", "reason": "outside_workspace_root"})

    would_block.sort(key=lambda x: (x.get("path", ""), x.get("reason", "")))
    allowlist_hits = sorted(set(allowlist_hits))

    status = "OK"
    if would_block:
        status = "WARN" if mode == "report" else "FAIL"
    if "git_status_unavailable" in notes and mode == "strict":
        status = "FAIL"
    elif "git_status_unavailable" in notes and status == "OK":
        status = "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "mode": mode,
        "enforcement_mode": enforcement_mode,
        "core_unlock_requested": bool(core_unlock_requested),
        "workspace_root_required": bool(workspace_root_required),
        "core_roots": [str(x) for x in core_roots],
        "catalog_roots": [str(x) for x in catalog_roots],
        "external_write_allowlist": [str(x) for x in external_write_allowlist],
        "checked_paths": {
            "git_status_paths": git_paths,
            "allowlist_hits": allowlist_hits,
        },
        "would_block": would_block,
        "notes": sorted(set(notes)),
    }

    out_dir = workspace_root / ".cache" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "layer_boundary_report.v1.json"
    out_md = out_dir / "layer_boundary_report.v1.md"
    out_json.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Layer Boundary Report (v1)",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Workspace: {report.get('workspace_root', '')}",
        f"Status: {report.get('status', '')}",
        f"Mode: {report.get('mode', '')}",
        f"Enforcement: {report.get('enforcement_mode', '')}",
        f"Core unlock requested: {report.get('core_unlock_requested', False)}",
        f"Would block: {len(would_block)}",
        "",
        "Would block list:",
    ]
    if would_block:
        for item in would_block[:25]:
            lines.append(
                f"- path={item.get('path', '')} layer={item.get('layer', '')} reason={item.get('reason', '')}"
            )
    else:
        lines.append("- none")
    if notes:
        lines.append("")
        lines.append("Notes: " + ", ".join(sorted(set(notes))))
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rel_json = _rel_to_workspace(out_json, workspace_root)
    rel_md = _rel_to_workspace(out_md, workspace_root)

    return {
        "status": status,
        "workspace_root": str(workspace_root),
        "mode": mode,
        "enforcement_mode": enforcement_mode,
        "would_block_count": len(would_block),
        "report_path": rel_json,
        "report_md_path": rel_md,
        "evidence_paths": [rel_json, rel_md],
        "notes": sorted(set(notes)),
    }
