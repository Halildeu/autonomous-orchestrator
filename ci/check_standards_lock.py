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
    "docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md",
    "policies/policy_pm_suite.v1.json",
    "policies/policy_feature_execution_bridge.v1.json",
    "policies/policy_ui_design_system.v1.json",
    "policies/policy_ux_catalog_enforcement.v1.json",
    "registry/technical_baseline.aistd.v1.json",
    "registry/archives/legacy_standards_archive.aistd.v1.json",
    "schemas/policy-pm-suite.schema.v1.json",
    "schemas/policy-feature-execution-bridge.schema.v1.json",
    "schemas/feature-execution-contract.schema.v1.json",
    "schemas/delivery-session-packet.schema.v1.json",
    "schemas/policy-ui-design-system.schema.v1.json",
    "schemas/policy-ux-catalog-enforcement.schema.v1.json",
    "schemas/technical-baseline-aistd.schema.v1.json",
    "schemas/legacy-standards-archive-aistd.schema.v1.json",
    "scripts/sync_managed_repo_standards.py",
    "scripts/archive_legacy_standards.py",
    "scripts/ops_technical_baseline_checklist.py",
    "scripts/export_managed_repo_standards_dashboard.py",
    "ci/check_standards_lock.py",
    "ci/check_module_delivery_lanes.py",
    "ci/run_module_delivery_lane.py",
    "ci/module_delivery_lanes.v1.json",
    "scripts/check_branch_protection_solo_policy.py",
    "extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json",
    "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
    "extensions/PRJ-UX-NORTH-STAR/contract/check_ux_catalog_enforcement.py",
    "extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json",
    "extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py",
    "extensions/PRJ-PM-SUITE/contract/seed_feature_execution_contract.py",
    "extensions/PRJ-PM-SUITE/contract/build_delivery_session_packet.py",
    "extensions/PRJ-PM-SUITE/contract/check_delivery_session_guard.py",
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
    "ux-catalog-gate",
    "feature-execution-bridge",
)

REQUIRED_STANDARD_SOURCES = (
    "technical_baseline_aistd",
    "pm_suite_policy",
    "feature_execution_bridge_policy",
    "layer_boundary_policy",
    "llm_live_policy",
    "llm_provider_guardrails_policy",
    "kernel_api_guardrails_policy",
    "ui_design_system_policy",
    "security_policy",
    "secrets_policy",
    "ux_catalog_enforcement_policy",
    "ux_catalog_lock",
)

REQUIRED_COMMANDS = (
    "python ci/validate_schemas.py",
    "python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json",
    "python ci/check_script_budget.py --out .cache/script_budget/report.json",
    "python -m src.ops.manage enforcement-check --profile strict",
    "python3 scripts/ops_technical_baseline_checklist.py --repo-root .",
    "python3 scripts/export_managed_repo_standards_dashboard.py --workspace-root .",
    "python3 scripts/sync_managed_repo_standards.py --target-repo-root <repo_root>",
    "python3 ci/check_module_delivery_lanes.py --strict",
    "python3 scripts/check_branch_protection_solo_policy.py --repo-slug <owner/repo>",
    "python3 extensions/PRJ-UX-NORTH-STAR/contract/check_ux_catalog_enforcement.py --repo-root .",
    "python3 extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py --repo-root .",
    "python3 extensions/PRJ-PM-SUITE/contract/build_delivery_session_packet.py --repo-root . --out .cache/reports/delivery_session_packet.v1.json",
    "python3 extensions/PRJ-PM-SUITE/contract/check_delivery_session_guard.py --repo-root . --packet .cache/reports/delivery_session_packet.v1.json",
)

REQUIRED_PRESERVE_PATHS = (
    "ci/module_delivery_lanes.v1.json",
    "registry/archives/legacy_standards_archive.aistd.v1.json",
    "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
    "extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json",
)

REQUIRED_BRANCH_PROTECTION_CHECKS = (
    "module-delivery-gate",
    "enforcement-check",
    "validate-schemas",
    "policy-dry-run",
    "gitleaks",
)

REQUIRED_DELIVERY_SEQUENCE = ("backend", "database", "api", "frontend", "integration", "e2e")
REQUIRED_SCOPE_LANE_MAP = {
    "backend": "unit",
    "database": "database",
    "api": "api",
    "frontend": "contract",
    "integration": "integration",
    "e2e_gate": "e2e",
}
REQUIRED_LANES = ("unit", "database", "api", "contract", "integration", "e2e")
REQUIRED_BACKEND_LAYERS = ("config", "controller", "dto", "model", "repository", "security", "service")
REQUIRED_FRONTEND_LAYOUT_EXPORTS = ("PageLayout", "DetailDrawer", "FormDrawer")


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


