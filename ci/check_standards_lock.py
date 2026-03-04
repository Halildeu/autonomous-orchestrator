from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "standards.lock",
    ".github/CODEOWNERS",
    ".github/workflows/gate-enforcement-check.yml",
    ".github/workflows/module-delivery-lanes.yml",
    "docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md",
    "scripts/sync_managed_repo_standards.py",
    "ci/check_standards_lock.py",
    "ci/check_module_delivery_lanes.py",
    "ci/run_module_delivery_lane.py",
    "ci/module_delivery_lanes.v1.json",
    "scripts/check_branch_protection_solo_policy.py",
)

REQUIRED_LOCK_KEYS = (
    "version",
    "operating_contract",
    "standard_sources",
    "required_files",
    "required_commands",
    "required_gates",
    "managed_repo_sync",
    "module_delivery_contract",
    "branch_protection",
    "solo_developer_policy",
    "pr_gate_mode",
)

REQUIRED_GATES = (
    "enforcement-check",
    "gate-schema",
    "gate-policy-dry-run",
    "gate-secrets",
    "module-delivery-gate",
)

REQUIRED_STANDARD_SOURCES = (
    "coding_standards",
    "repo_layout",
    "layer_boundary_policy",
    "llm_live_policy",
    "llm_provider_guardrails_policy",
    "kernel_api_guardrails_policy",
    "security_policy",
    "secrets_policy",
)

REQUIRED_COMMANDS = (
    "python ci/validate_schemas.py",
    "python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json",
    "python ci/check_script_budget.py --out .cache/script_budget/report.json",
    "python -m src.ops.manage enforcement-check --profile strict",
    "python3 scripts/sync_managed_repo_standards.py --target-repo-root <repo_root>",
    "python3 ci/check_module_delivery_lanes.py --strict",
    "python3 scripts/check_branch_protection_solo_policy.py --repo-slug <owner/repo>",
)

REQUIRED_PRESERVE_PATHS = (
    "ci/module_delivery_lanes.v1.json",
)

REQUIRED_BRANCH_PROTECTION_CHECKS = (
    "module-delivery-gate",
    "enforcement-check",
    "validate-schemas",
    "policy-dry-run",
    "gitleaks",
)

