from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"north_star_subject_plan_contract_test failed: {message}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_registry(ws: Path) -> tuple[str, list[str], list[tuple[str, str]]]:
    subject_id = "ai_ile_yazilim_gelistirirken_baglam_yonetimi"
    registry_obj = {
        "version": "v1",
        "generated_at": "2026-03-02T00:00:00Z",
        "source": "contract_test",
        "subjects": [
            {
                "subject_id": subject_id,
                "subject_title_tr": "AI ile yazilim gelistirirken baglam yonetimi",
                "subject_title_en": "Context Management for AI Software Development",
                "themes": [
                    {
                        "theme_id": "context_capture",
                        "title_tr": "Baglam Yakalama",
                        "title_en": "Context Capture",
                        "subthemes": [
                            {"subtheme_id": "request_intake", "title_tr": "Talep Alimi", "title_en": "Request Intake"},
                            {
                                "subtheme_id": "acceptance_scope",
                                "title_tr": "Kapsam Onayi",
                                "title_en": "Acceptance Scope",
                            },
                        ],
                    },
                    {
                        "theme_id": "memory_strategy",
                        "title_tr": "Hafiza Stratejisi",
                        "title_en": "Memory Strategy",
                        "subthemes": [
                            {
                                "subtheme_id": "session_memory",
                                "title_tr": "Oturum Hafizasi",
                                "title_en": "Session Memory",
                            },
                            {
                                "subtheme_id": "long_term_memory",
                                "title_tr": "Uzun Donem Hafiza",
                                "title_en": "Long Term Memory",
                            },
                        ],
                    },
                    {
                        "theme_id": "execution_control",
                        "title_tr": "Yurutme Kontrolu",
                        "title_en": "Execution Control",
                        "subthemes": [
                            {
                                "subtheme_id": "approval_gate",
                                "title_tr": "Onay Kapisi",
                                "title_en": "Approval Gate",
                            },
                            {
                                "subtheme_id": "context_sync",
                                "title_tr": "Baglam Senkronu",
                                "title_en": "Context Sync",
                            },
                        ],
                    },
                    {
                        "theme_id": "delivery_quality",
                        "title_tr": "Teslimat Kalitesi",
                        "title_en": "Delivery Quality",
                        "subthemes": [
                            {
                                "subtheme_id": "quality_metrics",
                                "title_tr": "Kalite Metrikleri",
                                "title_en": "Quality Metrics",
                            }
                        ],
                    },
                ],
            },
            {
                "subject_id": "dummy_subject",
                "subject_title_tr": "Dummy Subject",
                "themes": [],
            },
        ],
    }

    expected_theme_ids = ["context_capture", "memory_strategy", "execution_control", "delivery_quality"]
    expected_pairs = [
        ("context_capture", "request_intake"),
        ("context_capture", "acceptance_scope"),
        ("memory_strategy", "session_memory"),
        ("memory_strategy", "long_term_memory"),
        ("execution_control", "approval_gate"),
        ("execution_control", "context_sync"),
        ("delivery_quality", "quality_metrics"),
    ]

    registry_path = ws / ".cache" / "index" / "mechanisms.registry.v1.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return subject_id, expected_theme_ids, expected_pairs


