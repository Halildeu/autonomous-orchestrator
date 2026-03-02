from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ALLOWED_PROFILES = ("A", "B", "C")
_DEFAULT_ORDERS = [["B", "C", "A"], ["A", "C", "B"], ["C", "A", "B"]]
_DEFAULT_REPORT_REL = str(Path(".cache") / "reports" / "north_star_profile_order_ab_compare.v1.json")


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dump_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _normalize_profile(value: Any) -> str:
    profile = _safe_str(value).upper()
    if profile in _ALLOWED_PROFILES:
        return profile
    return ""


def _normalize_order(order: list[str]) -> list[str]:
    out: list[str] = []
    for item in order:
        profile = _normalize_profile(item)
        if profile and profile not in out:
            out.append(profile)
    for profile in _ALLOWED_PROFILES:
        if profile not in out:
            out.append(profile)
    return out[: len(_ALLOWED_PROFILES)]


def _parse_orders_spec(spec: str) -> list[list[str]]:
    text = _safe_str(spec)
    if not text:
        return [list(item) for item in _DEFAULT_ORDERS]

    orders: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for raw_token in text.split(";"):
        token = _safe_str(raw_token)
        if not token:
            continue
        normalized = token.replace(",", "").replace(" ", "").upper()
        if not normalized:
            continue
        chars = [_normalize_profile(ch) for ch in normalized]
        candidate = _normalize_order([ch for ch in chars if ch])
        key = tuple(candidate)
        if len(candidate) == 3 and key not in seen:
            orders.append(candidate)
            seen.add(key)
    if not orders:
        return [list(item) for item in _DEFAULT_ORDERS]
    return orders


def _restore_override(path: Path, original_bytes: bytes | None) -> str:
    if original_bytes is None:
        if not path.exists():
            return "no_original_missing"
        try:
            path.unlink()
            return "removed"
        except Exception:
            return "remove_failed"
    try:
        path.write_bytes(original_bytes)
        return "restored"
    except Exception:
        return "restore_failed"


def run_north_star_profile_order_compare(
    *,
    workspace_root: Path,
    subject_id: str,
    orders_spec: str = "BCA;ACB;CAB",
    mode: str = "plan_first",
    out: str = "latest",
    report_path: str = _DEFAULT_REPORT_REL,
) -> dict[str, Any]:
    from src.prj_planner.north_star_subject_plan_profile_run import run_north_star_subject_plan_profile_run

    workspace_root = workspace_root.resolve()
    subject_norm = _safe_str(subject_id)
    if not subject_norm:
        return {
            "status": "WARN",
            "error_code": "SUBJECT_ID_REQUIRED",
            "subject_id": "",
            "report_path": "",
            "notes": ["subject_id_missing"],
            "scenarios": [],
            "summary": {"total_scenarios": 0, "all_runs_ok": False, "all_comparisons_ok": False, "best_profile_counts": {}},
            "errors": [],
        }

    orders = _parse_orders_spec(orders_spec)
    mode_norm = _safe_str(mode) or "plan_first"
    out_norm = _safe_str(out) or "latest"

    report_target = _safe_str(report_path) or _DEFAULT_REPORT_REL
    report_abs = Path(report_target)
    if not report_abs.is_absolute():
        report_abs = workspace_root / report_target
    report_abs = report_abs.resolve()
    report_abs.parent.mkdir(parents=True, exist_ok=True)

    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_north_star_subject_plan.override.v1.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    original_override_bytes: bytes | None = None
    if override_path.exists():
        try:
            original_override_bytes = override_path.read_bytes()
        except Exception:
            original_override_bytes = None

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    notes: list[str] = [
        f"subject_id={subject_norm}",
        f"orders_spec={_safe_str(orders_spec) or 'default'}",
        f"orders_count={len(orders)}",
        f"mode={mode_norm}",
        f"out={out_norm}",
    ]
    restore_state = ""

    try:
        for index, order in enumerate(orders, start=1):
            override_obj = {"version": "v1", "quality_gate": {"preferred_profile_order": order}}
            override_path.write_text(_dump_json(override_obj), encoding="utf-8")

            payload = run_north_star_subject_plan_profile_run(
                workspace_root=workspace_root,
                subject_id=subject_norm,
                profile="C",
                run_set="abc",
                mode=mode_norm,
                out=out_norm,
                persist_profile=True,
            )

            comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
            rows.append(
                {
                    "scenario_id": f"order_{index}",
                    "preferred_profile_order": list(order),
                    "run_status": _safe_str(payload.get("status")),
                    "comparison_status": _safe_str(comparison.get("status")),
                    "best_profile": _safe_str(comparison.get("best_profile")),
                    "best_score": round(float(comparison.get("best_score") or 0.0), 6),
                    "available_profiles": [
                        _safe_str(item)
                        for item in (comparison.get("available_profiles") or [])
                        if _safe_str(item)
                    ],
                    "missing_profiles": [
                        _safe_str(item)
                        for item in (comparison.get("missing_profiles") or [])
                        if _safe_str(item)
                    ],
                    "comparison_preferred_profile_order": [
                        _safe_str(item)
                        for item in (comparison.get("preferred_profile_order") or [])
                        if _safe_str(item)
                    ],
                    "error_code": _safe_str(payload.get("error_code")),
                    "report_path": _safe_str(payload.get("report_path")),
                }
            )
    except Exception as exc:
        errors.append(f"scenario_run_failed:{_safe_str(exc)}")
    finally:
        restore_state = _restore_override(override_path, original_override_bytes)
        if restore_state.endswith("failed"):
            errors.append(f"override_restore:{restore_state}")

    best_profile_counts: dict[str, int] = {}
    for row in rows:
        key = _safe_str(row.get("best_profile")) or "_missing"
        best_profile_counts[key] = int(best_profile_counts.get(key, 0)) + 1

    summary = {
        "total_scenarios": len(rows),
        "all_runs_ok": all(_safe_str(row.get("run_status")).upper() == "OK" for row in rows),
        "all_comparisons_ok": all(_safe_str(row.get("comparison_status")).upper() == "OK" for row in rows),
        "best_profile_counts": best_profile_counts,
    }

    report_obj = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "subject_id": subject_norm,
        "policy_override_path": str(override_path),
        "restore_state": restore_state,
        "orders_spec": _safe_str(orders_spec),
        "scenarios": rows,
        "summary": summary,
        "notes": notes,
        "errors": errors,
    }
    report_abs.write_text(_dump_json(report_obj), encoding="utf-8")

    status = "OK" if not errors else "WARN"
    return {
        "status": status,
        "error_code": "",
        "subject_id": subject_norm,
        "report_path": str(report_abs),
        "orders_spec": _safe_str(orders_spec),
        "summary": summary,
        "scenarios": rows,
        "notes": notes,
        "errors": errors,
    }