REQUIRED_DELIVERY_SEQUENCE = ("backend", "frontend", "integration", "e2e")
REQUIRED_SCOPE_LANE_MAP = {
    "backend": "unit",
    "frontend": "contract",
    "integration": "integration",
    "e2e_gate": "e2e",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default="",
        help="Target repo root to validate (default: current repository root).",
    )
    return parser.parse_args(argv)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(error_code: str, message: str, *, details: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {
        "status": "FAIL",
        "error_code": error_code,
        "message": message,
    }
    if isinstance(details, dict) and details:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 1


def _require_json_file(root: Path, rel_path: str, *, key: str) -> dict[str, Any] | None:
    path = root / rel_path
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _check_standard_sources(root: Path, standard_sources: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"missing_keys": [], "missing_files": [], "invalid_content": []}

    for key in REQUIRED_STANDARD_SOURCES:
        if key not in standard_sources:
            details["missing_keys"].append(key)
    if details["missing_keys"]:
        return False, details

    # Existence check
    for key in REQUIRED_STANDARD_SOURCES:
        rel = standard_sources.get(key)
        if not isinstance(rel, str) or not rel.strip():
            details["invalid_content"].append(f"{key}:path_invalid")
            continue
        if not (root / rel).exists():
            details["missing_files"].append(rel)

    if details["missing_files"] or any(item.endswith(":path_invalid") for item in details["invalid_content"]):
        return False, details

    # Minimal semantic checks against existing system standards
    coding_path = root / str(standard_sources["coding_standards"])
    coding_text = coding_path.read_text(encoding="utf-8")
    if "src/shared/utils.py" not in coding_text:
        details["invalid_content"].append("coding_standards:missing_shared_utils_reference")

    repo_layout = _require_json_file(root, str(standard_sources["repo_layout"]), key="repo_layout")
    if not isinstance(repo_layout, dict):
        details["invalid_content"].append("repo_layout:invalid_json")
    else:
        allowed_dirs = repo_layout.get("allowed_top_level_dirs")
        if not isinstance(allowed_dirs, list) or "src" not in allowed_dirs or "policies" not in allowed_dirs:
            details["invalid_content"].append("repo_layout:allowed_top_level_dirs_invalid")

    layer_boundary = _require_json_file(root, str(standard_sources["layer_boundary_policy"]), key="layer_boundary_policy")
    if not isinstance(layer_boundary, dict):
        details["invalid_content"].append("layer_boundary_policy:invalid_json")
    else:
        if layer_boundary.get("enforcement_mode") != "fail_closed":
            details["invalid_content"].append("layer_boundary_policy:enforcement_mode_must_be_fail_closed")
        if layer_boundary.get("workspace_root_required") is not True:
            details["invalid_content"].append("layer_boundary_policy:workspace_root_required_must_be_true")

    llm_live = _require_json_file(root, str(standard_sources["llm_live_policy"]), key="llm_live_policy")
    if not isinstance(llm_live, dict):
        details["invalid_content"].append("llm_live_policy:invalid_json")
    else:
        allowed = llm_live.get("allowed_providers")
        if llm_live.get("live_enabled") is not True:
            details["invalid_content"].append("llm_live_policy:live_enabled_must_be_true")
        if not isinstance(allowed, list) or not allowed:
            details["invalid_content"].append("llm_live_policy:allowed_providers_missing")

    provider_guardrails = _require_json_file(
        root, str(standard_sources["llm_provider_guardrails_policy"]), key="llm_provider_guardrails_policy"
    )
    if not isinstance(provider_guardrails, dict):
        details["invalid_content"].append("llm_provider_guardrails_policy:invalid_json")
    else:
        live_gate = provider_guardrails.get("live_gate")
        if not isinstance(live_gate, dict):
            details["invalid_content"].append("llm_provider_guardrails_policy:live_gate_missing")
        else:
            explicit_env = live_gate.get("explicit_live_flag_env")
            if not isinstance(explicit_env, str) or not explicit_env.strip():
                details["invalid_content"].append("llm_provider_guardrails_policy:explicit_live_flag_env_missing")

    kernel_guardrails = _require_json_file(
        root, str(standard_sources["kernel_api_guardrails_policy"]), key="kernel_api_guardrails_policy"
    )
    if not isinstance(kernel_guardrails, dict):
        details["invalid_content"].append("kernel_api_guardrails_policy:invalid_json")
    else:
        actions = kernel_guardrails.get("actions")
        audit = kernel_guardrails.get("audit")
        if not isinstance(actions, dict) or not isinstance(actions.get("allowlist"), list):
            details["invalid_content"].append("kernel_api_guardrails_policy:actions_allowlist_missing")
        if not isinstance(audit, dict) or audit.get("enabled") is not True:
            details["invalid_content"].append("kernel_api_guardrails_policy:audit_enabled_required")

    security = _require_json_file(root, str(standard_sources["security_policy"]), key="security_policy")
    if not isinstance(security, dict):
        details["invalid_content"].append("security_policy:invalid_json")
    else:
        if security.get("network_access") is not False:
            details["invalid_content"].append("security_policy:network_access_must_be_false")
        allowlist = security.get("network_allowlist")
        if not isinstance(allowlist, list) or not allowlist:
            details["invalid_content"].append("security_policy:network_allowlist_missing")

    secrets = _require_json_file(root, str(standard_sources["secrets_policy"]), key="secrets_policy")
    if not isinstance(secrets, dict):
        details["invalid_content"].append("secrets_policy:invalid_json")
    else:
        allowed_ids = secrets.get("allowed_secret_ids")
        if not isinstance(allowed_ids, list) or not allowed_ids:
            details["invalid_content"].append("secrets_policy:allowed_secret_ids_missing")

    ok = not details["missing_keys"] and not details["missing_files"] and not details["invalid_content"]
    return ok, details


def _check_required_commands(required_commands: Any) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"missing_commands": []}
    if not isinstance(required_commands, list):
        details["missing_commands"] = list(REQUIRED_COMMANDS)
        return False, details

    cmd_set = {str(item) for item in required_commands if isinstance(item, str)}
    for cmd in REQUIRED_COMMANDS:
        if cmd not in cmd_set:
            details["missing_commands"].append(cmd)
    return not details["missing_commands"], details


