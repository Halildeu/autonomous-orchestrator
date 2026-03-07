#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = "policies/policy_feature_execution_bridge.v1.json"
DEFAULT_OUT_PATH = ".cache/reports/feature_execution_contract_check.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"invalid_json_root:{path}")
    return obj


def _match_any(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _normalize_rel(path: str) -> str:
    norm = str(path or "").strip().replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _git_changed_files(repo_root: Path, base: str, head: str) -> list[str]:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            base,
            head,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git_diff_failed").strip())
    return sorted(
        {
            _normalize_rel(line)
            for line in (proc.stdout or "").splitlines()
            if _normalize_rel(line)
        }
    )


def _default_diff_refs(repo_root: Path) -> tuple[str, str]:
    try:
        left = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^1"],
            text=True,
            capture_output=True,
            check=False,
        )
        right = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^2"],
            text=True,
            capture_output=True,
            check=False,
        )
        if left.returncode == 0 and right.returncode == 0:
            base_parent = left.stdout.strip()
            pr_head_parent = right.stdout.strip()
            merge_base = subprocess.run(
                ["git", "-C", str(repo_root), "merge-base", base_parent, pr_head_parent],
                text=True,
                capture_output=True,
                check=False,
            )
            if merge_base.returncode == 0 and merge_base.stdout.strip():
                return merge_base.stdout.strip(), pr_head_parent
    except Exception:
        pass
    return "HEAD~1", "HEAD"


def _contains_placeholder(value: Any, tokens: list[str]) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return True
    for token in tokens:
        needle = str(token or "").strip().upper()
        if needle and needle in text:
            return True
    return False


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy-path", default=DEFAULT_POLICY_PATH)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--changed-files", default="", help="Comma separated file list.")
    parser.add_argument("--out", default=DEFAULT_OUT_PATH)
    return parser.parse_args(argv)


def _load_ux_index(lock_obj: dict[str, Any]) -> tuple[set[str], dict[str, set[str]]]:
    themes = lock_obj.get("themes") if isinstance(lock_obj.get("themes"), list) else []
    theme_ids: set[str] = set()
    subthemes_by_theme: dict[str, set[str]] = {}
    for item in themes:
        if not isinstance(item, dict):
            continue
        theme_id = str(item.get("theme_id") or "").strip()
        if not theme_id:
            continue
        theme_ids.add(theme_id)
        subthemes = item.get("subthemes") if isinstance(item.get("subthemes"), list) else []
        subthemes_by_theme[theme_id] = {
            str(sub).strip()
            for sub in subthemes
            if isinstance(sub, str) and str(sub).strip()
        }
    return theme_ids, subthemes_by_theme


