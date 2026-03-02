from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _benchmark_status(workspace_root: Path) -> dict[str, Any]:
    catalog_path = workspace_root / ".cache" / "index" / "north_star_catalog.v1.json"
    assessment_path = workspace_root / ".cache" / "index" / "assessment.v1.json"
    assessment_raw_path = workspace_root / ".cache" / "index" / "assessment_raw.v1.json"
    assessment_eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    integrity_path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    scorecard_path = workspace_root / ".cache" / "reports" / "benchmark_scorecard.v1.json"
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    rel_catalog = str(Path(".cache") / "index" / "north_star_catalog.v1.json")
    rel_assessment = str(Path(".cache") / "index" / "assessment.v1.json")
    rel_assessment_raw = str(Path(".cache") / "index" / "assessment_raw.v1.json")
    rel_assessment_eval = str(Path(".cache") / "index" / "assessment_eval.v1.json")
    rel_integrity = str(Path(".cache") / "reports" / "integrity_verify.v1.json")
    rel_scorecard = str(Path(".cache") / "reports" / "benchmark_scorecard.v1.json")
    rel_gap = str(Path(".cache") / "index" / "gap_register.v1.json")
    status = "OK"
    notes: list[str] = []
    controls_count = 0
    metrics_count = 0
    gaps_count = 0
    maturity_avg = 0.0
    gaps_by_severity = {"low": 0, "medium": 0, "high": 0}
    top_next_actions: list[dict[str, str]] = []
    eval_lenses: dict[str, dict[str, Any]] = {}
    lens_coverages: dict[str, float] = {}
    lens_reasons_count: dict[str, int] = {}
    lenses_summary: list[dict[str, Any]] = []
    lens_gaps_count = 0
    lens_gaps_top: list[str] = []
    subject_plan_ab_path = workspace_root / ".cache" / "reports" / "north_star_subject_plan_ab_test.v1.json"
    rel_subject_plan_ab = str(Path(".cache") / "reports" / "north_star_subject_plan_ab_test.v1.json")
    subject_plan_ab_summary: dict[str, Any] = {
        "status": "FAIL",
        "report_path": rel_subject_plan_ab,
        "subject_id": "",
        "available_profiles": [],
        "missing_profiles": ["A", "B", "C"],
        "best_profile": "",
        "best_score": 0.0,
        "last_requested_profile": "",
        "last_run_set": "",
    }
    if not catalog_path.exists():
        status = "WARN"
        notes.append("missing_north_star_catalog")
    else:
        try:
            obj = _load_json(catalog_path)
            controls = obj.get("controls") if isinstance(obj, dict) else None
            metrics = obj.get("metrics") if isinstance(obj, dict) else None
            controls_count = len(controls) if isinstance(controls, list) else 0
            metrics_count = len(metrics) if isinstance(metrics, list) else 0
        except Exception:
            status = "FAIL"
            notes.append("invalid_north_star_catalog")
    if not assessment_path.exists() and not assessment_eval_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment")
    if not assessment_raw_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment_raw")
    if not assessment_eval_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment_eval")
    else:
        try:
            eval_obj = _load_json(assessment_eval_path)
        except Exception:
            notes.append("invalid_assessment_eval")
        else:
            lenses = eval_obj.get("lenses") if isinstance(eval_obj, dict) else None
            if isinstance(lenses, dict):
                for lens_id in sorted(k for k in lenses.keys() if isinstance(k, str)):
                    lens = lenses.get(lens_id)
                    if not isinstance(lens, dict):
                        continue
                    status_val = lens.get("status")
                    score_val = lens.get("score")
                    if isinstance(status_val, str):
                        entry = {
                            "status": status_val,
                            "score": float(score_val) if isinstance(score_val, (int, float)) else 0.0,
                        }
                        classification_val = lens.get("classification")
                        if isinstance(classification_val, str) and classification_val:
                            entry["classification"] = classification_val
                        reasons_val = lens.get("reasons")
                        if isinstance(reasons_val, list):
                            lens_reasons_count[lens_id] = len([r for r in reasons_val if isinstance(r, str)])
                            entry["reasons_count"] = lens_reasons_count.get(lens_id, 0)
                        eval_lenses[lens_id] = entry
                        coverage_val = lens.get("coverage")
                        if isinstance(coverage_val, (int, float)):
                            lens_coverages[lens_id] = float(coverage_val)
            elif not (isinstance(eval_obj, dict) and isinstance(eval_obj.get("assessment"), dict)):
                notes.append("missing_eval_lenses")
    if not integrity_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_integrity_verify")
    if not scorecard_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_scorecard")
    gap_list: list[dict[str, Any]] = []
    if not gap_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_gap_register")
    else:
        try:
            obj = _load_json(gap_path)
            gaps = obj.get("gaps") if isinstance(obj, dict) else None
            gaps_count = len(gaps) if isinstance(gaps, list) else 0
            if isinstance(gaps, list):
                for g in gaps:
                    if isinstance(g, dict):
                        gap_list.append(g)
        except Exception:
            status = "FAIL"
            notes.append("invalid_gap_register")
    total_items = controls_count + metrics_count
    if total_items > 0:
        maturity_avg = max(0.0, 1.0 - (gaps_count / float(total_items)))
    else:
        notes.append("no_controls_or_metrics")

    def _priority(value: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(value, 1)

    def _effort_priority(value: str) -> int:
        return {"low": 0, "medium": 1, "high": 2}.get(value, 1)

    regression_ids: set[str] = set()
    regression_path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    if regression_path.exists():
        try:
            obj = _load_json(regression_path)
            regs = obj.get("regressions") if isinstance(obj, dict) else None
            if isinstance(regs, list):
                for r in regs:
                    gid = r.get("gap_id") if isinstance(r, dict) else None
                    if isinstance(gid, str) and gid:
                        regression_ids.add(gid)
        except Exception:
            regression_ids = set()
    actions: list[tuple[int, int, int, int, str, dict[str, str]]] = []
    lens_gap_map: dict[str, list[str]] = {}
    for g in gap_list:
        gap_id = g.get("id") if isinstance(g.get("id"), str) else ""
        severity = g.get("severity") if isinstance(g.get("severity"), str) else "medium"
        risk_class = g.get("risk_class") if isinstance(g.get("risk_class"), str) else severity
        effort = g.get("effort") if isinstance(g.get("effort"), str) else "medium"
        is_regression = gap_id in regression_ids
        if severity in gaps_by_severity:
            gaps_by_severity[severity] += 1
        else:
            gaps_by_severity["medium"] += 1
        actions.append(
            (
                _priority(severity),
                _priority(risk_class),
                0 if is_regression else 1,
                _effort_priority(effort),
                gap_id,
                {"gap_id": gap_id, "severity": severity, "risk_class": risk_class, "effort": effort},
            )
        )
        metric_id = g.get("metric_id") if isinstance(g.get("metric_id"), str) else ""
        if metric_id.startswith("eval_lens:") or gap_id.startswith("GAP-EVAL-LENS-"):
            lens_id = ""
            if metric_id.startswith("eval_lens:"):
                parts = metric_id.split(":", 2)
                if len(parts) >= 2:
                    lens_id = parts[1]
            elif gap_id.startswith("GAP-EVAL-LENS-"):
                lens_id = gap_id.replace("GAP-EVAL-LENS-", "", 1).split("-", 1)[0]
            if lens_id:
                lens_gap_map.setdefault(lens_id, []).append(gap_id)
    actions.sort(key=lambda item: (item[0], item[2], item[3], item[4]))
    top_next_actions = [a[5] for a in actions[:5] if a[5].get("gap_id")]
    lens_gaps = []
    for lens_id in sorted(lens_gap_map.keys()):
        gap_ids = sorted(set(lens_gap_map.get(lens_id, [])))
        lens_gaps.extend(gap_ids)
        lens_info = eval_lenses.get(lens_id, {})
        if lens_id in eval_lenses:
            eval_lenses[lens_id]["gap_count"] = len(gap_ids)
        else:
            eval_lenses[lens_id] = {"status": "WARN", "score": 0.0, "gap_count": len(gap_ids)}
        coverage_val = lens_coverages.get(lens_id, 0.0)
        lenses_summary.append(
            {
                "lens_id": lens_id,
                "status": lens_info.get("status", "WARN"),
                "score": float(lens_info.get("score", 0.0) or 0.0),
                "coverage": float(coverage_val or 0.0),
                "top_gaps": gap_ids[:5],
            }
        )
    lens_gaps_count = len(lens_gaps)
    lens_gaps_top = lens_gaps[:5]
    if subject_plan_ab_path.exists():
        try:
            report_obj = _load_json(subject_plan_ab_path)
        except Exception:
            subject_plan_ab_summary["status"] = "FAIL"
            status = "FAIL"
            notes.append("invalid_subject_plan_ab_report")
        else:
            subjects_obj = report_obj.get("subjects") if isinstance(report_obj, dict) else None
            subject_id = str(report_obj.get("last_subject_id") or "") if isinstance(report_obj, dict) else ""
            subject_report = (
                subjects_obj.get(subject_id)
                if isinstance(subjects_obj, dict) and subject_id and isinstance(subjects_obj.get(subject_id), dict)
                else None
            )
            if isinstance(subject_report, dict):
                comparison = subject_report.get("comparison") if isinstance(subject_report.get("comparison"), dict) else {}
                available_profiles = (
                    [str(item) for item in comparison.get("available_profiles", []) if isinstance(item, str)]
                    if isinstance(comparison, dict)
                    else []
                )
                missing_profiles = (
                    [str(item) for item in comparison.get("missing_profiles", []) if isinstance(item, str)]
                    if isinstance(comparison, dict)
                    else []
                )
                best_profile = str(comparison.get("best_profile") or "") if isinstance(comparison, dict) else ""
                best_score = 0.0
                if isinstance(comparison, dict):
                    try:
                        best_score = float(comparison.get("best_score") or 0.0)
                    except Exception:
                        best_score = 0.0
                summary_status = "OK" if not missing_profiles else "FAIL"
                subject_plan_ab_summary = {
                    "status": summary_status,
                    "report_path": rel_subject_plan_ab,
                    "subject_id": subject_id,
                    "available_profiles": available_profiles,
                    "missing_profiles": missing_profiles,
                    "best_profile": best_profile,
                    "best_score": round(best_score, 6),
                    "last_requested_profile": str(subject_report.get("last_requested_profile") or ""),
                    "last_run_set": str(subject_report.get("last_run_set") or ""),
                }
                if missing_profiles:
                    status = "FAIL"
                    notes.append("subject_plan_ab_missing_profiles")
            else:
                subject_plan_ab_summary["status"] = "FAIL"
                status = "FAIL"
                notes.append("subject_plan_ab_subject_missing")
    else:
        subject_plan_ab_summary["status"] = "FAIL"
        status = "FAIL"
        notes.append("missing_subject_plan_ab_report")
    assessment_path_rel = rel_assessment_eval if assessment_eval_path.exists() else rel_assessment
    return {
        "status": status,
        "controls_count": controls_count,
        "metrics_count": metrics_count,
        "gaps_count": gaps_count,
        "maturity_avg": round(maturity_avg, 4),
        "gaps_by_severity": gaps_by_severity,
        "gaps_summary": gaps_by_severity,
        "top_next_actions": top_next_actions,
        "catalog_path": rel_catalog,
        "assessment_path": assessment_path_rel,
        "last_assessment_raw_path": rel_assessment_raw,
        "last_assessment_eval_path": rel_assessment_eval,
        "last_integrity_verify_path": rel_integrity,
        "scorecard_path": rel_scorecard,
        "gap_register_path": rel_gap,
        "eval_lenses": eval_lenses,
        "lenses": lenses_summary,
        "lens_gaps_count": lens_gaps_count,
        "lens_gaps_top": lens_gaps_top,
        "subject_plan_ab_summary": subject_plan_ab_summary,
        "notes": notes,
    }
