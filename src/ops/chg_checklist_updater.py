from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _checkbox_for_status(status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized == "DONE":
        return "x"
    if normalized == "DOING":
        return "~"
    return " "


def _normalize_paths(paths: list[str]) -> list[str]:
    return sorted({str(p).strip() for p in paths if isinstance(p, str) and str(p).strip()})


def _render_markdown(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    chg_id = str(plan.get("chg_id") or "CHG-UNKNOWN")
    lines.append(f"# {chg_id} Execution Checklist")
    lines.append("")
    lines.append(f"- extension_id: {plan.get('extension_id', '')}")
    lines.append(f"- gate: {plan.get('gate', '')}")
    lines.append(f"- owner: {plan.get('owner', '')}")
    lines.append(f"- eta: {plan.get('eta', '')}")
    lines.append(f"- priority: {plan.get('priority', '')}")
    lines.append(f"- objective: {plan.get('objective', '')}")

    root_cause_report = str(plan.get("root_cause_report") or "").strip()
    if root_cause_report:
        lines.append(f"- root_cause_report: {root_cause_report}")
    dirty_tree_report = str(plan.get("dirty_tree_source_report") or "").strip()
    if dirty_tree_report:
        lines.append(f"- dirty_tree_source_report: {dirty_tree_report}")
    lines.append("")

    root_causes = plan.get("root_causes") if isinstance(plan.get("root_causes"), list) else []
    if root_causes:
        lines.append("## Root Causes")
        for row in root_causes:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('id', 'RC-?')} ({row.get('severity', 'S?')}): {row.get('title', '')}"
            )
            impact = str(row.get("impact") or "").strip()
            if impact:
                lines.append(f"  - impact: {impact}")
            action = str(row.get("action") or "").strip()
            if action:
                lines.append(f"  - action: {action}")
            evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
            for pointer in evidence:
                if isinstance(pointer, str) and pointer.strip():
                    lines.append(f"  - evidence: {pointer.strip()}")
        lines.append("")

    lines.append("## Checklist")
    checklist = plan.get("execution_checklist") if isinstance(plan.get("execution_checklist"), list) else []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        title = str(item.get("title") or "")
        owner = str(item.get("owner") or "")
        eta = str(item.get("eta") or "")
        status = str(item.get("status") or "TODO").upper()
        lines.append(
            f"- [{_checkbox_for_status(status)}] {item_id} {title} (owner={owner} eta={eta})"
        )
        lines.append(f"  - status: {status}")
        done_criteria = str(item.get("done_criteria") or "").strip()
        if done_criteria:
            lines.append(f"  - done_criteria: {done_criteria}")
        commands = item.get("commands") if isinstance(item.get("commands"), list) else []
        for cmd in commands:
            if isinstance(cmd, str) and cmd.strip():
                lines.append(f"  - cmd: `{cmd.strip()}`")
        evidence_paths = item.get("evidence_paths") if isinstance(item.get("evidence_paths"), list) else []
        for path in evidence_paths:
            if isinstance(path, str) and path.strip():
                lines.append(f"  - evidence: {path.strip()}")

    parallel = plan.get("parallel_execution")
    if isinstance(parallel, dict):
        coord = parallel.get("coordination_points") if isinstance(parallel.get("coordination_points"), list) else []
        if coord:
            lines.append("")
            lines.append("## Parallel Coordination")
            for line in coord:
                if isinstance(line, str) and line.strip():
                    lines.append(f"- {line.strip()}")
    return "\n".join(lines) + "\n"


