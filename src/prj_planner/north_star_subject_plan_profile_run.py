from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ALLOWED_PROFILES = ("A", "B", "C")
_DEFAULT_PROFILE = "C"

_PROFILE_OVERRIDES: dict[str, dict[str, Any]] = {
    "A": {
        "version": "v1",
        "quality_gate": {
            "scoring_weights": {
                "pair_weight": 0.55,
                "theme_weight": 0.35,
                "completeness_weight": 0.10,
            }
        },
    },
    "B": {
        "version": "v1",
        "quality_gate": {
            "scoring_weights": {
                "pair_weight": 0.45,
                "theme_weight": 0.40,
                "completeness_weight": 0.15,
            }
        },
    },
    "C": {
        "version": "v1",
        "quality_gate": {
            "scoring_weights": {
                "pair_weight": 0.70,
                "theme_weight": 0.20,
                "completeness_weight": 0.10,
            }
        },
    },
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()))
    except Exception:
        return str(path.resolve())


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _normalize_profile(value: str) -> str:
    profile = _safe_str(value).upper()
    if profile in _ALLOWED_PROFILES:
        return profile
    return _DEFAULT_PROFILE


def _normalize_run_set(value: str) -> str:
    _ = _safe_str(value).lower()
    return "abc"


def _resolve_profiles_to_run(*, selected_profile: str, run_set: str) -> list[str]:
    _ = selected_profile
    _ = run_set
    return ["A", "B", "C"]


def _validate_scoring_override(override_obj: dict[str, Any]) -> tuple[bool, list[str]]:
    schema_path = _repo_root() / "schemas" / "policy-north-star-subject-plan-scoring.schema.v1.json"
    if not schema_path.exists():
        return False, ["override_schema_missing"]
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return False, ["override_validator_missing:jsonschema"]
    try:
        schema_obj = _load_json(schema_path)
    except Exception:
        return False, ["override_schema_invalid_json"]
    if not isinstance(schema_obj, dict):
        return False, ["override_schema_invalid_object"]
    validator = Draft202012Validator(schema_obj)
    errors = sorted(validator.iter_errors(override_obj), key=lambda err: list(err.path))
    if not errors:
        return True, []
    notes: list[str] = []
    for err in errors[:10]:
        path = "/".join(str(item) for item in err.path) or "$"
        message = str(err.message).replace("\n", " ").strip()
        notes.append(f"override_contract_error:{path}:{message}")
    if len(errors) > 10:
        notes.append(f"override_contract_error_truncated:{len(errors)}")
    return False, notes


def _extract_run_entry(
    *,
    workspace_root: Path,
    profile: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "profile": profile,
        "ran_at": _now_iso8601(),
        "status": _safe_str(payload.get("status")).upper() or "WARN",
        "error_code": _safe_str(payload.get("error_code")),
        "plan_id": _safe_str(payload.get("plan_id")),
        "plan_path": _safe_str(payload.get("plan_path")),
        "summary_path": _safe_str(payload.get("summary_path")),
        "quality_gate_status": _safe_str(payload.get("quality_gate_status")).upper(),
        "contract_validation_status": _safe_str(payload.get("contract_validation_status")).upper(),
        "coverage_complete": bool(payload.get("coverage_complete")),
        "coverage_quality_score": round(_safe_float(payload.get("coverage_quality_score"), 0.0), 6),
        "module_count": _safe_int(payload.get("module_count"), 0),
        "theme_count": _safe_int(payload.get("theme_count"), 0),
        "subtheme_count": _safe_int(payload.get("subtheme_count"), 0),
        "notes": [str(item) for item in payload.get("notes", []) if isinstance(item, str)],
    }

    plan_rel = _safe_str(payload.get("plan_path"))
    if not plan_rel:
        return entry

    plan_path = workspace_root / plan_rel
    if not plan_path.exists():
        entry["notes"].append("plan_path_missing_for_profile_run")
        return entry

    try:
        plan_obj = _load_json(plan_path)
    except Exception:
        entry["notes"].append("plan_json_invalid_for_profile_run")
        return entry

    decision = plan_obj.get("decision") if isinstance(plan_obj.get("decision"), dict) else {}
    quality_gate = decision.get("quality_gate") if isinstance(decision.get("quality_gate"), dict) else {}
    thresholds = quality_gate.get("thresholds") if isinstance(quality_gate.get("thresholds"), dict) else {}
    scoring = thresholds.get("scoring_weights") if isinstance(thresholds.get("scoring_weights"), dict) else {}
    entry["scoring_weights"] = {
        "pair_weight": round(_safe_float(scoring.get("pair_weight"), 0.0), 6),
        "theme_weight": round(_safe_float(scoring.get("theme_weight"), 0.0), 6),
        "completeness_weight": round(_safe_float(scoring.get("completeness_weight"), 0.0), 6),
    }
    entry["min_coverage_quality"] = round(_safe_float(thresholds.get("min_coverage_quality"), 0.0), 6)
    entry["max_module_count"] = _safe_int(thresholds.get("max_module_count"), 0)
    entry["require_full_coverage"] = bool(thresholds.get("require_full_coverage"))
    return entry