def _check_managed_repo_sync(root: Path, section: Any) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"missing_keys": [], "invalid_values": [], "missing_files": []}
    if not isinstance(section, dict):
        details["invalid_values"].append("managed_repo_sync:not_object")
        return False, details

    required_keys = (
        "default_mode",
        "script",
        "source_of_truth",
        "apply_requires_flag",
        "validation_command_template",
        "preserve_existing_paths",
    )
    for key in required_keys:
        if key not in section:
            details["missing_keys"].append(key)
    if details["missing_keys"]:
        return False, details

    if section.get("default_mode") != "dry-run":
        details["invalid_values"].append("default_mode:must_be_dry-run")
    if section.get("source_of_truth") != "standards.lock":
        details["invalid_values"].append("source_of_truth:must_be_standards.lock")
    if section.get("apply_requires_flag") is not True:
        details["invalid_values"].append("apply_requires_flag:must_be_true")

    script_rel = section.get("script")
    if not isinstance(script_rel, str) or not script_rel.strip():
        details["invalid_values"].append("script:path_invalid")
    else:
        script_path = root / script_rel
        if not script_path.exists():
            details["missing_files"].append(script_rel)

    validation_tmpl = section.get("validation_command_template")
    if not isinstance(validation_tmpl, str) or "<repo_root>" not in validation_tmpl:
        details["invalid_values"].append("validation_command_template:repo_root_placeholder_required")

    preserve_paths = section.get("preserve_existing_paths")
    if not isinstance(preserve_paths, list):
        details["invalid_values"].append("preserve_existing_paths:must_be_list")
    else:
        preserve_set = {str(item) for item in preserve_paths if isinstance(item, str)}
        for required_path in REQUIRED_PRESERVE_PATHS:
            if required_path not in preserve_set:
                details["invalid_values"].append(f"preserve_existing_paths:missing_{required_path}")

    ok = not details["missing_keys"] and not details["invalid_values"] and not details["missing_files"]
    return ok, details


def _check_module_delivery_contract(section: Any) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"missing_keys": [], "invalid_values": []}
    if not isinstance(section, dict):
        details["invalid_values"].append("module_delivery_contract:not_object")
        return False, details

    required_keys = (
        "service_scopes",
        "required_test_lanes",
        "delivery_sequence",
        "scope_lane_map",
        "merge_requires_all_green",
    )
    for key in required_keys:
        if key not in section:
            details["missing_keys"].append(key)
    if details["missing_keys"]:
        return False, details

    service_scopes = section.get("service_scopes")
    if not isinstance(service_scopes, list) or not service_scopes:
        details["invalid_values"].append("service_scopes:must_be_nonempty_list")
    else:
        expected = {"backend", "frontend", "database", "api"}
        actual = {str(item) for item in service_scopes}
        missing = sorted(expected - actual)
        if missing:
            details["invalid_values"].append(f"service_scopes:missing_{','.join(missing)}")

    lanes = section.get("required_test_lanes")
    if not isinstance(lanes, list) or not lanes:
        details["invalid_values"].append("required_test_lanes:must_be_nonempty_list")
    else:
        expected_lanes = {"unit", "contract", "integration", "e2e"}
        actual_lanes = {str(item) for item in lanes}
        missing_lanes = sorted(expected_lanes - actual_lanes)
        if missing_lanes:
            details["invalid_values"].append(f"required_test_lanes:missing_{','.join(missing_lanes)}")

    delivery_sequence = section.get("delivery_sequence")
    if not isinstance(delivery_sequence, list) or not delivery_sequence:
        details["invalid_values"].append("delivery_sequence:must_be_nonempty_list")
    else:
        actual_sequence = [str(item) for item in delivery_sequence]
        if actual_sequence != list(REQUIRED_DELIVERY_SEQUENCE):
            details["invalid_values"].append(
                f"delivery_sequence:must_equal_{','.join(REQUIRED_DELIVERY_SEQUENCE)}"
            )

    scope_lane_map = section.get("scope_lane_map")
    if not isinstance(scope_lane_map, dict):
        details["invalid_values"].append("scope_lane_map:must_be_object")
    else:
        for scope, expected_lane in REQUIRED_SCOPE_LANE_MAP.items():
            actual_lane = scope_lane_map.get(scope)
            if actual_lane != expected_lane:
                details["invalid_values"].append(
                    f"scope_lane_map:{scope}_must_map_to_{expected_lane}"
                )

    if section.get("merge_requires_all_green") is not True:
        details["invalid_values"].append("merge_requires_all_green:must_be_true")

    ok = not details["missing_keys"] and not details["invalid_values"]
    return ok, details