def _check_pm_suite_policy(root: Path, rel_path: str) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"invalid_values": [], "missing_files": []}
    policy = _require_json_file(root, rel_path, key="pm_suite_policy")
    if not isinstance(policy, dict):
        details["invalid_values"].append("pm_suite_policy:invalid_json")
        return False, details

    if policy.get("version") != "v1":
        details["invalid_values"].append("pm_suite_policy:version_must_be_v1")
    if policy.get("enabled") is not True:
        details["invalid_values"].append("pm_suite_policy:enabled_must_be_true")

    workflow = policy.get("default_workflow")
    statuses = workflow.get("statuses") if isinstance(workflow, dict) else []
    if not isinstance(statuses, list) or not {"OPEN", "IN_PROGRESS", "BLOCKED", "DONE"}.issubset(set(statuses)):
        details["invalid_values"].append("pm_suite_policy:default_workflow_statuses_invalid")

    if policy.get("default_priority") != "P2":
        details["invalid_values"].append("pm_suite_policy:default_priority_must_be_P2")
    if policy.get("default_severity") != "S3":
        details["invalid_values"].append("pm_suite_policy:default_severity_must_be_S3")

    execution_bridge = policy.get("execution_bridge")
    if not isinstance(execution_bridge, dict):
        details["invalid_values"].append("pm_suite_policy:execution_bridge_missing")
    else:
        if execution_bridge.get("enabled") is not True:
            details["invalid_values"].append("pm_suite_policy:execution_bridge.enabled_must_be_true")
        expected_paths = {
            "contract_path": "extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json",
            "checker_path": "extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py",
            "seed_script_path": "extensions/PRJ-PM-SUITE/contract/seed_feature_execution_contract.py",
            "contract_schema_path": "schemas/feature-execution-contract.schema.v1.json",
            "report_path": ".cache/reports/feature_execution_contract_check.v1.json",
        }
        for key, expected in expected_paths.items():
            if str(execution_bridge.get(key) or "") != expected:
                details["invalid_values"].append(f"pm_suite_policy:execution_bridge.{key}_invalid")

    delivery_session = policy.get("delivery_session")
    if not isinstance(delivery_session, dict):
        details["invalid_values"].append("pm_suite_policy:delivery_session_missing")
    else:
        if delivery_session.get("enabled") is not True:
            details["invalid_values"].append("pm_suite_policy:delivery_session.enabled_must_be_true")
        expected_paths = {
            "packet_path": ".cache/reports/delivery_session_packet.v1.json",
            "guard_report_path": ".cache/reports/delivery_session_guard.v1.json",
            "builder_path": "extensions/PRJ-PM-SUITE/contract/build_delivery_session_packet.py",
            "guard_path": "extensions/PRJ-PM-SUITE/contract/check_delivery_session_guard.py",
            "packet_schema_path": "schemas/delivery-session-packet.schema.v1.json",
            "note": "delivery_session_compiler_active",
        }
        for key, expected in expected_paths.items():
            if str(delivery_session.get(key) or "") != expected:
                details["invalid_values"].append(f"pm_suite_policy:delivery_session.{key}_invalid")

    return not details["invalid_values"] and not details["missing_files"], details


def _check_ux_catalog_enforcement_policy(root: Path, rel_path: str) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"invalid_values": [], "missing_files": []}
    policy = _require_json_file(root, rel_path, key="ux_catalog_enforcement_policy")
    if not isinstance(policy, dict):
        details["invalid_values"].append("ux_catalog_enforcement_policy:invalid_json")
        return False, details

    if policy.get("version") != "v1":
        details["invalid_values"].append("ux_catalog_enforcement_policy:version_must_be_v1")
    if policy.get("kind") != "policy-ux-catalog-enforcement":
        details["invalid_values"].append("ux_catalog_enforcement_policy:kind_invalid")
    if policy.get("status") != "ACTIVE":
        details["invalid_values"].append("ux_catalog_enforcement_policy:status_must_be_ACTIVE")
    if policy.get("enforcement_mode") != "blocking":
        details["invalid_values"].append("ux_catalog_enforcement_policy:enforcement_mode_must_be_blocking")
    if str(policy.get("lock_file") or "") != "extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json":
        details["invalid_values"].append("ux_catalog_enforcement_policy:lock_file_invalid")

    change_map = policy.get("change_map")
    if not isinstance(change_map, dict):
        details["invalid_values"].append("ux_catalog_enforcement_policy:change_map_missing")
    else:
        if str(change_map.get("path") or "") != "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json":
            details["invalid_values"].append("ux_catalog_enforcement_policy:change_map.path_invalid")
        if int(change_map.get("min_entries") or 0) < 1:
            details["invalid_values"].append("ux_catalog_enforcement_policy:change_map.min_entries_invalid")

    return not details["invalid_values"] and not details["missing_files"], details


