#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if isinstance(cwd, Path) else None,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_sec,
            env=merged_env,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "cmd": cmd,
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "cmd": cmd,
        }


def _safe_repo_slug(raw: str) -> str:
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


def _detect_repo_slug(repo_root: Path) -> str:
    res = _run(["git", "-C", str(repo_root), "remote", "get-url", "origin"])
    if not res["ok"]:
        return ""
    return _safe_repo_slug(str(res["stdout"]).strip())


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _safe_status(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if text in {"OK", "WARN", "FAIL", "UNKNOWN", "UNVERIFIED"}:
        return text
    return "UNKNOWN"


def _combine_status(values: list[str]) -> str:
    normalized = [_safe_status(v) for v in values if str(v or "").strip()]
    if not normalized:
        return "UNKNOWN"
    if any(v == "FAIL" for v in normalized):
        return "FAIL"
    if any(v in {"WARN", "UNVERIFIED", "UNKNOWN"} for v in normalized):
        return "WARN"
    return "OK"


def _parse_post_merge_target(raw: str) -> tuple[str, int] | None:
    text = str(raw or "").strip()
    if not text or "#" not in text:
        return None
    left, right = text.rsplit("#", 1)
    slug = _safe_repo_slug(left)
    if not slug:
        return None
    try:
        pr_number = int(right.strip())
    except Exception:
        return None
    if pr_number <= 0:
        return None
    return slug, pr_number


def _wait_commit_checks_all_green(*, repo_slug: str, sha: str, timeout_sec: int) -> dict[str, Any]:
    end = time.time() + max(10, int(timeout_sec))
    rows: list[dict[str, Any]] = []
    while True:
        res = _run(["gh", "api", f"repos/{repo_slug}/commits/{sha}/check-runs"])
        if not res["ok"]:
            return {
                "status": "FAIL",
                "error": (res["stderr"] or res["stdout"]).strip()[:240],
                "checks": rows,
            }
        try:
            obj = json.loads(res["stdout"])
        except Exception:
            return {"status": "FAIL", "error": "check_runs_invalid_json", "checks": rows}
        raw_runs = obj.get("check_runs") if isinstance(obj.get("check_runs"), list) else []
        rows = []
        pending = 0
        failed = 0
        for item in raw_runs:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            status = str(item.get("status") or "").lower()
            conclusion = str(item.get("conclusion") or "null").lower()
            ok = status == "completed" and conclusion in {"success", "neutral", "skipped"}
            rows.append(
                {
                    "name": name,
                    "status": status,
                    "conclusion": conclusion,
                    "ok": ok,
                    "url": str(item.get("details_url") or ""),
                }
            )
            if status != "completed":
                pending += 1
            elif not ok:
                failed += 1
        if rows and pending == 0:
            return {
                "status": "OK" if failed == 0 else "FAIL",
                "checks": rows,
                "failed_count": failed,
                "pending_count": 0,
            }
        if time.time() >= end:
            return {
                "status": "TIMEOUT",
                "checks": rows,
                "failed_count": failed,
                "pending_count": pending,
            }
        time.sleep(10)


def _build_post_merge_snapshot(
    *,
    repo_slug: str,
    pr_number: int,
    release_evidence_dir: Path,
    merge_open_pr: bool,
    wait_checks: bool,
    wait_timeout_sec: int,
) -> dict[str, Any]:
    pr_view_res = _run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "-R",
            repo_slug,
            "--json",
            "number,state,mergedAt,mergedBy,mergeCommit,headRefName,baseRefName,url,mergeStateStatus,mergeable",
        ]
    )
    if not pr_view_res["ok"]:
        return {
            "status": "FAIL",
            "error": f"pr_view_failed:{(pr_view_res['stderr'] or pr_view_res['stdout']).strip()[:240]}",
            "repo_slug": repo_slug,
            "pr_number": pr_number,
        }

    pr_obj = json.loads(pr_view_res["stdout"])
    pr_state = str(pr_obj.get("state") or "")
    if pr_state != "MERGED" and merge_open_pr:
        merge_res = _run(
            ["gh", "pr", "merge", str(pr_number), "-R", repo_slug, "--merge", "--delete-branch"],
            timeout_sec=wait_timeout_sec,
        )
        if not merge_res["ok"]:
            return {
                "status": "FAIL",
                "error": f"pr_merge_failed:{(merge_res['stderr'] or merge_res['stdout']).strip()[:240]}",
                "repo_slug": repo_slug,
                "pr_number": pr_number,
            }
        pr_view_res = _run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "-R",
                repo_slug,
                "--json",
                "number,state,mergedAt,mergedBy,mergeCommit,headRefName,baseRefName,url",
            ]
        )
        if not pr_view_res["ok"]:
            return {
                "status": "FAIL",
                "error": "pr_view_after_merge_failed",
                "repo_slug": repo_slug,
                "pr_number": pr_number,
            }
        pr_obj = json.loads(pr_view_res["stdout"])
        pr_state = str(pr_obj.get("state") or "")

    if pr_state != "MERGED":
        return {
            "status": "BLOCKED",
            "error": "pr_not_merged",
            "repo_slug": repo_slug,
            "pr_number": pr_number,
            "pr_state": pr_state,
            "pr_url": str(pr_obj.get("url") or ""),
        }

    merge_commit = pr_obj.get("mergeCommit") if isinstance(pr_obj.get("mergeCommit"), dict) else {}
    merge_sha = str(merge_commit.get("oid") or "").strip()
    if not merge_sha:
        return {
            "status": "FAIL",
            "error": "merge_commit_missing",
            "repo_slug": repo_slug,
            "pr_number": pr_number,
        }

    check_wait = {"status": "SKIPPED", "checks": []}
    if wait_checks:
        check_wait = _wait_commit_checks_all_green(repo_slug=repo_slug, sha=merge_sha, timeout_sec=wait_timeout_sec)
        if check_wait.get("status") != "OK":
            return {
                "status": "FAIL",
                "error": f"post_merge_checks_not_green:{check_wait.get('status')}",
                "repo_slug": repo_slug,
                "pr_number": pr_number,
                "merge_sha": merge_sha,
                "check_wait": check_wait,
            }

    protection_res = _run(["gh", "api", f"repos/{repo_slug}/branches/main/protection"])
    if not protection_res["ok"]:
        return {
            "status": "FAIL",
            "error": "branch_protection_fetch_failed",
            "repo_slug": repo_slug,
            "pr_number": pr_number,
            "merge_sha": merge_sha,
        }
    protection = json.loads(protection_res["stdout"])

    check_runs_res = _run(["gh", "api", f"repos/{repo_slug}/commits/{merge_sha}/check-runs"])
    if not check_runs_res["ok"]:
        return {
            "status": "FAIL",
            "error": "check_runs_fetch_failed",
            "repo_slug": repo_slug,
            "pr_number": pr_number,
            "merge_sha": merge_sha,
        }
    check_runs_obj = json.loads(check_runs_res["stdout"])
    check_runs = check_runs_obj.get("check_runs") if isinstance(check_runs_obj.get("check_runs"), list) else []

    collabs_res = _run(["gh", "api", f"repos/{repo_slug}/collaborators?per_page=100"])
    collabs = []
    if collabs_res["ok"]:
        try:
            collabs = json.loads(collabs_res["stdout"])
        except Exception:
            collabs = []

    required_status = (
        protection.get("required_status_checks")
        if isinstance(protection.get("required_status_checks"), dict)
        else {}
    )
    contexts = required_status.get("contexts") if isinstance(required_status.get("contexts"), list) else []
    required_checks = sorted({str(c) for c in contexts if isinstance(c, str) and c.strip()})

    check_map: dict[str, dict[str, Any]] = {}
    failed_checks: list[str] = []
    for item in check_runs:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        status = str(item.get("status") or "").lower()
        conclusion = str(item.get("conclusion") or "null").lower()
        ok = status == "completed" and conclusion in {"success", "neutral", "skipped"}
        row = {
            "status": status,
            "conclusion": conclusion,
            "ok": ok,
            "url": str(item.get("details_url") or ""),
        }
        check_map[name] = row
        if status == "completed" and not ok:
            failed_checks.append(name)

    required_check_results = {
        ctx: check_map.get(ctx, {"status": "missing", "conclusion": "missing", "ok": False, "url": ""})
        for ctx in required_checks
    }
    missing_required_checks = [ctx for ctx in required_checks if ctx not in check_map]

    write_users: list[str] = []
    if isinstance(collabs, list):
        for item in collabs:
            if not isinstance(item, dict):
                continue
            login = str(item.get("login") or "").strip()
            perms = item.get("permissions") if isinstance(item.get("permissions"), dict) else {}
            can_write = bool(
                perms.get("admin") is True
                or perms.get("maintain") is True
                or perms.get("push") is True
            )
            if can_write and login:
                write_users.append(login)
    write_users = sorted(set(write_users))
    write_count = len(write_users)

    reviews_obj = (
        protection.get("required_pull_request_reviews")
        if isinstance(protection.get("required_pull_request_reviews"), dict)
        else {}
    )
    review_count = int(reviews_obj.get("required_approving_review_count") or 0)
    require_code_owner = (
        bool(reviews_obj.get("require_code_owner_reviews"))
        if isinstance(reviews_obj.get("require_code_owner_reviews"), bool)
        else False
    )
    strict = required_status.get("strict") if isinstance(required_status.get("strict"), bool) else None
    enforce_admins = (
        (protection.get("enforce_admins") or {}).get("enabled")
        if isinstance(protection.get("enforce_admins"), dict)
        else None
    )

    solo_violations: list[str] = []
    if write_count <= 1:
        if review_count != 0:
            solo_violations.append("single_writer_required_approving_review_count_mismatch")
        if require_code_owner is not False:
            solo_violations.append("single_writer_require_code_owner_reviews_mismatch")
        solo_rule = "single_writer"
    else:
        if review_count < 1:
            solo_violations.append("multi_writer_required_approving_review_count_too_low")
        if require_code_owner is not True:
            solo_violations.append("multi_writer_require_code_owner_reviews_mismatch")
        solo_rule = "multi_writer"
    if strict is not True:
        solo_violations.append("strict_required_status_checks_must_be_true")
    if enforce_admins is not True:
        solo_violations.append("enforce_admins_must_be_true")
    if missing_required_checks:
        solo_violations.append("missing_required_checks")

    solo_ok = not solo_violations
    status = "OK"
    if failed_checks or missing_required_checks or not solo_ok:
        status = "FAIL"

    pr_merged_by = (
        (pr_obj.get("mergedBy") or {}).get("login")
        if isinstance(pr_obj.get("mergedBy"), dict)
        else ""
    )
    snapshot = {
        "version": "v1",
        "kind": "post-merge-lock-snapshot",
        "generated_at": _now_iso_utc(),
        "repo": repo_slug,
        "pull_request": {
            "number": int(pr_obj.get("number") or pr_number),
            "state": str(pr_obj.get("state") or ""),
            "url": str(pr_obj.get("url") or ""),
            "head": str(pr_obj.get("headRefName") or ""),
            "base": str(pr_obj.get("baseRefName") or ""),
            "merged_at": str(pr_obj.get("mergedAt") or ""),
            "merged_by": str(pr_merged_by or ""),
            "merge_commit": merge_sha,
        },
        "branch_protection": {
            "default_branch": "main",
            "required_checks": required_checks,
            "strict": strict,
            "enforce_admins": enforce_admins,
            "required_approving_review_count": review_count,
            "require_code_owner_reviews": require_code_owner,
        },
        "required_check_results": required_check_results,
        "solo_policy": {
            "rule": solo_rule,
            "collaborator_write_count": write_count,
            "collaborator_write_users": write_users,
            "status": "OK" if solo_ok else "FAIL",
            "violations": sorted(set(solo_violations)),
        },
        "summary": {
            "status": status,
            "required_checks_total": len(required_checks),
            "required_checks_missing_count": len(missing_required_checks),
            "failed_check_count": len(failed_checks),
            "all_required_green": len(missing_required_checks) == 0 and len(failed_checks) == 0,
            "solo_policy_ok": solo_ok,
        },
    }

    safe_repo = repo_slug.replace("/", "_")
    out_path = release_evidence_dir / f"{safe_repo}_pr{pr_number}_post_merge_lock_snapshot.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "status": status,
        "repo_slug": repo_slug,
        "pr_number": pr_number,
        "path": str(out_path),
        "merge_sha": merge_sha,
        "summary": snapshot["summary"],
    }