def _check_branch_protection(section: Any) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"missing_keys": [], "invalid_values": []}
    if not isinstance(section, dict):
        details["invalid_values"].append("branch_protection:not_object")
        return False, details

    required_keys = ("default_branch", "required_checks", "verification_mode")
    for key in required_keys:
        if key not in section:
            details["missing_keys"].append(key)
    if details["missing_keys"]:
        return False, details

    default_branch = section.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch.strip():
        details["invalid_values"].append("default_branch:must_be_nonempty_string")

    verification_mode = section.get("verification_mode")
    if verification_mode not in {"live_evidence", "report_only"}:
        details["invalid_values"].append("verification_mode:must_be_live_evidence_or_report_only")

    required_checks = section.get("required_checks")
    if not isinstance(required_checks, list) or not required_checks:
        details["invalid_values"].append("required_checks:must_be_nonempty_list")
    else:
        checks_set = {str(item) for item in required_checks if isinstance(item, str) and str(item).strip()}
        for required_check in REQUIRED_BRANCH_PROTECTION_CHECKS:
            if required_check not in checks_set:
                details["invalid_values"].append(f"required_checks:missing_{required_check}")

    ok = not details["missing_keys"] and not details["invalid_values"]
    return ok, details


def _check_solo_developer_policy(section: Any) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"missing_keys": [], "invalid_values": []}
    if not isinstance(section, dict):
        details["invalid_values"].append("solo_developer_policy:not_object")
        return False, details

    required_keys = (
        "enabled",
        "single_writer_requires_review_count",
        "single_writer_require_code_owner_reviews",
        "multi_writer_min_review_count",
        "multi_writer_require_code_owner_reviews",
        "strict_required_status_checks",
        "enforce_admins_required",
    )
    for key in required_keys:
        if key not in section:
            details["missing_keys"].append(key)
    if details["missing_keys"]:
        return False, details

    if section.get("enabled") is not True:
        details["invalid_values"].append("enabled:must_be_true")

    single_reviews = section.get("single_writer_requires_review_count")
    if not isinstance(single_reviews, int) or single_reviews != 0:
        details["invalid_values"].append("single_writer_requires_review_count:must_be_0")

    single_code_owner = section.get("single_writer_require_code_owner_reviews")
    if single_code_owner is not False:
        details["invalid_values"].append("single_writer_require_code_owner_reviews:must_be_false")

    multi_reviews = section.get("multi_writer_min_review_count")
    if not isinstance(multi_reviews, int) or multi_reviews < 1:
        details["invalid_values"].append("multi_writer_min_review_count:must_be_int_gte_1")

    multi_code_owner = section.get("multi_writer_require_code_owner_reviews")
    if multi_code_owner is not True:
        details["invalid_values"].append("multi_writer_require_code_owner_reviews:must_be_true")

    if section.get("strict_required_status_checks") is not True:
        details["invalid_values"].append("strict_required_status_checks:must_be_true")
    if section.get("enforce_admins_required") is not True:
        details["invalid_values"].append("enforce_admins_required:must_be_true")

    ok = not details["missing_keys"] and not details["invalid_values"]
    return ok, details