def _ensure_execution_checklist(plan: dict[str, Any], *, step_id: str) -> list[dict[str, Any]]:
    checklist = plan.get("execution_checklist")
    if isinstance(checklist, list):
        return [item for item in checklist if isinstance(item, dict)]

    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    if not steps:
        return []

    prefix_match = re.match(r"^([A-Za-z]+)-", str(step_id or "").strip())
    prefix = prefix_match.group(1).upper() if prefix_match else "STEP"
    owner = str(plan.get("owner") or "").strip()
    eta = str(plan.get("eta") or "").strip()
    generated: list[dict[str, Any]] = []
    for idx, title in enumerate(steps, start=1):
        if not isinstance(title, str) or not title.strip():
            continue
        generated.append(
            {
                "id": f"{prefix}-{idx:02d}",
                "title": title.strip(),
                "status": "TODO",
                "owner": owner,
                "eta": eta,
                "done_criteria": "",
                "evidence_paths": [],
            }
        )

    if generated:
        plan["execution_checklist"] = generated
        notes = plan.get("notes") if isinstance(plan.get("notes"), list) else []
        notes.append("CHECKLIST_BOOTSTRAPPED=true")
        plan["notes"] = _normalize_paths(notes)
    return generated


def update_checklist_step(
    *,
    plan_path: Path,
    step_id: str,
    status: str,
    note: str,
    evidence_paths: list[str],
    owner: str,
    eta: str,
) -> dict[str, Any]:
    plan = _load_json(plan_path)
    checklist = _ensure_execution_checklist(plan, step_id=step_id)
    if not checklist:
        raise ValueError("execution_checklist missing")

    target: dict[str, Any] | None = None
    for item in checklist:
        if isinstance(item, dict) and str(item.get("id") or "").strip() == step_id:
            target = item
            break
    if target is None:
        raise ValueError(f"step_not_found:{step_id}")

    now = _now_iso()
    normalized = str(status or "").strip().upper()
    if normalized not in {"TODO", "DOING", "DONE", "BLOCKED"}:
        raise ValueError(f"invalid_status:{normalized}")

    target["status"] = normalized
    if normalized == "DOING" and not str(target.get("started_at") or "").strip():
        target["started_at"] = now
    if normalized == "DONE":
        if not str(target.get("started_at") or "").strip():
            target["started_at"] = now
        target["finished_at"] = now

    history = target.get("status_history") if isinstance(target.get("status_history"), list) else []
    history_note = str(note).strip() if str(note).strip() else f"{step_id} -> {normalized}"
    history.append({"at": now, "status": normalized, "note": history_note})
    target["status_history"] = history

    if owner.strip():
        target["owner"] = owner.strip()
    if eta.strip():
        target["eta"] = eta.strip()

    if evidence_paths:
        existing = target.get("evidence_paths") if isinstance(target.get("evidence_paths"), list) else []
        target["evidence_paths"] = _normalize_paths([*existing, *evidence_paths])

    notes = plan.get("notes") if isinstance(plan.get("notes"), list) else []
    notes.append(f"{step_id}_{normalized}=true")
    plan["notes"] = _normalize_paths(notes)

    plan_path.write_text(_dump_json(plan), encoding="utf-8")
    md_path = plan_path.with_suffix(".md")
    md_path.write_text(_render_markdown(plan), encoding="utf-8")

    return {
        "status": "OK",
        "plan_json": str(plan_path),
        "plan_md": str(md_path),
        "step_id": step_id,
        "step_status": normalized,
        "updated_at": now,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-json", required=True, help="Path to CHG *.plan.json file.")
    ap.add_argument("--step-id", required=True, help="Checklist step id (e.g., P1-02).")
    ap.add_argument("--status", required=True, help="TODO|DOING|DONE|BLOCKED")
    ap.add_argument("--note", default="", help="Optional status note.")
    ap.add_argument("--owner", default="", help="Optional owner override.")
    ap.add_argument("--eta", default="", help="Optional ETA override.")
    ap.add_argument("--evidence", action="append", default=[], help="Optional evidence path (repeatable).")
    args = ap.parse_args(argv)

    plan_path = Path(str(args.plan_json)).expanduser().resolve()
    try:
        payload = update_checklist_step(
            plan_path=plan_path,
            step_id=str(args.step_id).strip(),
            status=str(args.status).strip(),
            note=str(args.note or ""),
            evidence_paths=[str(item) for item in (args.evidence or []) if str(item).strip()],
            owner=str(args.owner or ""),
            eta=str(args.eta or ""),
        )
    except Exception as exc:
        payload = {"status": "FAIL", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