def _append_missing(errors: list[str], prefix: str, payload: dict[str, Any], required_keys: tuple[str, ...]) -> None:
    for key in required_keys:
        if key not in payload:
            errors.append(f"{prefix}:missing_key:{key}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    policy_path = (repo_root / str(args.policy_path)).resolve()
    out_path = Path(str(args.out))
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()

    errors: list[str] = []
    warnings: list[str] = []

    if not policy_path.exists():
        report = {
            "version": "v1",
            "kind": "feature-execution-contract-check-report",
            "generated_at": _now_iso(),
            "status": "FAIL",
            "repo_root": str(repo_root),
            "policy_path": str(policy_path),
            "errors": [f"policy_missing:{policy_path.as_posix()}"],
            "warnings": [],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAIL", "error_code": "POLICY_MISSING", "out": str(out_path)}, ensure_ascii=False))
        return 2

    policy = _load_json(policy_path)
    enforcement_mode = str(policy.get("enforcement_mode") or "blocking").strip().lower()
    contract_path_rel = str(policy.get("contract_path") or "").strip()
    contract_schema_path_rel = str(policy.get("contract_schema_path") or "").strip()
    baseline_path_rel = str(policy.get("technical_baseline_path") or "").strip()
    ux_lock_path_rel = str(policy.get("ux_lock_path") or "").strip()

    contract_path = (repo_root / contract_path_rel).resolve() if contract_path_rel else Path("")
    contract_schema_path = (repo_root / contract_schema_path_rel).resolve() if contract_schema_path_rel else Path("")
    baseline_path = (repo_root / baseline_path_rel).resolve() if baseline_path_rel else Path("")
    ux_lock_path = (repo_root / ux_lock_path_rel).resolve() if ux_lock_path_rel else Path("")

    if not contract_path_rel:
        errors.append("policy:contract_path_missing")
    elif not contract_path.exists():
        errors.append(f"contract_missing:{contract_path_rel}")
    if not contract_schema_path_rel or not contract_schema_path.exists():
        errors.append(f"contract_schema_missing:{contract_schema_path_rel or 'unset'}")
    if not baseline_path_rel or not baseline_path.exists():
        errors.append(f"technical_baseline_missing:{baseline_path_rel or 'unset'}")
    if not ux_lock_path_rel or not ux_lock_path.exists():
        errors.append(f"ux_lock_missing:{ux_lock_path_rel or 'unset'}")

    scope_detection = policy.get("scope_detection") if isinstance(policy.get("scope_detection"), dict) else {}
    include_globs = [str(x).strip() for x in (scope_detection.get("include_globs") or []) if str(x).strip()]
    exclude_globs = [str(x).strip() for x in (scope_detection.get("exclude_globs") or []) if str(x).strip()]
    scope_globs = scope_detection.get("scope_globs") if isinstance(scope_detection.get("scope_globs"), dict) else {}
    ux_scope = policy.get("ux_scope") if isinstance(policy.get("ux_scope"), dict) else {}
    ux_required_globs = [str(x).strip() for x in (ux_scope.get("required_globs") or []) if str(x).strip()]
    validation = policy.get("validation") if isinstance(policy.get("validation"), dict) else {}
    placeholder_tokens = [str(x).strip() for x in (validation.get("placeholder_tokens") or []) if str(x).strip()]
    required_source_refs_min = int(validation.get("required_source_refs_min") or 1)
    active_status_on_scoped_change = bool(validation.get("active_status_on_scoped_change", True))
    require_sequence_from_lock = bool(validation.get("required_execution_sequence_from_lock", True))
    require_lanes_from_lock = bool(validation.get("required_lanes_from_lock", True))
    require_ux_on_frontend_changes = bool(ux_scope.get("require_ux_on_frontend_changes", True))

    changed_files: list[str] = []
    diff_base = str(args.base or "").strip()
    diff_head = str(args.head or "").strip()
    try:
        raw_changed = str(args.changed_files or "").strip()
        if raw_changed:
            changed_files = sorted(
                {
                    _normalize_rel(item)
                    for item in raw_changed.split(",")
                    if _normalize_rel(item)
                }
            )
        else:
            if not diff_base or not diff_head:
                diff_base, diff_head = _default_diff_refs(repo_root)
            changed_files = _git_changed_files(repo_root, diff_base, diff_head)
    except Exception as exc:
        errors.append(f"diff_collect_failed:{exc}")

    scoped_files = [
        path
        for path in changed_files
        if (not include_globs or _match_any(path, include_globs))
        and not (exclude_globs and _match_any(path, exclude_globs))
    ]
    ux_scoped_files = [path for path in scoped_files if _match_any(path, ux_required_globs)]

    detected_scopes: set[str] = set()
    for scope_name, patterns in scope_globs.items():
        if not isinstance(patterns, list):
            continue
        normalized_patterns = [str(item).strip() for item in patterns if isinstance(item, str) and str(item).strip()]
        if any(_match_any(path, normalized_patterns) for path in scoped_files):
            detected_scopes.add(str(scope_name))

    contract: dict[str, Any] = {}
    if contract_path_rel and contract_path.exists():
        try:
            contract = _load_json(contract_path)
        except Exception as exc:
            errors.append(f"contract_invalid_json:{exc}")

    baseline: dict[str, Any] = {}
    expected_profile_id = ""
    expected_sequence: list[str] = []
    expected_lanes: list[str] = []
    if baseline_path_rel and baseline_path.exists():
        try:
            baseline = _load_json(baseline_path)
            expected_profile_id = str(baseline.get("profile_id") or "").strip()
            ci_contract = baseline.get("ci_contract") if isinstance(baseline.get("ci_contract"), dict) else {}
            expected_sequence = [str(x) for x in (ci_contract.get("delivery_sequence") or []) if str(x).strip()]
            expected_lanes = [str(x) for x in (ci_contract.get("required_lanes") or []) if str(x).strip()]
        except Exception as exc:
            errors.append(f"technical_baseline_invalid_json:{exc}")

    ux_theme_ids: set[str] = set()
    ux_subthemes_by_theme: dict[str, set[str]] = {}
    if ux_lock_path_rel and ux_lock_path.exists():
        try:
            ux_lock = _load_json(ux_lock_path)
            ux_theme_ids, ux_subthemes_by_theme = _load_ux_index(ux_lock)
        except Exception as exc:
            errors.append(f"ux_lock_invalid_json:{exc}")

    contract_errors: list[str] = []
    contract_warnings: list[str] = []
    contract_change_globs: list[str] = []
    contract_service_scopes: list[str] = []
    artifact_globs: list[str] = []

    if scoped_files:
        if not contract:
            contract_errors.append("contract_required_for_scoped_changes")
        else:
            _append_missing(
                contract_errors,
                "contract",
                contract,
                (
                    "version",
                    "kind",
                    "status",
                    "feature_id",
                    "title",
                    "summary",
                    "source_context",
                    "delivery_scope",
                    "ux_contract",
                    "technical_contract",
                    "lane_plan",
                    "definition_of_done",
                    "notes",
                ),
            )

    if contract:
        if str(contract.get("version") or "") != "v1":
            contract_errors.append("contract:version_must_be_v1")
        if str(contract.get("kind") or "") != "feature-execution-contract":
            contract_errors.append("contract:kind_invalid")
        status = str(contract.get("status") or "").strip()
        if active_status_on_scoped_change and scoped_files and status != "ACTIVE":
            contract_errors.append("contract:status_must_be_ACTIVE_for_scoped_changes")

        for key in ("feature_id", "title", "summary"):
            value = str(contract.get(key) or "").strip()
            if not value:
                contract_errors.append(f"contract:{key}_missing")
            elif scoped_files and _contains_placeholder(value, placeholder_tokens):
                contract_errors.append(f"contract:{key}_contains_placeholder")

        source_context = contract.get("source_context") if isinstance(contract.get("source_context"), dict) else {}
        _append_missing(
            contract_errors,
            "source_context",
            source_context,
            ("source_type", "source_refs", "business_goal", "requested_outcome"),
        )
        source_refs = source_context.get("source_refs") if isinstance(source_context.get("source_refs"), list) else []
        if len(source_refs) < required_source_refs_min:
            contract_errors.append("source_context:source_refs_below_min")
        if scoped_files:
            for key in ("business_goal", "requested_outcome"):
                if _contains_placeholder(source_context.get(key), placeholder_tokens):
                    contract_errors.append(f"source_context:{key}_contains_placeholder")
            for idx, item in enumerate(source_refs):
                if _contains_placeholder(item, placeholder_tokens):
                    contract_errors.append(f"source_context:source_refs_contains_placeholder:{idx}")

        delivery_scope = contract.get("delivery_scope") if isinstance(contract.get("delivery_scope"), dict) else {}
        _append_missing(
            contract_errors,
            "delivery_scope",
            delivery_scope,
            ("repo_root", "service_scopes", "change_path_globs", "affected_modules"),
        )
        contract_service_scopes = [
            str(item).strip()
            for item in (delivery_scope.get("service_scopes") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        contract_change_globs = [
            str(item).strip()
            for item in (delivery_scope.get("change_path_globs") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        if scoped_files and not contract_service_scopes:
            contract_errors.append("delivery_scope:service_scopes_empty")
        if scoped_files and not contract_change_globs:
            contract_errors.append("delivery_scope:change_path_globs_empty")
        undeclared_scopes = sorted(detected_scopes - set(contract_service_scopes))
        if undeclared_scopes:
            contract_errors.append(f"delivery_scope:missing_detected_scopes:{','.join(undeclared_scopes)}")
        uncovered_files = [path for path in scoped_files if not _match_any(path, contract_change_globs)]
        if uncovered_files:
            contract_errors.extend([f"delivery_scope:uncovered_change:{path}" for path in uncovered_files])

        ux_contract = contract.get("ux_contract") if isinstance(contract.get("ux_contract"), dict) else {}
        _append_missing(contract_errors, "ux_contract", ux_contract, ("mode", "rationale", "artifacts"))
        ux_mode = str(ux_contract.get("mode") or "").strip()
        artifacts = ux_contract.get("artifacts") if isinstance(ux_contract.get("artifacts"), list) else []
        artifact_entries: list[dict[str, str]] = []
        for idx, item in enumerate(artifacts):
            if not isinstance(item, dict):
                contract_errors.append(f"ux_contract:artifact_not_object:{idx}")
                continue
            path_glob = str(item.get("path_glob") or "").strip()
            theme_id = str(item.get("ux_theme_id") or "").strip()
            subtheme_id = str(item.get("ux_subtheme_id") or "").strip()
            if not path_glob or not theme_id or not subtheme_id:
                contract_errors.append(f"ux_contract:artifact_missing_fields:{idx}")
                continue
            artifact_entries.append(
                {
                    "path_glob": path_glob,
                    "ux_theme_id": theme_id,
                    "ux_subtheme_id": subtheme_id,
                }
            )
            artifact_globs.append(path_glob)
            if ux_theme_ids and theme_id not in ux_theme_ids:
                contract_errors.append(f"ux_contract:invalid_theme_id:{theme_id}")
            elif ux_subthemes_by_theme and subtheme_id not in ux_subthemes_by_theme.get(theme_id, set()):
                contract_errors.append(f"ux_contract:invalid_subtheme_id:{theme_id}:{subtheme_id}")
        if require_ux_on_frontend_changes and ux_scoped_files:
            if ux_mode != "REQUIRED":
                contract_errors.append("ux_contract:mode_must_be_REQUIRED_for_frontend_changes")
            missing_ux_coverage = [path for path in ux_scoped_files if not _match_any(path, artifact_globs)]
            if missing_ux_coverage:
                contract_errors.extend([f"ux_contract:uncovered_ui_change:{path}" for path in missing_ux_coverage])
        if not ux_scoped_files and ux_mode == "NOT_APPLICABLE" and _contains_placeholder(
            ux_contract.get("rationale"), placeholder_tokens
        ):
            contract_errors.append("ux_contract:rationale_contains_placeholder")
        if ux_scoped_files and _contains_placeholder(ux_contract.get("rationale"), placeholder_tokens):
            contract_errors.append("ux_contract:rationale_contains_placeholder")

        technical_contract = (
            contract.get("technical_contract") if isinstance(contract.get("technical_contract"), dict) else {}
        )
        _append_missing(
            contract_errors,
            "technical_contract",
            technical_contract,
            ("baseline_profile_id", "api_version_prefix", "design_system_policy", "db_migration_required"),
        )
        if expected_profile_id and str(technical_contract.get("baseline_profile_id") or "").strip() != expected_profile_id:
            contract_errors.append("technical_contract:baseline_profile_id_mismatch")
        if str(technical_contract.get("api_version_prefix") or "").strip() != "/api/v1":
            contract_errors.append("technical_contract:api_version_prefix_invalid")
        if (
            str(technical_contract.get("design_system_policy") or "").strip()
            != "policies/policy_ui_design_system.v1.json"
        ):
            contract_errors.append("technical_contract:design_system_policy_invalid")
        if not isinstance(technical_contract.get("db_migration_required"), bool):
            contract_errors.append("technical_contract:db_migration_required_must_be_boolean")

        lane_plan = contract.get("lane_plan") if isinstance(contract.get("lane_plan"), dict) else {}
        _append_missing(contract_errors, "lane_plan", lane_plan, ("execution_sequence", "required_lanes", "notes"))
        actual_sequence = [
            str(item).strip()
            for item in (lane_plan.get("execution_sequence") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        actual_lanes = [
            str(item).strip()
            for item in (lane_plan.get("required_lanes") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        if require_sequence_from_lock and expected_sequence and actual_sequence != expected_sequence:
            contract_errors.append("lane_plan:execution_sequence_mismatch")
        if require_lanes_from_lock and expected_lanes and actual_lanes != expected_lanes:
            contract_errors.append("lane_plan:required_lanes_mismatch")

        definition_of_done = (
            contract.get("definition_of_done") if isinstance(contract.get("definition_of_done"), dict) else {}
        )
        _append_missing(
            contract_errors,
            "definition_of_done",
            definition_of_done,
            ("acceptance_criteria", "evidence_paths"),
        )
        acceptance_criteria = (
            definition_of_done.get("acceptance_criteria")
            if isinstance(definition_of_done.get("acceptance_criteria"), list)
            else []
        )
        evidence_paths = (
            definition_of_done.get("evidence_paths")
            if isinstance(definition_of_done.get("evidence_paths"), list)
            else []
        )
        if not acceptance_criteria:
            contract_errors.append("definition_of_done:acceptance_criteria_empty")
        if not evidence_paths:
            contract_errors.append("definition_of_done:evidence_paths_empty")
        if scoped_files:
            for idx, item in enumerate(acceptance_criteria):
                if _contains_placeholder(item, placeholder_tokens):
                    contract_errors.append(f"definition_of_done:acceptance_contains_placeholder:{idx}")

    errors.extend(contract_errors)
    warnings.extend(contract_warnings)

    status = "OK"
    if errors:
        status = "FAIL" if enforcement_mode == "blocking" else "WARN"

    report = {
        "version": "v1",
        "kind": "feature-execution-contract-check-report",
        "generated_at": _now_iso(),
        "status": status,
        "enforcement_mode": enforcement_mode,
        "repo_root": str(repo_root),
        "policy_path": str(policy_path.relative_to(repo_root)),
        "contract_path": contract_path_rel,
        "contract_schema_path": contract_schema_path_rel,
        "technical_baseline_path": baseline_path_rel,
        "ux_lock_path": ux_lock_path_rel,
        "diff": {
            "base": diff_base,
            "head": diff_head,
            "changed_files_count": len(changed_files),
            "scoped_changed_files_count": len(scoped_files),
            "scoped_changed_files": scoped_files,
        },
        "scope_detection": {
            "detected_scopes": sorted(detected_scopes),
            "ux_scoped_changed_files_count": len(ux_scoped_files),
            "ux_scoped_changed_files": ux_scoped_files,
        },
        "contract_summary": {
            "service_scopes": contract_service_scopes,
            "change_path_globs": contract_change_globs,
            "artifact_globs": artifact_globs,
            "expected_profile_id": expected_profile_id,
            "expected_execution_sequence": expected_sequence,
            "expected_required_lanes": expected_lanes,
        },
        "errors": errors,
        "warnings": warnings,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "enforcement_mode": enforcement_mode,
                "scoped_changed_files_count": len(scoped_files),
                "detected_scopes": sorted(detected_scopes),
                "errors": len(errors),
                "warnings": len(warnings),
                "out": str(out_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if status == "FAIL" and enforcement_mode == "blocking":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