def _seed_workspace_policy(ws: Path) -> None:
    policy_obj = {
        "version": "v1",
        "synthesis": {
            "mode": "holistic_module_pack.v1",
            "stopwords": [
                "ve",
                "ile",
                "icin",
                "the",
                "and",
                "module",
                "theme",
                "subtheme",
            ],
            "module_blueprints": [
                {
                    "module_id": "scope_bundle_custom",
                    "title_tr": "Kapsam Paketi",
                    "title_en": "Scope Bundle",
                    "module_kind": "intake_scope",
                    "keywords": ["request", "intake", "talep", "scope", "kapsam", "acceptance"],
                    "flow": {
                        "inputs": ["request_text", "acceptance_criteria"],
                        "process": ["intake_parse", "scope_align"],
                        "outputs": ["scope_contract"],
                    },
                },
                {
                    "module_id": "memory_control_custom",
                    "title_tr": "Hafiza ve Kontrol Paketi",
                    "title_en": "Memory and Control Bundle",
                    "module_kind": "context_memory",
                    "keywords": ["memory", "hafiza", "session", "long", "context", "sync", "execution"],
                    "flow": {
                        "inputs": ["session_events", "context_snapshot"],
                        "process": ["memory_link", "context_sync"],
                        "outputs": ["resume_checkpoint"],
                    },
                },
                {
                    "module_id": "execution_quality_custom",
                    "title_tr": "Yurutme ve Kalite Paketi",
                    "title_en": "Execution and Quality Bundle",
                    "module_kind": "execution_quality",
                    "keywords": ["approval", "gate", "control", "quality", "metrics"],
                    "flow": {
                        "inputs": ["approved_scope", "execution_trace"],
                        "process": ["gate_run", "quality_verify"],
                        "outputs": ["quality_gate_status"],
                    },
                },
                {
                    "module_id": "general_delivery_backlog",
                    "title_tr": "Genel Teslimat",
                    "title_en": "General Delivery",
                    "module_kind": "general_delivery",
                    "keywords": [],
                    "flow": {
                        "inputs": ["subject_catalog"],
                        "process": ["backlog_prepare"],
                        "outputs": ["delivery_backlog"],
                    },
                },
            ],
        },
        "quality_gate": {
            "enforce": True,
            "max_module_count": 4,
            "min_coverage_quality": 0.95,
            "require_full_coverage": True,
            "scoring_weights": {
                "pair_weight": 0.6,
                "theme_weight": 0.3,
                "completeness_weight": 0.1,
            },
        },
        "limits": {
            "max_steps": 16,
            "max_plan_bytes": 131072,
            "plan_bytes_over_limit_action": "warn",
        },
    }
    policy_path = ws / "policies" / "policy_north_star_subject_plan.v1.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _seed_quality_override_fail(ws: Path) -> None:
    override_obj = {
        "quality_gate": {
            "enforce": True,
            "max_module_count": 2,
            "min_coverage_quality": 0.95,
            "require_full_coverage": True,
            "scoring_weights": {
                "pair_weight": 0.6,
                "theme_weight": 0.3,
                "completeness_weight": 0.1,
            },
        }
    }
    override_path = ws / ".cache" / "policy_overrides" / "policy_north_star_subject_plan.override.v1.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(override_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _seed_plan_bytes_override_fail(ws: Path) -> None:
    override_obj = {
        "limits": {
            "max_plan_bytes": 4096,
            "plan_bytes_over_limit_action": "fail",
        }
    }
    override_path = ws / ".cache" / "policy_overrides" / "policy_north_star_subject_plan.override.v1.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(override_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_planner.north_star_subject_plan import run_north_star_subject_to_plan

    ws = repo_root / ".cache" / "ws_north_star_subject_plan_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    subject_id, expected_theme_ids, expected_pairs = _seed_registry(ws)
    _seed_workspace_policy(ws)

    pass_payload = run_north_star_subject_to_plan(workspace_root=ws, subject_id=subject_id, mode="plan_first", out="latest")
    _must(pass_payload.get("status") == "OK", "pass run status must be OK")
    _must(pass_payload.get("quality_gate_status") == "PASS", "pass run quality_gate_status must be PASS")
    _must(pass_payload.get("contract_validation_status") == "PASS", "pass run contract_validation_status must be PASS")
    _must(pass_payload.get("coverage_complete") is True, "pass run coverage must be complete")
    pass_notes = pass_payload.get("notes") if isinstance(pass_payload.get("notes"), list) else []
    _must(any("contract_validation=pass" == str(item) for item in pass_notes), "contract pass note missing")

    plan_rel = str(pass_payload.get("plan_path") or "")
    summary_rel = str(pass_payload.get("summary_path") or "")
    _must(bool(plan_rel), "plan_path missing")
    _must(bool(summary_rel), "summary_path missing")

    plan_path = ws / plan_rel
    summary_path = ws / summary_rel
    _must(plan_path.exists(), "plan file missing")
    _must(summary_path.exists(), "summary file missing")

    plan_obj = _load_json(plan_path)
    required_top = [
        "version",
        "plan_id",
        "created_at",
        "scope",
        "inputs",
        "decision",
        "steps",
        "modules",
        "evidence_paths",
        "notes",
    ]
    for field in required_top:
        _must(field in plan_obj, f"missing top-level field: {field}")

    scope = plan_obj.get("scope") if isinstance(plan_obj.get("scope"), dict) else {}
    _must(scope.get("subject_id") == subject_id, "scope.subject_id mismatch")
    _must(scope.get("synthesis_mode") == "holistic_module_pack.v1", "scope.synthesis_mode mismatch")

    decision = plan_obj.get("decision") if isinstance(plan_obj.get("decision"), dict) else {}
    _must(decision.get("selected_subject_id") == subject_id, "selected_subject_id mismatch")
    _must(decision.get("selected_theme_ids") == expected_theme_ids, "selected_theme_ids mismatch")
    _must(decision.get("selected_subtheme_ids") == [sub for _, sub in expected_pairs], "selected_subtheme_ids mismatch")

    selected_pairs = decision.get("selected_theme_subtheme_pairs")
    _must(isinstance(selected_pairs, list), "selected_theme_subtheme_pairs must be list")
    selected_pair_tuples = [
        (str(item.get("theme_id") or ""), str(item.get("subtheme_id") or ""))
        for item in selected_pairs
        if isinstance(item, dict)
    ]
    _must(selected_pair_tuples == expected_pairs, "selected theme/subtheme pairs mismatch")

    coverage = decision.get("coverage") if isinstance(decision.get("coverage"), dict) else {}
    _must(coverage.get("is_complete") is True, "coverage must be complete")
    _must(coverage.get("uncovered_theme_ids") == [], "uncovered_theme_ids must be empty")
    _must(coverage.get("uncovered_theme_subtheme_pairs") == [], "uncovered pairs must be empty")
    _must(float(coverage.get("coverage_quality_score") or 0.0) >= 0.95, "coverage_quality_score below threshold")

    quality_gate = decision.get("quality_gate") if isinstance(decision.get("quality_gate"), dict) else {}
    _must(quality_gate.get("status") == "PASS", "quality gate status must be PASS")
    thresholds = quality_gate.get("thresholds") if isinstance(quality_gate.get("thresholds"), dict) else {}
    _must(int(thresholds.get("max_module_count") or 0) == 4, "quality gate max_module_count mismatch")
    _must(float(thresholds.get("min_coverage_quality") or 0) == 0.95, "quality gate min_coverage_quality mismatch")
    scoring = thresholds.get("scoring_weights") if isinstance(thresholds.get("scoring_weights"), dict) else {}
    _must(float(scoring.get("pair_weight") or 0.0) == 0.6, "quality gate scoring pair_weight mismatch")
    _must(float(scoring.get("theme_weight") or 0.0) == 0.3, "quality gate scoring theme_weight mismatch")
    _must(float(scoring.get("completeness_weight") or 0.0) == 0.1, "quality gate scoring completeness_weight mismatch")

    modules = plan_obj.get("modules") if isinstance(plan_obj.get("modules"), list) else []
    module_ids = [str(item.get("module_id") or "") for item in modules if isinstance(item, dict)]
    _must("scope_bundle_custom" in module_ids, "policy module id scope_bundle_custom missing")
    _must("memory_control_custom" in module_ids, "policy module id memory_control_custom missing")
    _must("execution_quality_custom" in module_ids, "policy module id execution_quality_custom missing")
    _must(len(modules) <= 4, "module_count must obey policy max")
    _must(len(modules) < len(expected_theme_ids) + len(expected_pairs), "modules should be consolidated")

    steps = plan_obj.get("steps") if isinstance(plan_obj.get("steps"), list) else []
    _must(len(steps) == 1 + len(modules), "steps must be module-driven")

    step_schema = _load_json(repo_root / "schemas" / "planner-step.schema.v1.json")
    step_validator = Draft202012Validator(step_schema)
    for step in steps:
        step_validator.validate(step)

    policy_schema = _load_json(repo_root / "schemas" / "policy-north-star-subject-plan.schema.v1.json")
    policy_validator = Draft202012Validator(policy_schema)
    policy_obj = _load_json(ws / "policies" / "policy_north_star_subject_plan.v1.json")
    policy_validator.validate(policy_obj)

    summary_text = summary_path.read_text(encoding="utf-8")
    _must("Quality Gate" in summary_text, "summary quality gate section missing")
    _must("status: PASS" in summary_text, "summary pass status missing")
    _must("Module Plan" in summary_text, "summary module plan section missing")
    _must("Coverage" in summary_text, "summary coverage section missing")

    _seed_quality_override_fail(ws)
    fail_payload = run_north_star_subject_to_plan(
        workspace_root=ws,
        subject_id=subject_id,
        mode="plan_first",
        out="strict_threshold_run",
    )
    _must(fail_payload.get("status") == "WARN", "strict threshold run must be WARN")
    _must(fail_payload.get("error_code") == "QUALITY_BAR_NOT_MET", "strict threshold error_code mismatch")
    _must(fail_payload.get("quality_gate_status") == "FAIL", "strict threshold quality gate must FAIL")
    _must(fail_payload.get("contract_validation_status") == "PASS", "strict threshold contract_validation_status must be PASS")

    fail_plan_path = ws / str(fail_payload.get("plan_path") or "")
    _must(fail_plan_path.exists(), "strict threshold plan file missing")
    fail_plan_obj = _load_json(fail_plan_path)
    fail_decision = fail_plan_obj.get("decision") if isinstance(fail_plan_obj.get("decision"), dict) else {}
    fail_gate = fail_decision.get("quality_gate") if isinstance(fail_decision.get("quality_gate"), dict) else {}
    fail_thresholds = fail_gate.get("thresholds") if isinstance(fail_gate.get("thresholds"), dict) else {}
    _must(int(fail_thresholds.get("max_module_count") or 0) == 2, "override max_module_count not applied")
    reasons = fail_gate.get("reasons") if isinstance(fail_gate.get("reasons"), list) else []
    _must(any("module_count_exceeded" in str(item) for item in reasons), "override fail reason missing")

    _seed_plan_bytes_override_fail(ws)
    bytes_fail_payload = run_north_star_subject_to_plan(
        workspace_root=ws,
        subject_id=subject_id,
        mode="plan_first",
        out="bytes_limit_fail_run",
    )
    _must(bytes_fail_payload.get("status") == "WARN", "bytes fail run must be WARN")
    _must(bytes_fail_payload.get("error_code") == "PLAN_BYTES_OVER_LIMIT", "bytes fail run error_code mismatch")
    _must(
        bytes_fail_payload.get("contract_validation_status") == "PASS",
        "bytes fail run contract_validation_status must be PASS",
    )
    _must(str(bytes_fail_payload.get("plan_path") or "") == "", "bytes fail run should not write plan file")
    bytes_fail_notes = bytes_fail_payload.get("notes") if isinstance(bytes_fail_payload.get("notes"), list) else []
    _must(
        any(str(item) == "plan_bytes_over_limit" for item in bytes_fail_notes),
        "bytes fail run plan_bytes_over_limit note missing",
    )
    _must(
        any(str(item) == "plan_bytes_over_limit_action=fail" for item in bytes_fail_notes),
        "bytes fail run plan_bytes_over_limit_action note missing",
    )

    missing_payload = run_north_star_subject_to_plan(
        workspace_root=ws,
        subject_id="olmayan_subject",
        mode="plan_first",
        out="latest",
    )
    _must(missing_payload.get("status") == "IDLE", "missing subject status must be IDLE")
    _must(missing_payload.get("error_code") == "SUBJECT_NOT_FOUND", "missing subject error mismatch")

    print(
        json.dumps(
            {
                "status": "OK",
                "pass_plan_id": pass_payload.get("plan_id"),
                "fail_plan_id": fail_payload.get("plan_id"),
                "module_count": pass_payload.get("module_count"),
                "coverage_quality_score": pass_payload.get("coverage_quality_score"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
