from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"north_star_subject_plan_profile_run_contract_test failed: {message}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_registry(ws: Path) -> str:
    subject_id = "ai_ile_yazilim_projesi_yonetimi"
    registry_obj = {
        "version": "v1",
        "generated_at": "2026-03-02T00:00:00Z",
        "source": "contract_test",
        "subjects": [
            {
                "subject_id": subject_id,
                "subject_title_tr": "AI ile yazilim projesi yonetimi",
                "subject_title_en": "AI software project management",
                "themes": [
                    {
                        "theme_id": "planlama",
                        "title_tr": "Planlama",
                        "title_en": "Planning",
                        "subthemes": [
                            {"subtheme_id": "intake", "title_tr": "Intake", "title_en": "Intake"},
                            {"subtheme_id": "roadmap", "title_tr": "Roadmap", "title_en": "Roadmap"},
                        ],
                    },
                    {
                        "theme_id": "yurutme",
                        "title_tr": "Yurutme",
                        "title_en": "Execution",
                        "subthemes": [
                            {"subtheme_id": "dispatch", "title_tr": "Dispatch", "title_en": "Dispatch"},
                            {"subtheme_id": "apply", "title_tr": "Apply", "title_en": "Apply"},
                        ],
                    },
                ],
            }
        ],
    }
    path = ws / ".cache" / "index" / "mechanisms.registry.v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return subject_id


def _seed_policy(ws: Path) -> None:
    policy_obj = {
        "version": "v1",
        "synthesis": {
            "mode": "holistic_module_pack.v1",
            "stopwords": ["ve", "ile", "icin", "the", "and", "module", "theme", "subtheme"],
            "module_blueprints": [
                {
                    "module_id": "planning_bundle",
                    "title_tr": "Planlama Paketi",
                    "title_en": "Planning Bundle",
                    "module_kind": "planning",
                    "keywords": ["plan", "planlama", "intake", "roadmap"],
                    "flow": {
                        "inputs": ["request_text", "constraints"],
                        "process": ["scope_alignment", "roadmap_sync"],
                        "outputs": ["plan_scope"],
                    },
                },
                {
                    "module_id": "execution_bundle",
                    "title_tr": "Yurutme Paketi",
                    "title_en": "Execution Bundle",
                    "module_kind": "execution",
                    "keywords": ["dispatch", "apply", "execution", "yurutme"],
                    "flow": {
                        "inputs": ["approved_scope", "policy_state"],
                        "process": ["dispatch", "apply"],
                        "outputs": ["execution_trace"],
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
            "max_module_count": 6,
            "min_coverage_quality": 0.70,
            "require_full_coverage": True,
            "preferred_profile_order": ["C", "B", "A"],
            "scoring_weights": {
                "pair_weight": 0.55,
                "theme_weight": 0.35,
                "completeness_weight": 0.10,
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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_planner.north_star_subject_plan_profile_run import run_north_star_subject_plan_profile_run

    ws = repo_root / ".cache" / "ws_north_star_subject_plan_profile_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    subject_id = _seed_registry(ws)
    _seed_policy(ws)

    payload = run_north_star_subject_plan_profile_run(
        workspace_root=ws,
        subject_id=subject_id,
        profile="C",
        run_set="abc",
        mode="plan_first",
        out="latest",
        persist_profile=False,
    )
    _must(payload.get("status") in {"OK", "WARN"}, "abc run status must be OK/WARN")
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
    available = comparison.get("available_profiles") if isinstance(comparison.get("available_profiles"), list) else []
    _must(sorted(str(item) for item in available) == ["A", "B", "C"], "comparison available profiles mismatch")
    _must(str(comparison.get("best_profile") or "") == "C", "best_profile must honor preferred_profile_order")
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    _must(len(runs) == 3, "abc run must produce 3 entries")

    report_rel = str(payload.get("report_path") or "")
    _must(bool(report_rel), "report_path missing")
    report_path = ws / report_rel
    _must(report_path.exists(), "report file missing")
    report_obj = _load_json(report_path)
    subjects = report_obj.get("subjects") if isinstance(report_obj.get("subjects"), dict) else {}
    subject_obj = subjects.get(subject_id) if isinstance(subjects.get(subject_id), dict) else {}
    latest_by_profile = subject_obj.get("latest_by_profile") if isinstance(subject_obj.get("latest_by_profile"), dict) else {}
    _must(sorted(latest_by_profile.keys()) == ["A", "B", "C"], "report latest_by_profile keys mismatch")

    override_path = ws / ".cache" / "policy_overrides" / "policy_north_star_subject_plan_scoring.override.v1.json"
    _must(not override_path.exists(), "override file must be removed when persist_profile=false and no original override")

    payload_single = run_north_star_subject_plan_profile_run(
        workspace_root=ws,
        subject_id=subject_id,
        profile="B",
        run_set="single",
        mode="plan_first",
        out="latest",
        persist_profile=True,
    )
    _must(payload_single.get("status") in {"OK", "WARN"}, "single run status must be OK/WARN")
    _must(str(payload_single.get("run_set") or "") == "abc", "run_set must be forced to abc")
    single_runs = payload_single.get("runs") if isinstance(payload_single.get("runs"), list) else []
    _must(len(single_runs) == 3, "forced abc run must produce 3 entries")
    single_comparison = payload_single.get("comparison") if isinstance(payload_single.get("comparison"), dict) else {}
    single_missing = single_comparison.get("missing_profiles") if isinstance(single_comparison.get("missing_profiles"), list) else []
    _must(len(single_missing) == 0, "forced abc run must not have missing profiles")
    _must(str(single_comparison.get("best_profile") or "") == "C", "single run best_profile must honor preferred_profile_order")
    _must(override_path.exists(), "override file must exist when persist_profile=true")
    override_obj = _load_json(override_path)
    weights = (
        override_obj.get("quality_gate", {}).get("scoring_weights", {})
        if isinstance(override_obj.get("quality_gate"), dict)
        else {}
    )
    _must(abs(float(weights.get("pair_weight") or 0.0) - 0.45) < 1e-9, "persisted pair_weight mismatch")
    _must(abs(float(weights.get("theme_weight") or 0.0) - 0.40) < 1e-9, "persisted theme_weight mismatch")
    _must(abs(float(weights.get("completeness_weight") or 0.0) - 0.15) < 1e-9, "persisted completeness_weight mismatch")

    print(
        json.dumps(
            {
                "status": "OK",
                "subject_id": subject_id,
                "profiles": sorted(latest_by_profile.keys()),
                "persisted_profile": payload_single.get("profile"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
