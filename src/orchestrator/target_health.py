from __future__ import annotations

from pathlib import Path
from typing import Any

from src.orchestrator import target_registry
from src.utils.jsonio import save_json


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _severity_for_condition(policy: dict[str, Any], condition: str) -> str:
    blocking = policy.get("blocking") if isinstance(policy.get("blocking"), dict) else {}
    rollout = policy.get("rollout") if isinstance(policy.get("rollout"), dict) else {}
    hard = set(
        str(x).strip()
        for x in (blocking.get("hard_block_conditions") if isinstance(blocking.get("hard_block_conditions"), list) else [])
        if isinstance(x, str) and str(x).strip()
    )
    report_only = set(
        str(x).strip()
        for x in (blocking.get("report_only_conditions") if isinstance(blocking.get("report_only_conditions"), list) else [])
        if isinstance(x, str) and str(x).strip()
    )
    block_or_warn = set(
        str(x).strip()
        for x in (blocking.get("block_or_warn_conditions") if isinstance(blocking.get("block_or_warn_conditions"), list) else [])
        if isinstance(x, str) and str(x).strip()
    )
    promote_to_block = set(
        str(x).strip()
        for x in (rollout.get("promote_to_block_on") if isinstance(rollout.get("promote_to_block_on"), list) else [])
        if isinstance(x, str) and str(x).strip()
    )
    if condition in hard or condition in promote_to_block:
        return "BLOCK"
    if condition in report_only:
        return "WARN"
    if condition in block_or_warn:
        mode_default = str(rollout.get("mode_default") or "").strip()
        return "WARN" if mode_default == "report_only" else "BLOCK"
    return "WARN"


def _write_reports(workspace: Path, *, resolution: dict[str, Any], guard: dict[str, Any]) -> None:
    reports_dir = workspace / ".cache" / "reports"
    save_json(reports_dir / "execution_target_resolution.v1.json", resolution)
    save_json(reports_dir / "execution_target_guard.v1.json", guard)