def _check_enforcement_workflow(root: Path) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"issues": []}
    wf_path = root / ".github/workflows/gate-enforcement-check.yml"
    text = wf_path.read_text(encoding="utf-8")
    if "Standards lock + ownership baseline" not in text:
        details["issues"].append("standards_lock_step_missing")
    if "python3 ci/check_standards_lock.py" not in text:
        details["issues"].append("standards_lock_command_missing")
    if "Enforcement check (PR strict)" not in text:
        details["issues"].append("pr_strict_step_missing")
    if "continue-on-error: true" in text:
        details["issues"].append("pr_advisory_mode_detected")
    return not details["issues"], details


def _check_module_delivery_workflow(root: Path) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"issues": []}
    wf_path = root / ".github/workflows/module-delivery-lanes.yml"
    text = wf_path.read_text(encoding="utf-8")
    required_markers = (
        "module-delivery-contract-check",
        "module-lane-unit",
        "module-lane-contract",
        "module-lane-integration",
        "module-lane-e2e",
        "module-delivery-gate",
        "python3 ci/check_module_delivery_lanes.py --strict",
    )
    for marker in required_markers:
        if marker not in text:
            details["issues"].append(f"missing:{marker}")
    required_sequence_markers = (
        "module-lane-contract:\n    runs-on: ubuntu-latest\n    needs: [module-lane-unit]",
        "module-lane-integration:\n    runs-on: ubuntu-latest\n    needs: [module-lane-contract]",
        "module-lane-e2e:\n    runs-on: ubuntu-latest\n    needs: [module-lane-integration]",
    )
    for marker in required_sequence_markers:
        if marker not in text:
            details["issues"].append(f"missing_sequence:{marker}")
    if "needs.module-lane-unit.result" not in text:
        details["issues"].append("gate_job_result_check_missing")
    return not details["issues"], details


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root_arg = str(args.repo_root).strip()
    root = Path(repo_root_arg).expanduser().resolve() if repo_root_arg else _repo_root()
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).exists()]
    if missing:
        return _fail(
            "REQUIRED_FILES_MISSING",
            "Required standards files are missing.",
            details={"missing": missing},
        )

    lock_path = root / "standards.lock"
    try:
        lock = _load_json(lock_path)
    except Exception:
        return _fail("STANDARDS_LOCK_INVALID_JSON", "standards.lock must be valid JSON.")

    if not isinstance(lock, dict):
        return _fail("STANDARDS_LOCK_INVALID_TYPE", "standards.lock root must be an object.")

    missing_keys = [k for k in REQUIRED_LOCK_KEYS if k not in lock]
    if missing_keys:
        return _fail(
            "STANDARDS_LOCK_MISSING_KEYS",
            "standards.lock is missing required keys.",
            details={"missing_keys": missing_keys},
        )

    if lock.get("version") != "v1":
        return _fail("STANDARDS_LOCK_VERSION_INVALID", "standards.lock version must be v1.")

    operating_contract = lock.get("operating_contract")
    if operating_contract != "docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md":
        return _fail(
            "OPERATING_CONTRACT_PATH_INVALID",
            "operating_contract path must point to the v1 contract document.",
        )

    required_files = lock.get("required_files")
    if not isinstance(required_files, list):
        return _fail("REQUIRED_FILES_INVALID", "required_files must be a list.")
    file_set = {str(item) for item in required_files if isinstance(item, str)}
    missing_from_lock = [rel for rel in REQUIRED_FILES if rel not in file_set]
    if missing_from_lock:
        return _fail(
            "REQUIRED_FILES_INCOMPLETE",
            "standards.lock required_files does not include all critical files.",
            details={"missing": missing_from_lock},
        )

    commands_ok, command_details = _check_required_commands(lock.get("required_commands"))
    if not commands_ok:
        return _fail(
            "REQUIRED_COMMANDS_INCOMPLETE",
            "standards.lock required_commands does not include all baseline commands.",
            details=command_details,
        )

    sync_ok, sync_details = _check_managed_repo_sync(root, lock.get("managed_repo_sync"))
    if not sync_ok:
        return _fail(
            "MANAGED_REPO_SYNC_INVALID",
            "managed_repo_sync section is missing required keys or contains invalid values.",
            details=sync_details,
        )

    module_ok, module_details = _check_module_delivery_contract(lock.get("module_delivery_contract"))
    if not module_ok:
        return _fail(
            "MODULE_DELIVERY_CONTRACT_INVALID",
            "module_delivery_contract section is missing required keys or contains invalid values.",
            details=module_details,
        )

    branch_ok, branch_details = _check_branch_protection(lock.get("branch_protection"))
    if not branch_ok:
        return _fail(
            "BRANCH_PROTECTION_POLICY_INVALID",
            "branch_protection section is missing required keys or contains invalid values.",
            details=branch_details,
        )

    solo_ok, solo_details = _check_solo_developer_policy(lock.get("solo_developer_policy"))
    if not solo_ok:
        return _fail(
            "SOLO_DEVELOPER_POLICY_INVALID",
            "solo_developer_policy section is missing required keys or contains invalid values.",
            details=solo_details,
        )

    standard_sources = lock.get("standard_sources")
    if not isinstance(standard_sources, dict):
        return _fail("STANDARD_SOURCES_INVALID", "standard_sources must be an object.")
    sources_ok, source_details = _check_standard_sources(root, standard_sources)
    if not sources_ok:
        return _fail(
            "STANDARD_SOURCES_INVALID",
            "standard_sources references are missing or invalid against baseline expectations.",
            details=source_details,
        )

    workflow_ok, workflow_details = _check_enforcement_workflow(root)
    if not workflow_ok:
        return _fail(
            "ENFORCEMENT_WORKFLOW_NOT_HARDENED",
            "gate-enforcement-check workflow is not in hardened mode.",
            details=workflow_details,
        )

    module_wf_ok, module_wf_details = _check_module_delivery_workflow(root)
    if not module_wf_ok:
        return _fail(
            "MODULE_DELIVERY_WORKFLOW_INVALID",
            "module delivery workflow template is missing required jobs or checks.",
            details=module_wf_details,
        )

    required_gates = lock.get("required_gates")
    if not isinstance(required_gates, list):
        return _fail("REQUIRED_GATES_INVALID", "required_gates must be a list.")
    gate_set = {str(item) for item in required_gates if isinstance(item, str)}
    missing_gates = [gate for gate in REQUIRED_GATES if gate not in gate_set]
    if missing_gates:
        return _fail(
            "REQUIRED_GATES_INCOMPLETE",
            "standards.lock required_gates does not include all baseline gates.",
            details={"missing": missing_gates},
        )

    pr_gate_mode = lock.get("pr_gate_mode")
    if not isinstance(pr_gate_mode, dict):
        return _fail("PR_GATE_MODE_INVALID", "pr_gate_mode must be an object.")
    enf_mode = pr_gate_mode.get("enforcement_check_pull_request")
    if enf_mode != "blocking":
        return _fail(
            "PR_GATE_MODE_NOT_BLOCKING",
            "enforcement_check_pull_request must be blocking.",
        )

    print(
        json.dumps(
            {
                "status": "OK",
                "checked_files": list(REQUIRED_FILES),
                "checked_standard_sources": list(REQUIRED_STANDARD_SOURCES),
                "checked_commands": list(REQUIRED_COMMANDS),
                "checked_gates": list(REQUIRED_GATES),
                "checked_sections": [
                    "managed_repo_sync",
                    "module_delivery_contract",
                    "branch_protection",
                    "solo_developer_policy",
                ],
                "lock_path": str(lock_path.as_posix()),
                "repo_root": str(root.as_posix()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
