from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SYNC_REPORT_REL = Path(".cache") / "reports" / "managed_repo_standards_sync" / "report.v1.json"
MANAGED_REPOS_MANIFEST_REL = Path(".cache") / "managed_repos.v1.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path | None, workspace_root: Path, core_root: Path) -> str:
    if not isinstance(path, Path):
        return ""
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        pass
    try:
        return path.resolve().relative_to(core_root.resolve()).as_posix()
    except Exception:
        pass
    return str(path.resolve())


def _candidate_paths(workspace_root: Path, core_root: Path, rel: Path) -> list[Path]:
    # Workspace-first, then workspace prefix, then core root fallback.
    candidates = [
        (workspace_root / rel).resolve(),
        (workspace_root.parent / rel).resolve(),
        (core_root / rel).resolve(),
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def _manifest_repo_roots(manifest_obj: dict[str, Any]) -> list[str]:
    repos = manifest_obj.get("repos") if isinstance(manifest_obj, dict) else None
    if not isinstance(repos, list):
        return []
    roots: list[str] = []
    for item in repos:
        if not isinstance(item, dict):
            continue
        repo_root = item.get("repo_root")
        if isinstance(repo_root, str) and repo_root.strip():
            roots.append(str(Path(repo_root).expanduser().resolve()))
    roots = sorted(set(roots))
    return roots


def _manifest_meta_by_root(manifest_obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build lookup from absolute repo_root -> manifest metadata (repo_slug, domain_profile, etc.)."""
    repos = manifest_obj.get("repos") if isinstance(manifest_obj, dict) else None
    if not isinstance(repos, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in repos:
        if not isinstance(item, dict):
            continue
        repo_root = item.get("repo_root")
        if not isinstance(repo_root, str) or not repo_root.strip():
            continue
        abs_root = str(Path(repo_root).expanduser().resolve())
        result[abs_root] = {
            "repo_slug": str(item.get("repo_slug") or ""),
            "domain_profile": str(item.get("domain_profile") or ""),
            "critical": bool(item.get("critical", False)),
        }
    return result


def _lane_state_from_result(result: dict[str, Any]) -> tuple[str, str]:
    status = str(result.get("status") or "FAIL")
    files = result.get("files") if isinstance(result.get("files"), list) else []
    actions = {
        str(item.get("action"))
        for item in files
        if isinstance(item, dict) and isinstance(item.get("action"), str)
    }

    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    validation_status = str(validation.get("status") or "UNKNOWN")

    has_pending = bool(actions & {"would_create", "would_update"})
    has_fixed = bool(actions & {"created", "updated"})
    has_error = bool(actions & {"error"})

    if status != "OK" or validation_status == "FAIL" or has_error:
        return ("FAILED", validation_status)
    if has_pending:
        return ("PENDING", validation_status)
    if has_fixed:
        return ("FIXED", validation_status)
    return ("CLEAN", validation_status)


def build_managed_repo_standards_summary(
    *,
    workspace_root: Path,
    core_root: Path,
    max_repos: int = 200,
) -> dict[str, Any]:
    report_candidates = _candidate_paths(workspace_root, core_root, SYNC_REPORT_REL)
    manifest_candidates = _candidate_paths(workspace_root, core_root, MANAGED_REPOS_MANIFEST_REL)

    report_path = _first_existing(report_candidates)
    manifest_path = _first_existing(manifest_candidates)

    manifest_obj: dict[str, Any] = {}
    manifest_error = False
    if isinstance(manifest_path, Path):
        try:
            loaded = _load_json(manifest_path)
            if isinstance(loaded, dict):
                manifest_obj = loaded
            else:
                manifest_error = True
        except Exception:
            manifest_error = True
    manifest_repos = _manifest_repo_roots(manifest_obj)
    manifest_meta = _manifest_meta_by_root(manifest_obj)

    if not isinstance(report_path, Path):
        notes = ["sync_report_missing"]
        if manifest_error:
            notes.append("managed_repos_manifest_invalid")
        elif not isinstance(manifest_path, Path):
            notes.append("managed_repos_manifest_missing")
        status = "WARN" if manifest_repos else "IDLE"
        return {
            "status": status,
            "report_path": _display_path(report_candidates[0], workspace_root, core_root),
            "manifest_path": _display_path(manifest_path, workspace_root, core_root),
            "mode": "unknown",
            "target_count": 0,
            "managed_repo_count": len(manifest_repos),
            "failed_count": 0,
            "drift_pending_count": 0,
            "drift_fixed_count": 0,
            "clean_count": 0,
            "missing_in_report_count": len(manifest_repos),
            "repos": [],
            "notes": notes,
        }

    try:
        report_obj = _load_json(report_path)
    except Exception:
        return {
            "status": "FAIL",
            "report_path": _display_path(report_path, workspace_root, core_root),
            "manifest_path": _display_path(manifest_path, workspace_root, core_root),
            "mode": "unknown",
            "target_count": 0,
            "managed_repo_count": len(manifest_repos),
            "failed_count": 1,
            "drift_pending_count": 0,
            "drift_fixed_count": 0,
            "clean_count": 0,
            "missing_in_report_count": len(manifest_repos),
            "repos": [],
            "notes": ["sync_report_invalid_json"],
        }

    if not isinstance(report_obj, dict):
        return {
            "status": "FAIL",
            "report_path": _display_path(report_path, workspace_root, core_root),
            "manifest_path": _display_path(manifest_path, workspace_root, core_root),
            "mode": "unknown",
            "target_count": 0,
            "managed_repo_count": len(manifest_repos),
            "failed_count": 1,
            "drift_pending_count": 0,
            "drift_fixed_count": 0,
            "clean_count": 0,
            "missing_in_report_count": len(manifest_repos),
            "repos": [],
            "notes": ["sync_report_not_object"],
        }

    results = report_obj.get("results")
    results_list = results if isinstance(results, list) else []
    mode = str(report_obj.get("mode") or "unknown")
    target_count = int(report_obj.get("target_count") or len(results_list) or 0)

    repos: list[dict[str, Any]] = []
    pending_count = 0
    fixed_count = 0
    clean_count = 0
    failed_count_from_state = 0

    for item in results_list:
        if not isinstance(item, dict):
            continue
        repo_root_raw = item.get("repo_root")
        repo_root = str(Path(repo_root_raw).expanduser().resolve()) if isinstance(repo_root_raw, str) and repo_root_raw.strip() else ""
        drift_state, validation_status = _lane_state_from_result(item)
        changed_files = int(item.get("changed_files") or 0)

        if drift_state == "FAILED":
            failed_count_from_state += 1
        elif drift_state == "PENDING":
            pending_count += 1
        elif drift_state == "FIXED":
            fixed_count += 1
        elif drift_state == "CLEAN":
            clean_count += 1

        meta = manifest_meta.get(repo_root, {})
        repos.append(
            {
                "repo_root": repo_root,
                "origin": meta.get("repo_slug", ""),
                "domain_profile": meta.get("domain_profile", ""),
                "status": str(item.get("status") or "FAIL"),
                "drift_state": drift_state,
                "changed_files": changed_files,
                "validation_status": validation_status,
            }
        )

    repos.sort(key=lambda x: str(x.get("repo_root") or ""))
    if max_repos > 0:
        repos = repos[:max_repos]

    failed_count_reported = int(report_obj.get("failed_count") or 0)
    failed_count = max(failed_count_reported, failed_count_from_state)
    reported_repo_roots = {
        str(item.get("repo_root"))
        for item in repos
        if isinstance(item, dict) and isinstance(item.get("repo_root"), str) and str(item.get("repo_root")).strip()
    }
    missing_in_report = sorted([root for root in manifest_repos if root not in reported_repo_roots])

    notes = report_obj.get("notes") if isinstance(report_obj.get("notes"), list) else []
    notes_list = [str(item) for item in notes if isinstance(item, str)]
    if manifest_error:
        notes_list.append("managed_repos_manifest_invalid")
    if missing_in_report:
        notes_list.append("manifest_repos_missing_in_sync_report")

    status = "OK"
    if failed_count > 0:
        status = "FAIL"
    elif pending_count > 0:
        status = "WARN"
    elif target_count <= 0 and manifest_repos:
        status = "WARN"
    elif target_count <= 0:
        status = "IDLE"

    return {
        "status": status,
        "report_path": _display_path(report_path, workspace_root, core_root),
        "manifest_path": _display_path(manifest_path, workspace_root, core_root),
        "mode": mode,
        "target_count": target_count,
        "managed_repo_count": len(manifest_repos),
        "failed_count": failed_count,
        "drift_pending_count": pending_count,
        "drift_fixed_count": fixed_count,
        "clean_count": clean_count,
        "missing_in_report_count": len(missing_in_report),
        "repos": repos,
        "notes": sorted(set(notes_list)),
    }
