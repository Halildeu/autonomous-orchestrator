#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"invalid_json_root:{path}")
    return obj


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract-path", default="")
    parser.add_argument("--out", default="")
    return parser.parse_args(argv)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _phase_default_globs(phase: str) -> list[str]:
    defaults = {
        "backend": ["backend/**", "services/**"],
        "database": ["db/**", "database/**", "sql/**", "backend/**/migration/**"],
        "api": ["api/**", "backend/**/controller/**", "backend/**/dto/**", "docs/03-delivery/api/**"],
        "frontend": ["web/**", "frontend/**", "mobile/**", "apps/**", "ui/**"],
        "integration": ["backend/**", "web/**", "api/**", "docs/03-delivery/api/**"],
        "e2e": ["backend/**", "web/**", "api/**", "docs/03-delivery/api/**"],
    }
    return list(defaults.get(phase, ["**"]))


def _phase_related_globs(phase: str, contract_globs: list[str]) -> list[str]:
    phase_prefixes = {
        "backend": ("backend/", "services/", "extensions/"),
        "database": ("db/", "database/", "sql/", "backend/"),
        "api": ("api/", "backend/", "docs/03-delivery/api/"),
        "frontend": ("web/", "frontend/", "mobile/", "apps/", "ui/", "extensions/"),
        "integration": tuple(),
        "e2e": tuple(),
    }
    prefixes = phase_prefixes.get(phase, tuple())
    matched = [item for item in contract_globs if item.startswith(prefixes)]
    return matched or _phase_default_globs(phase)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()

    pm_policy_path = repo_root / "policies/policy_pm_suite.v1.json"
    pm_policy = _load_json(pm_policy_path)
    delivery_session = pm_policy.get("delivery_session") if isinstance(pm_policy.get("delivery_session"), dict) else {}
    execution_bridge = pm_policy.get("execution_bridge") if isinstance(pm_policy.get("execution_bridge"), dict) else {}

    contract_rel = str(args.contract_path).strip() or str(execution_bridge.get("contract_path") or "")
    if not contract_rel:
        raise SystemExit("delivery_session_build failed: contract path missing")
    contract_path = Path(contract_rel)
    if not contract_path.is_absolute():
        contract_path = (repo_root / contract_path).resolve()
    contract = _load_json(contract_path)

    standards_lock = _load_json(repo_root / "standards.lock")
    baseline = _load_json(repo_root / "registry/technical_baseline.aistd.v1.json")
    lane_cfg = _load_json(repo_root / "ci/module_delivery_lanes.v1.json")

    out_text = str(args.out).strip() or str(delivery_session.get("packet_path") or "")
    if not out_text:
        raise SystemExit("delivery_session_build failed: packet path missing")
    out_path = Path(out_text)
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()

    delivery_scope = contract.get("delivery_scope") if isinstance(contract.get("delivery_scope"), dict) else {}
    ux_contract = contract.get("ux_contract") if isinstance(contract.get("ux_contract"), dict) else {}
    lane_plan = contract.get("lane_plan") if isinstance(contract.get("lane_plan"), dict) else {}
    definition_of_done = (
        contract.get("definition_of_done") if isinstance(contract.get("definition_of_done"), dict) else {}
    )
    module_delivery_contract = (
        standards_lock.get("module_delivery_contract")
        if isinstance(standards_lock.get("module_delivery_contract"), dict)
        else {}
    )
    scope_lane_map = (
        module_delivery_contract.get("scope_lane_map")
        if isinstance(module_delivery_contract.get("scope_lane_map"), dict)
        else {}
    )
    service_scopes = _unique(
        [str(item) for item in (delivery_scope.get("service_scopes") or []) if isinstance(item, str)]
    )
    contract_globs = _unique(
        [str(item) for item in (delivery_scope.get("change_path_globs") or []) if isinstance(item, str)]
    )
    execution_sequence = _unique(
        [str(item) for item in (lane_plan.get("execution_sequence") or []) if isinstance(item, str)]
    )

    active_lanes: list[str] = []
    for scope in service_scopes:
        lane = str(scope_lane_map.get(scope) or "").strip()
        if lane:
            active_lanes.append(lane)
    active_lanes.extend(["integration", "e2e"])
    active_lanes = _unique(active_lanes)

    lane_commands_src = lane_cfg.get("lanes") if isinstance(lane_cfg.get("lanes"), dict) else {}
    lane_commands: dict[str, str] = {}
    for lane in active_lanes:
        lane_obj = lane_commands_src.get(lane) if isinstance(lane_commands_src.get(lane), dict) else {}
        lane_commands[lane] = str(lane_obj.get("command") or "").strip()

    phase_to_lane = {
        "backend": "unit",
        "database": "database",
        "api": "api",
        "frontend": "contract",
        "integration": "integration",
        "e2e": "e2e",
    }
    active_phases = _unique(service_scopes + ["integration", "e2e"])
    write_plan: list[dict[str, Any]] = []
    for phase in execution_sequence:
        if phase not in active_phases:
            continue
        lane = phase_to_lane.get(phase)
        if not lane:
            continue
        write_plan.append(
            {
                "phase": phase,
                "lane": lane,
                "write_globs": _phase_related_globs(phase, contract_globs),
                "read_paths": _unique(
                    [
                        str(contract_path.relative_to(repo_root).as_posix()),
                        "standards.lock",
                        "registry/technical_baseline.aistd.v1.json",
                        "ci/module_delivery_lanes.v1.json",
                        "policies/policy_feature_execution_bridge.v1.json",
                        "policies/policy_ui_design_system.v1.json",
                        "extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json",
                        "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
                    ]
                ),
                "command": lane_commands.get(lane) or "",
                "notes": [
                    f"Do not move to the next phase before the {lane} lane is locally green.",
                    "If a file outside write_globs is needed, rebuild the delivery session packet first.",
                ],
            }
        )

    allowed_write_paths = _unique(
        contract_globs
        + [
            str(contract_path.relative_to(repo_root).as_posix()),
            "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
        ]
    )
    required_read_paths = _unique(
        [
            str(contract_path.relative_to(repo_root).as_posix()),
            "standards.lock",
            "registry/technical_baseline.aistd.v1.json",
            "policies/policy_feature_execution_bridge.v1.json",
            "policies/policy_ui_design_system.v1.json",
            "ci/module_delivery_lanes.v1.json",
            "extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json",
            "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
        ]
    )

    report_path = str(delivery_session.get("guard_report_path") or ".cache/reports/delivery_session_guard.v1.json")
    packet = {
        "version": "v1",
        "kind": "delivery-session-packet",
        "generated_at": _now_iso(),
        "repo_root": str(repo_root),
        "source_contract_path": str(contract_path.relative_to(repo_root).as_posix()),
        "feature_id": str(contract.get("feature_id") or "").strip(),
        "title": str(contract.get("title") or "").strip(),
        "active_scopes": service_scopes,
        "affected_modules": _unique(
            [str(item) for item in (delivery_scope.get("affected_modules") or []) if isinstance(item, str)]
        ),
        "allowed_write_paths": allowed_write_paths,
        "required_read_paths": required_read_paths,
        "lane_plan": {
            "execution_sequence": execution_sequence,
            "active_lanes": active_lanes,
            "lane_commands": lane_commands,
        },
        "write_plan": write_plan,
        "ux_context": {
            "mode": str(ux_contract.get("mode") or "NOT_APPLICABLE"),
            "artifact_count": len(ux_contract.get("artifacts") or []),
            "change_map_path": "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
            "artifacts": ux_contract.get("artifacts") if isinstance(ux_contract.get("artifacts"), list) else [],
        },
        "stop_conditions": [
            "scope_expansion_requires_packet_rebuild",
            "frontend_without_ux_mapping_blocked",
            "lane_failure_blocks_next_lane",
            "write_outside_allowed_paths_blocked",
        ],
        "evidence_targets": _unique(
            [str(item) for item in (definition_of_done.get("evidence_paths") or []) if isinstance(item, str)] + [report_path]
        ),
        "notes": [
            str(delivery_session.get("note") or "delivery_session_compiler_active"),
            f"baseline_profile={baseline.get('profile_id')}",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "out": str(out_path),
                "feature_id": packet["feature_id"],
                "active_scopes": packet["active_scopes"],
                "active_lanes": packet["lane_plan"]["active_lanes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
