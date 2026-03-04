#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BRANCH = "main"
DEFAULT_REQUIRED_BRANCH_CHECKS = [
    "module-delivery-gate",
    "enforcement-check",
    "validate-schemas",
    "policy-dry-run",
    "gitleaks",
]
DEFAULT_SOLO_POLICY = {
    "enabled": True,
    "single_writer_requires_review_count": 0,
    "single_writer_require_code_owner_reviews": False,
    "multi_writer_min_review_count": 1,
    "multi_writer_require_code_owner_reviews": True,
    "strict_required_status_checks": True,
    "enforce_admins_required": True,
}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_relpath(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid relative path")
    p = Path(value.strip())
    if p.is_absolute():
        raise ValueError(f"absolute path not allowed: {value}")
    if ".." in p.parts:
        raise ValueError(f"path traversal not allowed: {value}")
    norm = p.as_posix()
    if not norm or norm == ".":
        raise ValueError("empty relative path")
    return norm


def _collect_standard_paths(lock_obj: dict[str, Any]) -> list[str]:
    required_files = lock_obj.get("required_files")
    if not isinstance(required_files, list):
        raise ValueError("standards.lock required_files must be a list")

    standard_sources = lock_obj.get("standard_sources")
    if not isinstance(standard_sources, dict):
        raise ValueError("standards.lock standard_sources must be an object")

    out: list[str] = []
    seen: set[str] = set()

    def add_path(raw: Any) -> None:
        rel = _safe_relpath(raw)
        if rel in seen:
            return
        seen.add(rel)
        out.append(rel)

    for rel in required_files:
        add_path(rel)
    for rel in standard_sources.values():
        add_path(rel)

    return out


def _load_manifest_targets(manifest_path: Path) -> list[Path]:
    manifest = _load_json(manifest_path)
    repos = manifest.get("repos")
    if not isinstance(repos, list):
        return []
    targets: list[Path] = []
    for item in repos:
        if not isinstance(item, dict):
            continue
        repo_root = item.get("repo_root")
        if not isinstance(repo_root, str) or not repo_root.strip():
            continue
        targets.append(Path(repo_root.strip()).expanduser().resolve())
    return targets


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p.resolve())
    return out


def _run_standards_validation(source_root: Path, target_root: Path) -> dict[str, Any]:
    check_script = (source_root / "ci" / "check_standards_lock.py").resolve()
    if not check_script.exists():
        return {"status": "FAIL", "reason": "CHECK_SCRIPT_MISSING"}

    proc = subprocess.run(
        ["python3", str(check_script), "--repo-root", str(target_root)],
        cwd=source_root,
        text=True,
        capture_output=True,
    )
    stdout_lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    parsed: dict[str, Any] = {}
    if stdout_lines:
        try:
            candidate = json.loads(stdout_lines[-1])
            if isinstance(candidate, dict):
                parsed = candidate
        except Exception:
            parsed = {}

    return {
        "status": "OK" if proc.returncode == 0 and parsed.get("status") == "OK" else "FAIL",
        "returncode": proc.returncode,
        "payload": parsed,
        "stderr_preview": (proc.stderr or "").strip().splitlines()[:10],
    }