def _check_ux_catalog_lock(root: Path, rel_path: str) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"invalid_values": [], "missing_files": []}
    lock = _require_json_file(root, rel_path, key="ux_catalog_lock")
    if not isinstance(lock, dict):
        details["invalid_values"].append("ux_catalog_lock:invalid_json")
        return False, details

    if lock.get("version") != "v1":
        details["invalid_values"].append("ux_catalog_lock:version_must_be_v1")
    if lock.get("kind") != "ux-catalog-lock":
        details["invalid_values"].append("ux_catalog_lock:kind_invalid")
    if lock.get("status") != "ACTIVE":
        details["invalid_values"].append("ux_catalog_lock:status_must_be_ACTIVE")
    if str(lock.get("subject_id") or "") != "ux_katalogu":
        details["invalid_values"].append("ux_catalog_lock:subject_id_invalid")
    if int(lock.get("theme_count") or 0) <= 0:
        details["invalid_values"].append("ux_catalog_lock:theme_count_invalid")
    if int(lock.get("subtheme_count") or 0) <= 0:
        details["invalid_values"].append("ux_catalog_lock:subtheme_count_invalid")

    return not details["invalid_values"] and not details["missing_files"], details


def _check_feature_execution_bridge_policy(root: Path, rel_path: str) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"invalid_values": [], "missing_files": []}
    policy = _require_json_file(root, rel_path, key="feature_execution_bridge_policy")
    if not isinstance(policy, dict):
        details["invalid_values"].append("feature_execution_bridge_policy:invalid_json")
        return False, details

    if policy.get("version") != "v1":
        details["invalid_values"].append("feature_execution_bridge_policy:version_must_be_v1")
    if policy.get("kind") != "policy-feature-execution-bridge":
        details["invalid_values"].append("feature_execution_bridge_policy:kind_invalid")
    if policy.get("status") != "ACTIVE":
        details["invalid_values"].append("feature_execution_bridge_policy:status_must_be_ACTIVE")
    if policy.get("enforcement_mode") != "blocking":
        details["invalid_values"].append("feature_execution_bridge_policy:enforcement_mode_must_be_blocking")

    expected_paths = {
        "contract_path": "extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json",
        "contract_schema_path": "schemas/feature-execution-contract.schema.v1.json",
        "pm_policy_path": "policies/policy_pm_suite.v1.json",
        "technical_baseline_path": "registry/technical_baseline.aistd.v1.json",
        "ux_lock_path": "extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json",
    }
    for key, expected in expected_paths.items():
        if str(policy.get(key) or "") != expected:
            details["invalid_values"].append(f"feature_execution_bridge_policy:{key}_invalid")

    scope_detection = policy.get("scope_detection")
    if not isinstance(scope_detection, dict):
        details["invalid_values"].append("feature_execution_bridge_policy:scope_detection_missing")
    else:
        if not isinstance(scope_detection.get("include_globs"), list) or not scope_detection.get("include_globs"):
            details["invalid_values"].append("feature_execution_bridge_policy:scope_detection.include_globs_invalid")
        if not isinstance(scope_detection.get("exclude_globs"), list):
            details["invalid_values"].append("feature_execution_bridge_policy:scope_detection.exclude_globs_invalid")
        scope_globs = scope_detection.get("scope_globs")
        required_scope_keys = {"backend", "frontend", "database", "api"}
        if not isinstance(scope_globs, dict) or not required_scope_keys.issubset(set(scope_globs.keys())):
            details["invalid_values"].append("feature_execution_bridge_policy:scope_detection.scope_globs_invalid")

    ux_scope = policy.get("ux_scope")
    if not isinstance(ux_scope, dict):
        details["invalid_values"].append("feature_execution_bridge_policy:ux_scope_missing")
    else:
        if not isinstance(ux_scope.get("required_globs"), list) or not ux_scope.get("required_globs"):
            details["invalid_values"].append("feature_execution_bridge_policy:ux_scope.required_globs_invalid")
        if ux_scope.get("require_ux_on_frontend_changes") is not True:
            details["invalid_values"].append(
                "feature_execution_bridge_policy:ux_scope.require_ux_on_frontend_changes_must_be_true"
            )

    validation = policy.get("validation")
    if not isinstance(validation, dict):
        details["invalid_values"].append("feature_execution_bridge_policy:validation_missing")
    else:
        if validation.get("active_status_on_scoped_change") is not True:
            details["invalid_values"].append(
                "feature_execution_bridge_policy:validation.active_status_on_scoped_change_must_be_true"
            )
        if int(validation.get("required_source_refs_min") or 0) < 1:
            details["invalid_values"].append(
                "feature_execution_bridge_policy:validation.required_source_refs_min_invalid"
            )
        if not isinstance(validation.get("placeholder_tokens"), list) or not validation.get("placeholder_tokens"):
            details["invalid_values"].append("feature_execution_bridge_policy:validation.placeholder_tokens_invalid")
        if validation.get("required_execution_sequence_from_lock") is not True:
            details["invalid_values"].append(
                "feature_execution_bridge_policy:validation.required_execution_sequence_from_lock_must_be_true"
            )
        if validation.get("required_lanes_from_lock") is not True:
            details["invalid_values"].append(
                "feature_execution_bridge_policy:validation.required_lanes_from_lock_must_be_true"
            )

    reporting = policy.get("reporting")
    if not isinstance(reporting, dict) or str(reporting.get("out_path") or "") != ".cache/reports/feature_execution_contract_check.v1.json":
        details["invalid_values"].append("feature_execution_bridge_policy:reporting.out_path_invalid")

    return not details["invalid_values"] and not details["missing_files"], details


