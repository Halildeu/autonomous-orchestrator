#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"invalid_json_root:{path}")
    return obj


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--source-type", default="manual")
    parser.add_argument("--source-ref", action="append", default=[])
    parser.add_argument("--business-goal", required=True)
    parser.add_argument("--requested-outcome", required=True)
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--change-glob", action="append", default=[])
    parser.add_argument("--affected-module", action="append", default=[])
    parser.add_argument("--ux-mode", default="NOT_APPLICABLE")
    parser.add_argument("--ux-rationale", default="No frontend scoped change.")
    parser.add_argument(
        "--ux-artifact",
        action="append",
        default=[],
        help="Format: <path_glob>:<ux_theme_id>:<ux_subtheme_id>",
    )
    parser.add_argument("--db-migration-required", default="false")
    parser.add_argument("--acceptance", action="append", default=[])
    parser.add_argument("--evidence-path", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--status", default="DRAFT")
    parser.add_argument("--out", default="")
    return parser.parse_args(argv)


def _parse_bool(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    template_path = repo_root / "extensions/PRJ-PM-SUITE/contract/feature_execution_contract.v1.json"
    policy_path = repo_root / "policies/policy_feature_execution_bridge.v1.json"
    baseline_path = repo_root / "registry/technical_baseline.aistd.v1.json"

    template = _load_json(template_path)
    policy = _load_json(policy_path)
    baseline = _load_json(baseline_path)

    out_path_text = str(args.out).strip() or str(policy.get("contract_path") or "")
    if not out_path_text:
        raise SystemExit("contract_seed failed: contract_path missing in policy")
    out_path = Path(out_path_text)
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()

    scope_globs = (
        (policy.get("scope_detection") if isinstance(policy.get("scope_detection"), dict) else {}).get("scope_globs")
        if isinstance((policy.get("scope_detection") if isinstance(policy.get("scope_detection"), dict) else {}).get("scope_globs"), dict)
        else {}
    )
    selected_scopes = [str(item).strip() for item in args.scope if str(item).strip()]
    if not selected_scopes:
        selected_scopes = ["frontend"]
    change_globs = [str(item).strip() for item in args.change_glob if str(item).strip()]
    if not change_globs:
        for scope in selected_scopes:
            default_patterns = scope_globs.get(scope) if isinstance(scope_globs, dict) else None
            if isinstance(default_patterns, list) and default_patterns:
                change_globs.append(str(default_patterns[0]))
    if not change_globs:
        change_globs = ["web/**/*"]

    ux_artifacts: list[dict[str, str]] = []
    for raw in args.ux_artifact:
        text = str(raw).strip()
        if not text:
            continue
        try:
            path_glob, theme_id, subtheme_id = text.split(":", 2)
        except ValueError as exc:
            raise SystemExit(f"contract_seed failed: invalid --ux-artifact format: {text}") from exc
        ux_artifacts.append(
            {
                "path_glob": path_glob.strip(),
                "ux_theme_id": theme_id.strip(),
                "ux_subtheme_id": subtheme_id.strip(),
            }
        )

    ci_contract = baseline.get("ci_contract") if isinstance(baseline.get("ci_contract"), dict) else {}
    contract = template
    contract["status"] = str(args.status).strip() or "DRAFT"
    contract["feature_id"] = str(args.feature_id).strip()
    contract["title"] = str(args.title).strip()
    contract["summary"] = str(args.summary).strip()
    contract["source_context"] = {
        "source_type": str(args.source_type).strip() or "manual",
        "source_refs": [str(item).strip() for item in args.source_ref if str(item).strip()] or ["manual:unspecified"],
        "business_goal": str(args.business_goal).strip(),
        "requested_outcome": str(args.requested_outcome).strip(),
    }
    contract["delivery_scope"] = {
        "repo_root": ".",
        "service_scopes": selected_scopes,
        "change_path_globs": change_globs,
        "affected_modules": [str(item).strip() for item in args.affected_module if str(item).strip()],
    }
    contract["ux_contract"] = {
        "mode": str(args.ux_mode).strip() or "NOT_APPLICABLE",
        "rationale": str(args.ux_rationale).strip() or "No UX rationale provided.",
        "artifacts": ux_artifacts,
    }
    contract["technical_contract"] = {
        "baseline_profile_id": str(baseline.get("profile_id") or "").strip(),
        "api_version_prefix": (
            str(
                ((baseline.get("baseline") if isinstance(baseline.get("baseline"), dict) else {}).get("api") or {}).get(
                    "version_prefix"
                )
                or "/api/v1"
            ).strip()
        ),
        "design_system_policy": "policies/policy_ui_design_system.v1.json",
        "db_migration_required": _parse_bool(str(args.db_migration_required)),
    }
    contract["lane_plan"] = {
        "execution_sequence": [str(item) for item in (ci_contract.get("delivery_sequence") or []) if str(item).strip()],
        "required_lanes": [str(item) for item in (ci_contract.get("required_lanes") or []) if str(item).strip()],
        "notes": [
            "Generated by seed_feature_execution_contract.py"
        ],
    }
    contract["definition_of_done"] = {
        "acceptance_criteria": [str(item).strip() for item in args.acceptance if str(item).strip()] or [str(args.summary).strip()],
        "evidence_paths": [str(item).strip() for item in args.evidence_path if str(item).strip()]
        or [".cache/reports/feature_execution_contract_check.v1.json"],
    }
    contract["notes"] = [str(item).strip() for item in args.note if str(item).strip()]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "out": str(out_path),
                "feature_id": contract["feature_id"],
                "service_scopes": contract["delivery_scope"]["service_scopes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
