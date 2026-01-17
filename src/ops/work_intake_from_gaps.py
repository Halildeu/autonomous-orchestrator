from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _load_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_work_intake.v1.json"
    core_policy = core_root / "policies" / "policy_work_intake.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {
            "version": "v1",
            "enabled": True,
            "plan_policy": "optional",
            "buckets": ["ROADMAP", "PROJECT", "TICKET", "INCIDENT"],
            "severity_levels": ["S0", "S1", "S2", "S3", "S4"],
            "sla_hints": {
                "S0": "hours",
                "S1": "1d",
                "S2": "1w",
                "S3": "1m",
                "S4": "backlog",
            },
            "classification": {
                "incident_keywords": ["service down", "data loss", "security breach", "urgent compliance"],
                "roadmap_keywords": ["adoption", "new_standard", "platform", "multi_project"],
                "coverage_suffixes": ["COVERAGE"],
                "regression_bucket": "INCIDENT",
                "default_bucket": "TICKET",
            },
            "severity_map": {"high": "S1", "medium": "S2", "low": "S3", "unknown": "S4"},
        }
    obj = _load_json(path)
    return obj if isinstance(obj, dict) else {}


def _severity_rank(sev: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}.get(sev, 4)


def _priority_from_severity(sev: str) -> str:
    return {"S0": "P0", "S1": "P1", "S2": "P2", "S3": "P3", "S4": "P4"}.get(sev, "P4")


def _bucket_rank(bucket: str, order: list[str]) -> int:
    try:
        return order.index(bucket)
    except ValueError:
        return len(order)


def _detect_keyword(texts: list[str], keywords: list[str]) -> bool:
    hay = " ".join([t.lower() for t in texts if isinstance(t, str)])
    for kw in keywords:
        if isinstance(kw, str) and kw.lower() in hay:
            return True
    return False


def _coverage_match(values: list[str], suffixes: list[str]) -> bool:
    for value in values:
        if not isinstance(value, str):
            continue
        for suf in suffixes:
            if isinstance(suf, str) and value.endswith(suf):
                return True
    return False


def _load_regressions(workspace_root: Path) -> set[str]:
    path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    if not path.exists():
        return set()
    try:
        obj = _load_json(path)
    except Exception:
        return set()
    regs = obj.get("regressions") if isinstance(obj, dict) else None
    if not isinstance(regs, list):
        return set()
    ids: set[str] = set()
    for r in regs:
        gid = r.get("gap_id") if isinstance(r, dict) else None
        if isinstance(gid, str) and gid:
            ids.add(gid)
    return ids


