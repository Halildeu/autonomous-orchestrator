from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .managed_repo_standards import build_managed_repo_standards_summary


SYNC_REPORT_REL = Path(".cache") / "reports" / "managed_repo_standards_sync" / "report.v1.json"
SCOREBOARD_REPORT_REL = Path(".cache") / "reports" / "drift_scoreboard.v1.json"
STANDARDS_LOCK_REL = Path("standards.lock")

DEFAULT_REQUIRED_LANES = ("unit", "contract", "integration", "e2e")
DEFAULT_DELIVERY_SEQUENCE = ("backend", "frontend", "integration", "e2e")
DEFAULT_REQUIRED_BRANCH_CHECK = "module-delivery-gate"
DEFAULT_BRANCH = "main"

PLACEHOLDER_TOKENS = (
    "TODO",
    "PLACEHOLDER",
    "<repo_root>",
    "<command>",
    "configure_me",
)


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_paths(workspace_root: Path, core_root: Path, rel: Path) -> list[Path]:
    candidates = [
        (workspace_root / rel).resolve(),
        (workspace_root.parent / rel).resolve(),
        (core_root / rel).resolve(),
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


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


def _contains_placeholder(value: str) -> bool:
    raw = str(value or "")
    raw_upper = raw.upper()
    for token in PLACEHOLDER_TOKENS:
        if token.upper() in raw_upper:
            return True
    return False


def _load_lock_policy(*, workspace_root: Path, core_root: Path) -> dict[str, Any]:
    lock_candidates = _candidate_paths(workspace_root, core_root, STANDARDS_LOCK_REL)
    lock_path = _first_existing(lock_candidates)
    if not isinstance(lock_path, Path):
        return {
            "required_lanes": list(DEFAULT_REQUIRED_LANES),
            "delivery_sequence": list(DEFAULT_DELIVERY_SEQUENCE),
            "required_branch_check": DEFAULT_REQUIRED_BRANCH_CHECK,
            "default_branch": DEFAULT_BRANCH,
            "branch_verification_mode": "live_evidence",
            "preserve_existing_paths": [],
            "lock_path": _display_path(lock_candidates[0], workspace_root, core_root),
        }

    try:
        lock_obj = _load_json(lock_path)
    except Exception:
        return {
            "required_lanes": list(DEFAULT_REQUIRED_LANES),
            "delivery_sequence": list(DEFAULT_DELIVERY_SEQUENCE),
            "required_branch_check": DEFAULT_REQUIRED_BRANCH_CHECK,
            "default_branch": DEFAULT_BRANCH,
            "branch_verification_mode": "live_evidence",
            "preserve_existing_paths": [],
            "lock_path": _display_path(lock_path, workspace_root, core_root),
            "notes": ["standards_lock_invalid_json"],
        }

    if not isinstance(lock_obj, dict):
        return {
            "required_lanes": list(DEFAULT_REQUIRED_LANES),
            "delivery_sequence": list(DEFAULT_DELIVERY_SEQUENCE),
            "required_branch_check": DEFAULT_REQUIRED_BRANCH_CHECK,
            "default_branch": DEFAULT_BRANCH,
            "branch_verification_mode": "live_evidence",
            "preserve_existing_paths": [],
            "lock_path": _display_path(lock_path, workspace_root, core_root),
            "notes": ["standards_lock_not_object"],
        }

    module_contract = (
        lock_obj.get("module_delivery_contract")
        if isinstance(lock_obj.get("module_delivery_contract"), dict)
        else {}
    )
    raw_lanes = module_contract.get("required_test_lanes")
    required_lanes = [
        str(item).strip()
        for item in (raw_lanes if isinstance(raw_lanes, list) else [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not required_lanes:
        required_lanes = list(DEFAULT_REQUIRED_LANES)
    raw_delivery_sequence = module_contract.get("delivery_sequence")
    delivery_sequence = [
        str(item).strip()
        for item in (raw_delivery_sequence if isinstance(raw_delivery_sequence, list) else [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not delivery_sequence:
        delivery_sequence = list(DEFAULT_DELIVERY_SEQUENCE)

    branch_section = lock_obj.get("branch_protection") if isinstance(lock_obj.get("branch_protection"), dict) else {}
    default_branch = str(branch_section.get("default_branch") or "").strip() or DEFAULT_BRANCH
    branch_verification_mode = str(branch_section.get("verification_mode") or "live_evidence").strip()
    if branch_verification_mode not in {"live_evidence", "report_only"}:
        branch_verification_mode = "live_evidence"

    raw_required_checks = branch_section.get("required_checks")
    required_checks = [
        str(item).strip()
        for item in (raw_required_checks if isinstance(raw_required_checks, list) else [])
        if isinstance(item, str) and str(item).strip()
    ]
    required_branch_check = required_checks[0] if required_checks else DEFAULT_REQUIRED_BRANCH_CHECK

    managed_sync = lock_obj.get("managed_repo_sync") if isinstance(lock_obj.get("managed_repo_sync"), dict) else {}
    raw_preserve = managed_sync.get("preserve_existing_paths")
    preserve_existing_paths = [
        str(item).strip()
        for item in (raw_preserve if isinstance(raw_preserve, list) else [])
        if isinstance(item, str) and str(item).strip()
    ]

    return {
        "required_lanes": sorted(set(required_lanes)),
        "delivery_sequence": delivery_sequence,
        "required_branch_check": required_branch_check,
        "default_branch": default_branch,
        "branch_verification_mode": branch_verification_mode,
        "preserve_existing_paths": sorted(set(preserve_existing_paths)),
        "lock_path": _display_path(lock_path, workspace_root, core_root),
    }


def _normalize_repo_root(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    return str(Path(raw).expanduser().resolve())


def _load_sync_report(*, workspace_root: Path, core_root: Path, managed_summary: dict[str, Any]) -> tuple[dict[str, Any], str]:
    report_path_str = str(managed_summary.get("report_path") or "").strip()
    candidates: list[Path] = []
    if report_path_str:
        p = Path(report_path_str)
        if p.is_absolute():
            candidates.append(p.resolve())
        else:
            candidates.append((workspace_root / p).resolve())
            candidates.append((core_root / p).resolve())
    candidates.extend(_candidate_paths(workspace_root, core_root, SYNC_REPORT_REL))
    path = _first_existing(candidates)
    if not isinstance(path, Path):
        return ({}, _display_path(candidates[0] if candidates else None, workspace_root, core_root))
    try:
        obj = _load_json(path)
    except Exception:
        return ({}, _display_path(path, workspace_root, core_root))
    return (obj if isinstance(obj, dict) else {}, _display_path(path, workspace_root, core_root))


def _read_lane_config(repo_root: str, *, required_lanes: list[str]) -> dict[str, Any]:
    commands: dict[str, str] = {lane: "" for lane in required_lanes}
    missing_lanes: list[str] = []
    placeholder_lanes: list[str] = []
    execution_sequence: list[str] = []
    scope_lane_map: dict[str, str] = {}
    profile = ""
    status = "MISSING"

    repo = Path(repo_root).expanduser().resolve() if repo_root else None
    if not isinstance(repo, Path):
        return {
            "config_status": "MISSING",
            "config_path": "",
            "managed_repo_profile": profile,
            "missing_lanes": list(required_lanes),
            "placeholder_lanes": [],
            "execution_sequence": execution_sequence,
            "scope_lane_map": scope_lane_map,
            "commands": commands,
        }

    config_path = repo / "ci" / "module_delivery_lanes.v1.json"
    if not config_path.exists():
        return {
            "config_status": "MISSING",
            "config_path": str(config_path),
            "managed_repo_profile": profile,
            "missing_lanes": list(required_lanes),
            "placeholder_lanes": [],
            "execution_sequence": execution_sequence,
            "scope_lane_map": scope_lane_map,
            "commands": commands,
        }

    try:
        obj = _load_json(config_path)
    except Exception:
        return {
            "config_status": "INVALID",
            "config_path": str(config_path),
            "managed_repo_profile": profile,
            "missing_lanes": list(required_lanes),
            "placeholder_lanes": [],
            "execution_sequence": execution_sequence,
            "scope_lane_map": scope_lane_map,
            "commands": commands,
        }
    if not isinstance(obj, dict):
        return {
            "config_status": "INVALID",
            "config_path": str(config_path),
            "managed_repo_profile": profile,
            "missing_lanes": list(required_lanes),
            "placeholder_lanes": [],
            "execution_sequence": execution_sequence,
            "scope_lane_map": scope_lane_map,
            "commands": commands,
        }

    profile = str(obj.get("managed_repo_profile") or "")
    raw_sequence = obj.get("execution_sequence")
    if isinstance(raw_sequence, list):
        execution_sequence = [str(item).strip() for item in raw_sequence if isinstance(item, str) and str(item).strip()]
    raw_scope_map = obj.get("scope_lane_map")
    if isinstance(raw_scope_map, dict):
        scope_lane_map = {
            str(key).strip(): str(value).strip()
            for key, value in raw_scope_map.items()
            if isinstance(key, str) and str(key).strip() and isinstance(value, str) and str(value).strip()
        }
    lanes = obj.get("lanes")
    if not isinstance(lanes, dict):
        return {
            "config_status": "INVALID",
            "config_path": str(config_path),
            "managed_repo_profile": profile,
            "missing_lanes": list(required_lanes),
            "placeholder_lanes": [],
            "execution_sequence": execution_sequence,
            "scope_lane_map": scope_lane_map,
            "commands": commands,
        }

    for lane in required_lanes:
        lane_obj = lanes.get(lane)
        if not isinstance(lane_obj, dict):
            missing_lanes.append(lane)
            continue
        command = lane_obj.get("command")
        if not isinstance(command, str) or not command.strip():
            missing_lanes.append(lane)
            continue
        cmd = str(command).strip()
        commands[lane] = cmd
        if _contains_placeholder(cmd):
            placeholder_lanes.append(lane)

    if not missing_lanes:
        status = "OK"
    elif len(missing_lanes) == len(required_lanes):
        status = "MISSING"
    else:
        status = "PARTIAL"

    return {
        "config_status": status,
        "config_path": str(config_path),
        "managed_repo_profile": profile,
        "missing_lanes": missing_lanes,
        "placeholder_lanes": sorted(set(placeholder_lanes)),
        "execution_sequence": execution_sequence,
        "scope_lane_map": scope_lane_map,
        "commands": commands,
    }


def _branch_protection_status(
    *,
    repo_root: str,
    sync_result: dict[str, Any] | None,
    required_check: str,
) -> dict[str, Any]:
    if isinstance(sync_result, dict):
        branch_obj = sync_result.get("branch_protection")
        if isinstance(branch_obj, dict):
            required_present = branch_obj.get("required_present")
            raw_status = str(branch_obj.get("status") or "").upper()
            source = str(branch_obj.get("source") or "sync_report")
            solo_obj = branch_obj.get("solo_policy") if isinstance(branch_obj.get("solo_policy"), dict) else {}
            solo_status = str(solo_obj.get("status") or "").upper()
            if solo_status not in {"OK", "FAIL", "UNVERIFIED", "SKIPPED"}:
                solo_status = "UNVERIFIED"
            solo_rule = str(solo_obj.get("rule") or "")
            solo_violations = (
                sorted(
                    {
                        str(item).strip()
                        for item in (solo_obj.get("violations") if isinstance(solo_obj.get("violations"), list) else [])
                        if isinstance(item, str) and str(item).strip()
                    }
                )
                if isinstance(solo_obj, dict)
                else []
            )
            collaborator_write_count = (
                int(branch_obj.get("collaborator_write_count"))
                if isinstance(branch_obj.get("collaborator_write_count"), int)
                else None
            )

            if raw_status in {"OK", "FAIL", "UNVERIFIED"}:
                return {
                    "status": raw_status,
                    "required_check": required_check,
                    "required_present": required_present if isinstance(required_present, bool) else None,
                    "source": source,
                    "solo_policy_status": solo_status,
                    "solo_policy_rule": solo_rule,
                    "solo_policy_violations": solo_violations,
                    "collaborator_write_count": collaborator_write_count,
                }
            if required_present is True:
                return {
                    "status": "OK",
                    "required_check": required_check,
                    "required_present": True,
                    "source": source,
                    "solo_policy_status": solo_status,
                    "solo_policy_rule": solo_rule,
                    "solo_policy_violations": solo_violations,
                    "collaborator_write_count": collaborator_write_count,
                }
            if required_present is False:
                return {
                    "status": "FAIL",
                    "required_check": required_check,
                    "required_present": False,
                    "source": source,
                    "solo_policy_status": solo_status,
                    "solo_policy_rule": solo_rule,
                    "solo_policy_violations": solo_violations,
                    "collaborator_write_count": collaborator_write_count,
                }

    repo = Path(repo_root).expanduser().resolve() if repo_root else None
    if not isinstance(repo, Path):
        return {
            "status": "UNVERIFIED",
            "required_check": required_check,
            "required_present": None,
            "source": "repo_missing",
            "solo_policy_status": "UNVERIFIED",
            "solo_policy_rule": "",
            "solo_policy_violations": ["repo_missing"],
            "collaborator_write_count": None,
        }

    local_report = repo / ".cache" / "reports" / "branch_protection.v1.json"
    if not local_report.exists():
        return {
            "status": "UNVERIFIED",
            "required_check": required_check,
            "required_present": None,
            "source": "branch_report_missing",
            "solo_policy_status": "UNVERIFIED",
            "solo_policy_rule": "",
            "solo_policy_violations": ["branch_report_missing"],
            "collaborator_write_count": None,
        }

    try:
        obj = _load_json(local_report)
    except Exception:
        return {
            "status": "UNVERIFIED",
            "required_check": required_check,
            "required_present": None,
            "source": "branch_report_invalid",
            "solo_policy_status": "UNVERIFIED",
            "solo_policy_rule": "",
            "solo_policy_violations": ["branch_report_invalid"],
            "collaborator_write_count": None,
        }
    if not isinstance(obj, dict):
        return {
            "status": "UNVERIFIED",
            "required_check": required_check,
            "required_present": None,
            "source": "branch_report_invalid",
            "solo_policy_status": "UNVERIFIED",
            "solo_policy_rule": "",
            "solo_policy_violations": ["branch_report_invalid"],
            "collaborator_write_count": None,
        }

    solo_obj = obj.get("solo_policy") if isinstance(obj.get("solo_policy"), dict) else {}
    solo_status = str(solo_obj.get("status") or "").upper()
    if solo_status not in {"OK", "FAIL", "UNVERIFIED", "SKIPPED"}:
        solo_status = "UNVERIFIED"
    solo_rule = str(solo_obj.get("rule") or "")
    solo_violations = sorted(
        {
            str(item).strip()
            for item in (solo_obj.get("violations") if isinstance(solo_obj.get("violations"), list) else [])
            if isinstance(item, str) and str(item).strip()
        }
    )
    collaborator_write_count = (
        int(obj.get("collaborator_write_count")) if isinstance(obj.get("collaborator_write_count"), int) else None
    )

    required_present = obj.get("required_present")
    if isinstance(required_present, bool):
        return {
            "status": "OK" if required_present else "FAIL",
            "required_check": required_check,
            "required_present": required_present,
            "source": "branch_report",
            "solo_policy_status": solo_status,
            "solo_policy_rule": solo_rule,
            "solo_policy_violations": solo_violations,
            "collaborator_write_count": collaborator_write_count,
        }

    contexts: list[str] = []
    raw_contexts = obj.get("contexts")
    if isinstance(raw_contexts, list):
        contexts = [str(item) for item in raw_contexts if isinstance(item, str) and str(item).strip()]
    if not contexts:
        rsc = obj.get("required_status_checks")
        if isinstance(rsc, dict):
            raw_ctx = rsc.get("contexts")
            if isinstance(raw_ctx, list):
                contexts = [str(item) for item in raw_ctx if isinstance(item, str) and str(item).strip()]
    if contexts:
        present = required_check in set(contexts)
        return {
            "status": "OK" if present else "FAIL",
            "required_check": required_check,
            "required_present": present,
            "source": "branch_report",
            "solo_policy_status": solo_status,
            "solo_policy_rule": solo_rule,
            "solo_policy_violations": solo_violations,
            "collaborator_write_count": collaborator_write_count,
        }

    return {
        "status": "UNVERIFIED",
        "required_check": required_check,
        "required_present": None,
        "source": "branch_report_no_contexts",
        "solo_policy_status": solo_status,
        "solo_policy_rule": solo_rule,
        "solo_policy_violations": solo_violations if solo_violations else ["branch_report_no_contexts"],
        "collaborator_write_count": collaborator_write_count,
    }


def _rollout_recommendation(
    *,
    repo_status: str,
    drift_state: str,
    lane_config_status: str,
    branch_status: str,
    preserve_hits: list[str],
) -> str:
    if repo_status != "OK" or drift_state == "FAILED":
        return "BLOCKED"
    if branch_status == "FAIL":
        return "BLOCKED"
    if lane_config_status in {"INVALID", "MISSING"}:
        return "REVIEW"
    if lane_config_status == "PARTIAL":
        return "REVIEW"
    if drift_state == "PENDING":
        if preserve_hits:
            return "APPLY_SAFE_WITH_PRESERVE"
        return "APPLY_SAFE"
    if drift_state == "FIXED":
        return "MONITOR"
    if preserve_hits:
        return "NOOP_PRESERVE"
    return "NOOP"


def _sync_result_map(sync_report_obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    results = sync_report_obj.get("results") if isinstance(sync_report_obj.get("results"), list) else []
    for item in results:
        if not isinstance(item, dict):
            continue
        repo_root = _normalize_repo_root(item.get("repo_root"))
        if not repo_root:
            continue
        out[repo_root] = item
    return out


def build_drift_scoreboard(
    *,
    workspace_root: Path,
    core_root: Path,
    managed_repo_standards_summary: dict[str, Any] | None = None,
    max_repos: int = 200,
) -> dict[str, Any]:
    managed = (
        managed_repo_standards_summary
        if isinstance(managed_repo_standards_summary, dict)
        else build_managed_repo_standards_summary(
            workspace_root=workspace_root,
            core_root=core_root,
            max_repos=max_repos,
        )
    )
    if not isinstance(managed, dict):
        managed = {}

    lock_policy = _load_lock_policy(workspace_root=workspace_root, core_root=core_root)
    required_lanes = [
        str(item)
        for item in (lock_policy.get("required_lanes") if isinstance(lock_policy.get("required_lanes"), list) else [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not required_lanes:
        required_lanes = list(DEFAULT_REQUIRED_LANES)
    delivery_sequence = [
        str(item)
        for item in (
            lock_policy.get("delivery_sequence")
            if isinstance(lock_policy.get("delivery_sequence"), list)
            else []
        )
        if isinstance(item, str) and str(item).strip()
    ]
    if not delivery_sequence:
        delivery_sequence = list(DEFAULT_DELIVERY_SEQUENCE)
    required_branch_check = str(lock_policy.get("required_branch_check") or DEFAULT_REQUIRED_BRANCH_CHECK)
    default_branch = str(lock_policy.get("default_branch") or DEFAULT_BRANCH)
    branch_verification_mode = str(lock_policy.get("branch_verification_mode") or "live_evidence")
    if branch_verification_mode not in {"live_evidence", "report_only"}:
        branch_verification_mode = "live_evidence"

    sync_report_obj, sync_report_path = _load_sync_report(
        workspace_root=workspace_root,
        core_root=core_root,
        managed_summary=managed,
    )
    sync_map = _sync_result_map(sync_report_obj)
    preserve_paths = [
        str(item)
        for item in (
            lock_policy.get("preserve_existing_paths")
            if isinstance(lock_policy.get("preserve_existing_paths"), list)
            else []
        )
        if isinstance(item, str) and str(item).strip()
    ]
    raw_repos = managed.get("repos") if isinstance(managed.get("repos"), list) else []
    repos: list[dict[str, Any]] = []

    lane_missing_count = 0
    lane_invalid_count = 0
    lane_partial_count = 0
    lane_placeholder_count = 0

    branch_unverified_count = 0
    branch_missing_required_check_count = 0
    solo_policy_fail_count = 0
    solo_policy_unverified_count = 0

    rollout_safe_count = 0
    rollout_review_count = 0
    rollout_blocked_count = 0

    for item in raw_repos:
        if not isinstance(item, dict):
            continue
        repo_root = _normalize_repo_root(item.get("repo_root"))
        if not repo_root:
            continue

        sync_item = sync_map.get(repo_root)
        preserve_hits: list[str] = []
        if isinstance(sync_item, dict):
            files = sync_item.get("files") if isinstance(sync_item.get("files"), list) else []
            for f in files:
                if not isinstance(f, dict):
                    continue
                if str(f.get("action")) != "preserve_existing":
                    continue
                p = str(f.get("path") or "")
                if p:
                    preserve_hits.append(p)
        preserve_hits = sorted(set(preserve_hits))

        lane_info = _read_lane_config(repo_root, required_lanes=required_lanes)
        lane_status = str(lane_info.get("config_status") or "MISSING")
        if lane_status == "MISSING":
            lane_missing_count += 1
        elif lane_status == "INVALID":
            lane_invalid_count += 1
        elif lane_status == "PARTIAL":
            lane_partial_count += 1
        if lane_info.get("placeholder_lanes"):
            lane_placeholder_count += 1

        branch_info = _branch_protection_status(
            repo_root=repo_root,
            sync_result=sync_item,
            required_check=required_branch_check,
        )
        branch_status = str(branch_info.get("status") or "UNVERIFIED")
        solo_policy_status = str(branch_info.get("solo_policy_status") or "UNVERIFIED")
        if solo_policy_status == "FAIL":
            solo_policy_fail_count += 1
        elif solo_policy_status == "UNVERIFIED":
            solo_policy_unverified_count += 1

        branch_status_effective = branch_status
        if solo_policy_status == "FAIL":
            branch_status_effective = "FAIL"
        if branch_status == "UNVERIFIED" and branch_verification_mode == "report_only":
            branch_status_effective = "OK"
        if branch_status == "UNVERIFIED":
            branch_unverified_count += 1
        elif branch_status_effective == "FAIL":
            branch_missing_required_check_count += 1

        repo_status = str(item.get("status") or "FAIL")
        drift_state = str(item.get("drift_state") or "FAILED")
        recommendation = _rollout_recommendation(
            repo_status=repo_status,
            drift_state=drift_state,
            lane_config_status=lane_status,
            branch_status=branch_status_effective,
            preserve_hits=preserve_hits,
        )
        if recommendation in {"APPLY_SAFE", "APPLY_SAFE_WITH_PRESERVE", "NOOP", "NOOP_PRESERVE", "MONITOR"}:
            rollout_safe_count += 1
        elif recommendation == "REVIEW":
            rollout_review_count += 1
        elif recommendation == "BLOCKED":
            rollout_blocked_count += 1

        repos.append(
            {
                "repo_root": repo_root,
                "status": repo_status,
                "drift_state": drift_state,
                "changed_files": int(item.get("changed_files") or 0),
                "validation_status": str(item.get("validation_status") or "UNKNOWN"),
                "lane_config_status": lane_status,
                "lane_commands": lane_info.get("commands") if isinstance(lane_info.get("commands"), dict) else {},
                "lane_missing": lane_info.get("missing_lanes") if isinstance(lane_info.get("missing_lanes"), list) else [],
                "lane_placeholders": (
                    lane_info.get("placeholder_lanes")
                    if isinstance(lane_info.get("placeholder_lanes"), list)
                    else []
                ),
                "execution_sequence": (
                    lane_info.get("execution_sequence")
                    if isinstance(lane_info.get("execution_sequence"), list)
                    else []
                ),
                "scope_lane_map": lane_info.get("scope_lane_map") if isinstance(lane_info.get("scope_lane_map"), dict) else {},
                "managed_repo_profile": str(lane_info.get("managed_repo_profile") or ""),
                "preserve_existing_hits": preserve_hits,
                "branch_protection_status": branch_status,
                "branch_protection_effective_status": branch_status_effective,
                "branch_required_check": required_branch_check,
                "branch_required_present": branch_info.get("required_present")
                if isinstance(branch_info.get("required_present"), bool)
                else None,
                "branch_source": str(branch_info.get("source") or ""),
                "branch_solo_policy_status": solo_policy_status,
                "branch_solo_policy_rule": str(branch_info.get("solo_policy_rule") or ""),
                "branch_solo_policy_violations": (
                    branch_info.get("solo_policy_violations")
                    if isinstance(branch_info.get("solo_policy_violations"), list)
                    else []
                ),
                "branch_collaborator_write_count": (
                    int(branch_info.get("collaborator_write_count"))
                    if isinstance(branch_info.get("collaborator_write_count"), int)
                    else None
                ),
                "rollout_recommendation": recommendation,
            }
        )

    repos.sort(key=lambda x: str(x.get("repo_root") or ""))
    if max_repos > 0:
        repos = repos[:max_repos]

    repos_count = len(repos)
    drift_pending_count = int(managed.get("drift_pending_count") or 0)
    drift_failed_count = int(managed.get("failed_count") or 0)
    drift_fixed_count = int(managed.get("drift_fixed_count") or 0)
    drift_clean_count = int(managed.get("clean_count") or 0)

    lane_matrix_status = "OK"
    if repos_count <= 0:
        lane_matrix_status = "IDLE"
    elif lane_invalid_count > 0:
        lane_matrix_status = "FAIL"
    elif lane_missing_count > 0 or lane_partial_count > 0 or lane_placeholder_count > 0:
        lane_matrix_status = "WARN"

    branch_status = "OK"
    branch_unverified_blocking_count = branch_unverified_count
    if branch_verification_mode == "report_only":
        branch_unverified_blocking_count = 0
    if repos_count <= 0:
        branch_status = "IDLE"
    elif branch_missing_required_check_count > 0:
        branch_status = "FAIL"
    elif branch_unverified_blocking_count > 0:
        branch_status = "WARN"

    scoreboard_status = "OK"
    if repos_count <= 0:
        scoreboard_status = "IDLE"
    elif drift_failed_count > 0 or rollout_blocked_count > 0 or branch_missing_required_check_count > 0:
        scoreboard_status = "FAIL"
    elif solo_policy_fail_count > 0:
        scoreboard_status = "FAIL"
    elif (
        drift_pending_count > 0
        or lane_matrix_status == "WARN"
        or branch_status == "WARN"
        or solo_policy_unverified_count > 0
        or rollout_review_count > 0
    ):
        scoreboard_status = "WARN"

    notes = managed.get("notes") if isinstance(managed.get("notes"), list) else []
    notes_list = [str(item) for item in notes if isinstance(item, str) and str(item).strip()]
    if branch_unverified_count > 0:
        if branch_verification_mode == "report_only":
            notes_list.append("branch_protection_unverified_report_only")
        else:
            notes_list.append("branch_protection_unverified_repos")
    if lane_placeholder_count > 0:
        notes_list.append("lane_placeholder_commands_detected")
    if rollout_review_count > 0:
        notes_list.append("rollout_manual_review_required")
    if solo_policy_fail_count > 0:
        notes_list.append("solo_policy_violation")
    if solo_policy_unverified_count > 0:
        notes_list.append("solo_policy_unverified")

    summary = {
        "status": scoreboard_status,
        "repos_count": repos_count,
        "drift_pending_count": drift_pending_count,
        "drift_failed_count": drift_failed_count,
        "drift_fixed_count": drift_fixed_count,
        "drift_clean_count": drift_clean_count,
        "lane_matrix_status": lane_matrix_status,
        "repos_missing_lane_config": lane_missing_count,
        "repos_invalid_lane_config": lane_invalid_count,
        "repos_partial_lane_config": lane_partial_count,
        "repos_with_lane_placeholders": lane_placeholder_count,
        "branch_protection_status": branch_status,
        "branch_unverified_count": branch_unverified_count,
        "branch_missing_required_check_count": branch_missing_required_check_count,
        "solo_policy_fail_count": solo_policy_fail_count,
        "solo_policy_unverified_count": solo_policy_unverified_count,
        "rollout_safe_count": rollout_safe_count,
        "rollout_review_count": rollout_review_count,
        "rollout_blocked_count": rollout_blocked_count,
    }

    return {
        "version": "v1",
        "kind": "managed-repo-drift-scoreboard",
        "generated_at": _now_iso_utc(),
        "workspace_root": str(workspace_root),
        "report_path": SCOREBOARD_REPORT_REL.as_posix(),
        "policy": {
            "required_lanes": required_lanes,
            "delivery_sequence": delivery_sequence,
            "required_branch_check": required_branch_check,
            "default_branch": default_branch,
            "branch_verification_mode": branch_verification_mode,
            "preserve_existing_paths": preserve_paths,
            "standards_lock_path": str(lock_policy.get("lock_path") or ""),
        },
        "source_refs": {
            "sync_report_path": sync_report_path,
            "managed_repo_sync_mode": str(managed.get("mode") or ""),
            "managed_repo_manifest_path": str(managed.get("manifest_path") or ""),
        },
        "summary": summary,
        "repos": repos,
        "notes": sorted(set(notes_list)),
    }


def build_drift_scoreboard_summary(scoreboard: dict[str, Any]) -> dict[str, Any]:
    summary = scoreboard.get("summary") if isinstance(scoreboard.get("summary"), dict) else {}
    return {
        "status": str(summary.get("status") or "IDLE"),
        "report_path": str(scoreboard.get("report_path") or SCOREBOARD_REPORT_REL.as_posix()),
        "repos_count": int(summary.get("repos_count") or 0),
        "drift_pending_count": int(summary.get("drift_pending_count") or 0),
        "drift_failed_count": int(summary.get("drift_failed_count") or 0),
        "lane_matrix_status": str(summary.get("lane_matrix_status") or "IDLE"),
        "repos_missing_lane_config": int(summary.get("repos_missing_lane_config") or 0),
        "repos_invalid_lane_config": int(summary.get("repos_invalid_lane_config") or 0),
        "repos_partial_lane_config": int(summary.get("repos_partial_lane_config") or 0),
        "repos_with_lane_placeholders": int(summary.get("repos_with_lane_placeholders") or 0),
        "branch_protection_status": str(summary.get("branch_protection_status") or "IDLE"),
        "branch_unverified_count": int(summary.get("branch_unverified_count") or 0),
        "branch_missing_required_check_count": int(
            summary.get("branch_missing_required_check_count") or 0
        ),
        "rollout_safe_count": int(summary.get("rollout_safe_count") or 0),
        "rollout_review_count": int(summary.get("rollout_review_count") or 0),
        "rollout_blocked_count": int(summary.get("rollout_blocked_count") or 0),
    }


def write_drift_scoreboard(*, workspace_root: Path, scoreboard: dict[str, Any]) -> str:
    out_path = workspace_root / SCOREBOARD_REPORT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scoreboard, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return SCOREBOARD_REPORT_REL.as_posix()