def _comparison_summary(latest_by_profile: dict[str, dict[str, Any]]) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    available_profiles: list[str] = []
    for profile in _ALLOWED_PROFILES:
        current = latest_by_profile.get(profile)
        if isinstance(current, dict):
            available_profiles.append(profile)
            profiles.append(
                {
                    "profile": profile,
                    "status": _safe_str(current.get("status")).upper() or "WARN",
                    "quality_gate_status": _safe_str(current.get("quality_gate_status")).upper(),
                    "coverage_quality_score": round(_safe_float(current.get("coverage_quality_score"), 0.0), 6),
                    "module_count": _safe_int(current.get("module_count"), 0),
                    "plan_id": _safe_str(current.get("plan_id")),
                    "ran_at": _safe_str(current.get("ran_at")),
                }
            )
        else:
            profiles.append(
                {
                    "profile": profile,
                    "status": "MISSING",
                    "quality_gate_status": "",
                    "coverage_quality_score": 0.0,
                    "module_count": 0,
                    "plan_id": "",
                    "ran_at": "",
                }
            )

    missing_profiles = [profile for profile in _ALLOWED_PROFILES if profile not in available_profiles]
    ranked = [row for row in profiles if row.get("status") in {"OK", "WARN"}]
    ranked.sort(
        key=lambda row: (
            0 if str(row.get("quality_gate_status") or "").upper() == "PASS" else 1,
            -_safe_float(row.get("coverage_quality_score"), 0.0),
            _safe_int(row.get("module_count"), 999999),
            str(row.get("profile") or ""),
        )
    )
    best_profile = str(ranked[0].get("profile") or "") if ranked else ""
    best_score = round(_safe_float(ranked[0].get("coverage_quality_score"), 0.0), 6) if ranked else 0.0
    status = "OK" if len(missing_profiles) == 0 else ("WARN" if available_profiles else "IDLE")

    return {
        "status": status,
        "available_profiles": available_profiles,
        "missing_profiles": missing_profiles,
        "best_profile": best_profile,
        "best_score": best_score,
        "profiles": profiles,
    }