def _safe_bool(value: Any, *, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_repo_slug(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if "/" in text and not text.startswith(("http://", "https://", "git@", "ssh://")):
        candidate = text.strip("/")
        if candidate.count("/") == 1:
            owner, repo = candidate.split("/", 1)
            owner = owner.strip()
            repo = repo.strip().removesuffix(".git")
            if owner and repo:
                return f"{owner}/{repo}"

    patterns = [
        r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        m = re.match(pattern, text)
        if not m:
            continue
        owner, repo = m.group(1), m.group(2)
        if owner and repo:
            return f"{owner}/{repo}"
    return ""


def _detect_repo_slug(target_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(target_root), "remote", "get-url", "origin"],
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return _parse_repo_slug(proc.stdout.strip())


def _run_gh_api_json(path: str) -> tuple[bool, Any, str]:
    try:
        proc = subprocess.run(
            ["gh", "api", path],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False, None, "GH_CLI_NOT_FOUND"
    except Exception as exc:
        return False, None, f"GH_EXEC_ERROR:{exc}"

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        return False, None, f"GH_API_ERROR:{stderr[:240]}"

    raw = (proc.stdout or "").strip()
    if not raw:
        return False, None, "GH_API_EMPTY"
    try:
        return True, json.loads(raw), ""
    except Exception:
        return False, None, "GH_API_INVALID_JSON"


def _extract_required_contexts(protection_obj: dict[str, Any]) -> list[str]:
    required_status_checks = (
        protection_obj.get("required_status_checks")
        if isinstance(protection_obj.get("required_status_checks"), dict)
        else {}
    )
    contexts: list[str] = []
    raw_contexts = required_status_checks.get("contexts")
    if isinstance(raw_contexts, list):
        contexts = [str(item).strip() for item in raw_contexts if isinstance(item, str) and str(item).strip()]
    if contexts:
        return sorted(set(contexts))

    checks = required_status_checks.get("checks")
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict):
                continue
            ctx = item.get("context")
            if isinstance(ctx, str) and ctx.strip():
                contexts.append(ctx.strip())
    return sorted(set(contexts))


def _read_branch_policy_from_lock(lock_obj: dict[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    branch_obj = lock_obj.get("branch_protection") if isinstance(lock_obj.get("branch_protection"), dict) else {}
    default_branch = str(branch_obj.get("default_branch") or "").strip() or DEFAULT_BRANCH
    raw_required_checks = branch_obj.get("required_checks")
    required_checks = [
        str(item).strip()
        for item in (raw_required_checks if isinstance(raw_required_checks, list) else [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not required_checks:
        required_checks = list(DEFAULT_REQUIRED_BRANCH_CHECKS)

    solo_raw = lock_obj.get("solo_developer_policy") if isinstance(lock_obj.get("solo_developer_policy"), dict) else {}
    solo_policy = {
        "enabled": _safe_bool(solo_raw.get("enabled"), default=DEFAULT_SOLO_POLICY["enabled"]),
        "single_writer_requires_review_count": _safe_int(
            solo_raw.get("single_writer_requires_review_count"),
            default=DEFAULT_SOLO_POLICY["single_writer_requires_review_count"],
        ),
        "single_writer_require_code_owner_reviews": _safe_bool(
            solo_raw.get("single_writer_require_code_owner_reviews"),
            default=DEFAULT_SOLO_POLICY["single_writer_require_code_owner_reviews"],
        ),
        "multi_writer_min_review_count": _safe_int(
            solo_raw.get("multi_writer_min_review_count"),
            default=DEFAULT_SOLO_POLICY["multi_writer_min_review_count"],
        ),
        "multi_writer_require_code_owner_reviews": _safe_bool(
            solo_raw.get("multi_writer_require_code_owner_reviews"),
            default=DEFAULT_SOLO_POLICY["multi_writer_require_code_owner_reviews"],
        ),
        "strict_required_status_checks": _safe_bool(
            solo_raw.get("strict_required_status_checks"),
            default=DEFAULT_SOLO_POLICY["strict_required_status_checks"],
        ),
        "enforce_admins_required": _safe_bool(
            solo_raw.get("enforce_admins_required"),
            default=DEFAULT_SOLO_POLICY["enforce_admins_required"],
        ),
    }
    return default_branch, sorted(set(required_checks)), solo_policy


def _live_branch_protection_check(
    *,
    target_root: Path,
    default_branch: str,
    required_checks: list[str],
    solo_policy: dict[str, Any],
) -> dict[str, Any]:
    repo_slug = _detect_repo_slug(target_root)
    if not repo_slug:
        return {
            "source": "github_live_check",
            "status": "UNVERIFIED",
            "repo_slug": "",
            "branch": default_branch,
            "required_checks": required_checks,
            "required_present": None,
            "missing_required_checks": [],
            "contexts": [],
            "strict": None,
            "enforce_admins": None,
            "required_pull_request_reviews": None,
            "collaborator_write_count": None,
            "collaborator_write_users": [],
            "solo_policy": {
                "enabled": bool(solo_policy.get("enabled")),
                "status": "UNVERIFIED",
                "rule": "unknown",
                "violations": ["repo_slug_not_detected"],
            },
        }

    protection_ok, protection_obj, protection_error = _run_gh_api_json(
        f"repos/{repo_slug}/branches/{default_branch}/protection"
    )
    if not protection_ok or not isinstance(protection_obj, dict):
        return {
            "source": "github_live_check",
            "status": "UNVERIFIED",
            "repo_slug": repo_slug,
            "branch": default_branch,
            "required_checks": required_checks,
            "required_present": None,
            "missing_required_checks": [],
            "contexts": [],
            "strict": None,
            "enforce_admins": None,
            "required_pull_request_reviews": None,
            "collaborator_write_count": None,
            "collaborator_write_users": [],
            "error": protection_error or "protection_unavailable",
            "solo_policy": {
                "enabled": bool(solo_policy.get("enabled")),
                "status": "UNVERIFIED",
                "rule": "unknown",
                "violations": ["protection_unavailable"],
            },
        }

    contexts = _extract_required_contexts(protection_obj)
    missing_required_checks = [check for check in required_checks if check not in set(contexts)]
    required_present = bool(required_checks) and not missing_required_checks

    required_status_checks = (
        protection_obj.get("required_status_checks")
        if isinstance(protection_obj.get("required_status_checks"), dict)
        else {}
    )
    strict = required_status_checks.get("strict")
    strict = strict if isinstance(strict, bool) else None

    enforce_admins_obj = (
        protection_obj.get("enforce_admins")
        if isinstance(protection_obj.get("enforce_admins"), dict)
        else {}
    )
    enforce_admins = enforce_admins_obj.get("enabled")
    enforce_admins = enforce_admins if isinstance(enforce_admins, bool) else None

    reviews_obj = (
        protection_obj.get("required_pull_request_reviews")
        if isinstance(protection_obj.get("required_pull_request_reviews"), dict)
        else {}
    )
    review_count_raw = reviews_obj.get("required_approving_review_count")
    review_count = review_count_raw if isinstance(review_count_raw, int) else 0
    require_code_owner = reviews_obj.get("require_code_owner_reviews")
    require_code_owner = require_code_owner if isinstance(require_code_owner, bool) else False

    collab_ok, collab_obj, collab_error = _run_gh_api_json(f"repos/{repo_slug}/collaborators?per_page=100")
    collaborator_write_count: int | None = None
    collaborator_write_users: list[str] = []
    collaborator_violations: list[str] = []
    if collab_ok and isinstance(collab_obj, list):
        for item in collab_obj:
            if not isinstance(item, dict):
                continue
            login = str(item.get("login") or "").strip()
            permissions = item.get("permissions") if isinstance(item.get("permissions"), dict) else {}
            can_write = bool(
                permissions.get("admin") is True
                or permissions.get("maintain") is True
                or permissions.get("push") is True
            )
            if can_write and login:
                collaborator_write_users.append(login)
        collaborator_write_users = sorted(set(collaborator_write_users))
        collaborator_write_count = len(collaborator_write_users)
    else:
        collaborator_violations.append("collaborators_unverified")
        if collab_error:
            collaborator_violations.append(collab_error)

    policy_enabled = bool(solo_policy.get("enabled"))
    solo_status = "SKIPPED" if not policy_enabled else "OK"
    solo_rule = "none"
    violations: list[str] = []
    expected: dict[str, Any] = {}

    if policy_enabled:
        if collaborator_write_count is None:
            solo_status = "UNVERIFIED"
            solo_rule = "unknown"
            violations.extend(collaborator_violations)
        elif collaborator_write_count <= 1:
            solo_rule = "single_writer"
            expected = {
                "required_approving_review_count": int(solo_policy.get("single_writer_requires_review_count") or 0),
                "require_code_owner_reviews": bool(solo_policy.get("single_writer_require_code_owner_reviews")),
            }
            if review_count != expected["required_approving_review_count"]:
                violations.append("single_writer_required_approving_review_count_mismatch")
            if require_code_owner is not expected["require_code_owner_reviews"]:
                violations.append("single_writer_require_code_owner_reviews_mismatch")
        else:
            solo_rule = "multi_writer"
            expected = {
                "required_approving_review_count_min": int(solo_policy.get("multi_writer_min_review_count") or 1),
                "require_code_owner_reviews": bool(solo_policy.get("multi_writer_require_code_owner_reviews")),
            }
            if review_count < expected["required_approving_review_count_min"]:
                violations.append("multi_writer_required_approving_review_count_too_low")
            if require_code_owner is not expected["require_code_owner_reviews"]:
                violations.append("multi_writer_require_code_owner_reviews_mismatch")

        if bool(solo_policy.get("strict_required_status_checks")) and strict is not True:
            violations.append("strict_required_status_checks_must_be_true")
        if bool(solo_policy.get("enforce_admins_required")) and enforce_admins is not True:
            violations.append("enforce_admins_must_be_true")
        if missing_required_checks:
            violations.append("missing_required_branch_checks")

        if solo_status != "UNVERIFIED":
            solo_status = "FAIL" if violations else "OK"

    status = "OK"
    if missing_required_checks:
        status = "FAIL"
    if solo_status == "FAIL":
        status = "FAIL"
    elif solo_status == "UNVERIFIED" and status == "OK":
        status = "UNVERIFIED"

    return {
        "source": "github_live_check",
        "status": status,
        "repo_slug": repo_slug,
        "branch": default_branch,
        "required_check": required_checks[0] if required_checks else "",
        "required_checks": required_checks,
        "required_present": required_present,
        "missing_required_checks": missing_required_checks,
        "contexts": contexts,
        "strict": strict,
        "enforce_admins": enforce_admins,
        "required_pull_request_reviews": {
            "required_approving_review_count": review_count,
            "require_code_owner_reviews": require_code_owner,
            "dismiss_stale_reviews": (
                bool(reviews_obj.get("dismiss_stale_reviews"))
                if isinstance(reviews_obj.get("dismiss_stale_reviews"), bool)
                else None
            ),
        },
        "collaborator_write_count": collaborator_write_count,
        "collaborator_write_users": collaborator_write_users,
        "solo_policy": {
            "enabled": policy_enabled,
            "status": solo_status,
            "rule": solo_rule,
            "expected": expected,
            "actual": {
                "required_approving_review_count": review_count,
                "require_code_owner_reviews": require_code_owner,
                "strict_required_status_checks": strict,
                "enforce_admins": enforce_admins,
                "collaborator_write_count": collaborator_write_count,
            },
            "violations": sorted(set(violations)),
        },
    }


def _sync_target_repo(
    *,
    source_root: Path,
    target_root: Path,
    rel_paths: list[str],
    preserve_existing_paths: set[str],
    default_branch: str,
    required_branch_checks: list[str],
    solo_policy: dict[str, Any],
    apply: bool,
    validate_after_sync: bool,
    branch_live_check: bool,
) -> dict[str, Any]:
    if not target_root.exists() or not target_root.is_dir():
        return {
            "repo_root": str(target_root),
            "status": "FAIL",
            "reason": "TARGET_REPO_NOT_FOUND",
            "files": [],
            "branch_protection": {
                "source": "github_live_check",
                "status": "UNVERIFIED",
                "repo_slug": "",
                "branch": default_branch,
                "required_checks": required_branch_checks,
                "required_present": None,
                "missing_required_checks": [],
                "solo_policy": {
                    "enabled": bool(solo_policy.get("enabled")),
                    "status": "UNVERIFIED",
                    "rule": "unknown",
                    "violations": ["target_repo_not_found"],
                },
            },
        }

    file_results: list[dict[str, Any]] = []
    missing_source: list[str] = []
    write_errors: list[str] = []
    changed_count = 0

    for rel in rel_paths:
        src = (source_root / rel).resolve()
        dst = (target_root / rel).resolve()
        if not src.exists() or not src.is_file():
            missing_source.append(rel)
            continue

        src_hash = _sha256_file(src)
        dst_exists = dst.exists()
        dst_hash = _sha256_file(dst) if dst_exists and dst.is_file() else None

        if dst_exists and rel in preserve_existing_paths:
            action = "preserve_existing"
            file_results.append(
                {
                    "path": rel,
                    "action": action,
                    "source_sha256": src_hash,
                    "target_sha256_before": dst_hash,
                }
            )
            continue

        if dst_exists and dst_hash == src_hash:
            action = "no_change"
        elif apply:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                action = "updated" if dst_exists else "created"
                changed_count += 1
            except Exception as exc:
                write_errors.append(f"{rel}:{exc}")
                action = "error"
        else:
            action = "would_update" if dst_exists else "would_create"
            changed_count += 1

        file_results.append(
            {
                "path": rel,
                "action": action,
                "source_sha256": src_hash,
                "target_sha256_before": dst_hash,
            }
        )

    if missing_source:
        return {
            "repo_root": str(target_root),
            "status": "FAIL",
            "reason": "SOURCE_FILES_MISSING",
            "missing_source_files": missing_source,
            "files": file_results,
            "branch_protection": {
                "source": "github_live_check",
                "status": "UNVERIFIED",
                "repo_slug": "",
                "branch": default_branch,
                "required_checks": required_branch_checks,
                "required_present": None,
                "missing_required_checks": [],
                "solo_policy": {
                    "enabled": bool(solo_policy.get("enabled")),
                    "status": "UNVERIFIED",
                    "rule": "unknown",
                    "violations": ["source_files_missing"],
                },
            },
        }

    if write_errors:
        return {
            "repo_root": str(target_root),
            "status": "FAIL",
            "reason": "WRITE_FAILED",
            "write_errors": write_errors,
            "files": file_results,
            "branch_protection": {
                "source": "github_live_check",
                "status": "UNVERIFIED",
                "repo_slug": "",
                "branch": default_branch,
                "required_checks": required_branch_checks,
                "required_present": None,
                "missing_required_checks": [],
                "solo_policy": {
                    "enabled": bool(solo_policy.get("enabled")),
                    "status": "UNVERIFIED",
                    "rule": "unknown",
                    "violations": ["write_failed"],
                },
            },
        }

    validation: dict[str, Any] | None = None
    if apply and validate_after_sync:
        validation = _run_standards_validation(source_root, target_root)

    status = "OK"
    if isinstance(validation, dict) and validation.get("status") != "OK":
        status = "FAIL"

    branch_report = (
        _live_branch_protection_check(
            target_root=target_root,
            default_branch=default_branch,
            required_checks=required_branch_checks,
            solo_policy=solo_policy,
        )
        if branch_live_check
        else {
            "source": "github_live_check",
            "status": "UNVERIFIED",
            "repo_slug": "",
            "branch": default_branch,
            "required_checks": required_branch_checks,
            "required_present": None,
            "missing_required_checks": [],
            "solo_policy": {
                "enabled": bool(solo_policy.get("enabled")),
                "status": "UNVERIFIED",
                "rule": "unknown",
                "violations": ["branch_live_check_disabled"],
            },
        }
    )

    return {
        "repo_root": str(target_root),
        "status": status,
        "mode": "apply" if apply else "dry-run",
        "changed_files": changed_count,
        "files": file_results,
        "validation": validation,
        "branch_protection": branch_report,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        default="",
        help="Standards source repo root (default: current script parent repo).",
    )
    parser.add_argument(
        "--target-repo-root",
        action="append",
        default=[],
        help="Managed repo root (repeatable).",
    )
    parser.add_argument(
        "--manifest-path",
        default="",
        help="Optional managed repos manifest path (.cache/managed_repos.v1.json).",
    )
    parser.add_argument(
        "--output",
        default=".cache/reports/managed_repo_standards_sync/report.v1.json",
        help="Output report path (relative to source root if not absolute).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply sync to target repos. Default mode is dry-run.",
    )
    parser.add_argument(
        "--include-self",
        action="store_true",
        help="Include source root if it is also listed as a target.",
    )
    parser.add_argument(
        "--validate-after-sync",
        action="store_true",
        help="Run standards.lock validation per target after apply.",
    )
    parser.add_argument(
        "--skip-branch-live-check",
        action="store_true",
        help="Skip GitHub live branch protection check (report uses UNVERIFIED).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    script_root = Path(__file__).resolve().parents[1]
    source_root = (
        Path(str(args.source_root).strip()).expanduser().resolve()
        if str(args.source_root).strip()
        else script_root
    )

    lock_path = source_root / "standards.lock"
    if not lock_path.exists():
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "STANDARDS_LOCK_MISSING",
                    "source_root": str(source_root),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    lock_obj = _load_json(lock_path)
    rel_paths = _collect_standard_paths(lock_obj)
    default_branch, required_branch_checks, solo_policy = _read_branch_policy_from_lock(lock_obj)

    managed_repo_sync = lock_obj.get("managed_repo_sync")
    preserve_existing_paths: set[str] = set()
    if isinstance(managed_repo_sync, dict):
        raw_preserve = managed_repo_sync.get("preserve_existing_paths")
        if isinstance(raw_preserve, list):
            for item in raw_preserve:
                if isinstance(item, str) and item.strip():
                    preserve_existing_paths.add(_safe_relpath(item))

    targets: list[Path] = []
    for raw in args.target_repo_root:
        txt = str(raw).strip()
        if txt:
            targets.append(Path(txt).expanduser().resolve())

    manifest_arg = str(args.manifest_path).strip()
    if manifest_arg:
        manifest_path = Path(manifest_arg).expanduser().resolve()
        if not manifest_path.exists():
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "error_code": "MANIFEST_NOT_FOUND",
                        "manifest_path": str(manifest_path),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 2
        targets.extend(_load_manifest_targets(manifest_path))

    targets = _dedupe_paths(targets)
    if not args.include_self:
        targets = [p for p in targets if p != source_root]

    if not targets:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "TARGET_REPO_REQUIRED",
                    "message": "En az bir target repo gereklidir.",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    results = [
        _sync_target_repo(
            source_root=source_root,
            target_root=target,
            rel_paths=rel_paths,
            preserve_existing_paths=preserve_existing_paths,
            default_branch=default_branch,
            required_branch_checks=required_branch_checks,
            solo_policy=solo_policy,
            apply=bool(args.apply),
            validate_after_sync=bool(args.validate_after_sync),
            branch_live_check=not bool(args.skip_branch_live_check),
        )
        for target in targets
    ]

    failed = [r for r in results if r.get("status") != "OK"]
    changed_total = sum(int(r.get("changed_files") or 0) for r in results if isinstance(r, dict))

    output_arg = str(args.output).strip()
    output_path = Path(output_arg)
    if not output_path.is_absolute():
        output_path = (source_root / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "version": "v1",
        "kind": "managed-repo-standards-sync-report",
        "generated_at": _now_iso_utc(),
        "source_root": str(source_root),
        "mode": "apply" if args.apply else "dry-run",
        "branch_policy": {
            "default_branch": default_branch,
            "required_checks": required_branch_checks,
            "solo_developer_policy": solo_policy,
            "live_check_enabled": not bool(args.skip_branch_live_check),
        },
        "sync_paths": rel_paths,
        "preserve_existing_paths": sorted(preserve_existing_paths),
        "target_count": len(results),
        "changed_total": changed_total,
        "failed_count": len(failed),
        "results": results,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    status = "OK" if not failed else "FAIL"
    print(
        json.dumps(
            {
                "status": status,
                "mode": report["mode"],
                "target_count": report["target_count"],
                "changed_total": report["changed_total"],
                "failed_count": report["failed_count"],
                "report_path": str(output_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