def _check_technical_baseline_aistd(root: Path, rel_path: str) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {"invalid_values": [], "missing_files": []}
    baseline = _require_json_file(root, rel_path, key="technical_baseline_aistd")
    if not isinstance(baseline, dict):
        details["invalid_values"].append("technical_baseline_aistd:invalid_json")
        return False, details

    if baseline.get("version") != "v1":
        details["invalid_values"].append("technical_baseline_aistd:version_must_be_v1")
    if baseline.get("kind") != "technical-baseline-aistd":
        details["invalid_values"].append("technical_baseline_aistd:kind_must_be_technical-baseline-aistd")
    if baseline.get("status") != "ACTIVE":
        details["invalid_values"].append("technical_baseline_aistd:status_must_be_ACTIVE")

    ownership = baseline.get("ownership")
    if not isinstance(ownership, dict):
        details["invalid_values"].append("technical_baseline_aistd:ownership_missing")
    else:
        if str(ownership.get("sync_script") or "") != "scripts/sync_managed_repo_standards.py":
            details["invalid_values"].append("technical_baseline_aistd:ownership.sync_script_invalid")
        if str(ownership.get("validation_script") or "") != "ci/check_standards_lock.py":
            details["invalid_values"].append("technical_baseline_aistd:ownership.validation_script_invalid")

    baseline_obj = baseline.get("baseline")
    if not isinstance(baseline_obj, dict):
        details["invalid_values"].append("technical_baseline_aistd:baseline_missing")
        return False, details

    backend = baseline_obj.get("backend")
    if not isinstance(backend, dict):
        details["invalid_values"].append("technical_baseline_aistd:baseline.backend_missing")
    else:
        if backend.get("language") != "java":
            details["invalid_values"].append("technical_baseline_aistd:backend.language_must_be_java")
        if int(backend.get("java_major") or 0) < 21:
            details["invalid_values"].append("technical_baseline_aistd:backend.java_major_must_be_gte_21")
        if backend.get("framework") != "spring-boot":
            details["invalid_values"].append("technical_baseline_aistd:backend.framework_must_be_spring-boot")
        if backend.get("service_architecture") != "microservice":
            details["invalid_values"].append("technical_baseline_aistd:backend.service_architecture_must_be_microservice")
        layer_set = {
            str(item).strip()
            for item in (backend.get("required_layers") if isinstance(backend.get("required_layers"), list) else [])
            if isinstance(item, str) and str(item).strip()
        }
        missing_layers = [name for name in REQUIRED_BACKEND_LAYERS if name not in layer_set]
        if missing_layers:
            details["invalid_values"].append(
                f"technical_baseline_aistd:backend.required_layers_missing_{','.join(missing_layers)}"
            )
        comm_set = {
            str(item).strip()
            for item in (
                backend.get("inter_service_communication")
                if isinstance(backend.get("inter_service_communication"), list)
                else []
            )
            if isinstance(item, str) and str(item).strip()
        }
        if "rest" not in comm_set or "event" not in comm_set:
            details["invalid_values"].append("technical_baseline_aistd:backend.inter_service_communication_must_include_rest_event")

    frontend = baseline_obj.get("frontend")
    if not isinstance(frontend, dict):
        details["invalid_values"].append("technical_baseline_aistd:baseline.frontend_missing")
    else:
        if frontend.get("language") != "typescript":
            details["invalid_values"].append("technical_baseline_aistd:frontend.language_must_be_typescript")
        if frontend.get("framework") != "react":
            details["invalid_values"].append("technical_baseline_aistd:frontend.framework_must_be_react")
        if int(frontend.get("node_major") or 0) != 20:
            details["invalid_values"].append("technical_baseline_aistd:frontend.node_major_must_be_20")
        if frontend.get("package_manager") != "npm":
            details["invalid_values"].append("technical_baseline_aistd:frontend.package_manager_must_be_npm")
        design_contract = frontend.get("design_contract")
        if not isinstance(design_contract, dict):
            details["invalid_values"].append("technical_baseline_aistd:frontend.design_contract_missing")
        else:
            if design_contract.get("single_ui_library") != "mfe-ui-kit":
                details["invalid_values"].append("technical_baseline_aistd:frontend.design_contract.single_ui_library_invalid")
            if (
                str(design_contract.get("ui_package_manifest_path") or "")
                != "web/packages/ui-kit/package.json"
            ):
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.design_contract.ui_package_manifest_path_invalid"
                )
            if (
                str(design_contract.get("design_catalog_index_path") or "")
                != "web/apps/mfe-shell/src/pages/admin/design-lab.index.json"
            ):
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.design_contract.design_catalog_index_path_invalid"
                )
            if str(design_contract.get("token_source_path") or "") != "web/design-tokens/figma.tokens.json":
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.design_contract.token_source_path_invalid"
                )
            forbidden_imports = {
                str(item).strip()
                for item in (
                    design_contract.get("forbidden_imports")
                    if isinstance(design_contract.get("forbidden_imports"), list)
                    else []
                )
                if isinstance(item, str) and str(item).strip()
            }
            if "antd" not in forbidden_imports or "@ant-design/icons" not in forbidden_imports:
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.design_contract.forbidden_imports_missing_antd_rules"
                )
            generated_paths = {
                str(item).strip()
                for item in (
                    design_contract.get("token_generated_paths")
                    if isinstance(design_contract.get("token_generated_paths"), list)
                    else []
                )
                if isinstance(item, str) and str(item).strip()
            }
            required_generated = {
                "web/apps/mfe-shell/src/styles/theme.css",
                "web/design-tokens/generated/theme-contract.json",
            }
            missing_generated = sorted(required_generated - generated_paths)
            if missing_generated:
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.design_contract.token_generated_paths_missing_"
                    + ",".join(missing_generated)
                )

        page_composition = frontend.get("page_composition")
        if not isinstance(page_composition, dict):
            details["invalid_values"].append("technical_baseline_aistd:frontend.page_composition_missing")
        else:
            layout_exports = {
                str(item).strip()
                for item in (
                    page_composition.get("required_layout_exports")
                    if isinstance(page_composition.get("required_layout_exports"), list)
                    else []
                )
                if isinstance(item, str) and str(item).strip()
            }
            missing_layout_exports = [name for name in REQUIRED_FRONTEND_LAYOUT_EXPORTS if name not in layout_exports]
            if missing_layout_exports:
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.page_composition.required_layout_exports_missing_"
                    + ",".join(missing_layout_exports)
                )
            if str(page_composition.get("ui_import_prefix") or "") != "from 'mfe-ui-kit'":
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.page_composition.ui_import_prefix_invalid"
                )
            if str(page_composition.get("pages_root") or "") != "web/apps":
                details["invalid_values"].append("technical_baseline_aistd:frontend.page_composition.pages_root_invalid")

        parametric_data = frontend.get("parametric_data")
        if not isinstance(parametric_data, dict):
            details["invalid_values"].append("technical_baseline_aistd:frontend.parametric_data_missing")
        else:
            if (
                str(parametric_data.get("query_builder_path") or "")
                != "web/packages/ui-kit/src/components/entity-grid/buildEntityGridQueryParams.ts"
            ):
                details["invalid_values"].append("technical_baseline_aistd:frontend.parametric_data.query_builder_path_invalid")
            if (
                str(parametric_data.get("theme_contract_runtime_path") or "")
                != "web/packages/ui-kit/src/runtime/theme-contract.ts"
            ):
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.parametric_data.theme_contract_runtime_path_invalid"
                )
            if (
                str(parametric_data.get("theme_context_provider_path") or "")
                != "web/apps/mfe-shell/src/app/theme/theme-context.provider.tsx"
            ):
                details["invalid_values"].append(
                    "technical_baseline_aistd:frontend.parametric_data.theme_context_provider_path_invalid"
                )

    database = baseline_obj.get("database")
    if not isinstance(database, dict):
        details["invalid_values"].append("technical_baseline_aistd:baseline.database_missing")
    else:
        if database.get("engine") != "postgresql":
            details["invalid_values"].append("technical_baseline_aistd:database.engine_must_be_postgresql")
        if database.get("migration_tool") != "flyway":
            details["invalid_values"].append("technical_baseline_aistd:database.migration_tool_must_be_flyway")

    api = baseline_obj.get("api")
    if not isinstance(api, dict):
        details["invalid_values"].append("technical_baseline_aistd:baseline.api_missing")
    else:
        if api.get("protocol") != "rest":
            details["invalid_values"].append("technical_baseline_aistd:api.protocol_must_be_rest")
        if api.get("version_prefix") != "/api/v1":
            details["invalid_values"].append("technical_baseline_aistd:api.version_prefix_must_be_/api/v1")
        if api.get("auth_scheme") != "bearer-jwt":
            details["invalid_values"].append("technical_baseline_aistd:api.auth_scheme_must_be_bearer-jwt")
        fields = {
            str(item).strip()
            for item in (api.get("error_envelope_fields") if isinstance(api.get("error_envelope_fields"), list) else [])
            if isinstance(item, str) and str(item).strip()
        }
        required_fields = {"code", "message", "timestamp", "path"}
        missing_fields = sorted(required_fields - fields)
        if missing_fields:
            details["invalid_values"].append(
                f"technical_baseline_aistd:api.error_envelope_fields_missing_{','.join(missing_fields)}"
            )

    topology = baseline.get("topology")
    if not isinstance(topology, dict):
        details["invalid_values"].append("technical_baseline_aistd:topology_missing")
    else:
        if topology.get("edge_gateway") != "spring-cloud-gateway":
            details["invalid_values"].append("technical_baseline_aistd:topology.edge_gateway_invalid")
        if topology.get("service_discovery") != "eureka":
            details["invalid_values"].append("technical_baseline_aistd:topology.service_discovery_invalid")

    ci_contract = baseline.get("ci_contract")
    if not isinstance(ci_contract, dict):
        details["invalid_values"].append("technical_baseline_aistd:ci_contract_missing")
    else:
        actual_sequence = [str(item) for item in (ci_contract.get("delivery_sequence") or [])]
        if actual_sequence != list(REQUIRED_DELIVERY_SEQUENCE):
            details["invalid_values"].append(
                f"technical_baseline_aistd:ci_contract.delivery_sequence_must_equal_{','.join(REQUIRED_DELIVERY_SEQUENCE)}"
            )
        lane_set = {
            str(item).strip()
            for item in (ci_contract.get("required_lanes") if isinstance(ci_contract.get("required_lanes"), list) else [])
            if isinstance(item, str) and str(item).strip()
        }
        missing_lanes = [name for name in REQUIRED_LANES if name not in lane_set]
        if missing_lanes:
            details["invalid_values"].append(
                f"technical_baseline_aistd:ci_contract.required_lanes_missing_{','.join(missing_lanes)}"
            )
        if ci_contract.get("gate_name") != "module-delivery-gate":
            details["invalid_values"].append("technical_baseline_aistd:ci_contract.gate_name_invalid")
        if ci_contract.get("merge_requires_all_green") is not True:
            details["invalid_values"].append("technical_baseline_aistd:ci_contract.merge_requires_all_green_must_be_true")

    archive = baseline.get("archive")
    if not isinstance(archive, dict):
        details["invalid_values"].append("technical_baseline_aistd:archive_missing")
    else:
        if archive.get("legacy_mode") != "read-only":
            details["invalid_values"].append("technical_baseline_aistd:archive.legacy_mode_must_be_read-only")
        manifest_rel = str(archive.get("legacy_manifest_path") or "")
        if manifest_rel != "registry/archives/legacy_standards_archive.aistd.v1.json":
            details["invalid_values"].append("technical_baseline_aistd:archive.legacy_manifest_path_invalid")
        else:
            manifest_path = root / manifest_rel
            if not manifest_path.exists():
                details["missing_files"].append(manifest_rel)
            else:
                manifest_obj = _require_json_file(root, manifest_rel, key="legacy_standards_archive_aistd")
                if not isinstance(manifest_obj, dict):
                    details["invalid_values"].append("technical_baseline_aistd:archive.manifest_invalid_json")
                else:
                    if manifest_obj.get("kind") != "legacy-standards-archive-aistd":
                        details["invalid_values"].append("technical_baseline_aistd:archive.manifest_kind_invalid")
                    if manifest_obj.get("version") != "v1":
                        details["invalid_values"].append("technical_baseline_aistd:archive.manifest_version_invalid")

    ok = not details["invalid_values"] and not details["missing_files"]
    return ok, details


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

    ui_design_policy = _require_json_file(root, str(standard_sources["ui_design_system_policy"]), key="ui_design_system_policy")
    if not isinstance(ui_design_policy, dict):
        details["invalid_content"].append("ui_design_system_policy:invalid_json")
    else:
        if ui_design_policy.get("version") != "v1":
            details["invalid_content"].append("ui_design_system_policy:version_must_be_v1")
        if ui_design_policy.get("kind") != "policy-ui-design-system":
            details["invalid_content"].append("ui_design_system_policy:kind_invalid")
        if ui_design_policy.get("status") != "ACTIVE":
            details["invalid_content"].append("ui_design_system_policy:status_must_be_ACTIVE")
        if ui_design_policy.get("enforcement_mode") != "blocking":
            details["invalid_content"].append("ui_design_system_policy:enforcement_mode_must_be_blocking")
        if ui_design_policy.get("ci_lane") != "contract":
            details["invalid_content"].append("ui_design_system_policy:ci_lane_must_be_contract")
        single_ui = ui_design_policy.get("single_ui_library")
        if not isinstance(single_ui, dict):
            details["invalid_content"].append("ui_design_system_policy:single_ui_library_missing")
        else:
            if single_ui.get("package_name") != "mfe-ui-kit":
                details["invalid_content"].append("ui_design_system_policy:single_ui_library.package_name_invalid")
            if str(single_ui.get("package_manifest_path") or "") != "web/packages/ui-kit/package.json":
                details["invalid_content"].append(
                    "ui_design_system_policy:single_ui_library.package_manifest_path_invalid"
                )
            if (
                str(single_ui.get("design_catalog_index_path") or "")
                != "web/apps/mfe-shell/src/pages/admin/design-lab.index.json"
            ):
                details["invalid_content"].append(
                    "ui_design_system_policy:single_ui_library.design_catalog_index_path_invalid"
                )
            forbidden_imports = {
                str(item).strip()
                for item in (
                    single_ui.get("forbidden_imports")
                    if isinstance(single_ui.get("forbidden_imports"), list)
                    else []
                )
                if isinstance(item, str) and str(item).strip()
            }
            if "antd" not in forbidden_imports or "@ant-design/icons" not in forbidden_imports:
                details["invalid_content"].append(
                    "ui_design_system_policy:single_ui_library.forbidden_imports_missing_antd_rules"
                )
        design_tokens = ui_design_policy.get("design_tokens")
        if not isinstance(design_tokens, dict):
            details["invalid_content"].append("ui_design_system_policy:design_tokens_missing")
        else:
            if str(design_tokens.get("source_path") or "") != "web/design-tokens/figma.tokens.json":
                details["invalid_content"].append("ui_design_system_policy:design_tokens.source_path_invalid")
            generated_paths = {
                str(item).strip()
                for item in (
                    design_tokens.get("generated_paths")
                    if isinstance(design_tokens.get("generated_paths"), list)
                    else []
                )
                if isinstance(item, str) and str(item).strip()
            }
            required_generated = {
                "web/apps/mfe-shell/src/styles/theme.css",
                "web/design-tokens/generated/theme-contract.json",
            }
            missing_generated = sorted(required_generated - generated_paths)
            if missing_generated:
                details["invalid_content"].append(
                    "ui_design_system_policy:design_tokens.generated_paths_missing_" + ",".join(missing_generated)
                )
        page_modularity = ui_design_policy.get("page_modularity")
        if not isinstance(page_modularity, dict):
            details["invalid_content"].append("ui_design_system_policy:page_modularity_missing")
        else:
            layout_exports = {
                str(item).strip()
                for item in (
                    page_modularity.get("layout_exports_required")
                    if isinstance(page_modularity.get("layout_exports_required"), list)
                    else []
                )
                if isinstance(item, str) and str(item).strip()
            }
            missing_layout_exports = [name for name in REQUIRED_FRONTEND_LAYOUT_EXPORTS if name not in layout_exports]
            if missing_layout_exports:
                details["invalid_content"].append(
                    "ui_design_system_policy:page_modularity.layout_exports_required_missing_"
                    + ",".join(missing_layout_exports)
                )
            if str(page_modularity.get("ui_usage_import_prefix") or "") != "from 'mfe-ui-kit'":
                details["invalid_content"].append("ui_design_system_policy:page_modularity.ui_usage_import_prefix_invalid")
            if str(page_modularity.get("pages_root") or "") != "web/apps":
                details["invalid_content"].append("ui_design_system_policy:page_modularity.pages_root_invalid")
        parametric_data = ui_design_policy.get("parametric_data")
        if not isinstance(parametric_data, dict):
            details["invalid_content"].append("ui_design_system_policy:parametric_data_missing")
        else:
            if (
                str(parametric_data.get("query_builder_path") or "")
                != "web/packages/ui-kit/src/components/entity-grid/buildEntityGridQueryParams.ts"
            ):
                details["invalid_content"].append("ui_design_system_policy:parametric_data.query_builder_path_invalid")
            if (
                str(parametric_data.get("theme_contract_runtime_path") or "")
                != "web/packages/ui-kit/src/runtime/theme-contract.ts"
            ):
                details["invalid_content"].append(
                    "ui_design_system_policy:parametric_data.theme_contract_runtime_path_invalid"
                )
            if (
                str(parametric_data.get("theme_context_provider_path") or "")
                != "web/apps/mfe-shell/src/app/theme/theme-context.provider.tsx"
            ):
                details["invalid_content"].append(
                    "ui_design_system_policy:parametric_data.theme_context_provider_path_invalid"
                )

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

    technical_rel = str(standard_sources["technical_baseline_aistd"])
    tech_ok, tech_details = _check_technical_baseline_aistd(root, technical_rel)
    if not tech_ok:
        for item in tech_details.get("invalid_values", []):
            details["invalid_content"].append(item)
        for item in tech_details.get("missing_files", []):
            details["missing_files"].append(item)

    pm_ok, pm_details = _check_pm_suite_policy(root, str(standard_sources["pm_suite_policy"]))
    if not pm_ok:
        for item in pm_details.get("invalid_values", []):
            details["invalid_content"].append(item)
        for item in pm_details.get("missing_files", []):
            details["missing_files"].append(item)

    ux_policy_ok, ux_policy_details = _check_ux_catalog_enforcement_policy(
        root, str(standard_sources["ux_catalog_enforcement_policy"])
    )
    if not ux_policy_ok:
        for item in ux_policy_details.get("invalid_values", []):
            details["invalid_content"].append(item)
        for item in ux_policy_details.get("missing_files", []):
            details["missing_files"].append(item)

    ux_lock_ok, ux_lock_details = _check_ux_catalog_lock(root, str(standard_sources["ux_catalog_lock"]))
    if not ux_lock_ok:
        for item in ux_lock_details.get("invalid_values", []):
            details["invalid_content"].append(item)
        for item in ux_lock_details.get("missing_files", []):
            details["missing_files"].append(item)

    feature_bridge_ok, feature_bridge_details = _check_feature_execution_bridge_policy(
        root, str(standard_sources["feature_execution_bridge_policy"])
    )
    if not feature_bridge_ok:
        for item in feature_bridge_details.get("invalid_values", []):
            details["invalid_content"].append(item)
        for item in feature_bridge_details.get("missing_files", []):
            details["missing_files"].append(item)

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
        expected_lanes = {"unit", "database", "api", "contract", "integration", "e2e"}
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
    if "Feature execution bridge gate" not in text:
        details["issues"].append("feature_execution_bridge_step_missing")
    if "python3 extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py" not in text:
        details["issues"].append("feature_execution_bridge_command_missing")
    if "Delivery session packet build" not in text:
        details["issues"].append("delivery_session_packet_step_missing")
    if "python3 extensions/PRJ-PM-SUITE/contract/build_delivery_session_packet.py" not in text:
        details["issues"].append("delivery_session_packet_command_missing")
    if "Delivery session guard" not in text:
        details["issues"].append("delivery_session_guard_step_missing")
    if "python3 extensions/PRJ-PM-SUITE/contract/check_delivery_session_guard.py" not in text:
        details["issues"].append("delivery_session_guard_command_missing")
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
        "module-lane-database",
        "module-lane-api",
        "module-lane-contract",
        "module-lane-integration",
        "module-lane-e2e",
        "module-delivery-gate",
        "python3 ci/check_module_delivery_lanes.py --strict",
        "python3 extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py",
        "python3 extensions/PRJ-PM-SUITE/contract/build_delivery_session_packet.py",
        "python3 extensions/PRJ-PM-SUITE/contract/check_delivery_session_guard.py",
        "python3 ci/run_module_delivery_lane.py --lane unit",
        "python3 ci/run_module_delivery_lane.py --lane database",
        "python3 ci/run_module_delivery_lane.py --lane api",
        "python3 ci/run_module_delivery_lane.py --lane contract",
        "python3 ci/run_module_delivery_lane.py --lane integration",
        "python3 ci/run_module_delivery_lane.py --lane e2e",
    )
    for marker in required_markers:
        if marker not in text:
            details["issues"].append(f"missing:{marker}")
    required_sequence_markers = (
        "module-lane-database:\n    runs-on: ubuntu-latest\n    needs: [module-lane-unit]",
        "module-lane-api:\n    runs-on: ubuntu-latest\n    needs: [module-lane-database]",
        "module-lane-contract:\n    runs-on: ubuntu-latest\n    needs: [module-lane-api]",
        "module-lane-integration:\n    runs-on: ubuntu-latest\n    needs: [module-lane-contract]",
        "module-lane-e2e:\n    runs-on: ubuntu-latest\n    needs: [module-lane-integration]",
    )
    for marker in required_sequence_markers:
        if marker not in text:
            details["issues"].append(f"missing_sequence:{marker}")
    if "needs.module-lane-unit.result" not in text:
        details["issues"].append("gate_job_result_check_missing")
    if "needs.module-lane-database.result" not in text:
        details["issues"].append("gate_job_database_result_check_missing")
    if "needs.module-lane-api.result" not in text:
        details["issues"].append("gate_job_api_result_check_missing")
    if "needs.module-lane-contract.result" not in text:
        details["issues"].append("gate_job_contract_result_check_missing")
    if "needs.module-lane-integration.result" not in text:
        details["issues"].append("gate_job_integration_result_check_missing")
    if "needs.module-lane-e2e.result" not in text:
        details["issues"].append("gate_job_e2e_result_check_missing")
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