def run_north_star_subject_plan_profile_run(
    *,
    workspace_root: Path,
    subject_id: str,
    profile: str = "C",
    run_set: str = "abc",
    mode: str = "plan_first",
    out: str = "latest",
    persist_profile: bool = True,
) -> dict[str, Any]:
    from src.prj_planner.north_star_subject_plan import run_north_star_subject_to_plan

    workspace_root = workspace_root.resolve()
    subject_norm = _safe_str(subject_id)
    if not subject_norm:
        return {
            "status": "WARN",
            "error_code": "SUBJECT_ID_REQUIRED",
            "subject_id": "",
            "profile": "",
            "run_set": "",
            "runs": [],
            "comparison": {
                "status": "IDLE",
                "available_profiles": [],
                "missing_profiles": list(_ALLOWED_PROFILES),
                "best_profile": "",
                "best_score": 0.0,
                "profiles": [],
            },
            "report_path": "",
            "scoring_override_path": "",
            "notes": ["subject_id_missing"],
        }

    selected_profile = _normalize_profile(profile)
    requested_run_set = _safe_str(run_set).lower() or "single"
    normalized_run_set = _normalize_run_set(run_set)
    profiles_to_run = _resolve_profiles_to_run(selected_profile=selected_profile, run_set=normalized_run_set)

    notes: list[str] = [
        f"subject_id={subject_norm}",
        f"profile={selected_profile}",
        f"run_set={normalized_run_set}",
        f"profiles_to_run={','.join(profiles_to_run)}",
    ]
    if requested_run_set != "abc":
        notes.append(f"run_set_forced=abc(requested:{requested_run_set})")

    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_north_star_subject_plan_scoring.override.v1.json"
    report_path = workspace_root / ".cache" / "reports" / "north_star_subject_plan_ab_test.v1.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    original_override_bytes: bytes | None = None
    if override_path.exists():
        try:
            original_override_bytes = override_path.read_bytes()
        except Exception:
            notes.append("original_override_read_failed")

    run_entries: list[dict[str, Any]] = []
    execution_error_code = ""

    try:
        for current_profile in profiles_to_run:
            profile_override = _PROFILE_OVERRIDES.get(current_profile)
            if not isinstance(profile_override, dict):
                execution_error_code = "INVALID_PROFILE"
                notes.append(f"invalid_profile={current_profile}")
                break

            valid_override, validation_notes = _validate_scoring_override(profile_override)
            if not valid_override:
                execution_error_code = "SCORING_OVERRIDE_INVALID"
                notes.extend(validation_notes)
                break

            override_path.write_text(_dump_json(profile_override), encoding="utf-8")

            requested_out = _safe_str(out).lower()
            if requested_out in {"", "latest"}:
                run_out = f"{subject_norm}_{current_profile.lower()}"
            else:
                run_out = f"{requested_out}_{current_profile.lower()}"

            run_payload = run_north_star_subject_to_plan(
                workspace_root=workspace_root,
                subject_id=subject_norm,
                mode=_safe_str(mode) or "plan_first",
                out=run_out,
            )
            run_entry = _extract_run_entry(
                workspace_root=workspace_root,
                profile=current_profile,
                payload=run_payload if isinstance(run_payload, dict) else {},
            )
            run_entries.append(run_entry)

        if execution_error_code:
            return {
                "status": "WARN",
                "error_code": execution_error_code,
                "subject_id": subject_norm,
                "profile": selected_profile,
                "run_set": normalized_run_set,
                "runs": run_entries,
                "comparison": {
                    "status": "IDLE",
                    "available_profiles": [entry.get("profile") for entry in run_entries if isinstance(entry, dict)],
                    "missing_profiles": [p for p in _ALLOWED_PROFILES if p not in {e.get("profile") for e in run_entries}],
                    "best_profile": "",
                    "best_score": 0.0,
                    "profiles": [],
                },
                "report_path": _rel_path(workspace_root, report_path),
                "scoring_override_path": _rel_path(workspace_root, override_path),
                "notes": notes,
            }

    finally:
        if persist_profile:
            selected_override = _PROFILE_OVERRIDES.get(selected_profile, _PROFILE_OVERRIDES[_DEFAULT_PROFILE])
            valid_override, validation_notes = _validate_scoring_override(selected_override)
            if valid_override:
                override_path.write_text(_dump_json(selected_override), encoding="utf-8")
                notes.append(f"persist_profile={selected_profile}")
            else:
                notes.append("persist_profile_failed_contract")
                notes.extend(validation_notes)
        else:
            if original_override_bytes is None:
                if override_path.exists():
                    try:
                        override_path.unlink()
                        notes.append("override_restored=removed")
                    except Exception:
                        notes.append("override_restore_failed=remove")
            else:
                try:
                    override_path.write_bytes(original_override_bytes)
                    notes.append("override_restored=original")
                except Exception:
                    notes.append("override_restore_failed=write")

    report_obj: dict[str, Any] = {"version": "v1", "updated_at": _now_iso8601(), "last_subject_id": subject_norm, "subjects": {}}
    if report_path.exists():
        try:
            loaded_report = _load_json(report_path)
            if isinstance(loaded_report, dict):
                report_obj = _deep_merge(report_obj, loaded_report)
        except Exception:
            notes.append("existing_report_invalid_json")

    subjects = report_obj.get("subjects") if isinstance(report_obj.get("subjects"), dict) else {}
    subject_report = subjects.get(subject_norm) if isinstance(subjects.get(subject_norm), dict) else {}
    latest_by_profile = subject_report.get("latest_by_profile") if isinstance(subject_report.get("latest_by_profile"), dict) else {}
    history = subject_report.get("history") if isinstance(subject_report.get("history"), list) else []
    cleaned_history = [entry for entry in history if isinstance(entry, dict)]

    for entry in run_entries:
        profile_key = _safe_str(entry.get("profile")).upper()
        if profile_key in _ALLOWED_PROFILES:
            latest_by_profile[profile_key] = entry
            cleaned_history.append(entry)

    if len(cleaned_history) > 60:
        cleaned_history = cleaned_history[-60:]

    comparison = _comparison_summary(latest_by_profile)

    subject_report = {
        "subject_id": subject_norm,
        "updated_at": _now_iso8601(),
        "last_requested_profile": selected_profile,
        "last_run_set": normalized_run_set,
        "latest_by_profile": latest_by_profile,
        "history": cleaned_history,
        "comparison": comparison,
    }
    subjects[subject_norm] = subject_report
    report_obj["subjects"] = subjects
    report_obj["last_subject_id"] = subject_norm
    report_obj["updated_at"] = _now_iso8601()
    report_path.write_text(_dump_json(report_obj), encoding="utf-8")

    run_statuses = [str(entry.get("status") or "").upper() for entry in run_entries if isinstance(entry, dict)]
    if run_statuses and all(status == "OK" for status in run_statuses):
        final_status = "OK"
    elif run_statuses and all(status in {"OK", "WARN", "IDLE"} for status in run_statuses):
        final_status = "WARN"
    else:
        final_status = "WARN"

    return {
        "status": final_status,
        "error_code": "",
        "subject_id": subject_norm,
        "profile": selected_profile,
        "run_set": normalized_run_set,
        "runs": run_entries,
        "comparison": comparison,
        "report_path": _rel_path(workspace_root, report_path),
        "scoring_override_path": _rel_path(workspace_root, override_path),
        "notes": notes,
    }
