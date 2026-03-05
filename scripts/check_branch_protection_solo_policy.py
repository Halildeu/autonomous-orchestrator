#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BRANCH = "main"
DEFAULT_REQUIRED_CHECKS = [
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
        owner_repo = text.strip("/")
        if owner_repo.count("/") == 1:
            owner, repo = owner_repo.split("/", 1)
            if owner.strip() and repo.strip():
                return f"{owner.strip()}/{repo.strip().removesuffix('.git')}"

    patterns = [
        r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        m = re.match(pattern, text)
        if m:
            owner, repo = m.group(1), m.group(2)
            if owner and repo:
                return f"{owner}/{repo}"
    return ""


def _repo_slug_from_remote(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return _parse_repo_slug(proc.stdout.strip())


def _run_gh_api(path: str) -> tuple[bool, Any, str]:
    cmd = ["gh", "api", path]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return False, None, "GH_CLI_NOT_FOUND"
    except Exception as exc:
        return False, None, f"GH_EXEC_ERROR:{exc}"

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        return False, None, f"GH_API_ERROR:{stderr[:240]}"

    out = (proc.stdout or "").strip()
    if not out:
        return False, None, "GH_API_EMPTY"
    try:
        return True, json.loads(out), ""
    except Exception:
        return False, None, "GH_API_INVALID_JSON"


def _extract_contexts(protection_obj: dict[str, Any]) -> list[str]:
    required_status_checks = (
        protection_obj.get("required_status_checks")
        if isinstance(protection_obj.get("required_status_checks"), dict)
        else {}
    )
    contexts: list[str] = []
    raw = required_status_checks.get("contexts")
    if isinstance(raw, list):
        contexts = [str(item).strip() for item in raw if isinstance(item, str) and str(item).strip()]
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


def _extract_write_collaborators(collaborators_obj: Any) -> tuple[int | None, list[str], str]:
    if not isinstance(collaborators_obj, list):
        return None, [], "collaborators_not_list"

    write_users: list[str] = []
    for item in collaborators_obj:
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
            write_users.append(login)
    write_users = sorted(set(write_users))
    return len(write_users), write_users, ""


def _load_lock_defaults(lock_path: Path) -> tuple[str, list[str], dict[str, Any], str]:
    if not lock_path.exists():
        return DEFAULT_BRANCH, list(DEFAULT_REQUIRED_CHECKS), dict(DEFAULT_SOLO_POLICY), "lock_missing"
    try:
        lock_obj = _load_json(lock_path)
    except Exception:
        return DEFAULT_BRANCH, list(DEFAULT_REQUIRED_CHECKS), dict(DEFAULT_SOLO_POLICY), "lock_invalid"

    branch_obj = lock_obj.get("branch_protection") if isinstance(lock_obj.get("branch_protection"), dict) else {}
    default_branch = str(branch_obj.get("default_branch") or "").strip() or DEFAULT_BRANCH
    raw_required_checks = branch_obj.get("required_checks")
    required_checks = [
        str(item).strip()
        for item in (raw_required_checks if isinstance(raw_required_checks, list) else [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not required_checks:
        required_checks = list(DEFAULT_REQUIRED_CHECKS)

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
    return default_branch, sorted(set(required_checks)), solo_policy, "lock"


def _evaluate_repo(
    *,
    repo_slug: str,
    branch: str,
    required_checks: list[str],
    solo_policy: dict[str, Any],
) -> dict[str, Any]:
    protection_ok, protection_obj, protection_error = _run_gh_api(
        f"repos/{repo_slug}/branches/{branch}/protection"
    )
    if not protection_ok or not isinstance(protection_obj, dict):
        return {
            "repo_slug": repo_slug,
            "branch": branch,
            "status": "UNVERIFIED",
            "source": "github_live_check",
            "error": protection_error or "protection_unavailable",
            "required_checks": required_checks,
            "missing_required_checks": [],
            "required_present": None,
            "strict": None,
            "enforce_admins": None,
            "required_pull_request_reviews": None,
            "collaborator_write_count": None,
            "collaborator_write_users": [],
            "solo_policy": {
                "enabled": bool(solo_policy.get("enabled")),
                "status": "UNVERIFIED",
                "rule": "unknown",
                "violations": ["protection_unavailable"],
            },
        }

    contexts = _extract_contexts(protection_obj)
    required_set = set(required_checks)
    missing_required_checks = [check for check in required_checks if check not in set(contexts)]
    required_present = not missing_required_checks and bool(required_checks)

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
    review_count = reviews_obj.get("required_approving_review_count")
    review_count = int(review_count) if isinstance(review_count, int) else 0
    require_code_owner = reviews_obj.get("require_code_owner_reviews")
    require_code_owner = require_code_owner if isinstance(require_code_owner, bool) else False

    collab_ok, collab_obj, collab_error = _run_gh_api(f"repos/{repo_slug}/collaborators?per_page=100")
    write_count, write_users, write_error = _extract_write_collaborators(collab_obj) if collab_ok else (None, [], collab_error)

    policy_enabled = bool(solo_policy.get("enabled"))
    policy_status = "SKIPPED" if not policy_enabled else "OK"
    policy_rule = "none"
    violations: list[str] = []
    expected: dict[str, Any] = {}

    if policy_enabled:
        if write_count is None:
            policy_status = "UNVERIFIED"
            policy_rule = "unknown"
            violations.append("collaborators_unverified")
            if write_error:
                violations.append(write_error)
        elif write_count <= 1:
            policy_rule = "single_writer"
            expected = {
                "required_approving_review_count": int(solo_policy.get("single_writer_requires_review_count") or 0),
                "require_code_owner_reviews": bool(solo_policy.get("single_writer_require_code_owner_reviews")),
            }
            if review_count != expected["required_approving_review_count"]:
                violations.append(
                    "single_writer_required_approving_review_count_mismatch"
                )
            if require_code_owner is not expected["require_code_owner_reviews"]:
                violations.append("single_writer_require_code_owner_reviews_mismatch")
        else:
            policy_rule = "multi_writer"
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

        if policy_status != "UNVERIFIED":
            policy_status = "FAIL" if violations else "OK"

    repo_status = "OK"
    if missing_required_checks:
        repo_status = "FAIL"
    if policy_status == "FAIL":
        repo_status = "FAIL"
    elif policy_status == "UNVERIFIED" and repo_status == "OK":
        repo_status = "UNVERIFIED"

    return {
        "repo_slug": repo_slug,
        "branch": branch,
        "status": repo_status,
        "source": "github_live_check",
        "error": "",
        "required_checks": required_checks,
        "missing_required_checks": missing_required_checks,
        "required_present": required_present,
        "contexts": contexts,
        "strict": strict,
        "enforce_admins": enforce_admins,
        "required_pull_request_reviews": {
            "required_approving_review_count": review_count,
            "require_code_owner_reviews": require_code_owner,
            "dismiss_stale_reviews": bool(reviews_obj.get("dismiss_stale_reviews"))
            if isinstance(reviews_obj.get("dismiss_stale_reviews"), bool)
            else None,
        },
        "collaborator_write_count": write_count,
        "collaborator_write_users": write_users,
        "solo_policy": {
            "enabled": policy_enabled,
            "status": policy_status,
            "rule": policy_rule,
            "expected": expected,
            "actual": {
                "required_approving_review_count": review_count,
                "require_code_owner_reviews": require_code_owner,
                "strict_required_status_checks": strict,
                "enforce_admins": enforce_admins,
                "collaborator_write_count": write_count,
            },
            "violations": sorted(set(violations)),
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", action="append", default=[], help="Repo root to detect origin slug from.")
    parser.add_argument("--repo-slug", action="append", default=[], help="GitHub repo slug: owner/repo.")
    parser.add_argument("--branch", default="", help="Target branch (default: standards.lock -> main).")
    parser.add_argument(
        "--required-check",
        action="append",
        default=[],
        help="Repeatable required check context. Defaults to standards.lock branch_protection.required_checks.",
    )
    parser.add_argument(
        "--standards-lock",
        default="standards.lock",
        help="standards.lock path for policy defaults.",
    )
    parser.add_argument("--mode", choices=["fail", "warn"], default="fail", help="How UNVERIFIED maps to exit code.")
    parser.add_argument(
        "--out",
        default=".cache/reports/branch_protection_solo_policy.v1.json",
        help="Output JSON report path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    lock_path = Path(str(args.standards_lock).strip() or "standards.lock").expanduser().resolve()
    default_branch, lock_required_checks, lock_solo_policy, policy_source = _load_lock_defaults(lock_path)

    branch = str(args.branch).strip() or default_branch
    required_checks = [
        str(item).strip()
        for item in args.required_check
        if isinstance(item, str) and str(item).strip()
    ]
    if not required_checks:
        required_checks = lock_required_checks
    required_checks = sorted(set(required_checks))

    raw_slugs = [
        str(item).strip()
        for item in args.repo_slug
        if isinstance(item, str) and str(item).strip()
    ]
    repo_roots = [Path(str(item).strip()).expanduser().resolve() for item in args.repo_root if str(item).strip()]
    if not raw_slugs and not repo_roots:
        repo_roots = [Path.cwd().resolve()]

    repo_slugs: list[str] = []
    for raw in raw_slugs:
        parsed = _parse_repo_slug(raw)
        if parsed:
            repo_slugs.append(parsed)
    for root in repo_roots:
        slug = _repo_slug_from_remote(root)
        if slug:
            repo_slugs.append(slug)
    repo_slugs = sorted(set(repo_slugs))

    if not repo_slugs:
        payload = {
            "status": "FAIL",
            "error_code": "REPO_SLUG_REQUIRED",
            "message": "GitHub repo slug tespit edilemedi.",
            "generated_at": _now_iso_utc(),
            "policy_source": policy_source,
            "standards_lock_path": str(lock_path),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    repos = [
        _evaluate_repo(
            repo_slug=slug,
            branch=branch,
            required_checks=required_checks,
            solo_policy=lock_solo_policy,
        )
        for slug in repo_slugs
    ]

    fail_count = sum(1 for item in repos if str(item.get("status")) == "FAIL")
    unverified_count = sum(1 for item in repos if str(item.get("status")) == "UNVERIFIED")
    ok_count = sum(1 for item in repos if str(item.get("status")) == "OK")

    overall = "OK"
    if fail_count > 0:
        overall = "FAIL"
    elif unverified_count > 0:
        overall = "WARN" if args.mode == "warn" else "FAIL"

    report = {
        "version": "v1",
        "kind": "branch-protection-solo-policy-report",
        "generated_at": _now_iso_utc(),
        "policy_source": policy_source,
        "standards_lock_path": str(lock_path),
        "mode": str(args.mode),
        "branch": branch,
        "required_checks": required_checks,
        "solo_policy": lock_solo_policy,
        "summary": {
            "status": overall,
            "repos_count": len(repos),
            "ok_count": ok_count,
            "fail_count": fail_count,
            "unverified_count": unverified_count,
        },
        "repos": repos,
    }

    out_path = Path(str(args.out).strip() or ".cache/reports/branch_protection_solo_policy.v1.json")
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": overall,
                "repos_count": len(repos),
                "ok_count": ok_count,
                "fail_count": fail_count,
                "unverified_count": unverified_count,
                "report_path": str(out_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if overall in {"OK", "WARN"} else 2


if __name__ == "__main__":
    sys.exit(main())