def _build_items(
    *,
    gaps: list[dict[str, Any]],
    policy: dict[str, Any],
    regression_ids: set[str],
    notes_out: list[str],
) -> list[dict[str, Any]]:
    classification = policy.get("classification") if isinstance(policy.get("classification"), dict) else {}
    incident_keywords = classification.get("incident_keywords") if isinstance(classification.get("incident_keywords"), list) else []
    roadmap_keywords = classification.get("roadmap_keywords") if isinstance(classification.get("roadmap_keywords"), list) else []
    coverage_suffixes = classification.get("coverage_suffixes") if isinstance(classification.get("coverage_suffixes"), list) else []
    regression_bucket = classification.get("regression_bucket") if isinstance(classification.get("regression_bucket"), str) else "INCIDENT"
    default_bucket = classification.get("default_bucket") if isinstance(classification.get("default_bucket"), str) else "TICKET"
    severity_map = policy.get("severity_map") if isinstance(policy.get("severity_map"), dict) else {}
    sla_hints = policy.get("sla_hints") if isinstance(policy.get("sla_hints"), dict) else {}

    items: list[dict[str, Any]] = []
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        gap_id = gap.get("id") if isinstance(gap.get("id"), str) else ""
        control_id = gap.get("control_id") if isinstance(gap.get("control_id"), str) else ""
        metric_id = gap.get("metric_id") if isinstance(gap.get("metric_id"), str) else ""
        severity = gap.get("severity") if isinstance(gap.get("severity"), str) else "unknown"
        risk_class = gap.get("risk_class") if isinstance(gap.get("risk_class"), str) else "medium"
        effort = gap.get("effort") if isinstance(gap.get("effort"), str) else "medium"
        report_only = bool(gap.get("report_only", False))
        evidence = gap.get("evidence_pointers") if isinstance(gap.get("evidence_pointers"), list) else []

        is_regression = gap_id in regression_ids
        reason_tags: list[str] = []
        bucket = default_bucket

        if is_regression:
            bucket = regression_bucket
            reason_tags.append("regression")
        else:
            if _detect_keyword([gap_id, control_id, metric_id, gap.get("notes")], incident_keywords):
                bucket = "INCIDENT"
                reason_tags.append("incident_keyword")
            elif _detect_keyword([gap_id, control_id, metric_id], roadmap_keywords):
                bucket = "ROADMAP"
                report_only = True
                reason_tags.append("roadmap_candidate")
            elif _coverage_match([gap_id, metric_id], coverage_suffixes):
                bucket = "PROJECT"
                reason_tags.append("coverage_gap")
            elif effort == "low" and severity in {"low", "medium"}:
                bucket = "TICKET"
                reason_tags.append("bounded_scope")
            elif effort in {"medium", "high"}:
                bucket = "PROJECT"
                reason_tags.append("multi_step")

        sev = "S0" if is_regression else str(severity_map.get(severity, severity_map.get("unknown", "S4")))
        priority = _priority_from_severity(sev)
        if bucket == "INCIDENT":
            priority = "P0"
            sev = "S0" if not is_regression else sev

        title = f"Gap: {gap_id}"
        if control_id:
            title = f"Control gap: {control_id}"
        elif metric_id:
            title = f"Metric gap: {metric_id}"

        intake_id = f"INTAKE-{gap_id}" if gap_id else f"INTAKE-{_hash_text(title)[:8]}"
        plan_policy = str(policy.get("plan_policy", "optional") or "optional")
        sla_hint = str(sla_hints.get(sev, "")) if isinstance(sla_hints, dict) else ""

        source = {
            "kind": "gap",
            "gap_id": gap_id or title,
            "regression": bool(is_regression),
            "evidence_pointers": [str(x) for x in evidence if isinstance(x, str)],
        }
        if control_id:
            source["control_id"] = control_id
        if metric_id:
            source["metric_id"] = metric_id

        item = {
            "intake_id": intake_id,
            "bucket": bucket,
            "severity": sev,
            "priority": priority,
            "title": title,
            "source": source,
            "risk_class": risk_class if risk_class in {"low", "medium", "high"} else "medium",
            "effort": effort if effort in {"low", "medium", "high"} else "medium",
            "report_only": bool(report_only),
            "plan_policy": "optional" if plan_policy not in {"optional", "required"} else plan_policy,
            "reasons": sorted(set(reason_tags)) if reason_tags else [],
        }
        if sla_hint:
            item["sla_hint"] = sla_hint
        items.append(item)

    return items