def _build_managed_pipeline_snapshot(
    *,
    orchestrator_root: Path,
    managed_manifest_path: Path,
    sync_report_path: Path,
    drift_scoreboard_path: Path,
    system_status_path: Path,
    portfolio_status_path: Path,
    live_gate_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    manifest = _load_json(managed_manifest_path) if managed_manifest_path.exists() else {}
    sync = _load_json(sync_report_path) if sync_report_path.exists() else {}
    drift = _load_json(drift_scoreboard_path) if drift_scoreboard_path.exists() else {}
    system = _load_json(system_status_path) if system_status_path.exists() else {}
    portfolio = _load_json(portfolio_status_path) if portfolio_status_path.exists() else {}
    live_gate = _load_json(live_gate_path) if live_gate_path.exists() else {}

    drift_summary = drift.get("summary") if isinstance(drift.get("summary"), dict) else {}
    sync_results = sync.get("results") if isinstance(sync.get("results"), list) else []
    drift_repos = drift.get("repos") if isinstance(drift.get("repos"), list) else []
    live_summary = live_gate.get("summary") if isinstance(live_gate.get("summary"), dict) else {}

    portfolio_status = _safe_status(portfolio.get("status"))
    if portfolio_status == "UNKNOWN":
        portfolio_status = _combine_status(
            [
                str((portfolio.get("drift_scoreboard") or {}).get("status") or ""),
                str((portfolio.get("managed_repo_standards") or {}).get("status") or ""),
            ]
        )

    live_gate_status = _safe_status(live_summary.get("status"))
    if live_gate_status == "UNKNOWN":
        live_gate_status = _safe_status(live_gate.get("status"))

    snapshot = {
        "version": "v1",
        "kind": "managed-repo-onboarding-pipeline-snapshot",
        "generated_at": _now_iso_utc(),
        "workspace_root": str(orchestrator_root),
        "scope": {
            "managed_repo_count": int((manifest.get("meta") or {}).get("count") or 0),
            "managed_repo_roots": [
                str(item.get("repo_root"))
                for item in (manifest.get("repos") if isinstance(manifest.get("repos"), list) else [])
                if isinstance(item, dict) and isinstance(item.get("repo_root"), str)
            ],
        },
        "sources": {
            "manifest_path": str(managed_manifest_path),
            "sync_report_path": str(sync_report_path),
            "drift_scoreboard_path": str(drift_scoreboard_path),
            "system_status_path": str(system_status_path),
            "portfolio_status_path": str(portfolio_status_path),
            "live_gate_path": str(live_gate_path),
        },
        "summary": {
            "sync_status": "OK" if int(sync.get("failed_count") or 0) == 0 else "FAIL",
            "sync_target_count": int(sync.get("target_count") or len(sync_results)),
            "sync_failed_count": int(sync.get("failed_count") or 0),
            "drift_status": _safe_status(drift_summary.get("status")),
            "drift_repos_count": int(drift_summary.get("repos_count") or len(drift_repos)),
            "rollout_blocked_count": int(drift_summary.get("rollout_blocked_count") or 0),
            "system_overall_status": _safe_status(system.get("overall_status")),
            "portfolio_status": portfolio_status,
            "live_gate_status": live_gate_status,
            "live_gate_fail_count": int(live_summary.get("fail_count") or 0),
            "live_gate_unverified_count": int(live_summary.get("unverified_count") or 0),
        },
        "repos": [
            {
                "repo_root": str(item.get("repo_root") or ""),
                "status": str(item.get("status") or ""),
                "drift_state": str(item.get("drift_state") or ""),
                "lane_config_status": str(item.get("lane_config_status") or ""),
                "branch_protection_status": str(item.get("branch_protection_status") or ""),
                "branch_solo_policy_status": str(item.get("branch_solo_policy_status") or ""),
                "rollout_recommendation": str(item.get("rollout_recommendation") or ""),
            }
            for item in drift_repos
            if isinstance(item, dict)
        ],
        "live_gate_repos": [
            {
                "repo_slug": str(item.get("repo_slug") or ""),
                "status": str(item.get("status") or ""),
                "solo_policy_status": str((item.get("solo_policy") or {}).get("status") or ""),
                "rule": str((item.get("solo_policy") or {}).get("rule") or ""),
            }
            for item in (live_gate.get("repos") if isinstance(live_gate.get("repos"), list) else [])
            if isinstance(item, dict)
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return snapshot


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", action="append", default=[], help="Managed repo root (repeatable).")
    parser.add_argument("--repos-csv", default="", help="Managed repo roots in CSV format.")
    parser.add_argument(
        "--workspace-root-prefix",
        default=".cache/ws_customer_default_multi2",
        help="Workspace root prefix for onboarding script.",
    )
    parser.add_argument("--repo-slug", action="append", default=[], help="Repo slug for live gate (repeatable).")
    parser.add_argument(
        "--post-merge-target",
        action="append",
        default=[],
        help="Format: owner/repo#pr_number (repeatable).",
    )
    parser.add_argument(
        "--merge-open-pr",
        action="store_true",
        help="Allow script to merge open PR for post-merge target.",
    )
    parser.add_argument(
        "--skip-wait-post-merge-checks",
        action="store_true",
        help="Do not wait merge commit check-runs after merge.",
    )
    parser.add_argument(
        "--wait-timeout-sec",
        type=int,
        default=1800,
        help="Timeout for waiting post-merge checks.",
    )
    parser.add_argument(
        "--live-gate-mode",
        choices=["fail", "warn"],
        default="fail",
        help="Mode for check_branch_protection_solo_policy.",
    )
    parser.add_argument(
        "--out",
        default=".cache/reports/release-evidence/managed_repo_onboarding_pipeline.v1.json",
        help="Pipeline report output path.",
    )
    parser.add_argument(
        "--snapshot-out",
        default=".cache/reports/release-evidence/managed_repo_onboarding_pipeline_lock_snapshot.v1.json",
        help="Managed repo lock snapshot output path.",
    )
    parser.add_argument(
        "--bundle-out",
        default=".cache/reports/release-evidence/portfolio_lock_bundle.v1.json",
        help="Portfolio lock bundle output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    orchestrator_root = Path.cwd().resolve()
    release_evidence_dir = (orchestrator_root / ".cache/reports/release-evidence").resolve()
    release_evidence_dir.mkdir(parents=True, exist_ok=True)

    repo_roots: list[Path] = []
    for raw in args.repo_root:
        text = str(raw).strip()
        if text:
            repo_roots.append(Path(text).expanduser().resolve())
    csv_text = str(args.repos_csv).strip()
    if csv_text:
        for part in csv_text.split(","):
            text = str(part).strip()
            if text:
                repo_roots.append(Path(text).expanduser().resolve())
    repo_roots = sorted({p for p in repo_roots})
    if not repo_roots:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "REPO_ROOT_REQUIRED",
                    "message": "--repo-root or --repos-csv must include at least one path.",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    workspace_root_prefix = Path(str(args.workspace_root_prefix).strip() or ".cache/ws_customer_default_multi2")
    if not workspace_root_prefix.is_absolute():
        workspace_root_prefix = (orchestrator_root / workspace_root_prefix).resolve()
    workspace_root_prefix.mkdir(parents=True, exist_ok=True)

    repos_csv = ",".join(str(p) for p in repo_roots)

    onboard_cmd = [
        str((orchestrator_root / "scripts/onboard_managed_repos.sh").resolve()),
        repos_csv,
        str(workspace_root_prefix),
    ]
    onboard_res = _run(
        onboard_cmd,
        cwd=orchestrator_root,
        env={"SYNC_STANDARDS_ONBOARD": "true", "SYNC_STANDARDS_VALIDATE": "true"},
    )

    workspace_manifest = (workspace_root_prefix / ".cache/managed_repos.v1.json").resolve()
    root_manifest = (orchestrator_root / ".cache/managed_repos.v1.json").resolve()
    manifest_sync = {"status": "SKIPPED", "path": str(root_manifest)}
    if workspace_manifest.exists():
        root_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace_manifest, root_manifest)
        manifest_sync = {"status": "OK", "path": str(root_manifest), "source": str(workspace_manifest)}
    else:
        manifest_sync = {"status": "FAIL", "path": str(root_manifest), "source": str(workspace_manifest)}

    sync_cmd = [
        "python3",
        str((orchestrator_root / "scripts/sync_managed_repo_standards.py").resolve()),
        "--source-root",
        str(orchestrator_root),
        "--manifest-path",
        str(root_manifest),
        "--apply",
        "--validate-after-sync",
    ]
    sync_res = _run(sync_cmd, cwd=orchestrator_root)

    live_slugs: set[str] = set()
    for raw in args.repo_slug:
        slug = _safe_repo_slug(raw)
        if slug:
            live_slugs.add(slug)
    for root in repo_roots:
        slug = _detect_repo_slug(root)
        if slug:
            live_slugs.add(slug)
    self_slug = _detect_repo_slug(orchestrator_root)
    if self_slug:
        live_slugs.add(self_slug)

    live_gate_path = release_evidence_dir / "managed_repo_live_gate_snapshot.v1.json"
    live_gate_cmd = [
        "python3",
        str((orchestrator_root / "scripts/check_branch_protection_solo_policy.py").resolve()),
        "--mode",
        str(args.live_gate_mode),
        "--out",
        str(live_gate_path),
    ]
    for slug in sorted(live_slugs):
        live_gate_cmd.extend(["--repo-slug", slug])
    live_gate_res = _run(live_gate_cmd, cwd=orchestrator_root)

    system_res = _run(
        ["python3", "-m", "src.ops.manage", "system-status", "--workspace-root", "."],
        cwd=orchestrator_root,
    )
    portfolio_res = _run(
        ["python3", "-m", "src.ops.manage", "portfolio-status", "--workspace-root", "."],
        cwd=orchestrator_root,
    )

    snapshot_out = Path(str(args.snapshot_out).strip() or ".cache/reports/release-evidence/managed_repo_onboarding_pipeline_lock_snapshot.v1.json")
    if not snapshot_out.is_absolute():
        snapshot_out = (orchestrator_root / snapshot_out).resolve()

    managed_snapshot = _build_managed_pipeline_snapshot(
        orchestrator_root=orchestrator_root,
        managed_manifest_path=root_manifest,
        sync_report_path=(orchestrator_root / ".cache/reports/managed_repo_standards_sync/report.v1.json").resolve(),
        drift_scoreboard_path=(orchestrator_root / ".cache/reports/drift_scoreboard.v1.json").resolve(),
        system_status_path=(orchestrator_root / ".cache/reports/system_status.v1.json").resolve(),
        portfolio_status_path=(orchestrator_root / ".cache/reports/portfolio_status.v1.json").resolve(),
        live_gate_path=live_gate_path,
        out_path=snapshot_out,
    )

    post_merge_results: list[dict[str, Any]] = []
    for raw in args.post_merge_target:
        parsed = _parse_post_merge_target(raw)
        if not parsed:
            post_merge_results.append({"status": "FAIL", "error": f"invalid_post_merge_target:{raw}"})
            continue
        repo_slug, pr_number = parsed
        post_merge_results.append(
            _build_post_merge_snapshot(
                repo_slug=repo_slug,
                pr_number=pr_number,
                release_evidence_dir=release_evidence_dir,
                merge_open_pr=bool(args.merge_open_pr),
                wait_checks=not bool(args.skip_wait_post_merge_checks),
                wait_timeout_sec=int(args.wait_timeout_sec),
            )
        )

    bundle_out = Path(str(args.bundle_out).strip() or ".cache/reports/release-evidence/portfolio_lock_bundle.v1.json")
    if not bundle_out.is_absolute():
        bundle_out = (orchestrator_root / bundle_out).resolve()
    bundle_cmd = [
        "python3",
        str((orchestrator_root / "scripts/build_portfolio_lock_bundle.py").resolve()),
        "--evidence-dir",
        str(release_evidence_dir),
        "--out",
        str(bundle_out),
    ]
    bundle_res = _run(bundle_cmd, cwd=orchestrator_root)

    steps = {
        "onboard": {
            "ok": onboard_res["ok"],
            "returncode": onboard_res["returncode"],
            "stdout_tail": str(onboard_res["stdout"]).splitlines()[-20:],
            "stderr_tail": str(onboard_res["stderr"]).splitlines()[-20:],
        },
        "manifest_sync": manifest_sync,
        "sync": {
            "ok": sync_res["ok"],
            "returncode": sync_res["returncode"],
            "stdout_tail": str(sync_res["stdout"]).splitlines()[-20:],
            "stderr_tail": str(sync_res["stderr"]).splitlines()[-20:],
        },
        "live_gate": {
            "ok": live_gate_res["ok"],
            "returncode": live_gate_res["returncode"],
            "path": str(live_gate_path),
            "stdout_tail": str(live_gate_res["stdout"]).splitlines()[-20:],
            "stderr_tail": str(live_gate_res["stderr"]).splitlines()[-20:],
            "repo_slugs": sorted(live_slugs),
        },
        "system_status": {
            "ok": system_res["ok"],
            "returncode": system_res["returncode"],
            "stdout_tail": str(system_res["stdout"]).splitlines()[-20:],
            "stderr_tail": str(system_res["stderr"]).splitlines()[-20:],
        },
        "portfolio_status": {
            "ok": portfolio_res["ok"],
            "returncode": portfolio_res["returncode"],
            "stdout_tail": str(portfolio_res["stdout"]).splitlines()[-20:],
            "stderr_tail": str(portfolio_res["stderr"]).splitlines()[-20:],
        },
        "managed_snapshot": {"path": str(snapshot_out), "status": str(managed_snapshot.get("summary", {}).get("sync_status", ""))},
        "post_merge": post_merge_results,
        "bundle": {
            "ok": bundle_res["ok"],
            "returncode": bundle_res["returncode"],
            "path": str(bundle_out),
            "stdout_tail": str(bundle_res["stdout"]).splitlines()[-20:],
            "stderr_tail": str(bundle_res["stderr"]).splitlines()[-20:],
        },
    }

    overall_status = "OK"
    if not onboard_res["ok"] or not sync_res["ok"] or not system_res["ok"] or not portfolio_res["ok"]:
        overall_status = "FAIL"
    if manifest_sync.get("status") == "FAIL":
        overall_status = "FAIL"
    if post_merge_results and any(str(item.get("status")) != "OK" for item in post_merge_results):
        overall_status = "FAIL"
    if not bundle_res["ok"] and overall_status == "OK":
        overall_status = "WARN"
    if not live_gate_res["ok"] and overall_status == "OK":
        overall_status = "WARN"

    report = {
        "version": "v1",
        "kind": "managed-repo-onboarding-pipeline-report",
        "generated_at": _now_iso_utc(),
        "status": overall_status,
        "workspace_root": str(orchestrator_root),
        "repo_roots": [str(p) for p in repo_roots],
        "post_merge_targets": [str(x) for x in args.post_merge_target],
        "outputs": {
            "managed_snapshot": str(snapshot_out),
            "bundle": str(bundle_out),
            "live_gate": str(live_gate_path),
        },
        "steps": steps,
    }

    out_path = Path(str(args.out).strip() or ".cache/reports/release-evidence/managed_repo_onboarding_pipeline.v1.json")
    if not out_path.is_absolute():
        out_path = (orchestrator_root / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": overall_status,
                "out": str(out_path),
                "managed_snapshot": str(snapshot_out),
                "bundle_out": str(bundle_out),
                "post_merge_count": len(post_merge_results),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if overall_status in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