def evaluate_execution_target_guard(*, workspace: Path, envelope: dict[str, Any], writes_allowed: bool) -> dict[str, Any]:
    policy_path, policy = target_registry.load_execution_target_policy(workspace)
    resolution = target_registry.resolve_target_selection(workspace, envelope)
    apply_class = bool(resolution.get("apply_class"))
    ai_entry_pack_path: Path | None = None
    ai_entry_pack: dict[str, Any] | None = None
    ai_entry_pack_error = ""
    try:
        ai_entry_pack_path, ai_entry_pack = target_registry.load_ai_entry_pack(workspace)
    except Exception as e:
        ai_entry_pack_error = str(e)
    ai_entry_pack_info = target_registry.ai_entry_pack_health(ai_entry_pack)

    warnings: list[dict[str, str]] = []
    block: dict[str, str] | None = None

    if not target_registry.has_execution_target_authority_surface(
        resolution.get("authority_matrix") if isinstance(resolution.get("authority_matrix"), dict) else {}
    ):
        issue = _issue(
            "AUTHORITY_MATRIX_MISSING_SURFACE",
            "Authority matrix icinde core:execution-target-governance surface kaydi yok.",
        )
        if apply_class and block is None:
            block = issue
        else:
            warnings.append(issue)

    uncontrolled_duplicates = target_registry.find_uncontrolled_target_duplicates(
        resolution.get("duplicate_surface_register")
        if isinstance(resolution.get("duplicate_surface_register"), dict)
        else {}
    )
    guardrails = policy.get("guardrails") if isinstance(policy.get("guardrails"), dict) else {}
    if uncontrolled_duplicates:
        issue = _issue(
            "UNCONTROLLED_DUPLICATE_SURFACE",
            "Target/launch concern icin uncontrolled duplicate surface bulundu: "
            + ", ".join(sorted(uncontrolled_duplicates)),
        )
        if apply_class and bool(guardrails.get("block_if_uncontrolled_duplicate_exists", False)) and block is None:
            block = issue
        else:
            warnings.append(issue)

    target_id = str(resolution.get("target_id") or "").strip()
    repo_id = str(resolution.get("repo_id") or "").strip()
    repo = resolution.get("repo") if isinstance(resolution.get("repo"), dict) else {}
    target = resolution.get("target") if isinstance(resolution.get("target"), dict) else {}
    launch_profile = (
        resolution.get("launch_profile") if isinstance(resolution.get("launch_profile"), dict) else {}
    )
    hints = resolution.get("hints") if isinstance(resolution.get("hints"), dict) else {}
    resolved_target = bool(target) or bool(repo)

    if apply_class and not resolved_target and block is None:
        block = _issue("UNKNOWN_TARGET", "Apply sinifi run icin target resolve edilemedi.")
    elif not target_id and apply_class and block is None:
        block = _issue("UNKNOWN_TARGET", "Apply sinifi run icin target resolve edilemedi.")
    elif not target_id:
        warnings.append(
            _issue(
                "TARGET_HINT_MISSING_REPORT_ONLY",
                "Target hint verilmedi; run report-only baglaminda target resolve kaydi olmadan devam ediyor.",
            )
        )

    lifecycle_state = str(resolution.get("lifecycle_state") or "").strip()
    blocked_states = set(
        str(x).strip()
        for x in (
            policy.get("blocking", {}).get("blocked_lifecycle_states")
            if isinstance(policy.get("blocking"), dict)
            and isinstance(policy.get("blocking", {}).get("blocked_lifecycle_states"), list)
            else []
        )
        if isinstance(x, str) and str(x).strip()
    )
    if lifecycle_state in blocked_states and block is None:
        code = f"{lifecycle_state.upper()}_TARGET"
        block = _issue(code, f"Target lifecycle durumu blocked: {lifecycle_state}")

    requested_launch_profile = str(hints.get("launch_profile_id") or hints.get("app_id") or "").strip()
    if requested_launch_profile and not launch_profile and block is None:
        block = _issue(
            "LAUNCH_PROFILE_MISSING",
            f"Istenen launch profile registry icinde bulunamadi: {requested_launch_profile}",
        )

    if requested_launch_profile and launch_profile and target and block is None:
        if str(launch_profile.get("target_id") or "").strip() != str(target.get("target_id") or "").strip():
            block = _issue(
                "LAUNCH_PROFILE_TARGET_MISMATCH",
                "Launch profile, secilen target ile eslesmiyor.",
            )

    version_source_refs = (
        resolution.get("version_source_refs") if isinstance(resolution.get("version_source_refs"), list) else []
    )
    if apply_class and not version_source_refs and block is None:
        block = _issue("UNKNOWN_VERSION_SOURCE", "Apply sinifi run icin version source resolve edilemedi.")

    if apply_class and block is None:
        if ai_entry_pack_error:
            issue = _issue(
                "AI_ENTRY_PACK_INVALID",
                "AI entry pack okunamadi: " + ai_entry_pack_error,
            )
            if bool(guardrails.get("block_if_ai_entry_pack_missing_on_apply", False)):
                block = issue
            else:
                warnings.append(issue)
        elif not bool(ai_entry_pack_info.get("present", False)):
            issue = _issue("AI_ENTRY_PACK_MISSING", "Apply sinifi run icin AI entry pack bulunamadi.")
            if bool(guardrails.get("block_if_ai_entry_pack_missing_on_apply", False)):
                block = issue
            else:
                warnings.append(issue)
        elif not bool(ai_entry_pack_info.get("valid", False)):
            missing_refs = ai_entry_pack_info.get("missing_refs") if isinstance(ai_entry_pack_info.get("missing_refs"), list) else []
            issue = _issue(
                "AI_ENTRY_PACK_INVALID",
                "AI entry pack gecersiz: eksik ref anahtarlari="
                + ", ".join(str(x) for x in missing_refs if isinstance(x, str)),
            )
            if bool(guardrails.get("block_if_ai_entry_pack_missing_on_apply", False)):
                block = issue
            else:
                warnings.append(issue)

    if repo_id:
        allowed_worktrees = (
            repo.get("allowed_worktrees") if isinstance(repo.get("allowed_worktrees"), list) else []
        )
        observed_worktrees = (
            repo.get("observed_worktrees") if isinstance(repo.get("observed_worktrees"), list) else []
        )
        unapproved = [
            str(x).strip()
            for x in observed_worktrees
            if isinstance(x, str) and str(x).strip() and str(x).strip() not in set(allowed_worktrees)
        ]
        if unapproved and block is None:
            block = _issue(
                "UNAPPROVED_WORKTREE",
                "Allowlist disi worktree gozlendi: " + ", ".join(sorted(unapproved)),
            )

        if bool(repo.get("dirty", False)):
            warnings.append(
                _issue("DIRTY_TREE", f"Target repo dirty durumda: {repo_id}")
            )

        if not str(repo.get("upstream") or "").strip():
            warnings.append(
                _issue("NO_UPSTREAM_ON_CURRENT_BRANCH", f"Target repo upstream baglantisi yok: {repo_id}")
            )

        current_branch = str(repo.get("current_branch") or "").strip()
        canonical_branch = str(repo.get("canonical_branch") or "").strip()
        if current_branch and canonical_branch and current_branch != canonical_branch:
            issue = _issue(
                "WRONG_BRANCH",
                f"Target repo canonical branch disinda: current={current_branch} canonical={canonical_branch}",
            )
            if _severity_for_condition(policy, "wrong_branch") == "BLOCK":
                block = issue
            else:
                warnings.append(issue)

        if not current_branch or current_branch == "HEAD":
            issue = _issue("DETACHED_HEAD", f"Target repo detached head/unknown branch durumunda: {repo_id}")
            if _severity_for_condition(policy, "detached_head") == "BLOCK":
                block = issue
            else:
                warnings.append(issue)

        upstream_sync_state = str(repo.get("upstream_sync_state") or "").strip()
        if upstream_sync_state and upstream_sync_state != "0_behind_0_ahead":
            issue = _issue(
                "STALE_CHECKOUT",
                f"Target repo upstream sync state stale: {upstream_sync_state}",
            )
            if _severity_for_condition(policy, "stale_checkout") == "BLOCK":
                block = issue
            else:
                warnings.append(issue)

    branch = str(repo.get("current_branch") or "").strip()
    head = str(repo.get("current_head") or "").strip()
    ai_entry_pack_state = "MISSING"
    if ai_entry_pack_error:
        ai_entry_pack_state = "INVALID"
    elif bool(ai_entry_pack_info.get("present", False)):
        ai_entry_pack_state = "READY" if bool(ai_entry_pack_info.get("valid", False)) else "INVALID"

    target_evidence = {
        "repo_id": repo_id,
        "target_id": target_id,
        "repo_root": str(resolution.get("repo_root") or "").strip(),
        "working_dir": str(resolution.get("working_dir") or "").strip(),
        "branch": branch,
        "head": head,
        "launch_profile_id": str(resolution.get("launch_profile_id") or "").strip(),
        "version_source_refs": version_source_refs,
        "selection_reason": str(resolution.get("selection_reason") or "").strip() or "unresolved",
        "lifecycle_state": lifecycle_state,
        "ai_entry_pack_path": str(ai_entry_pack_path) if ai_entry_pack_path is not None else "",
        "ai_entry_pack_state": ai_entry_pack_state,
        "ai_entry_pack_project_id": str(ai_entry_pack_info.get("project_id") or "").strip(),
        "ai_entry_pack_ref_count": int(ai_entry_pack_info.get("ref_count") or 0),
    }

    guard_status = "BLOCKED" if block else ("WARN" if warnings else "OK")
    selection_reason = str(resolution.get("selection_reason") or "").strip() or "unresolved"

    resolution_report = {
        "version": "v1",
        "kind": "execution-target-resolution",
        "status": guard_status,
        "apply_class": apply_class,
        "repo_id": repo_id,
        "target_id": target_id,
        "repo_root": str(resolution.get("repo_root") or "").strip(),
        "working_dir": str(resolution.get("working_dir") or "").strip(),
        "branch": branch,
        "head": head,
        "lifecycle_state": lifecycle_state,
        "launch_profile_id": str(resolution.get("launch_profile_id") or "").strip(),
        "version_source_refs": version_source_refs,
        "selection_reason": selection_reason,
        "ai_entry_pack": {
            "path": str(ai_entry_pack_path) if ai_entry_pack_path is not None else "",
            "state": ai_entry_pack_state,
            "project_id": str(ai_entry_pack_info.get("project_id") or "").strip(),
            "ref_count": int(ai_entry_pack_info.get("ref_count") or 0),
            "missing_refs": (
                ai_entry_pack_info.get("missing_refs") if isinstance(ai_entry_pack_info.get("missing_refs"), list) else []
            ),
        },
        "target_evidence": target_evidence,
        "source_paths": resolution.get("source_paths") if isinstance(resolution.get("source_paths"), dict) else {},
    }
    guard_report = {
        "version": "v1",
        "kind": "execution-target-guard",
        "status": guard_status,
        "apply_class": apply_class,
        "writes_allowed": bool(writes_allowed),
        "policy_path": str(policy_path),
        "repo_id": repo_id,
        "target_id": target_id,
        "repo_root": str(resolution.get("repo_root") or "").strip(),
        "working_dir": str(resolution.get("working_dir") or "").strip(),
        "branch": branch,
        "head": head,
        "lifecycle_state": lifecycle_state,
        "launch_profile_id": str(resolution.get("launch_profile_id") or "").strip(),
        "version_source_refs": version_source_refs,
        "selection_reason": selection_reason,
        "ai_entry_pack": resolution_report.get("ai_entry_pack"),
        "target_evidence": target_evidence,
        "warnings": warnings,
        "block": block,
        "resolution": resolution_report,
    }
    _write_reports(workspace, resolution=resolution_report, guard=guard_report)
    return guard_report