def _build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    by_severity = {"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 0}
    top_next = []
    for item in items:
        bucket = item.get("bucket")
        sev = item.get("severity")
        if bucket in by_bucket:
            by_bucket[bucket] += 1
        if sev in by_severity:
            by_severity[sev] += 1
    for item in items[:5]:
        top_next.append(
            {
                "intake_id": item.get("intake_id"),
                "bucket": item.get("bucket"),
                "severity": item.get("severity"),
                "priority": item.get("priority"),
                "title": item.get("title"),
            }
        )
    return {"total": len(items), "by_bucket": by_bucket, "by_severity": by_severity, "top_next": top_next}


def _write_md(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Work Intake Summary",
        "",
        f"Total items: {summary.get('total', 0)}",
        "",
        "By bucket:",
        f"- ROADMAP: {summary.get('by_bucket', {}).get('ROADMAP', 0)}",
        f"- PROJECT: {summary.get('by_bucket', {}).get('PROJECT', 0)}",
        f"- TICKET: {summary.get('by_bucket', {}).get('TICKET', 0)}",
        f"- INCIDENT: {summary.get('by_bucket', {}).get('INCIDENT', 0)}",
        "",
        "Top next:",
    ]
    for item in summary.get("top_next", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('intake_id', '')} bucket={item.get('bucket', '')} "
            f"severity={item.get('severity', '')} priority={item.get('priority', '')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_work_intake_build(*, workspace_root: Path, mode: str = "build") -> dict[str, Any]:
    core_root = Path(__file__).resolve().parents[2]
    policy = _load_policy(core_root=core_root, workspace_root=workspace_root)
    if not isinstance(policy, dict) or not policy.get("enabled", True):
        return {"status": "IDLE", "reason": "policy_disabled"}

    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    pdca_path = workspace_root / ".cache" / "reports" / "pdca_recheck_report.v1.json"
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    summary_md_path = workspace_root / ".cache" / "reports" / "work_intake_summary.v1.md"
    _ensure_inside_workspace(workspace_root, intake_path)
    _ensure_inside_workspace(workspace_root, summary_md_path)

    notes: list[str] = []
    gaps: list[dict[str, Any]] = []
    if not gap_path.exists():
        notes.append("gap_register_missing")
    else:
        try:
            gap_obj = _load_json(gap_path)
            raw = gap_obj.get("gaps") if isinstance(gap_obj, dict) else None
            gaps = raw if isinstance(raw, list) else []
        except Exception:
            notes.append("gap_register_invalid")

    if not pdca_path.exists():
        notes.append("pdca_recheck_missing")

    regression_ids = _load_regressions(workspace_root)
    items = _build_items(gaps=gaps, policy=policy, regression_ids=regression_ids, notes_out=notes)
    bucket_order = policy.get("buckets") if isinstance(policy.get("buckets"), list) else ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"]
    items.sort(
        key=lambda x: (
            _priority_from_severity(str(x.get("severity"))),
            _severity_rank(str(x.get("severity"))),
            _bucket_rank(str(x.get("bucket")), [str(b) for b in bucket_order]),
            str(x.get("intake_id")),
        )
    )

    summary = _build_summary(items)
    status = "OK" if items else "IDLE"
    if notes and status == "OK":
        status = "WARN"

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "plan_policy": str(policy.get("plan_policy", "optional") or "optional"),
        "items": items,
        "summary": summary,
        "notes": sorted(set(notes)),
    }

    schema_path = core_root / "schemas" / "work-intake.schema.v1.json"
    if schema_path.exists():
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(payload)

    intake_path.parent.mkdir(parents=True, exist_ok=True)
    summary_md_path.parent.mkdir(parents=True, exist_ok=True)
    intake_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _write_md(summary_md_path, summary)

    if mode == "next":
        return {
            "status": status,
            "work_intake_path": str(intake_path),
            "top_next": summary.get("top_next", []),
        }

    if mode == "create_plan":
        if not items:
            return {"status": "IDLE", "work_intake_path": str(intake_path), "plan_path": None}
        intake_ids = [str(item.get("intake_id")) for item in items if isinstance(item, dict)]
        hash_id = _hash_text(",".join(sorted(intake_ids)))[:8]
        chg_dir = workspace_root / ".cache" / "reports" / "chg"
        chg_dir.mkdir(parents=True, exist_ok=True)
        chg_id = f"CHG-INTAKE-{hash_id}"
        plan_path = chg_dir / f"{chg_id}.plan.json"
        plan_md_path = chg_dir / f"{chg_id}.plan.md"
        plan = {
            "chg_id": chg_id,
            "plan_only": True,
            "scope": "work_intake",
            "intake_ids": intake_ids,
            "generated_at": _now_iso(),
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        plan_md_path.write_text(f"CHG PLAN: {chg_id}\n\nItems: {len(intake_ids)}\n", encoding="utf-8")
        return {"status": "OK", "work_intake_path": str(intake_path), "plan_path": str(plan_path)}

    return {
        "status": status,
        "work_intake_path": str(intake_path),
        "summary_path": str(summary_md_path),
        "items_count": len(items),
        "top_next": summary.get("top_next", []),
    }
