from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.roadmap.evidence import write_integrity_manifest, write_json, write_text
from src.roadmap.state import (
    bootstrap_completed_milestones,
    bump_attempt,
    clear_backoff,
    clear_quarantine,
    is_in_backoff,
    is_quarantined,
    load_state,
    mark_completed,
    pause_state,
    quarantine_milestone,
    record_last_result,
    resume_state,
    save_state,
    set_backoff,
    set_checkpoint,
    set_current_milestone,
)
from src.session.context_store import SessionContextError, SessionPaths, load_context


def _core_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso8601(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_hex(s: str) -> str:
    return sha256(s.encode("utf-8")).hexdigest()


def _git_status_porcelain(core_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "")


def _git_status_lines(core_root: Path) -> list[str] | None:
    status = _git_status_porcelain(core_root)
    if status is None:
        return None
    return [line.strip() for line in status.splitlines() if line.strip()]


def _git_status_paths(lines: list[str]) -> list[str]:
    paths: list[str] = []
    for line in lines:
        if not line:
            continue
        payload = line[3:] if len(line) > 3 else line
        if "->" in payload:
            parts = [p.strip() for p in payload.split("->") if p.strip()]
            paths.extend(parts)
            continue
        path = payload.strip()
        if path:
            paths.append(path)
    return paths


def _core_paths_allowed(paths: list[str], allowed: tuple[str, ...]) -> bool:
    if not allowed:
        return False
    for path in paths:
        if not any(fnmatch.fnmatch(path, pattern) for pattern in allowed):
            return False
    return True


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_sha256_hex(s: Any) -> bool:
    if not isinstance(s, str):
        return False
    if len(s) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in s)


def _snapshot_tree(root: Path, *, ignore_prefixes: list[str] | None = None) -> dict[str, str]:
    ignore_prefixes = ignore_prefixes or []
    cleaned: list[str] = []
    for raw in ignore_prefixes:
        pref = str(raw).strip().replace("\\", "/").strip("/")
        if pref:
            cleaned.append(pref)

    def ignored(rel: str) -> bool:
        rel = rel.replace("\\", "/")
        if rel.startswith("./"):
            rel = rel[2:]
        rel = rel.lstrip("/")
        return any(rel == pref or rel.startswith(pref + "/") for pref in cleaned)

    snap: dict[str, str] = {}
    if not root.exists():
        return snap

    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(root).as_posix()
        except Exception:
            continue
        if ignored(rel):
            continue
        try:
            snap[rel] = _sha256_file(p)
        except Exception:
            snap[rel] = "UNREADABLE"
    return snap


def _load_governor_global_mode(core_root: Path) -> str:
    path = core_root / "governor" / "health_brain.v1.json"
    if not path.exists():
        return "normal"
    try:
        obj = _load_json(path)
    except Exception:
        return "normal"
    if not isinstance(obj, dict):
        return "normal"
    mode = obj.get("global_mode")
    return str(mode) if isinstance(mode, str) else "normal"


def _load_and_validate_roadmap(core_root: Path, roadmap_path: Path) -> dict[str, Any]:
    obj = _load_json(roadmap_path)
    if not isinstance(obj, dict):
        raise ValueError("ROADMAP_INVALID")

    try:
        from src.roadmap.compiler import validate_roadmap
    except Exception as e:
        raise ValueError("ROADMAP_VALIDATE_IMPORT_FAILED") from e

    schema_path = core_root / "schemas" / "roadmap.schema.json"
    errors = validate_roadmap(obj, schema_path)
    if errors:
        raise ValueError("ROADMAP_SCHEMA_INVALID: " + "; ".join(errors))
    return obj


def _roadmap_milestones(roadmap_obj: dict[str, Any]) -> list[str]:
    out: list[str] = []
    ms = roadmap_obj.get("milestones")
    if not isinstance(ms, list):
        return out
    for m in ms:
        if isinstance(m, dict) and isinstance(m.get("id"), str):
            out.append(m["id"])
    return out


def _next_milestone(roadmap_ids: list[str], completed: list[str]) -> str | None:
    done = set(str(x) for x in completed if isinstance(x, str))
    for mid in roadmap_ids:
        if mid not in done:
            return mid
    return None


def _check_iso_core_presence(workspace_root: Path) -> bool:
    base = workspace_root / "tenant" / "TENANT-DEFAULT"
    required = ["context.v1.md", "stakeholders.v1.md", "scope.v1.md", "criteria.v1.md"]
    return all((base / f).exists() for f in required)


def _parse_iso8601(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _actions_path(workspace_root: Path) -> Path:
    return (workspace_root / ".cache" / "roadmap_actions.v1.json").resolve()


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _load_action_register(path: Path, *, roadmap_path: Path, workspace_root: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": "v1",
            "roadmap_path": str(roadmap_path),
            "workspace_root": str(workspace_root),
            "actions": [],
        }
    try:
        obj = _load_json(path)
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("version", "v1")
    obj.setdefault("roadmap_path", str(roadmap_path))
    obj.setdefault("workspace_root", str(workspace_root))
    if not isinstance(obj.get("actions"), list):
        obj["actions"] = []
    return obj


def _action_id(kind: str, message: str) -> str:
    return _sha256_hex(f"{kind}:{message}")[:16]


def _placeholder_milestones_from_roadmap(*, roadmap_obj: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    milestones = roadmap_obj.get("milestones")
    if not isinstance(milestones, list):
        return out
    for ms in milestones:
        if not isinstance(ms, dict):
            continue
        mid = ms.get("id")
        if not isinstance(mid, str) or not mid:
            continue
        steps = ms.get("steps")
        if not isinstance(steps, list) or not steps:
            out.add(mid)
            continue
        has_executable = False
        for st in steps:
            if not isinstance(st, dict):
                continue
            t = st.get("type")
            if isinstance(t, str) and t != "note":
                has_executable = True
                break
        if not has_executable:
            out.add(mid)
    return out


def _self_heal_placeholder_actions(
    *,
    actions_reg: dict[str, Any],
    placeholder_milestones: set[str],
    roadmap_milestones: set[str],
) -> bool:
    actions = actions_reg.get("actions")
    if not isinstance(actions, list):
        return False

    changed = False
    for a in actions:
        if not isinstance(a, dict):
            continue
        if a.get("kind") != "PLACEHOLDER_MILESTONE":
            continue
        if a.get("resolved") is True:
            continue
        mid = a.get("milestone_hint")
        if not isinstance(mid, str) or not mid:
            continue
        if mid not in roadmap_milestones or mid not in placeholder_milestones:
            a["resolved"] = True
            changed = True

    if changed:
        actions_reg["actions"] = sorted(
            [x for x in actions if isinstance(x, dict)],
            key=lambda x: str(x.get("action_id") or ""),
        )
    return changed


def _supported_step_types(*, core_root: Path) -> set[str]:
    schema_path = core_root / "schemas" / "roadmap.schema.json"
    if not schema_path.exists():
        return set()
    try:
        obj = _load_json(schema_path)
    except Exception:
        return set()
    defs = obj.get("$defs") if isinstance(obj, dict) else None
    if not isinstance(defs, dict):
        return set()
    types: set[str] = set()
    for key, val in defs.items():
        if not isinstance(key, str) or not key.startswith("step_"):
            continue
        if not isinstance(val, dict):
            continue
        props = val.get("properties") if isinstance(val.get("properties"), dict) else None
        type_prop = props.get("type") if isinstance(props, dict) else None
        if isinstance(type_prop, dict):
            const = type_prop.get("const")
            if isinstance(const, str):
                types.add(const)
            enum = type_prop.get("enum")
            if isinstance(enum, list):
                for item in enum:
                    if isinstance(item, str):
                        types.add(item)
    return types


def _parse_unknown_step_types(message: str) -> list[str]:
    if not isinstance(message, str) or not message.strip():
        return []
    _, _, tail = message.partition(":")
    raw = tail if tail else message
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts


def _self_heal_unknown_step_actions(
    *,
    actions_reg: dict[str, Any],
    supported_types: set[str],
    roadmap_milestones: set[str],
    completed_milestones: set[str],
) -> dict[str, Any]:
    actions = actions_reg.get("actions")
    if not isinstance(actions, list):
        return {"changed": False, "resolved": 0, "kept": 0, "reasons": []}

    changed = False
    resolved = 0
    kept = 0
    reasons: list[str] = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        if a.get("kind") != "UNKNOWN_STEP_TYPES":
            continue
        if a.get("resolved") is True:
            continue
        msg = str(a.get("message") or "")
        unknown = _parse_unknown_step_types(msg)
        if not unknown:
            kept += 1
            reasons.append("UNKNOWN_STEP_TYPES_NO_PARSE")
            continue
        if not all(t in supported_types for t in unknown):
            kept += 1
            reasons.append("UNKNOWN_STEP_TYPES_STILL_UNSUPPORTED")
            continue
        mid = a.get("milestone_hint")
        if not isinstance(mid, str) or mid not in roadmap_milestones or mid not in completed_milestones:
            kept += 1
            reasons.append("UNKNOWN_STEP_TYPES_NOT_COMPLETED")
            continue
        a["resolved"] = True
        if a.get("severity") != "WARN":
            a["severity"] = "WARN"
        resolved += 1
        changed = True

    if changed:
        actions_reg["actions"] = sorted(
            [x for x in actions if isinstance(x, dict)],
            key=lambda x: str(x.get("action_id") or ""),
        )

    return {"changed": changed, "resolved": resolved, "kept": kept, "reasons": sorted(set(reasons))}


def _milestone_has_apply_only_steps(*, roadmap_obj: dict[str, Any], milestone_id: str) -> bool:
    milestones = roadmap_obj.get("milestones")
    if not isinstance(milestones, list):
        return False
    for ms in milestones:
        if not isinstance(ms, dict):
            continue
        if ms.get("id") != milestone_id:
            continue
        deliverables = ms.get("steps") if isinstance(ms.get("steps"), list) else ms.get("deliverables")
        if not isinstance(deliverables, list):
            deliverables = []
        for st in deliverables:
            if not isinstance(st, dict):
                continue
            if st.get("apply_only") is not True:
                continue
            if st.get("type") in {"run_cmd", "assert_paths_exist"}:
                return True
        return False
    return False


def _action_register_has_placeholder(*, actions_reg: dict[str, Any], milestone_id: str) -> bool:
    actions = actions_reg.get("actions")
    if not isinstance(actions, list):
        return False
    for a in actions:
        if not isinstance(a, dict):
            continue
        if a.get("kind") != "PLACEHOLDER_MILESTONE":
            continue
        if a.get("milestone_hint") != milestone_id:
            continue
        if a.get("resolved") is True:
            continue
        return True
    return False


def _m0_m1_markers_present(*, workspace_root: Path, milestone_id: str) -> bool:
    if milestone_id == "M0":
        required = [
            "tenant/TENANT-DEFAULT/.gitkeep",
            "formats/.gitkeep",
            "packs/.gitkeep",
            "best_practices/.gitkeep",
            "incubator/.gitkeep",
        ]
    elif milestone_id == "M1":
        required = [
            "tenant/TENANT-DEFAULT/context.v1.md",
            "tenant/TENANT-DEFAULT/stakeholders.v1.md",
            "tenant/TENANT-DEFAULT/scope.v1.md",
            "tenant/TENANT-DEFAULT/criteria.v1.md",
        ]
    else:
        return True
    return all((workspace_root / p).exists() for p in required)


def _remove_completed_milestone(state: dict[str, Any], *, milestone_id: str) -> None:
    completed = state.get("completed_milestones")
    if isinstance(completed, list):
        state["completed_milestones"] = [m for m in completed if str(m) != milestone_id]
    attempts = state.get("attempts")
    if isinstance(attempts, dict):
        attempts[milestone_id] = 0
    meta = state.get("completed_milestones_meta")
    if isinstance(meta, dict):
        meta.pop(milestone_id, None)
    if state.get("current_milestone") == milestone_id:
        state["current_milestone"] = None


def _detect_roadmap_drift_and_update_state(
    *,
    state: dict[str, Any],
    roadmap_path: Path,
    workspace_root: Path,
    roadmap_obj: dict[str, Any],
    actions_reg: dict[str, Any] | None,
) -> dict[str, Any]:
    current_sha = _sha256_file(roadmap_path)
    old_sha_raw = state.get("roadmap_sha256")
    old_sha = old_sha_raw if _is_sha256_hex(old_sha_raw) else None

    completed_raw = state.get("completed_milestones", [])
    completed = [str(x) for x in completed_raw] if isinstance(completed_raw, list) else []

    drift_detected = False
    drift_reason: str | None = None
    if old_sha is not None and old_sha != current_sha:
        drift_detected = True
        drift_reason = "ROADMAP_SHA_CHANGED"
    elif old_sha is None and completed:
        drift_detected = True
        drift_reason = "ROADMAP_SHA_MISSING"

    if drift_detected:
        state["last_roadmap_sha256"] = old_sha
    state["roadmap_sha256"] = current_sha
    state["drift_detected"] = bool(drift_detected)

    stale_milestones: list[str] = []
    stale_reset: list[str] = []
    if drift_detected:
        meta = state.get("completed_milestones_meta")
        if not isinstance(meta, dict):
            meta = {}
            state["completed_milestones_meta"] = meta

        for m in completed:
            entry = meta.get(m)
            sha_at = entry.get("roadmap_sha256_at_completion") if isinstance(entry, dict) else None
            if sha_at != current_sha:
                stale_milestones.append(m)

        actions_reg = actions_reg or {"actions": []}
        for m in sorted(set(stale_milestones)):
            if m in {"M0", "M1"} and _m0_m1_markers_present(workspace_root=workspace_root, milestone_id=m):
                continue
            placeholder_hit = _action_register_has_placeholder(actions_reg=actions_reg, milestone_id=m)
            apply_only_hit = _milestone_has_apply_only_steps(roadmap_obj=roadmap_obj, milestone_id=m)
            if placeholder_hit or apply_only_hit or (m in {"M0", "M1"}):
                _remove_completed_milestone(state, milestone_id=m)
                stale_reset.append(m)

    return {
        "roadmap_sha256": current_sha,
        "last_roadmap_sha256": old_sha,
        "drift_detected": bool(drift_detected),
        "drift_reason": drift_reason,
        "stale_milestones": sorted(set(stale_milestones)),
        "stale_reset_milestones": sorted(set(stale_reset)),
    }


def _script_budget_action_id(*, status: str, path: str, soft: int | None, hard: int | None) -> str:
    soft_s = str(int(soft)) if isinstance(soft, int) else "null"
    hard_s = str(int(hard)) if isinstance(hard, int) else "null"
    seed = f"SCRIPT_BUDGET|{status}|{path}|{soft_s}/{hard_s}"
    return _sha256_hex(seed)[:16]


def _upsert_actions(reg: dict[str, Any], new_actions: list[dict[str, Any]]) -> None:
    actions_raw = reg.get("actions")
    existing: list[dict[str, Any]] = [a for a in actions_raw if isinstance(a, dict)] if isinstance(actions_raw, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for a in existing:
        aid = a.get("action_id")
        if isinstance(aid, str) and aid:
            by_id[aid] = a

    for a in new_actions:
        if not isinstance(a, dict):
            continue
        aid = a.get("action_id")
        if not isinstance(aid, str) or not aid:
            continue
        by_id[aid] = a

    reg["actions"] = sorted(by_id.values(), key=lambda x: str(x.get("action_id") or ""))

def _add_actions(reg: dict[str, Any], new_actions: list[dict[str, Any]]) -> None:
    actions = reg.get("actions")
    if not isinstance(actions, list):
        actions = []
        reg["actions"] = actions
    existing_ids = {a.get("action_id") for a in actions if isinstance(a, dict)}
    for a in new_actions:
        if not isinstance(a, dict):
            continue
        aid = a.get("action_id")
        if not isinstance(aid, str) or not aid:
            continue
        if aid in existing_ids:
            continue
        actions.append(a)
        existing_ids.add(aid)
    actions.sort(key=lambda x: str(x.get("action_id") or ""))


def _known_step_types() -> set[str]:
    # Must match roadmap executor dispatch table.
    return {
        "note",
        "workspace_root_guard",
        "write_file_allowlist",
        "create_file",
        "ensure_dir",
        "patch_file",
        "create_json_from_template",
        "add_schema_file",
        "add_ci_gate_script",
        "patch_policy_report_inject",
        "change_proposal_apply",
        "incubator_sanitize_scan",
        "run_cmd",
        "assert_paths_exist",
        "assert_core_paths_exist",
        "assert_pointer_target_exists",
        "iso_core_check",
    }


def _step_target_summary(tpl: dict[str, Any]) -> dict[str, Any]:
    t = tpl.get("type")
    if not isinstance(t, str):
        return {}
    if t in {"create_file", "ensure_dir", "patch_file", "create_json_from_template", "add_schema_file", "add_ci_gate_script", "patch_policy_report_inject"}:
        p = tpl.get("path") if "path" in tpl else tpl.get("target")
        return {"path": str(p) if isinstance(p, str) else None}
    if t == "assert_paths_exist":
        paths = tpl.get("paths")
        return {"paths_count": len(paths) if isinstance(paths, list) else 0}
    if t == "run_cmd":
        cmd = tpl.get("cmd")
        return {"cmd": str(cmd) if isinstance(cmd, str) else None}
    if t in {"note", "workspace_root_guard", "write_file_allowlist", "change_proposal_apply", "incubator_sanitize_scan", "iso_core_check"}:
        return {}
    return {}


def _risk_reasons_for_step(tpl: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    t = tpl.get("type")
    if not isinstance(t, str):
        return ["MISSING_TYPE"]

    if t == "run_cmd":
        reasons.append("RUN_CMD")
    if t in {"patch_file", "patch_policy_report_inject"}:
        reasons.append("PATCH")

    # Path-based risk: these prefixes represent control-plane/infra surface area.
    risky_prefixes = (
        "policies/",
        "schemas/",
        "ci/",
        "roadmaps/",
        "src/roadmap/",
        "src/tools/",
        "src/ops/",
    )
    target_path = None
    if isinstance(tpl.get("path"), str):
        target_path = tpl.get("path")
    if target_path is None and isinstance(tpl.get("target"), str):
        target_path = tpl.get("target")
    if isinstance(target_path, str):
        norm = target_path.replace("\\", "/").lstrip("/")
        for pref in risky_prefixes:
            if norm == pref.rstrip("/") or norm.startswith(pref):
                reasons.append(f"TOUCHES_{pref.rstrip('/').upper()}")
                break
    return reasons


def _eval_level_for_step(tpl: dict[str, Any]) -> str:
    # v0.2: deterministic heuristics only (no LLM).
    reasons = _risk_reasons_for_step(tpl)
    if any(r in {"RUN_CMD", "PATCH"} or r.startswith("TOUCHES_") for r in reasons):
        return "deep"
    return "short"


def _render_deep_analysis(step: dict[str, Any]) -> str:
    step_id = step.get("step_id")
    ms_id = step.get("milestone_id")
    phase = step.get("phase")
    tpl = step.get("template") if isinstance(step.get("template"), dict) else {}
    tpl_type = tpl.get("type")
    reasons = _risk_reasons_for_step(tpl)
    target = _step_target_summary(tpl)

    lines: list[str] = []
    lines.append("# Step Analysis (deep)\n")
    lines.append(f"- step_id: `{step_id}`\n")
    lines.append(f"- milestone_id: `{ms_id}`\n")
    lines.append(f"- phase: `{phase}`\n")
    lines.append(f"- template.type: `{tpl_type}`\n")
    if target:
        lines.append("\n## Target\n")
        lines.append("```json\n")
        lines.append(json.dumps(target, ensure_ascii=False, sort_keys=True, indent=2))
        lines.append("\n```\n")
    lines.append("\n## Risk Reasons\n")
    for r in reasons:
        lines.append(f"- {r}\n")
    lines.append("\n## Suggested Checks\n")
    lines.append("- `python ci/validate_schemas.py`\n")
    lines.append("- `python -m src.ops.manage smoke --level fast`\n")
    lines.append("- `python -m src.ops.manage policy-check --source fixtures`\n")
    return "".join(lines)


def _compile_preview_plan(*, core_root: Path, roadmap_path: Path, milestone_id: str) -> dict[str, Any]:
    from src.roadmap.compiler import compile_roadmap

    schema_path = core_root / "schemas" / "roadmap.schema.json"
    res = compile_roadmap(
        roadmap_path=roadmap_path,
        schema_path=schema_path,
        cache_root=core_root / ".cache",
        out_path=None,
        milestone_ids=[milestone_id],
    )
    return res.plan


def _build_milestone_preview(*, roadmap_obj: dict[str, Any], milestone_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    title = ""
    for ms in roadmap_obj.get("milestones", []) if isinstance(roadmap_obj.get("milestones"), list) else []:
        if isinstance(ms, dict) and ms.get("id") == milestone_id:
            title = str(ms.get("title") or "")
            break

    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    known = _known_step_types()
    step_summaries: list[dict[str, Any]] = []
    unknown_types: list[str] = []
    for st in steps:
        if not isinstance(st, dict):
            continue
        tpl = st.get("template") if isinstance(st.get("template"), dict) else {}
        tpl_type = tpl.get("type")
        if isinstance(tpl_type, str) and tpl_type not in known and tpl_type not in unknown_types:
            unknown_types.append(tpl_type)
        eval_level = _eval_level_for_step(tpl)
        step_summaries.append(
            {
                "step_id": st.get("step_id"),
                "phase": st.get("phase"),
                "template_type": tpl_type,
                "eval_level": eval_level,
                "target": _step_target_summary(tpl),
                "risk_reasons": _risk_reasons_for_step(tpl),
            }
        )

    return {
        "milestone_id": milestone_id,
        "title": title,
        "steps_count": len(step_summaries),
        "unknown_step_types": sorted(unknown_types),
        "steps": step_summaries,
    }


def _derive_actions_for_milestone(*, milestone_id: str, preview: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    unknown = preview.get("unknown_step_types")
    if isinstance(unknown, list) and unknown:
        msg = "Unknown roadmap step types: " + ", ".join(sorted(str(x) for x in unknown))
        actions.append(
            {
                "action_id": _action_id("UNKNOWN_STEP_TYPES", msg),
                "severity": "FAIL",
                "kind": "UNKNOWN_STEP_TYPES",
                "milestone_hint": milestone_id,
                "message": msg,
            }
        )

    steps = preview.get("steps")
    if isinstance(steps, list):
        deliverables = [s for s in steps if isinstance(s, dict) and s.get("phase") == "DELIVERABLE"]
        only_notes = bool(deliverables) and all(d.get("template_type") == "note" for d in deliverables)
        if only_notes:
            msg = f"Milestone {milestone_id} appears to be placeholder-only (deliverables are note steps)."
            actions.append(
                {
                    "action_id": _action_id("PLACEHOLDER_MILESTONE", msg),
                    "severity": "WARN",
                    "kind": "PLACEHOLDER_MILESTONE",
                    "milestone_hint": milestone_id,
                    "message": msg,
                }
            )
    return actions


def _derive_actions_from_script_budget(core_root: Path) -> list[dict[str, Any]]:
    # Legacy hook: roadmap-finish now runs the checker and derives detailed actions.
    return []


def _run_script_budget_checker(*, core_root: Path) -> tuple[str, dict[str, Any]]:
    report_path = (core_root / ".cache" / "script_budget" / "report.json").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(core_root / "ci" / "check_script_budget.py"), "--out", str(report_path)],
        cwd=core_root,
        text=True,
        capture_output=True,
    )
    try:
        obj = _load_json(report_path) if report_path.exists() else {}
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}

    status = obj.get("status")
    if status not in {"OK", "WARN", "FAIL"}:
        status = "FAIL" if proc.returncode != 0 else "WARN"
    obj.setdefault("status", status)
    return (str(status), obj)

def _run_quality_gate_checker(*, core_root: Path, workspace_root: Path) -> tuple[str, dict[str, Any]]:
    try:
        from src.quality.quality_gate import evaluate_quality_gate
    except Exception as e:
        msg = str(e)[:300]
        report = {"status": "FAIL", "error_code": "QUALITY_GATE_IMPORT_FAILED", "message": msg}
        return ("FAIL", report)

    try:
        report = evaluate_quality_gate(workspace_root=workspace_root, core_root=core_root)
    except Exception as e:
        msg = str(e)[:300]
        report = {"status": "FAIL", "error_code": "QUALITY_GATE_EXCEPTION", "message": msg}

    if not isinstance(report, dict):
        report = {"status": "FAIL", "error_code": "QUALITY_GATE_INVALID_REPORT"}
    status = report.get("status")
    if status not in {"OK", "WARN", "FAIL"}:
        status = "FAIL"
    report.setdefault("status", status)
    return (str(status), report)


def _quality_gate_warn_action_from_report(report: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    if report.get("status") != "WARN":
        return None

    missing = report.get("missing") if isinstance(report.get("missing"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    missing_s = sorted({str(x) for x in missing if isinstance(x, str) and x})
    warnings_s = sorted({str(x) for x in warnings if isinstance(x, str) and x})

    details = {"missing": missing_s[:10], "warnings": warnings_s[:10]}
    title = "Quality gate warnings"
    msg_parts: list[str] = []
    if details["missing"]:
        msg_parts.append("missing=" + ",".join(details["missing"][:5]))
    if details["warnings"]:
        msg_parts.append("warnings=" + ",".join(details["warnings"][:5]))
    msg = (title + (": " + " ".join(msg_parts) if msg_parts else ""))[:300]

    seed = "QUALITY_GATE|WARN|" + "|".join(details["missing"] + details["warnings"])
    action_id = _sha256_hex(seed)[:16]

    return {
        "action_id": action_id,
        "severity": "WARN",
        "kind": "QUALITY_GATE_WARN",
        "milestone_hint": "M6",
        "source": "QUALITY_GATE",
        "target_milestone": "M6",
        "title": title,
        "details": details,
        "recommendation": "Run M6 and ensure ISO core docs + formats index exist; keep output standards enforced.",
        "resolved": False,
        "message": msg,
    }


def _run_ops_index_builder(*, core_root: Path, workspace_root: Path) -> tuple[str, dict[str, Any]]:
    try:
        from src.ops.build_ops_index import build_ops_index

        report = build_ops_index(workspace_root=workspace_root, core_root=core_root)
    except Exception as e:
        return ("FAIL", {"status": "FAIL", "error_code": "OPS_INDEX_EXCEPTION", "message": str(e)[:300]})

    status = report.get("status")
    if status == "SKIPPED":
        return ("OK", report)
    if status not in {"OK", "WARN", "FAIL"}:
        status = "FAIL"
        report["status"] = "FAIL"
        report.setdefault("error_code", "OPS_INDEX_INVALID_STATUS")
    return (str(status), report)


def _ops_index_action_from_report(report: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    status = report.get("status")
    if status != "WARN":
        return None
    run_count = report.get("run_count")
    dlq_count = report.get("dlq_count")
    parse_errors = report.get("parse_errors")
    seed = f"OPS_INDEX|{status}"
    action_id = _sha256_hex(seed)[:16]
    msg = f"Ops index WARN: runs={run_count} dlq={dlq_count} parse_errors={parse_errors}"
    return {
        "action_id": action_id,
        "severity": "WARN",
        "kind": "OPS_INDEX_WARN",
        "milestone_hint": "M6.6",
        "source": "OPS_INDEX",
        "target_milestone": "M6.6",
        "title": "Ops index produced with warnings",
        "details": {
            "run_count": run_count,
            "dlq_count": dlq_count,
            "parse_errors": parse_errors,
        },
        "recommendation": "Keep scans bounded; review parse errors and index sources.",
        "resolved": False,
        "message": msg[:300],
    }


@dataclass(frozen=True)
class _ArtifactCheck:
    check_id: str
    path: str
    owner_milestone: str
    severity: str
    auto_heal: bool


def _pack_manifest_sha_map(core_root: Path, workspace_root: Path) -> dict[str, str]:
    manifests: list[Path] = []
    core_dir = core_root / "packs"
    if core_dir.exists():
        manifests.extend(sorted(core_dir.rglob("pack.manifest.v1.json")))
    ws_dir = workspace_root / "packs"
    if ws_dir.exists():
        manifests.extend(sorted(ws_dir.rglob("pack.manifest.v1.json")))
    sha_map: dict[str, str] = {}
    for path in manifests:
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except Exception:
            continue
        try:
            obj = _load_json(path)
        except Exception:
            continue
        pack_id = obj.get("pack_id") if isinstance(obj, dict) else None
        if not isinstance(pack_id, str):
            continue
        sha_map[pack_id] = sha256(data).hexdigest()
    return sha_map


def _pack_list_sha(sha_map: dict[str, str]) -> str | None:
    if not sha_map:
        return None
    payload = "\n".join(f"{pid}:{sha_map.get(pid, '')}" for pid in sorted(sha_map)).encode("utf-8")
    return sha256(payload).hexdigest()


def _pack_validation_report_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "pack_validation_report.json"


def _run_pack_validation(
    *,
    core_root: Path,
    workspace_root: Path,
    logs: list[str],
) -> tuple[dict[str, Any] | None, str, int]:
    report_path = _pack_validation_report_path(workspace_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    cmd = [
        sys.executable,
        "-m",
        "ci.validate_pack_manifest",
        "--workspace-root",
        str(workspace_root),
        "--out",
        str(report_path),
    ]
    res = _run_cmd(core_root, cmd, env=env)
    report_obj: dict[str, Any] | None = None
    if report_path.exists():
        try:
            report_obj = _load_json(report_path)
        except Exception as e:
            logs.append("PACK_VALIDATION_REPORT_INVALID " + str(e)[:200] + "\n")
    return (report_obj, str(report_path), res.returncode)


def _pack_conflict_action(
    *,
    kind: str,
    severity: str,
    report_path: str,
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    top = conflicts[:3] if isinstance(conflicts, list) else []
    details = []
    for c in top:
        if not isinstance(c, dict):
            continue
        label = c.get("kind") or c.get("intent") or c.get("capability_id") or c.get("format_id") or ""
        if isinstance(label, str) and label:
            details.append(label)
    detail_text = ", ".join(details)
    msg = f"Pack conflicts detected; see {report_path}."
    if detail_text:
        msg += " Top: " + detail_text
    return {
        "action_id": _sha256_hex(f"{kind}|{report_path}|{len(conflicts)}")[:16],
        "kind": kind,
        "severity": severity,
        "milestone_hint": "M9.2",
        "title": "Pack conflict detected",
        "message": msg,
        "resolved": False,
    }


@dataclass(frozen=True)
class _DebtPolicy:
    enabled: bool
    max_items: int
    outdir: str
    mode: str
    max_auto_apply_per_finish: int
    safe_action_kinds: tuple[str, ...]
    require_sanitize_pass: bool
    recheck_system_status: bool
    on_apply_fail: str


def _load_debt_policy(*, core_root: Path, workspace_root: Path) -> _DebtPolicy:
    defaults = _DebtPolicy(
        enabled=False,
        max_items=3,
        outdir=".cache/debt_chg",
        mode="draft_only",
        max_auto_apply_per_finish=1,
        safe_action_kinds=("DOC_NOTE", "TEMPLATE_ADD", "ADD_IGNORE"),
        require_sanitize_pass=True,
        recheck_system_status=True,
        on_apply_fail="warn",
    )
    ws_policy = workspace_root / "policies" / "policy_debt.v1.json"
    core_policy = core_root / "policies" / "policy_debt.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults
    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults
    enabled = bool(obj.get("enabled", defaults.enabled))
    try:
        max_items = int(obj.get("max_items", defaults.max_items))
    except Exception:
        max_items = defaults.max_items
    outdir = obj.get("outdir", defaults.outdir)
    if not isinstance(outdir, str) or not outdir.strip():
        outdir = defaults.outdir
    mode = obj.get("mode", defaults.mode)
    if mode not in {"draft_only", "safe_apply"}:
        mode = defaults.mode
    try:
        max_auto = int(obj.get("max_auto_apply_per_finish", defaults.max_auto_apply_per_finish))
    except Exception:
        max_auto = defaults.max_auto_apply_per_finish
    safe_action_kinds = obj.get("safe_action_kinds", list(defaults.safe_action_kinds))
    if not isinstance(safe_action_kinds, list) or not safe_action_kinds:
        safe_action_kinds = list(defaults.safe_action_kinds)
    safe_action_kinds_clean = tuple(sorted({str(x) for x in safe_action_kinds if isinstance(x, str) and x.strip()}))
    if not safe_action_kinds_clean:
        safe_action_kinds_clean = defaults.safe_action_kinds
    require_sanitize_pass = bool(obj.get("require_sanitize_pass", defaults.require_sanitize_pass))
    recheck_system_status = bool(obj.get("recheck_system_status", defaults.recheck_system_status))
    on_apply_fail = obj.get("on_apply_fail", defaults.on_apply_fail)
    if on_apply_fail not in {"warn", "block"}:
        on_apply_fail = defaults.on_apply_fail
    return _DebtPolicy(
        enabled=enabled,
        max_items=max(0, max_items),
        outdir=str(outdir),
        mode=str(mode),
        max_auto_apply_per_finish=max(0, max_auto),
        safe_action_kinds=safe_action_kinds_clean,
        require_sanitize_pass=require_sanitize_pass,
        recheck_system_status=recheck_system_status,
        on_apply_fail=str(on_apply_fail),
    )


@dataclass(frozen=True)
class _CoreImmutabilityPolicy:
    enabled: bool
    default_mode: str
    allow_env_var: str
    allow_env_value: str
    evidence_required_when_unlocked: bool
    blocked_write_error_code: str
    core_git_required: bool


def _load_core_immutability_policy(*, core_root: Path, workspace_root: Path) -> _CoreImmutabilityPolicy:
    defaults = _CoreImmutabilityPolicy(
        enabled=True,
        default_mode="locked",
        allow_env_var="CORE_UNLOCK",
        allow_env_value="1",
        evidence_required_when_unlocked=True,
        blocked_write_error_code="CORE_IMMUTABLE_WRITE_BLOCKED",
        core_git_required=True,
    )
    ws_policy = workspace_root / "policies" / "policy_core_immutability.v1.json"
    core_policy = core_root / "policies" / "policy_core_immutability.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults
    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults
    enabled = bool(obj.get("enabled", defaults.enabled))
    default_mode = obj.get("default_mode", defaults.default_mode)
    if default_mode not in {"locked"}:
        default_mode = defaults.default_mode
    allow_obj = obj.get("allow_core_writes_only_when", {})
    if not isinstance(allow_obj, dict):
        allow_obj = {}
    allow_env_var = allow_obj.get("env_var", defaults.allow_env_var)
    allow_env_value = allow_obj.get("env_value", defaults.allow_env_value)
    if not isinstance(allow_env_var, str) or not allow_env_var.strip():
        allow_env_var = defaults.allow_env_var
    if not isinstance(allow_env_value, str) or not allow_env_value.strip():
        allow_env_value = defaults.allow_env_value
    evidence_required_when_unlocked = bool(
        obj.get("evidence_required_when_unlocked", defaults.evidence_required_when_unlocked)
    )
    blocked_write_error_code = obj.get("blocked_write_error_code", defaults.blocked_write_error_code)
    if not isinstance(blocked_write_error_code, str) or not blocked_write_error_code.strip():
        blocked_write_error_code = defaults.blocked_write_error_code
    core_git_required = bool(obj.get("core_git_required", defaults.core_git_required))
    return _CoreImmutabilityPolicy(
        enabled=enabled,
        default_mode=str(default_mode),
        allow_env_var=str(allow_env_var),
        allow_env_value=str(allow_env_value),
        evidence_required_when_unlocked=evidence_required_when_unlocked,
        blocked_write_error_code=str(blocked_write_error_code),
        core_git_required=core_git_required,
    )


def _core_unlock_requested(policy: _CoreImmutabilityPolicy) -> bool:
    return str(os.environ.get(policy.allow_env_var, "")).strip() == str(policy.allow_env_value)


def _core_immutability_check(
    *, core_root: Path, policy: _CoreImmutabilityPolicy, baseline: str | None
) -> tuple[bool, str | None, list[str]]:
    if not policy.enabled:
        return (True, None, [])
    if baseline is None and policy.core_git_required:
        return (False, "GIT_REQUIRED", [])
    lines = _git_status_lines(core_root)
    if lines is None:
        return (True, None, []) if not policy.core_git_required else (False, "GIT_REQUIRED", [])
    if not lines:
        return (True, None, [])
    baseline_lines = [line.strip() for line in (baseline or "").splitlines() if line.strip()]
    new_lines = [line for line in lines if line not in baseline_lines]
    if not new_lines:
        return (True, None, [])
    if _core_unlock_requested(policy) and policy.default_mode == "locked":
        return (True, None, new_lines)
    return (False, policy.blocked_write_error_code, new_lines)


def _core_touched_action(*, error_code: str, paths: list[str]) -> dict[str, Any]:
    seed = "CORE_TOUCHED|" + error_code + "|" + "|".join(sorted(paths))
    msg = "Core repo became dirty during workspace run; aborting (fail-closed)."
    if error_code == "GIT_REQUIRED":
        msg = "Core git status unavailable; aborting (fail-closed)."
    return {
        "action_id": _sha256_hex(seed)[:16],
        "kind": "CORE_TOUCHED",
        "severity": "FAIL",
        "milestone_hint": "M0",
        "title": "Core repo integrity violation",
        "message": msg,
        "details": {"error_code": error_code, "paths": paths},
        "resolved": False,
    }


def _system_status_include_repo_hygiene_suggestions(*, core_root: Path, workspace_root: Path) -> bool:
    ws_policy = workspace_root / "policies" / "policy_system_status.v1.json"
    core_policy = core_root / "policies" / "policy_system_status.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return False
    try:
        obj = _load_json(policy_path)
    except Exception:
        return False
    if not isinstance(obj, dict):
        return False
    return bool(obj.get("include_repo_hygiene_suggestions", False))


def _system_status_snapshot_from_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    out_json = result.get("out_json")
    if not isinstance(out_json, str) or not out_json:
        return None
    out_path = Path(out_json)
    if not out_path.exists():
        return None
    try:
        snap = _load_json(out_path)
    except Exception:
        return None
    return snap if isinstance(snap, dict) else None


def _extract_repo_hygiene_count(snapshot: dict[str, Any] | None) -> int | None:
    if not isinstance(snapshot, dict):
        return None
    sections = snapshot.get("sections") if isinstance(snapshot.get("sections"), dict) else None
    if not isinstance(sections, dict):
        return None
    repo = sections.get("repo_hygiene") if isinstance(sections.get("repo_hygiene"), dict) else None
    if not isinstance(repo, dict):
        return None
    count = repo.get("tracked_generated_files")
    return int(count) if isinstance(count, int) else None


def _extract_quality_status(snapshot: dict[str, Any] | None) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    sections = snapshot.get("sections") if isinstance(snapshot.get("sections"), dict) else None
    if not isinstance(sections, dict):
        return None
    quality = sections.get("quality_gate") if isinstance(sections.get("quality_gate"), dict) else None
    if not isinstance(quality, dict):
        return None
    status = quality.get("status")
    return status if isinstance(status, str) else None


def _load_artifact_completeness_policy(*, core_root: Path, workspace_root: Path) -> tuple[bool, list[_ArtifactCheck]]:
    defaults = [
        _ArtifactCheck("formats_index", ".cache/index/formats.v1.json", "M2.5", "warn", True),
        _ArtifactCheck("catalog_index", ".cache/index/catalog.v1.json", "M3", "warn", True),
        _ArtifactCheck("session_context", ".cache/sessions/default/session_context.v1.json", "M3.5", "warn", True),
        _ArtifactCheck("ops_run_index", ".cache/index/run_index.v1.json", "M6.6", "warn", True),
        _ArtifactCheck("ops_dlq_index", ".cache/index/dlq_index.v1.json", "M6.6", "warn", True),
        _ArtifactCheck("harvest_cursor", ".cache/learning/harvest_cursor.v1.json", "M6.7", "warn", True),
        _ArtifactCheck("advisor_suggestions", ".cache/learning/advisor_suggestions.v1.json", "M7", "warn", False),
        _ArtifactCheck("readiness_report", ".cache/ops/autopilot_readiness.v1.json", "M8", "warn", False),
        _ArtifactCheck("system_status", ".cache/reports/system_status.v1.json", "M8.1", "warn", False),
    ]

    ws_policy = workspace_root / "policies" / "policy_artifact_completeness.v1.json"
    core_policy = core_root / "policies" / "policy_artifact_completeness.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return (True, defaults)

    try:
        obj = _load_json(policy_path)
    except Exception:
        return (True, defaults)
    if not isinstance(obj, dict):
        return (True, defaults)

    enabled = bool(obj.get("enabled", True))
    raw_checks = obj.get("checks")
    if not isinstance(raw_checks, list):
        return (enabled, defaults)

    out: list[_ArtifactCheck] = []
    for item in raw_checks:
        if not isinstance(item, dict):
            continue
        check_id = item.get("id")
        path = item.get("path")
        owner = item.get("owner_milestone")
        if not (isinstance(check_id, str) and isinstance(path, str) and isinstance(owner, str)):
            continue
        severity = item.get("severity", "warn")
        if severity not in {"warn", "block"}:
            severity = "warn"
        auto_heal = bool(item.get("auto_heal", False))
        out.append(_ArtifactCheck(check_id.strip(), path.strip(), owner.strip(), str(severity), auto_heal))

    if not out:
        out = defaults
    out.sort(key=lambda c: c.check_id)
    return (enabled, out)


def _promotion_outputs_exist(workspace_root: Path) -> bool:
    required = [
        ".cache/promotion/promotion_bundle.v1.zip",
        ".cache/promotion/promotion_report.v1.json",
        ".cache/promotion/core_patch_summary.v1.md",
    ]
    return all((workspace_root / p).exists() for p in required)


def _incubator_has_files(workspace_root: Path) -> bool:
    incubator_root = workspace_root / "incubator"
    if not incubator_root.exists():
        return False
    for root, _, files in os.walk(incubator_root):
        if files:
            return True
    return False


def _ensure_promotion_seed_note(workspace_root: Path) -> tuple[bool, str | None]:
    note_path = workspace_root / "incubator" / "notes" / "PROMOTION_SEED.md"
    content = "Promotion seed note (auto-generated).\n"
    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        if existing == content:
            return (False, str(note_path))
        raise ValueError("CONTENT_MISMATCH")
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return (True, str(note_path))


def _artifact_missing(
    *, checks: list[_ArtifactCheck], workspace_root: Path
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for chk in checks:
        rel = Path(chk.path)
        target = (workspace_root / rel).resolve()
        if not target.exists():
            missing.append(
                {
                    "id": chk.check_id,
                    "path": chk.path,
                    "owner_milestone": chk.owner_milestone,
                    "severity": chk.severity,
                    "auto_heal": chk.auto_heal,
                }
            )
    missing.sort(key=lambda x: str(x.get("id") or ""))
    return missing


def _artifact_missing_action(item: dict[str, Any]) -> dict[str, Any]:
    check_id = str(item.get("id") or "")
    path = str(item.get("path") or "")
    owner = str(item.get("owner_milestone") or "")
    severity = "WARN" if item.get("severity") != "block" else "FAIL"
    msg = f"Missing derived artifact: {check_id} path={path} owner={owner}"
    return {
        "action_id": _sha256_hex(f"DERIVED_ARTIFACT_MISSING|{check_id}|{path}|{owner}")[:16],
        "severity": severity,
        "kind": "DERIVED_ARTIFACT_MISSING",
        "milestone_hint": owner,
        "source": "ARTIFACT_COMPLETENESS",
        "title": "Derived artifact missing",
        "details": {
            "id": check_id,
            "path": path,
            "owner_milestone": owner,
            "severity": item.get("severity"),
            "auto_heal": bool(item.get("auto_heal")),
        },
        "message": msg[:300],
        "resolved": False,
    }


def _artifact_heal_failed_action(item: dict[str, Any]) -> dict[str, Any]:
    check_id = str(item.get("id") or "")
    path = str(item.get("path") or "")
    owner = str(item.get("owner_milestone") or "")
    msg = f"Auto-heal failed for derived artifact: {check_id} path={path} owner={owner}"
    return {
        "action_id": _sha256_hex(f"DERIVED_ARTIFACT_HEAL_FAILED|{check_id}|{path}|{owner}")[:16],
        "severity": "WARN",
        "kind": "DERIVED_ARTIFACT_HEAL_FAILED",
        "milestone_hint": owner,
        "source": "ARTIFACT_COMPLETENESS",
        "title": "Derived artifact auto-heal failed",
        "details": {
            "id": check_id,
            "path": path,
            "owner_milestone": owner,
        },
        "message": msg[:300],
        "resolved": False,
    }


def _script_budget_actions_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    status = report.get("status")
    if status not in {"OK", "WARN", "FAIL"}:
        return []

    exceeded_soft = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
    exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []

    offenders: list[dict[str, Any]] = []
    for item in exceeded_hard:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            offenders.append({**item, "_severity": "HARD"})
    for item in exceeded_soft:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            offenders.append({**item, "_severity": "SOFT"})

    def offender_key(x: dict[str, Any]) -> tuple[int, int, str]:
        sev = 0 if x.get("_severity") == "HARD" else 1
        lines = x.get("lines")
        lines_i = int(lines) if isinstance(lines, int) else -1
        return (sev, -lines_i, str(x.get("path") or ""))

    offenders.sort(key=offender_key)
    limit = 0
    if status == "WARN":
        limit = 3
    elif status == "FAIL":
        limit = 5
    else:
        limit = 0
    offenders = offenders[:limit]

    out: list[dict[str, Any]] = []
    for o in offenders:
        path = str(o.get("path") or "")
        lines = o.get("lines")
        soft = o.get("soft")
        hard = o.get("hard")
        gf_note = None
        if str(o.get("error") or "") == "GRANDFATHERED":
            gf_note = "NO_GROWTH enforced; refactor required."
        if str(o.get("error_code") or "") == "PY_FILE_GROWTH_FORBIDDEN":
            gf_note = "NO_GROWTH violated; growth forbidden."

        title = "Script budget soft limit exceeded" if status == "WARN" else "Script budget hard limit exceeded"
        action_type = "MAINTAINABILITY_DEBT" if status == "WARN" else "MAINTAINABILITY_BLOCKER"
        severity = "WARN" if status == "WARN" else ("FAIL" if status == "FAIL" else "INFO")

        details = {
            "path": path,
            "lines": int(lines) if isinstance(lines, int) else None,
            "soft": int(soft) if isinstance(soft, int) else None,
            "hard": int(hard) if isinstance(hard, int) else None,
            "note": gf_note,
        }

        msg = f"{title}: {path} lines={details.get('lines')} soft={details.get('soft')} hard={details.get('hard')}"
        if gf_note:
            msg = msg + f" ({gf_note})"

        out.append(
            {
                "action_id": _script_budget_action_id(status=str(status), path=path, soft=details.get("soft"), hard=details.get("hard")),
                "severity": severity,
                "kind": "SCRIPT_BUDGET",
                "milestone_hint": "M0",
                "type": action_type,
                "source": "SCRIPT_BUDGET",
                "target_milestone": "M0",
                "title": title,
                "details": details,
                "recommendation": "Split into modules (commands/*, smoke/*) to reduce LOC; keep behavior unchanged.",
                "resolved": False,
                "message": msg[:300],
            }
        )

    return out


def _mk_finish_run_id(*, roadmap_path: Path, workspace_root: Path, state_before: dict[str, Any]) -> str:
    seed = "|".join(
        [
            "FINISH",
            str(roadmap_path),
            str(workspace_root),
            _sha256_hex(_to_canonical_json(state_before)),
        ]
    )
    return _sha256_hex(seed)[:16]


def pause(*, workspace_root: Path, reason: str, state_path: Path | None = None) -> dict[str, Any]:
    core_root = _core_root()
    workspace_root = (core_root / workspace_root).resolve() if not workspace_root.is_absolute() else workspace_root.resolve()
    state_path = (
        (workspace_root / ".cache" / "roadmap_state.v1.json").resolve() if state_path is None else state_path.resolve()
    )
    if not state_path.exists():
        return {"status": "FAIL", "error_code": "STATE_NOT_FOUND", "state_path": str(state_path)}

    obj = _load_json(state_path)
    roadmap_path_raw = obj.get("roadmap_path") if isinstance(obj, dict) else None
    if not isinstance(roadmap_path_raw, str) or not roadmap_path_raw:
        return {"status": "FAIL", "error_code": "STATE_INVALID", "state_path": str(state_path)}

    schema_path = core_root / "schemas" / "roadmap-state.schema.json"
    state_res = load_state(
        state_path=state_path,
        schema_path=schema_path,
        roadmap_path=Path(roadmap_path_raw),
        workspace_root=workspace_root,
    )
    state = state_res.state
    pause_state(state, reason=str(reason or "paused"), now=_now_utc())
    clear_backoff(state)
    record_last_result(state, status="FAIL", milestone_id=state.get("current_milestone"), evidence_path=None, error_code="PAUSED")
    save_state(state_path=state_path, state=state)
    return {"status": "OK", "paused": True, "pause_reason": state.get("pause_reason"), "state_path": str(state_path)}


def resume(*, workspace_root: Path, state_path: Path | None = None) -> dict[str, Any]:
    core_root = _core_root()
    workspace_root = (core_root / workspace_root).resolve() if not workspace_root.is_absolute() else workspace_root.resolve()
    state_path = (
        (workspace_root / ".cache" / "roadmap_state.v1.json").resolve() if state_path is None else state_path.resolve()
    )
    if not state_path.exists():
        return {"status": "FAIL", "error_code": "STATE_NOT_FOUND", "state_path": str(state_path)}

    obj = _load_json(state_path)
    roadmap_path_raw = obj.get("roadmap_path") if isinstance(obj, dict) else None
    if not isinstance(roadmap_path_raw, str) or not roadmap_path_raw:
        return {"status": "FAIL", "error_code": "STATE_INVALID", "state_path": str(state_path)}

    schema_path = core_root / "schemas" / "roadmap-state.schema.json"
    state_res = load_state(
        state_path=state_path,
        schema_path=schema_path,
        roadmap_path=Path(roadmap_path_raw),
        workspace_root=workspace_root,
    )
    state = state_res.state
    resume_state(state)
    clear_backoff(state)
    save_state(state_path=state_path, state=state)
    return {"status": "OK", "paused": False, "state_path": str(state_path)}


def finish(
    *,
    roadmap_path: Path,
    workspace_root: Path,
    max_minutes: int = 120,
    sleep_seconds: int = 120,
    max_steps_per_iteration: int = 3,
    auto_apply_chg: bool = False,
) -> dict[str, Any]:
    core_root = _core_root()
    roadmap_path = (core_root / roadmap_path).resolve() if not roadmap_path.is_absolute() else roadmap_path.resolve()
    workspace_root = (core_root / workspace_root).resolve() if not workspace_root.is_absolute() else workspace_root.resolve()

    state_path = (workspace_root / ".cache" / "roadmap_state.v1.json").resolve()
    state_schema = core_root / "schemas" / "roadmap-state.schema.json"

    evidence_root = (core_root / "evidence" / "roadmap_finish").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)

    core_git_baseline = _git_status_porcelain(core_root)

    start_monotonic = time.monotonic()
    deadline_seconds = max(0, int(max_minutes)) * 60

    roadmap_obj = _load_and_validate_roadmap(core_root, roadmap_path)
    roadmap_ids = _roadmap_milestones(roadmap_obj)

    state_res = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    )
    state = state_res.state
    state_before = json.loads(json.dumps(state))

    actions_file = _actions_path(workspace_root)
    actions_reg = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)

    drift_info = _detect_roadmap_drift_and_update_state(
        state=state,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        roadmap_obj=roadmap_obj,
        actions_reg=actions_reg,
    )
    save_state(state_path=state_path, state=state)

    # Bootstrap state deterministically from workspace artifacts (same as follow).
    completed = state.get("completed_milestones", [])
    if not bool(state.get("bootstrapped", False)) or not isinstance(completed, list) or not completed:
        bootstrap_completed_milestones(state=state, workspace_root=workspace_root)
        save_state(state_path=state_path, state=state)
    run_id = _mk_finish_run_id(roadmap_path=roadmap_path, workspace_root=workspace_root, state_before=state_before)
    run_dir = (evidence_root / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    actions_file = _actions_path(workspace_root)
    actions_before = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
    # Ensure the action register exists even if the run terminates early.
    _atomic_write_json(actions_file, actions_before)
    _atomic_write_json(run_dir / "actions_before.json", actions_before)

    iterations: list[dict[str, Any]] = []
    logs: list[str] = []
    chg_generated: list[str] = []
    script_budget_status: str | None = None
    quality_gate_status: str | None = None
    harvest_status: str | None = None
    ops_index_status: str | None = None
    advisor_status: str | None = None
    autopilot_readiness_status: str | None = None
    system_status_status: str | None = None
    system_status_snapshot_before: dict[str, Any] | None = None
    promotion_status: str | None = None
    debt_auto_applied = False
    artifact_completeness: dict[str, Any] | None = None
    pack_conflict_blocked = False
    pack_conflict_report_path = ""
    session_context_hash: str | None = None
    smoke_drift_minimal = os.environ.get("SMOKE_DRIFT_MINIMAL") == "1"
    debt_policy = _load_debt_policy(core_root=core_root, workspace_root=workspace_root)
    core_policy = _load_core_immutability_policy(core_root=core_root, workspace_root=workspace_root)
    auto_apply_remaining = (
        debt_policy.max_auto_apply_per_finish
        if debt_policy.enabled and debt_policy.mode == "safe_apply"
        else 0
    )
    skipped_ingest = [
        "script_budget",
        "quality_gate",
        "ops_index",
        "harvest",
        "artifact_pointer",
        "advisor",
        "autopilot_readiness",
        "system_status",
        "artifact_completeness",
    ] if smoke_drift_minimal else []

    status_payload: dict[str, Any] = status(roadmap_path=roadmap_path, workspace_root=workspace_root, state_path=state_path)
    next_mid = status_payload.get("next_milestone") if isinstance(status_payload, dict) else None

    logs.append(f"roadmap-finish start roadmap={roadmap_path} workspace={workspace_root}\n")
    if bool(state.get("paused", False)):
        logs.append("PAUSED\n")
        out = {
            "status": "DISABLED",
            "next_milestone": next_mid,
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "error_code": "PAUSED",
        }
        write_json(run_dir / "input.json", {"roadmap": str(roadmap_path), "workspace_root": str(workspace_root)})
        write_json(run_dir / "output.json", out)
        write_json(run_dir / "state_before.json", state_before)
        write_json(run_dir / "state_after.json", state)
        write_text(run_dir / "logs.txt", "".join(logs))
        write_integrity_manifest(run_dir)
        return {**out, "evidence": [str(run_dir.relative_to(core_root))]}

    stop_status: str | None = None
    stop_code: str | None = None

    def write_preview_and_analysis(milestone_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        plan = _compile_preview_plan(core_root=core_root, roadmap_path=roadmap_path, milestone_id=milestone_id)
        preview_obj = _build_milestone_preview(roadmap_obj=roadmap_obj, milestone_id=milestone_id, plan=plan)

        previews_dir = run_dir / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        write_json(previews_dir / f"{milestone_id}.json", preview_obj)

        steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            tpl = step.get("template") if isinstance(step.get("template"), dict) else {}
            if _eval_level_for_step(tpl) != "deep":
                continue
            step_id = str(step.get("step_id") or "")
            if not step_id:
                continue
            analysis_text = _render_deep_analysis(step)
            write_text(run_dir / "steps" / step_id / "analysis.md", analysis_text)

        derived_actions: list[dict[str, Any]] = []
        derived_actions.extend(_derive_actions_for_milestone(milestone_id=milestone_id, preview=preview_obj))
        return (plan, preview_obj, derived_actions)

    core_violation_code: str | None = None

    def _enforce_core_clean(*, phase: str) -> tuple[bool, str | None]:
        nonlocal core_violation_code
        ok, code, lines = _core_immutability_check(
            core_root=core_root,
            policy=core_policy,
            baseline=core_git_baseline,
        )
        if ok:
            if _core_unlock_requested(core_policy) and core_policy.evidence_required_when_unlocked and lines:
                write_json(run_dir / "core_dirty_files.json", sorted(lines))
            elif phase == "final":
                write_json(run_dir / "core_dirty_files.json", [])
            return (True, None)
        paths = _git_status_paths(lines)
        write_json(run_dir / "core_dirty_files.json", sorted(lines))
        reg_core = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
        _upsert_actions(reg_core, [_core_touched_action(error_code=str(code), paths=paths)])
        _atomic_write_json(actions_file, reg_core)
        logs.append(f"CORE_WRITE_VIOLATION phase={phase} code={code}\n")
        core_violation_code = str(code) if code else "CORE_WRITE_VIOLATION"
        return (False, core_violation_code)

    # Always ingest Script Budget debt into the workspace Action Register (no network, deterministic).
    if not smoke_drift_minimal:
        script_budget_status, script_budget_report = _run_script_budget_checker(core_root=core_root)
        write_json(run_dir / "script_budget_report.json", script_budget_report)
        sb_actions = _script_budget_actions_from_report(script_budget_report)
        if script_budget_status == "OK":
            # Prefer history: mark any previous SCRIPT_BUDGET items resolved instead of deleting.
            reg0 = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            actions0 = reg0.get("actions")
            if isinstance(actions0, list):
                for a in actions0:
                    if not isinstance(a, dict):
                        continue
                    if a.get("source") == "SCRIPT_BUDGET" or a.get("kind") == "SCRIPT_BUDGET":
                        a["resolved"] = True
            _atomic_write_json(actions_file, reg0)
        elif sb_actions:
            reg0 = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            _upsert_actions(reg0, sb_actions)
            _atomic_write_json(actions_file, reg0)

    # Self-healing (v0.1): resolve stale PLACEHOLDER_MILESTONE actions based on the current roadmap definition.
    placeholder_milestones = _placeholder_milestones_from_roadmap(roadmap_obj=roadmap_obj)
    roadmap_milestones = set(str(x) for x in roadmap_ids)
    supported_step_types = _supported_step_types(core_root=core_root)
    reg_ph = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
    if _self_heal_placeholder_actions(
        actions_reg=reg_ph,
        placeholder_milestones=placeholder_milestones,
        roadmap_milestones=roadmap_milestones,
    ):
        _atomic_write_json(actions_file, reg_ph)
    cleanup_report = _self_heal_unknown_step_actions(
        actions_reg=reg_ph,
        supported_types=supported_step_types,
        roadmap_milestones=roadmap_milestones,
        completed_milestones=set(
            str(x) for x in (state.get("completed_milestones") or []) if isinstance(x, str)
        ),
    )
    if cleanup_report.get("changed"):
        _atomic_write_json(actions_file, reg_ph)
    write_json(run_dir / "stale_action_cleanup_report.json", cleanup_report)

    if not smoke_drift_minimal and script_budget_status == "FAIL":
        stop_status = "BLOCKED"
        stop_code = "SCRIPT_BUDGET_HARD_FAIL"
        logs.append("SCRIPT_BUDGET_HARD_FAIL\n")

    if not smoke_drift_minimal and stop_status is None:
        enabled, checks = _load_artifact_completeness_policy(core_root=core_root, workspace_root=workspace_root)
        if enabled:
            missing_before = _artifact_missing(checks=checks, workspace_root=workspace_root)
            attempted: list[str] = []
            healed_ids: set[str] = set()
            still_missing = list(missing_before)
            pack_derived_milestones = {"M2.5", "M3", "M9.2", "M9.3"}
            pack_related_missing = [
                item
                for item in missing_before
                if str(item.get("owner_milestone") or "") in pack_derived_milestones
            ]
            pack_drift_detected = False
            pack_sha_map = _pack_manifest_sha_map(core_root, workspace_root)
            pack_list_sha = _pack_list_sha(pack_sha_map)
            cursor_path = workspace_root / ".cache" / "index" / "pack_index_cursor.v1.json"
            if pack_list_sha and cursor_path.exists():
                try:
                    cursor_obj = _load_json(cursor_path)
                    last_sha = cursor_obj.get("last_pack_list_sha256") if isinstance(cursor_obj, dict) else None
                    if isinstance(last_sha, str) and last_sha and last_sha != pack_list_sha:
                        pack_drift_detected = True
                except Exception:
                    pack_drift_detected = True

            reg_ac = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            actions_changed = False
            if missing_before:
                _upsert_actions(reg_ac, [_artifact_missing_action(item) for item in missing_before])
                actions_changed = True

            pack_validation_obj: dict[str, Any] | None = None
            if pack_related_missing or pack_drift_detected:
                pack_validation_obj, report_path, rc = _run_pack_validation(
                    core_root=core_root,
                    workspace_root=workspace_root,
                    logs=logs,
                )
                pack_conflict_report_path = report_path
                if pack_validation_obj is not None:
                    write_json(run_dir / "pack_validation_report_snapshot.json", pack_validation_obj)
                pack_validation_status = (
                    pack_validation_obj.get("status") if isinstance(pack_validation_obj, dict) else None
                )
                hard_conflicts = (
                    pack_validation_obj.get("hard_conflicts") if isinstance(pack_validation_obj, dict) else None
                )
                soft_conflicts = (
                    pack_validation_obj.get("soft_conflicts") if isinstance(pack_validation_obj, dict) else None
                )
                hard_list = hard_conflicts if isinstance(hard_conflicts, list) else []
                soft_list = soft_conflicts if isinstance(soft_conflicts, list) else []
                if rc != 0 or pack_validation_status == "FAIL":
                    pack_conflict_blocked = True
                    _upsert_actions(
                        reg_ac,
                        [
                            _pack_conflict_action(
                                kind="PACK_CONFLICT",
                                severity="FAIL",
                                report_path=report_path,
                                conflicts=hard_list,
                            )
                        ],
                    )
                    actions_changed = True
                elif soft_list:
                    _upsert_actions(
                        reg_ac,
                        [
                            _pack_conflict_action(
                                kind="PACK_SOFT_CONFLICT",
                                severity="WARN",
                                report_path=report_path,
                                conflicts=soft_list,
                            )
                        ],
                    )
                    actions_changed = True

            if actions_changed:
                _atomic_write_json(actions_file, reg_ac)

            heal_milestones = sorted(
                {
                    str(item.get("owner_milestone") or "")
                    for item in missing_before
                    if item.get("auto_heal")
                }
            )
            if pack_conflict_blocked and heal_milestones:
                heal_milestones = [m for m in heal_milestones if m not in pack_derived_milestones]
            heal_milestones = [m for m in heal_milestones if m][:2]

            if heal_milestones:
                try:
                    from src.roadmap.executor import apply_roadmap
                except Exception as e:
                    logs.append("ARTIFACT_AUTOHEAL_IMPORT_FAILED " + str(e)[:200] + "\n")
                    heal_milestones = []
                for mid in heal_milestones:
                    if deadline_seconds and (time.monotonic() - start_monotonic) > deadline_seconds:
                        break
                    try:
                        apply_roadmap(
                            roadmap_path=roadmap_path,
                            core_root=core_root,
                            workspace_root=workspace_root,
                            cache_root=core_root / ".cache",
                            evidence_root=core_root / "evidence" / "roadmap",
                            dry_run=False,
                            dry_run_mode="simulate",
                            milestone_ids=[mid],
                        )
                        attempted.append(mid)
                    except Exception as e:
                        logs.append("ARTIFACT_AUTOHEAL_FAILED " + str(e)[:200] + "\n")

                missing_after = _artifact_missing(checks=checks, workspace_root=workspace_root)
                missing_after_ids = {str(item.get("id") or "") for item in missing_after}
                for item in missing_before:
                    item_id = str(item.get("id") or "")
                    if item_id and item_id not in missing_after_ids:
                        healed_ids.add(item_id)
                still_missing = missing_after

                if still_missing:
                    reg_ac = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                    for item in still_missing:
                        if item.get("auto_heal") and str(item.get("owner_milestone") or "") in attempted:
                            _upsert_actions(reg_ac, [_artifact_heal_failed_action(item)])
                    _atomic_write_json(actions_file, reg_ac)

            artifact_completeness = {
                "missing": missing_before,
                "healed": sorted(healed_ids),
                "still_missing": still_missing,
                "attempted_milestones": attempted,
                "pack_conflict_blocked": pack_conflict_blocked,
                "pack_conflict_report_path": pack_conflict_report_path,
            }
            write_json(run_dir / "artifact_completeness_report.json", artifact_completeness)

            if any(item.get("severity") == "block" for item in still_missing):
                stop_status = "BLOCKED"
                stop_code = "DERIVED_ARTIFACT_BLOCKED"
                logs.append("DERIVED_ARTIFACT_BLOCKED\n")

    while True:
        if stop_status is not None:
            break
        if deadline_seconds and (time.monotonic() - start_monotonic) > deadline_seconds:
            stop_status = "BLOCKED"
            stop_code = "TIME_LIMIT"
            logs.append("TIME_LIMIT\n")
            break

        st = status(roadmap_path=roadmap_path, workspace_root=workspace_root, state_path=state_path)
        next_mid = st.get("next_milestone") if isinstance(st, dict) else None
        if next_mid is None:
            stop_status = "DONE"
            break

        slept_for_backoff = False
        for _ in range(max(1, int(max_steps_per_iteration))):
            if deadline_seconds and (time.monotonic() - start_monotonic) > deadline_seconds:
                stop_status = "BLOCKED"
                stop_code = "TIME_LIMIT"
                logs.append("TIME_LIMIT\n")
                break

            st2 = status(roadmap_path=roadmap_path, workspace_root=workspace_root, state_path=state_path)
            next_mid = st2.get("next_milestone") if isinstance(st2, dict) else None
            if next_mid is None:
                stop_status = "DONE"
                break

            milestone_id = str(next_mid)

            # Preview + deep evaluation (saved to evidence).
            try:
                _, preview_obj, new_actions = write_preview_and_analysis(milestone_id)
            except Exception as e:
                stop_status = "BLOCKED"
                stop_code = "PREVIEW_FAILED"
                logs.append("PREVIEW_PLAN_FAILED " + str(e)[:300] + "\n")
                break

            iterations.append({"milestone_id": milestone_id, "preview": preview_obj})

            # Action register updates: placeholder/unknown steps + script budget WARN.
            reg = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            _add_actions(reg, new_actions)
            _atomic_write_json(actions_file, reg)

            # Optional CHG generation (explicitly enabled; may dirty core repo).
            if auto_apply_chg and new_actions:
                changes_dir = core_root / "roadmaps" / "SSOT" / "changes"
                changes_dir.mkdir(parents=True, exist_ok=True)
                today = _now_utc().strftime("%Y%m%d")
                existing = sorted([p for p in changes_dir.glob(f"CHG-{today}-*.json") if p.is_file()])
                seq = len(existing) + 1
                change_id = f"CHG-{today}-{seq:03d}"
                change_path = changes_dir / f"{change_id}.json"
                change_obj = {
                    "change_id": change_id,
                    "version": "v1",
                    "type": "modify",
                    "risk_level": "low",
                    "target": {"milestone_id": milestone_id},
                    "rationale": "Auto-generated by roadmap-finish (v0.2) from action register warnings.",
                    "patches": [{"op": "append_milestone_note", "milestone_id": milestone_id, "note": "AUTO_CHG: review action register warnings"}],
                    "gates": ["python ci/validate_schemas.py", "python -m src.ops.manage smoke --level fast"],
                }
                _atomic_write_json(change_path, change_obj)
                chg_generated.append(str(change_path.relative_to(core_root)))

            # Advance exactly one milestone (follow is fail-closed and writes its own evidence).
            res = follow(roadmap_path=roadmap_path, workspace_root=workspace_root, max_steps=1, dry_run_mode="readonly")
            iterations[-1]["follow"] = res
            logs.append(json.dumps({"milestone_id": milestone_id, "follow_status": res.get("status")}, ensure_ascii=False, sort_keys=True) + "\n")

            if not smoke_drift_minimal:
                # Ingest Script Budget after the iteration gates (fail-closed).
                script_budget_status, script_budget_report = _run_script_budget_checker(core_root=core_root)
                write_json(run_dir / "script_budget_report.json", script_budget_report)
                iterations[-1]["script_budget_status"] = script_budget_status
                reg_sb = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                sb_actions = _script_budget_actions_from_report(script_budget_report)
                if script_budget_status == "OK":
                    actions_sb = reg_sb.get("actions")
                    if isinstance(actions_sb, list):
                        for a in actions_sb:
                            if not isinstance(a, dict):
                                continue
                            if a.get("source") == "SCRIPT_BUDGET" or a.get("kind") == "SCRIPT_BUDGET":
                                a["resolved"] = True
                else:
                    _upsert_actions(reg_sb, sb_actions)
                _atomic_write_json(actions_file, reg_sb)

                if script_budget_status == "FAIL":
                    stop_status = "BLOCKED"
                    stop_code = "SCRIPT_BUDGET_HARD_FAIL"
                    logs.append("SCRIPT_BUDGET_HARD_FAIL\n")
                    break

                # Ingest Quality Gate after the iteration gates (fail-closed).
                quality_gate_status, quality_gate_report = _run_quality_gate_checker(core_root=core_root, workspace_root=workspace_root)
                write_json(run_dir / "quality_gate_report.json", quality_gate_report)
                iterations[-1]["quality_gate_status"] = quality_gate_status
                reg_qg = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                if quality_gate_status == "OK":
                    actions_qg = reg_qg.get("actions")
                    if isinstance(actions_qg, list):
                        for a in actions_qg:
                            if not isinstance(a, dict):
                                continue
                            if a.get("kind") == "QUALITY_GATE_WARN" or a.get("source") == "QUALITY_GATE":
                                a["resolved"] = True
                elif quality_gate_status == "WARN":
                    action = _quality_gate_warn_action_from_report(quality_gate_report)
                    if action:
                        _upsert_actions(reg_qg, [action])
                else:
                    stop_status = "BLOCKED"
                    stop_code = "QUALITY_GATE_FAIL"
                    logs.append("QUALITY_GATE_FAIL\n")
                    _atomic_write_json(actions_file, reg_qg)
                    break
                _atomic_write_json(actions_file, reg_qg)

                # Learning harvest (public candidates, offline, sanitized).
                try:
                    from src.learning.harvest_public_candidates import action_from_harvest_result, run_harvest_for_workspace
                    harvest_res = run_harvest_for_workspace(workspace_root=workspace_root, core_root=core_root, dry_run=False)
                except Exception as e:
                    harvest_res = {"status": "FAIL", "error_code": "HARVEST_EXCEPTION", "message": str(e)[:300]}
                harvest_status = str(harvest_res.get("status") or "FAIL")
                iterations[-1]["harvest_status"] = harvest_status
                write_json(run_dir / "public_candidates_report.json", harvest_res)
                out_raw = harvest_res.get("out") if isinstance(harvest_res, dict) else None
                if isinstance(out_raw, str) and out_raw:
                    out_path = Path(out_raw)
                    if out_path.exists():
                        try:
                            write_json(run_dir / "public_candidates_snapshot.json", _load_json(out_path))
                        except Exception:
                            pass
                reg_h = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                action = action_from_harvest_result(harvest_res) if isinstance(harvest_res, dict) else None
                if isinstance(action, dict):
                    _upsert_actions(reg_h, [action])
                _atomic_write_json(actions_file, reg_h)
                if harvest_status == "FAIL":
                    stop_status = "BLOCKED"
                    stop_code = "HARVEST_PUBLIC_CANDIDATES_FAIL"
                    logs.append("HARVEST_PUBLIC_CANDIDATES_FAIL\n")
                    break

                # Ops index (run_index + dlq_index) after iteration gates.
                ops_index_status, ops_index_report = _run_ops_index_builder(core_root=core_root, workspace_root=workspace_root)
                write_json(run_dir / "ops_index_report.json", ops_index_report)
                iterations[-1]["ops_index_status"] = ops_index_status
                out_paths = ops_index_report.get("out_paths") if isinstance(ops_index_report, dict) else None
                if isinstance(out_paths, list):
                    for raw in out_paths:
                        if not isinstance(raw, str) or not raw:
                            continue
                        p = Path(raw)
                        if not p.exists():
                            continue
                        name = p.name
                        if "run_index" in name:
                            try:
                                write_json(run_dir / "run_index_snapshot.json", _load_json(p))
                            except Exception:
                                pass
                        elif "dlq_index" in name:
                            try:
                                write_json(run_dir / "dlq_index_snapshot.json", _load_json(p))
                            except Exception:
                                pass
                reg_ops = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                if ops_index_status == "OK":
                    actions_ops = reg_ops.get("actions")
                    if isinstance(actions_ops, list):
                        for a in actions_ops:
                            if not isinstance(a, dict):
                                continue
                            if a.get("kind") == "OPS_INDEX_WARN" or a.get("source") == "OPS_INDEX":
                                a["resolved"] = True
                elif ops_index_status == "WARN":
                    action = _ops_index_action_from_report(ops_index_report)
                    if action:
                        _upsert_actions(reg_ops, [action])
                else:
                    stop_status = "BLOCKED"
                    stop_code = "OPS_INDEX_FAIL"
                    logs.append("OPS_INDEX_FAIL\n")
                    _atomic_write_json(actions_file, reg_ops)
                    break
                _atomic_write_json(actions_file, reg_ops)

                # Advisor suggestions (suggest-only, offline).
                try:
                    from src.learning.advisor_suggest import action_from_advisor_result, run_advisor_for_workspace
                    advisor_res = run_advisor_for_workspace(workspace_root=workspace_root, core_root=core_root, dry_run=False)
                except Exception as e:
                    advisor_res = {"status": "FAIL", "error_code": "ADVISOR_EXCEPTION", "message": str(e)[:300], "on_fail": "warn"}
                advisor_status = str(advisor_res.get("status") or "FAIL")
                iterations[-1]["advisor_status"] = advisor_status
                write_json(run_dir / "advisor_suggestions_report.json", advisor_res)
                advisor_out = advisor_res.get("out") if isinstance(advisor_res, dict) else None
                if isinstance(advisor_out, str) and advisor_out:
                    out_path = Path(advisor_out)
                    if out_path.exists():
                        try:
                            write_json(run_dir / "advisor_suggestions_snapshot.json", _load_json(out_path))
                        except Exception:
                            pass

                reg_adv = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                adv_action = action_from_advisor_result(advisor_res) if isinstance(advisor_res, dict) else None
                if isinstance(adv_action, dict):
                    _upsert_actions(reg_adv, [adv_action])
                _atomic_write_json(actions_file, reg_adv)

                if advisor_status == "FAIL" and advisor_res.get("on_fail") == "block":
                    stop_status = "BLOCKED"
                    stop_code = "ADVISOR_FAIL"
                    logs.append("ADVISOR_FAIL\n")
                    break

                # Autopilot readiness (offline, deterministic).
                try:
                    from src.autopilot.readiness_report import action_from_readiness_result, run_readiness_for_workspace
                    readiness_res = run_readiness_for_workspace(workspace_root=workspace_root, core_root=core_root, dry_run=False)
                except Exception as e:
                    readiness_res = {"status": "FAIL", "error_code": "AUTOPILOT_READINESS_EXCEPTION", "message": str(e)[:300], "on_fail": "warn"}
                autopilot_readiness_status = str(readiness_res.get("status") or "FAIL")
                iterations[-1]["autopilot_readiness_status"] = autopilot_readiness_status
                write_json(run_dir / "autopilot_readiness_report.json", readiness_res)
                readiness_out = readiness_res.get("out") if isinstance(readiness_res, dict) else None
                if isinstance(readiness_out, str) and readiness_out:
                    out_path = Path(readiness_out)
                    if out_path.exists():
                        try:
                            write_json(run_dir / "autopilot_readiness_snapshot.json", _load_json(out_path))
                        except Exception:
                            pass

                reg_ready = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                ready_action = action_from_readiness_result(readiness_res) if isinstance(readiness_res, dict) else None
                if isinstance(ready_action, dict):
                    _upsert_actions(reg_ready, [ready_action])
                _atomic_write_json(actions_file, reg_ready)

                if autopilot_readiness_status == "FAIL" and readiness_res.get("on_fail") == "block":
                    stop_status = "BLOCKED"
                    stop_code = "AUTOPILOT_READINESS_FAIL"
                    logs.append("AUTOPILOT_READINESS_FAIL\n")
                    break

                # System status report (JSON + Markdown).
                try:
                    from src.ops.system_status_report import action_from_system_status_result, run_system_status
                    system_res = run_system_status(workspace_root=workspace_root, core_root=core_root, dry_run=False)
                except Exception as e:
                    system_res = {"status": "FAIL", "error_code": "SYSTEM_STATUS_EXCEPTION", "message": str(e)[:300], "on_fail": "warn"}
                system_status_status = str(system_res.get("status") or "FAIL")
                iterations[-1]["system_status_status"] = system_status_status
                write_json(run_dir / "system_status_report.json", system_res)
                system_status_snapshot_before = _system_status_snapshot_from_result(system_res)

                out_json = system_res.get("out_json") if isinstance(system_res, dict) else None
                if isinstance(out_json, str) and out_json:
                    json_path = Path(out_json)
                    if json_path.exists():
                        try:
                            write_json(run_dir / "system_status_snapshot.json", _load_json(json_path))
                        except Exception:
                            pass
                out_md = system_res.get("out_md") if isinstance(system_res, dict) else None
                if isinstance(out_md, str) and out_md:
                    md_path = Path(out_md)
                    if md_path.exists():
                        try:
                            write_text(run_dir / "system_status_snapshot.md", md_path.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                reg_sys = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                sys_action = action_from_system_status_result(system_res) if isinstance(system_res, dict) else None
                if isinstance(sys_action, dict):
                    _upsert_actions(reg_sys, [sys_action])
                _atomic_write_json(actions_file, reg_sys)

                if system_status_status == "FAIL" and system_res.get("on_fail") == "block":
                    stop_status = "BLOCKED"
                    stop_code = "SYSTEM_STATUS_FAIL"
                    logs.append("SYSTEM_STATUS_FAIL\n")
                    break

                # Debt drafting (suggest-only, workspace-only).
                if not smoke_drift_minimal:
                    include_repo_suggest = _system_status_include_repo_hygiene_suggestions(
                        core_root=core_root, workspace_root=workspace_root
                    )
                    debt_auto_applied = False
                    debt_auto_applied_chg: Path | None = None
                    if debt_policy.enabled or include_repo_suggest:
                        try:
                            from src.ops.debt_drafter import action_from_debt_draft_result, run_debt_drafter
                            max_items = debt_policy.max_items if debt_policy.enabled else 3
                            max_items = min(max_items if max_items > 0 else 3, 3)
                            outdir = Path(debt_policy.outdir)
                            if not outdir.is_absolute():
                                outdir = (workspace_root / outdir).resolve()
                            debt_res = run_debt_drafter(
                                workspace_root=workspace_root,
                                core_root=core_root,
                                outdir=outdir,
                                max_items=max_items,
                            )
                        except Exception as e:
                            debt_res = {
                                "status": "FAIL",
                                "error_code": "DEBT_DRAFTER_EXCEPTION",
                                "message": str(e)[:300],
                            }
                        iterations[-1]["debt_draft_status"] = str(debt_res.get("status") or "FAIL")
                        write_json(run_dir / "debt_draft_report.json", debt_res)
                        reg_debt = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                        debt_action = action_from_debt_draft_result(debt_res) if isinstance(debt_res, dict) else None
                        if isinstance(debt_action, dict):
                            _upsert_actions(reg_debt, [debt_action])
                        _atomic_write_json(actions_file, reg_debt)

                        # Safe-only auto-apply (workspace incubator only).
                        if debt_policy.enabled and debt_policy.mode == "safe_apply" and auto_apply_remaining > 0:
                            chg_candidates = []
                            chg_files = debt_res.get("chg_files") if isinstance(debt_res, dict) else None
                            if isinstance(chg_files, list):
                                for item in chg_files:
                                    if isinstance(item, str) and item:
                                        chg_candidates.append(Path(item))
                            if not chg_candidates:
                                try:
                                    chg_candidates = sorted(outdir.glob("CHG-*.json"))
                                except Exception:
                                    chg_candidates = []
                            else:
                                try:
                                    for p in outdir.glob("CHG-*.json"):
                                        if p not in chg_candidates:
                                            chg_candidates.append(p)
                                except Exception:
                                    pass
                            chg_candidates = [p for p in chg_candidates if p.exists()]
                            chg_candidates.sort(key=lambda p: p.as_posix())

                            apply_action: dict[str, Any] | None = None
                            apply_result: dict[str, Any] | None = None
                            chg_target_kind: str | None = None
                            if chg_candidates:
                                chg_path = chg_candidates[0]
                                chg_obj = None
                                try:
                                    chg_obj = _load_json(chg_path)
                                except Exception:
                                    chg_obj = None
                                safe_reason = None
                                if not isinstance(chg_obj, dict):
                                    safe_reason = "CHG_INVALID"
                                else:
                                    safety = chg_obj.get("safety") if isinstance(chg_obj.get("safety"), dict) else {}
                                    if safety.get("apply_scope") != "INCUBATOR_ONLY":
                                        safe_reason = "INVALID_APPLY_SCOPE"
                                    elif safety.get("destructive") is True:
                                        safe_reason = "DESTRUCTIVE_NOT_ALLOWED"
                                    actions = chg_obj.get("actions") if isinstance(chg_obj.get("actions"), list) else []
                                    if not actions:
                                        safe_reason = "NO_ACTIONS"
                                    else:
                                        for act in actions:
                                            if not isinstance(act, dict):
                                                continue
                                            kind = act.get("kind")
                                            if not isinstance(kind, str) or kind not in debt_policy.safe_action_kinds:
                                                safe_reason = "UNSAFE_ACTION_KIND"
                                                break
                                    chg_target_kind = chg_obj.get("target_debt_kind") if isinstance(chg_obj.get("target_debt_kind"), str) else None

                                if safe_reason:
                                    action_id = _sha256_hex(f"DEBT_AUTO_APPLY_SKIPPED|{chg_path}|{safe_reason}")[:16]
                                    apply_action = {
                                        "action_id": action_id,
                                        "severity": "INFO",
                                        "kind": "DEBT_AUTO_APPLY_SKIPPED",
                                        "milestone_hint": "M0",
                                        "source": "DEBT_AUTOPILOT",
                                        "title": "Debt auto-apply skipped",
                                        "details": {
                                            "reason": safe_reason,
                                            "chg_path": str(chg_path),
                                        },
                                        "message": f"Auto-apply skipped: {safe_reason}",
                                        "resolved": False,
                                    }
                                    apply_result = {"status": "SKIPPED", "reason": safe_reason, "chg_path": str(chg_path)}
                                else:
                                    try:
                                        from src.ops.debt_apply_incubator import apply_debt_incubator
                                        apply_result = apply_debt_incubator(
                                            workspace_root=workspace_root,
                                            chg_path=chg_path,
                                            dry_run=False,
                                        )
                                    except Exception as e:
                                        apply_result = {
                                            "status": "FAIL",
                                            "error_code": "DEBT_AUTO_APPLY_EXCEPTION",
                                            "message": str(e)[:300],
                                        }

                                    write_json(run_dir / "debt_apply_report.json", apply_result)
                                    iterations[-1]["debt_auto_apply_status"] = str(apply_result.get("status") or "FAIL")

                                    if apply_result.get("status") == "OK":
                                        auto_apply_remaining = max(0, auto_apply_remaining - 1)
                                        debt_auto_applied = True
                                        debt_auto_applied_chg = chg_path
                                        action_id = _sha256_hex(f"DEBT_AUTO_APPLIED|{chg_path}")[:16]
                                        apply_action = {
                                            "action_id": action_id,
                                            "severity": "INFO",
                                            "kind": "DEBT_AUTO_APPLIED",
                                            "milestone_hint": "M0",
                                            "source": "DEBT_AUTOPILOT",
                                            "title": "Debt auto-apply succeeded",
                                            "details": {
                                                "chg_path": str(chg_path),
                                                "incubator_paths": apply_result.get("incubator_paths"),
                                            },
                                            "message": f"Auto-apply OK: {chg_path}",
                                            "resolved": True,
                                        }
                                    else:
                                        action_id = _sha256_hex(f"DEBT_AUTO_APPLY_FAIL|{chg_path}|{apply_result.get('status')}")[:16]
                                        apply_action = {
                                            "action_id": action_id,
                                            "severity": "WARN",
                                            "kind": "DEBT_AUTO_APPLY_FAIL",
                                            "milestone_hint": "M0",
                                            "source": "DEBT_AUTOPILOT",
                                            "title": "Debt auto-apply failed",
                                            "details": {
                                                "chg_path": str(chg_path),
                                                "error_code": apply_result.get("error_code"),
                                            },
                                            "message": f"Auto-apply failed: {apply_result.get('error_code') or apply_result.get('status')}",
                                            "resolved": False,
                                        }
                                        if debt_policy.on_apply_fail == "block":
                                            stop_status = "BLOCKED"
                                            stop_code = "DEBT_AUTO_APPLY_FAIL"
                                            logs.append("DEBT_AUTO_APPLY_FAIL\n")

                                if apply_result is not None and not (run_dir / "debt_apply_report.json").exists():
                                    write_json(run_dir / "debt_apply_report.json", apply_result)

                                # Re-check system status after apply (optional).
                                if apply_result and apply_result.get("status") == "OK" and debt_policy.recheck_system_status:
                                    try:
                                        from src.ops.system_status_report import run_system_status
                                        system_after = run_system_status(
                                            workspace_root=workspace_root,
                                            core_root=core_root,
                                            dry_run=False,
                                        )
                                    except Exception as e:
                                        system_after = {
                                            "status": "FAIL",
                                            "error_code": "SYSTEM_STATUS_AFTER_APPLY_EXCEPTION",
                                            "message": str(e)[:300],
                                            "on_fail": "warn",
                                        }
                                    write_json(run_dir / "system_status_after_apply.json", system_after)
                                    system_after_snapshot = _system_status_snapshot_from_result(system_after)

                                    improved = False
                                    if chg_target_kind == "REPO_HYGIENE":
                                        before = _extract_repo_hygiene_count(system_status_snapshot_before)
                                        after = _extract_repo_hygiene_count(system_after_snapshot)
                                        if before is not None and after is not None and after < before:
                                            improved = True
                                    if chg_target_kind == "QUALITY_GATE_WARN":
                                        before_status = _extract_quality_status(system_status_snapshot_before)
                                        after_status = _extract_quality_status(system_after_snapshot)
                                        if after_status == "OK" and before_status in {"WARN", "FAIL"}:
                                            improved = True

                                    reg_apply = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                                    if improved:
                                        actions_list = reg_apply.get("actions")
                                        if isinstance(actions_list, list):
                                            for a in actions_list:
                                                if not isinstance(a, dict):
                                                    continue
                                                if chg_target_kind == "REPO_HYGIENE" and (
                                                    a.get("kind") in {"REPO_HYGIENE", "REPO_HYGIENE_WARN", "REPO_HYGIENE_FAIL"}
                                                    or a.get("source") == "REPO_HYGIENE"
                                                ):
                                                    a["resolved"] = True
                                                if chg_target_kind == "QUALITY_GATE_WARN" and (
                                                    a.get("kind") == "QUALITY_GATE_WARN" or a.get("source") == "QUALITY_GATE"
                                                ):
                                                    a["resolved"] = True
                                    else:
                                        action_id = _sha256_hex(f"DEBT_NO_IMPROVEMENT|{chg_target_kind}")[:16]
                                        _upsert_actions(
                                            reg_apply,
                                            [
                                                {
                                                    "action_id": action_id,
                                                    "severity": "WARN",
                                                    "kind": "DEBT_NO_IMPROVEMENT",
                                                    "milestone_hint": "M0",
                                                    "source": "DEBT_AUTOPILOT",
                                                    "title": "Debt auto-apply did not improve status",
                                                    "details": {"target_debt_kind": chg_target_kind},
                                                    "message": "No measurable improvement after auto-apply.",
                                                    "resolved": False,
                                                }
                                            ],
                                        )
                                    _atomic_write_json(actions_file, reg_apply)

                            if apply_action is not None:
                                reg_apply = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                                _upsert_actions(reg_apply, [apply_action])
                                _atomic_write_json(actions_file, reg_apply)

                            if debt_auto_applied:
                                try:
                                    from src.ops.promotion_bundle import run_promotion_bundle
                                    promo_res = run_promotion_bundle(
                                        workspace_root=workspace_root,
                                        core_root=core_root,
                                        mode=None,
                                        dry_run=False,
                                    )
                                except Exception as e:
                                    promo_res = {
                                        "status": "FAIL",
                                        "error_code": "PROMOTION_BUNDLE_EXCEPTION",
                                        "message": str(e)[:300],
                                    }
                                promotion_status = str(promo_res.get("status") or "FAIL")
                                iterations[-1]["promotion_status"] = promotion_status

                                if isinstance(promo_res, dict):
                                    write_json(run_dir / "promotion_report_snapshot.json", promo_res)
                                    out_report = promo_res.get("out_report")
                                    if isinstance(out_report, str):
                                        report_path = Path(out_report)
                                        if report_path.exists():
                                            try:
                                                write_json(run_dir / "promotion_report_snapshot.json", _load_json(report_path))
                                            except Exception:
                                                pass
                                    out_zip = promo_res.get("out_zip")
                                    if isinstance(out_zip, str):
                                        try:
                                            write_text(run_dir / "promotion_bundle_path.txt", out_zip)
                                        except Exception:
                                            pass
                                    out_patch_md = promo_res.get("out_patch_md")
                                    if isinstance(out_patch_md, str):
                                        md_path = Path(out_patch_md)
                                        if md_path.exists():
                                            try:
                                                write_text(run_dir / "core_patch_summary_snapshot.md", md_path.read_text(encoding="utf-8"))
                                            except Exception:
                                                pass

                                reg_prom = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                                if promotion_status == "OK":
                                    action_id = _sha256_hex(f"PROMOTION_BUNDLE|{promo_res.get('out_zip')}")[:16]
                                    _upsert_actions(
                                        reg_prom,
                                        [
                                            {
                                                "action_id": action_id,
                                                "severity": "INFO",
                                                "kind": "PROMOTION_BUNDLE_READY",
                                                "milestone_hint": "M0",
                                                "source": "PROMOTION_BUNDLE",
                                                "title": "Promotion bundle ready",
                                                "details": {
                                                    "included": promo_res.get("included"),
                                                    "bundle_zip": promo_res.get("out_zip"),
                                                },
                                                "message": f"Promotion bundle ready: {promo_res.get('out_zip')}",
                                                "resolved": False,
                                            }
                                        ],
                                    )
                                else:
                                    action_id = _sha256_hex(f"PROMOTION_BUNDLE_FAIL|{promo_res.get('status')}")[:16]
                                    _upsert_actions(
                                        reg_prom,
                                        [
                                            {
                                                "action_id": action_id,
                                                "severity": "WARN",
                                                "kind": "PROMOTION_BUNDLE_FAIL",
                                                "milestone_hint": "M0",
                                                "source": "PROMOTION_BUNDLE",
                                                "title": "Promotion bundle failed",
                                                "details": {
                                                    "status": promotion_status,
                                                    "error_code": promo_res.get("error_code"),
                                                },
                                                "message": f"Promotion bundle failed: {promo_res.get('error_code') or promotion_status}",
                                                "resolved": False,
                                            }
                                        ],
                                    )
                                _atomic_write_json(actions_file, reg_prom)

            if not smoke_drift_minimal:
                completed_set = set(
                    str(x) for x in (state.get("completed_milestones") or []) if isinstance(x, str)
                )
                if "M8.2" not in completed_set:
                    seed_path = workspace_root / "incubator" / "notes" / "PROMOTION_SEED.md"
                    seed_exists = seed_path.exists()
                    should_attempt = debt_auto_applied or seed_exists
                    if _promotion_outputs_exist(workspace_root):
                        mark_completed(state, "M8.2")
                        save_state(state_path=state_path, state=state)
                        completed_set.add("M8.2")
                    elif should_attempt:
                        if not _incubator_has_files(workspace_root):
                            try:
                                _ensure_promotion_seed_note(workspace_root)
                            except ValueError:
                                stop_status = "BLOCKED"
                                stop_code = "PROMOTION_SEED_CONTENT_MISMATCH"
                                logs.append("PROMOTION_SEED_CONTENT_MISMATCH\n")
                                break

                        try:
                            from src.roadmap.executor import apply_roadmap

                            m82_res = apply_roadmap(
                                roadmap_path=roadmap_path,
                                core_root=core_root,
                                workspace_root=workspace_root,
                                cache_root=core_root / ".cache",
                                evidence_root=core_root / "evidence" / "roadmap",
                                dry_run=False,
                                dry_run_mode="simulate",
                                milestone_ids=["M8.2"],
                            )
                        except Exception as e:
                            m82_res = {
                                "status": "FAIL",
                                "error_code": "M8_2_APPLY_EXCEPTION",
                                "message": str(e)[:300],
                            }
                        write_json(run_dir / "promotion_bundle_apply_report.json", m82_res)

                        if m82_res.get("status") == "OK" and _promotion_outputs_exist(workspace_root):
                            mark_completed(state, "M8.2")
                            save_state(state_path=state_path, state=state)
                            completed_set.add("M8.2")

                            report_path = workspace_root / ".cache" / "promotion" / "promotion_report.v1.json"
                            if report_path.exists():
                                try:
                                    write_json(run_dir / "promotion_report_snapshot.json", _load_json(report_path))
                                except Exception:
                                    pass
                            patch_md = workspace_root / ".cache" / "promotion" / "core_patch_summary.v1.md"
                            if patch_md.exists():
                                try:
                                    write_text(run_dir / "core_patch_summary_snapshot.md", patch_md.read_text(encoding="utf-8"))
                                except Exception:
                                    pass
                            zip_path = workspace_root / ".cache" / "promotion" / "promotion_bundle.v1.zip"
                            if zip_path.exists():
                                try:
                                    write_text(run_dir / "promotion_bundle_path.txt", str(zip_path))
                                except Exception:
                                    pass

                            included = 0
                            if report_path.exists():
                                try:
                                    obj = _load_json(report_path)
                                    inc = obj.get("included_files") if isinstance(obj, dict) else None
                                    included = len(inc) if isinstance(inc, list) else 0
                                except Exception:
                                    included = 0

                            reg_prom = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                            action_id = _sha256_hex(f"PROMOTION_BUNDLE|{zip_path.as_posix()}")[:16]
                            _upsert_actions(
                                reg_prom,
                                [
                                    {
                                        "action_id": action_id,
                                        "severity": "INFO",
                                        "kind": "PROMOTION_BUNDLE_READY",
                                        "milestone_hint": "M8.2",
                                        "source": "PROMOTION_BUNDLE",
                                        "title": "Promotion bundle ready",
                                        "details": {"included": included, "bundle_zip": str(zip_path)},
                                        "message": f"Promotion bundle ready: {zip_path}",
                                        "resolved": False,
                                    }
                                ],
                            )
                            _atomic_write_json(actions_file, reg_prom)
                        elif m82_res.get("status") != "OK":
                            reg_prom = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                            action_id = _sha256_hex("PROMOTION_BUNDLE_FAIL|M8.2")[:16]
                            _upsert_actions(
                                reg_prom,
                                [
                                    {
                                        "action_id": action_id,
                                        "severity": "WARN",
                                        "kind": "PROMOTION_BUNDLE_FAIL",
                                        "milestone_hint": "M8.2",
                                        "source": "PROMOTION_BUNDLE",
                                        "title": "Promotion bundle failed",
                                        "details": {"status": m82_res.get("status"), "error_code": m82_res.get("error_code")},
                                        "message": f"Promotion bundle failed: {m82_res.get('error_code') or m82_res.get('status')}",
                                        "resolved": False,
                                    }
                                ],
                            )
                            _atomic_write_json(actions_file, reg_prom)

            if core_policy.enabled:
                ok, code = _enforce_core_clean(phase=f"iteration:{milestone_id}")
                if not ok:
                    stop_status = "BLOCKED"
                    stop_code = code or "CORE_WRITE_VIOLATION"
                    break

            st_after = load_state(
                state_path=state_path,
                schema_path=state_schema,
                roadmap_path=roadmap_path,
                workspace_root=workspace_root,
            ).state
            record_last_result(
                st_after,
                status="OK" if res.get("status") in {"OK", "DONE"} else "FAIL",
                milestone_id=milestone_id,
                evidence_path=(res.get("evidence")[-1] if isinstance(res.get("evidence"), list) and res.get("evidence") else None),
                error_code=str(res.get("error_code") or "")[:200] if res.get("error_code") else None,
            )
            save_state(state_path=state_path, state=st_after)

            if res.get("status") == "DONE":
                stop_status = "DONE"
                break
            if res.get("status") == "OK":
                continue
            if res.get("status") == "BLOCKED" and res.get("error_code") == "BACKOFF":
                # Bounded sleep; allow sleep_seconds=0 for deterministic smoke runs.
                if sleep_seconds <= 0:
                    stop_status = "BLOCKED"
                    stop_code = "BACKOFF"
                    break
                next_try_at = None
                b = st_after.get("backoff") if isinstance(st_after.get("backoff"), dict) else {}
                if isinstance(b, dict) and isinstance(b.get("next_try_at"), str):
                    next_try_at = _parse_iso8601(b.get("next_try_at"))
                if next_try_at is not None:
                    remaining = max(0, int((next_try_at - _now_utc()).total_seconds()))
                    time.sleep(min(int(sleep_seconds), remaining))
                else:
                    time.sleep(int(sleep_seconds))
                slept_for_backoff = True
                break

            stop_status = str(res.get("status") or "BLOCKED")
            stop_code = str(res.get("error_code") or "FAILED")
            break

        if stop_status is not None:
            break
        if slept_for_backoff:
            continue
        # Completed a batch; continue until DONE/BLOCKED or time limit.
        continue

    # Final payload
    state_after = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    ).state
    completed_after = state_after.get("completed_milestones", [])
    next_after = _next_milestone(roadmap_ids, completed_after if isinstance(completed_after, list) else [])
    if stop_status is None:
        out_status = "DONE" if next_after is None else "OK"
    else:
        out_status = stop_status
    error_code = stop_code
    if error_code is None:
        last_result = state_after.get("last_result") if isinstance(state_after.get("last_result"), dict) else {}
        error_code = last_result.get("error_code") if isinstance(last_result, dict) else None
    if out_status == "OK" and next_after is None:
        out_status = "DONE"

    try:
        from src.ops.system_status_report import action_from_system_status_result, run_system_status
        system_final = run_system_status(workspace_root=workspace_root, core_root=core_root, dry_run=False)
    except Exception as e:
        system_final = {"status": "FAIL", "error_code": "SYSTEM_STATUS_FINAL_EXCEPTION", "message": str(e)[:300], "on_fail": "warn"}
    system_status_status = str(system_final.get("status") or "FAIL")
    write_json(run_dir / "system_status_report.json", system_final)
    out_json = system_final.get("out_json") if isinstance(system_final, dict) else None
    if isinstance(out_json, str) and out_json:
        json_path = Path(out_json)
        if json_path.exists():
            try:
                write_json(run_dir / "system_status_snapshot.json", _load_json(json_path))
            except Exception:
                pass
    out_md = system_final.get("out_md") if isinstance(system_final, dict) else None
    if isinstance(out_md, str) and out_md:
        md_path = Path(out_md)
        if md_path.exists():
            try:
                write_text(run_dir / "system_status_snapshot.md", md_path.read_text(encoding="utf-8"))
            except Exception:
                pass
    reg_sys_final = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
    sys_action = action_from_system_status_result(system_final) if isinstance(system_final, dict) else None
    if isinstance(sys_action, dict):
        _upsert_actions(reg_sys_final, [sys_action])
    _atomic_write_json(actions_file, reg_sys_final)

    if core_policy.enabled:
        ok, code = _enforce_core_clean(phase="final")
        if not ok:
            out_status = "BLOCKED"
            error_code = code or "CORE_WRITE_VIOLATION"

    actions_after = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
    _atomic_write_json(run_dir / "actions_after.json", actions_after)

    actions_list = actions_after.get("actions") if isinstance(actions_after, dict) else None
    unresolved_actions = [
        a for a in actions_list if isinstance(a, dict) and a.get("resolved") is not True
    ] if isinstance(actions_list, list) else []
    unresolved_actions.sort(key=lambda x: str(x.get("action_id") or ""))
    actions_count = len(unresolved_actions)
    top_actions = []
    for a in unresolved_actions[:5]:
        top_actions.append(
            {
                "action_id": a.get("action_id"),
                "severity": a.get("severity"),
                "kind": a.get("kind"),
                "milestone_hint": a.get("milestone_hint") or a.get("target_milestone"),
                "title": a.get("title"),
                "message": a.get("message"),
            }
        )

    # Session RAM (Ephemeral SSOT) hook (v0.1): if default session exists, capture its hash in evidence output.
    try:
        sp = SessionPaths(workspace_root=workspace_root, session_id="default")
        if sp.context_path.exists():
            ctx = load_context(sp.context_path)
            hashes = ctx.get("hashes") if isinstance(ctx, dict) else None
            sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
            if isinstance(sha, str) and len(sha) == 64:
                session_context_hash = sha
    except SessionContextError:
        session_context_hash = None
    except Exception:
        session_context_hash = None

    # v0.4: If the roadmap is fully DONE but debt remains in the Action Register, surface it explicitly.
    if out_status == "DONE" and actions_count > 0:
        out_status = "DONE_WITH_DEBT"

    core_unlock_requested = _core_unlock_requested(core_policy)
    core_unlock_allowed = core_unlock_requested and core_policy.default_mode == "locked"

    out = {
        "status": out_status,
        "next_milestone": next_after,
        "completed": completed_after if isinstance(completed_after, list) else [],
        "iterations": len(iterations),
        "chg_generated": chg_generated,
        "error_code": error_code,
        "script_budget_status": script_budget_status,
        "quality_gate_status": quality_gate_status,
        "harvest_status": harvest_status,
        "ops_index_status": ops_index_status,
        "advisor_status": advisor_status,
        "autopilot_readiness_status": autopilot_readiness_status,
        "system_status_status": system_status_status,
        "artifact_completeness": {
            "missing_count": len(artifact_completeness.get("missing", [])) if isinstance(artifact_completeness, dict) else 0,
            "healed_count": len(artifact_completeness.get("healed", [])) if isinstance(artifact_completeness, dict) else 0,
            "still_missing_count": len(artifact_completeness.get("still_missing", [])) if isinstance(artifact_completeness, dict) else 0,
        },
        "smoke_drift_minimal": smoke_drift_minimal,
        "skipped_ingest": skipped_ingest,
        "session_context_hash": session_context_hash,
        "roadmap_sha256": drift_info.get("roadmap_sha256"),
        "drift_detected": drift_info.get("drift_detected"),
        "stale_milestones": drift_info.get("stale_milestones"),
        "stale_reset_milestones": drift_info.get("stale_reset_milestones"),
        "actions_count": actions_count,
        "top_actions": top_actions,
        "pack_conflict_blocked": pack_conflict_blocked,
        "pack_conflict_report_path": pack_conflict_report_path,
        "core_lock_enabled": bool(core_policy.enabled),
        "core_lock_mode": core_policy.default_mode,
        "core_unlock_env_var": core_policy.allow_env_var,
        "core_unlock_requested": core_unlock_requested,
        "core_unlock_allowed": core_unlock_allowed,
    }

    write_json(
        run_dir / "input.json",
        {
            "roadmap": str(roadmap_path),
            "workspace_root": str(workspace_root),
            "state_path": str(state_path),
            "requested": {
                "max_minutes": int(max_minutes),
                "sleep_seconds": int(sleep_seconds),
                "max_steps_per_iteration": int(max_steps_per_iteration),
                "auto_apply_chg": bool(auto_apply_chg),
            },
        },
    )
    write_json(run_dir / "state_before.json", state_before)
    write_json(run_dir / "state_after.json", state_after)
    write_json(run_dir / "output.json", out)
    write_json(run_dir / "iterations.json", {"iterations": iterations})
    _atomic_write_text(
        workspace_root / ".cache" / "last_finish_evidence.v1.txt",
        str(run_dir.relative_to(core_root)),
    )
    write_text(run_dir / "logs.txt", "".join(logs))
    write_integrity_manifest(run_dir)

    return {**out, "evidence": [str(run_dir.relative_to(core_root))]}


@dataclass(frozen=True)
class _CmdResult:
    returncode: int
    stdout: str
    stderr: str


def _run_cmd(core_root: Path, argv: list[str], *, env: dict[str, str]) -> _CmdResult:
    proc = subprocess.run(argv, cwd=core_root, text=True, capture_output=True, env=env)
    return _CmdResult(returncode=int(proc.returncode), stdout=(proc.stdout or ""), stderr=(proc.stderr or ""))


def _enforce_readonly_clean(
    *,
    core_root: Path,
    baseline_git_status: str,
    workspace_root: Path,
    baseline_workspace_snapshot: dict[str, str],
) -> tuple[bool, str | None]:
    current_git = _git_status_porcelain(core_root)
    if current_git is None:
        return (False, "READONLY_MODE_REQUIRES_GIT")
    if current_git != baseline_git_status:
        return (False, "READONLY_MODE_VIOLATION")

    current_ws = _snapshot_tree(
        workspace_root,
        ignore_prefixes=[
            ".cache",
            "evidence",
            "dlq",
            "__pycache__",
        ],
    )
    if current_ws != baseline_workspace_snapshot:
        return (False, "READONLY_WORKSPACE_VIOLATION")
    return (True, None)


def _mk_orchestrator_run_id(*, roadmap_path: Path, workspace_root: Path, next_milestone: str | None, state_before: dict[str, Any]) -> str:
    seed = "|".join(
        [
            str(roadmap_path),
            str(workspace_root),
            str(next_milestone or "DONE"),
            _sha256_hex(_to_canonical_json(state_before)),
        ]
    )
    return _sha256_hex(seed)[:16]


def status(*, roadmap_path: Path, workspace_root: Path, state_path: Path | None = None) -> dict[str, Any]:
    core_root = _core_root()
    roadmap_path = (core_root / roadmap_path).resolve() if not roadmap_path.is_absolute() else roadmap_path.resolve()
    workspace_root = (core_root / workspace_root).resolve() if not workspace_root.is_absolute() else workspace_root.resolve()
    state_path = (
        (workspace_root / ".cache" / "roadmap_state.v1.json").resolve() if state_path is None else state_path.resolve()
    )
    state_schema = core_root / "schemas" / "roadmap-state.schema.json"

    roadmap_obj = _load_and_validate_roadmap(core_root, roadmap_path)
    roadmap_ids = _roadmap_milestones(roadmap_obj)

    state_res = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    )
    st = state_res.state
    completed = st.get("completed_milestones", [])
    if not isinstance(completed, list):
        completed = []

    next_mid = _next_milestone(roadmap_ids, completed)
    return {
        "status": "OK",
        "bootstrapped": bool(st.get("bootstrapped", False)),
        "next_milestone": next_mid,
        "completed_milestones": completed,
        "completed_count": len(completed),
        "quarantine": st.get("quarantine"),
        "backoff": st.get("backoff"),
        "last_result": st.get("last_result"),
        "state_path": str(state_path),
    }


def follow(
    *,
    roadmap_path: Path,
    workspace_root: Path,
    until: str | None = None,
    max_steps: int = 1,
    dry_run_mode: str = "readonly",
    no_apply: bool = False,
    state_path: Path | None = None,
    force_unquarantine: bool = False,
) -> dict[str, Any]:
    core_root = _core_root()
    roadmap_path = (core_root / roadmap_path).resolve() if not roadmap_path.is_absolute() else roadmap_path.resolve()
    workspace_root = (core_root / workspace_root).resolve() if not workspace_root.is_absolute() else workspace_root.resolve()
    state_path = (
        (workspace_root / ".cache" / "roadmap_state.v1.json").resolve() if state_path is None else state_path.resolve()
    )
    state_schema = core_root / "schemas" / "roadmap-state.schema.json"

    evidence_root = (core_root / "evidence" / "roadmap_orchestrator").resolve()

    evidence_paths: list[str] = []
    logs_parts: list[str] = []

    def finalize(*, out: dict[str, Any], state_before: dict[str, Any], state_after: dict[str, Any]) -> dict[str, Any]:
        out.setdefault("bootstrapped", bool(state_after.get("bootstrapped", False)))
        run_id = _mk_orchestrator_run_id(
            roadmap_path=roadmap_path,
            workspace_root=workspace_root,
            next_milestone=str(out.get("next_milestone") or ""),
            state_before=state_before,
        )
        run_dir = evidence_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            run_dir / "input.json",
            {
                "roadmap": str(roadmap_path),
                "workspace_root": str(workspace_root),
                "state_path": str(state_path),
                "requested": {
                    "until": until,
                    "max_steps": int(max_steps),
                    "dry_run_mode": dry_run_mode,
                    "no_apply": bool(no_apply),
                    "force_unquarantine": bool(force_unquarantine),
                },
            },
        )
        write_json(run_dir / "state_before.json", state_before)
        write_json(run_dir / "state_after.json", state_after)
        write_json(run_dir / "output.json", out)
        write_text(run_dir / "logs.txt", "".join(logs_parts))
        write_integrity_manifest(run_dir)

        out["evidence"] = list(out.get("evidence") or []) + [str(run_dir.relative_to(core_root))]
        return out

    if os.environ.get("AUTOPILOT_DISABLED") == "1" or os.environ.get("ORCH_AUTOPILOT_DISABLED") == "1":
        logs_parts.append("AUTOPILOT_DISABLED=1\n")
        out = {
            "status": "DISABLED",
            "next_milestone": None,
            "completed": [],
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": "AUTOPILOT_DISABLED",
        }
        return finalize(out=out, state_before={}, state_after={})

    if _load_governor_global_mode(core_root) == "report_only":
        logs_parts.append("governor.global_mode=report_only\n")
        out = {
            "status": "DISABLED",
            "next_milestone": None,
            "completed": [],
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": "GOVERNOR_REPORT_ONLY",
        }
        return finalize(out=out, state_before={}, state_after={})

    roadmap_obj = _load_and_validate_roadmap(core_root, roadmap_path)
    roadmap_ids = _roadmap_milestones(roadmap_obj)
    if until is not None and until not in set(roadmap_ids):
        raise ValueError("MILESTONE_NOT_FOUND: " + str(until))

    state_res = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    )
    state = state_res.state
    state_before = json.loads(json.dumps(state))

    # Drift detection (v0.4): if the roadmap changed, update state hashes and optionally re-run stale milestones.
    actions_reg = None
    actions_path = _actions_path(workspace_root)
    if actions_path.exists():
        actions_reg = _load_action_register(actions_path, roadmap_path=roadmap_path, workspace_root=workspace_root)
    drift_info = _detect_roadmap_drift_and_update_state(
        state=state,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        roadmap_obj=roadmap_obj,
        actions_reg=actions_reg,
    )
    save_state(state_path=state_path, state=state)

    now = _now_utc()
    if force_unquarantine:
        clear_quarantine(state)
        clear_backoff(state)

    if bool(state.get("paused", False)):
        reason = state.get("pause_reason") if isinstance(state.get("pause_reason"), str) else None
        logs_parts.append(f"PAUSED reason={reason or 'paused'}\n")
        clear_backoff(state)
        record_last_result(state, status="FAIL", milestone_id=None, evidence_path=None, error_code="PAUSED")
        save_state(state_path=state_path, state=state)
        out = {
            "status": "DISABLED",
            "next_milestone": None,
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": "PAUSED",
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    # Fail-closed: if we are in quarantine/backoff, do not attempt anything.
    if is_quarantined(state, now=now):
        q = state.get("quarantine", {})
        logs_parts.append("QUARANTINED\n")
        out = {
            "status": "BLOCKED",
            "next_milestone": q.get("milestone"),
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": q.get("until"),
            "error_code": "QUARANTINED",
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    if is_in_backoff(state, now=now):
        b = state.get("backoff", {})
        logs_parts.append("BACKOFF\n")
        out = {
            "status": "BLOCKED",
            "next_milestone": state.get("current_milestone"),
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "backoff_seconds": b.get("seconds"),
            "quarantine_until": None,
            "error_code": "BACKOFF",
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    baseline_git = _git_status_porcelain(core_root)
    if baseline_git is None:
        raise ValueError("READONLY_MODE_REQUIRES_GIT")
    baseline_ws = _snapshot_tree(
        workspace_root,
        ignore_prefixes=[
            ".cache",
            "evidence",
            "dlq",
            "__pycache__",
        ],
    )

    completed = state.get("completed_milestones", [])
    if not isinstance(completed, list):
        completed = []

    # Bootstrap from workspace artifacts when state is empty or not bootstrapped yet.
    if not bool(state.get("bootstrapped", False)) or not completed:
        warnings = bootstrap_completed_milestones(state=state, workspace_root=workspace_root)
        if warnings:
            logs_parts.append("BOOTSTRAP_WARNINGS: " + "; ".join(warnings) + "\n")
        save_state(state_path=state_path, state=state)
        completed = state.get("completed_milestones", [])
        if not isinstance(completed, list):
            completed = []
    if until is not None and until in set(str(x) for x in completed):
        logs_parts.append("DONE (until already completed)\n")
        out = {
            "status": "DONE",
            "next_milestone": None,
            "completed": completed,
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": None,
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    out: dict[str, Any] = {
        "status": "DONE",
        "next_milestone": None,
        "completed": completed,
        "evidence": evidence_paths,
        "backoff_seconds": None,
        "quarantine_until": None,
        "error_code": None,
        "roadmap_sha256": drift_info.get("roadmap_sha256"),
        "drift_detected": drift_info.get("drift_detected"),
        "stale_milestones": drift_info.get("stale_milestones"),
        "stale_reset_milestones": drift_info.get("stale_reset_milestones"),
    }

    for _ in range(max(1, int(max_steps))):
        next_mid = _next_milestone(roadmap_ids, completed)
        if next_mid is None:
            break

        # ISO-core preflight (v0.1): if roadmap says ISO is required, ensure it exists before running non-ISO milestones.
        iso_required = bool(roadmap_obj.get("iso_core_required", False))
        if iso_required and next_mid != "M1" and not _check_iso_core_presence(workspace_root):
            clear_backoff(state)
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code="ISO_MISSING")
            save_state(state_path=state_path, state=state)
            out = {
                "status": "ISO_MISSING",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": "ISO_MISSING",
            }
            break

        set_current_milestone(state, next_mid)
        attempt = bump_attempt(state, next_mid)
        set_checkpoint(state, current_step_id=f"{next_mid}:READONLY_APPLY", last_completed_step_id=state.get("last_completed_step_id"), last_gate_ok=None)
        save_state(state_path=state_path, state=state)

        env = os.environ.copy()
        env["ORCH_WORKSPACE_ROOT"] = str(workspace_root)
        # Avoid recursion when gates run smoke_test.py.
        env["ORCH_ROADMAP_ORCHESTRATOR"] = "1"

        logs_parts.append(f"== milestone {next_mid} attempt {attempt} ==\n")

        # 1) Readonly dry-run apply
        argv_ro = [
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            str(roadmap_path),
            "--milestone",
            next_mid,
            "--workspace-root",
            str(workspace_root),
            "--dry-run",
            "true",
            "--dry-run-mode",
            str(dry_run_mode),
        ]
        res_ro = _run_cmd(core_root, argv_ro, env=env)
        logs_parts.append(res_ro.stdout)
        if res_ro.stderr:
            logs_parts.append("\n" + res_ro.stderr)
        ro_obj: dict[str, Any] = {}
        try:
            ro_obj = json.loads(res_ro.stdout.strip() or "{}")
        except Exception:
            ro_obj = {}
        ev_ro = ro_obj.get("evidence_path") if isinstance(ro_obj, dict) else None
        if isinstance(ev_ro, str) and ev_ro:
            evidence_paths.append(ev_ro)

        if res_ro.returncode != 0:
            code = str(ro_obj.get("error_code") or "ROADMAP_APPLY_READONLY_FAILED")
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=code)
            set_checkpoint(state, current_step_id=f"{next_mid}:READONLY_APPLY", last_completed_step_id=state.get("last_completed_step_id"), last_gate_ok=False)
            backoff_seconds = 120 if attempt == 1 else 300 if attempt == 2 else 900
            set_backoff(state, seconds=backoff_seconds, now=now)
            if attempt >= 3:
                quarantine_milestone(state, milestone_id=next_mid, now=now, reason=code)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": backoff_seconds,
                "quarantine_until": state.get("quarantine", {}).get("until"),
                "error_code": code,
            }
            break

        ok_clean, clean_code = _enforce_readonly_clean(
            core_root=core_root,
            baseline_git_status=baseline_git,
            workspace_root=workspace_root,
            baseline_workspace_snapshot=baseline_ws,
        )
        if not ok_clean:
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=clean_code)
            set_checkpoint(state, current_step_id=f"{next_mid}:READONLY_APPLY", last_completed_step_id=state.get("last_completed_step_id"), last_gate_ok=False)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": clean_code,
            }
            break

        if no_apply:
            clear_backoff(state)
            record_last_result(state, status="OK", milestone_id=next_mid, evidence_path=None, error_code=None)
            set_checkpoint(state, current_step_id=None, last_completed_step_id=f"{next_mid}:READONLY_APPLY", last_gate_ok=True)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "OK",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": None,
            }
            break

        # 2) Apply
        argv_apply = [
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            str(roadmap_path),
            "--milestone",
            next_mid,
            "--workspace-root",
            str(workspace_root),
            "--dry-run",
            "false",
        ]
        set_checkpoint(state, current_step_id=f"{next_mid}:APPLY", last_completed_step_id=f"{next_mid}:READONLY_APPLY", last_gate_ok=None)
        save_state(state_path=state_path, state=state)
        res_apply = _run_cmd(core_root, argv_apply, env=env)
        logs_parts.append(res_apply.stdout)
        if res_apply.stderr:
            logs_parts.append("\n" + res_apply.stderr)
        apply_obj: dict[str, Any] = {}
        try:
            apply_obj = json.loads(res_apply.stdout.strip() or "{}")
        except Exception:
            apply_obj = {}
        ev_apply = apply_obj.get("evidence_path") if isinstance(apply_obj, dict) else None
        if isinstance(ev_apply, str) and ev_apply:
            evidence_paths.append(ev_apply)

        if res_apply.returncode != 0:
            code = str(apply_obj.get("error_code") or "ROADMAP_APPLY_FAILED")
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=code)
            set_checkpoint(state, current_step_id=f"{next_mid}:APPLY", last_completed_step_id=f"{next_mid}:READONLY_APPLY", last_gate_ok=False)
            backoff_seconds = 120 if attempt == 1 else 300 if attempt == 2 else 900
            set_backoff(state, seconds=backoff_seconds, now=now)
            if attempt >= 3:
                quarantine_milestone(state, milestone_id=next_mid, now=now, reason=code)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": backoff_seconds,
                "quarantine_until": state.get("quarantine", {}).get("until"),
                "error_code": code,
            }
            break

        # After apply, snapshot the workspace state so post-gates can enforce "no further writes".
        baseline_ws = _snapshot_tree(
            workspace_root,
            ignore_prefixes=[
                ".cache",
                "evidence",
                "dlq",
                "__pycache__",
            ],
        )

        # 3) Post gates (readonly verification style)
        set_checkpoint(state, current_step_id=f"{next_mid}:POST_GATES", last_completed_step_id=f"{next_mid}:APPLY", last_gate_ok=None)
        save_state(state_path=state_path, state=state)
        gate_env = env.copy()
        gate_env["ORCH_ROADMAP_ORCHESTRATOR"] = "1"
        # Avoid recursion + keep it cheaper: post-gate smoke should not re-run roadmap-runner smoke sections.
        gate_env["ORCH_ROADMAP_RUNNER"] = "1"
        gate_argvs = [
            [sys.executable, str(core_root / "ci" / "validate_schemas.py")],
            [sys.executable, str(core_root / "smoke_test.py")],
            [sys.executable, "-m", "src.ops.manage", "policy-check", "--source", "fixtures"],
        ]
        gate_failed_code: str | None = None
        for gargv in gate_argvs:
            gres = _run_cmd(core_root, gargv, env=gate_env)
            logs_parts.append(gres.stdout)
            if gres.stderr:
                logs_parts.append("\n" + gres.stderr)
            ok_clean, clean_code = _enforce_readonly_clean(
                core_root=core_root,
                baseline_git_status=baseline_git,
                workspace_root=workspace_root,
                baseline_workspace_snapshot=baseline_ws,
            )
            if not ok_clean:
                gate_failed_code = clean_code
                break
            if gres.returncode != 0:
                gate_failed_code = "POST_GATES_FAILED"
                break

        if gate_failed_code is not None:
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=gate_failed_code)
            set_checkpoint(state, current_step_id=f"{next_mid}:POST_GATES", last_completed_step_id=f"{next_mid}:APPLY", last_gate_ok=False)
            backoff_seconds = 120 if attempt == 1 else 300 if attempt == 2 else 900
            set_backoff(state, seconds=backoff_seconds, now=now)
            if attempt >= 3:
                quarantine_milestone(state, milestone_id=next_mid, now=now, reason=gate_failed_code)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": backoff_seconds,
                "quarantine_until": state.get("quarantine", {}).get("until"),
                "error_code": gate_failed_code,
            }
            break

        # Success path: mark completed and move on.
        clear_backoff(state)
        clear_quarantine(state)
        mark_completed(state, next_mid)
        completed = state.get("completed_milestones", completed)
        record_last_result(state, status="OK", milestone_id=next_mid, evidence_path=None, error_code=None)
        set_checkpoint(state, current_step_id=None, last_completed_step_id=f"{next_mid}:POST_GATES", last_gate_ok=True)
        save_state(state_path=state_path, state=state)

        if until is not None and next_mid == until:
            out = {
                "status": "OK",
                "next_milestone": None,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": None,
            }
            break

        # Continue loop for --max-steps > 1
        out = {
            "status": "OK",
            "next_milestone": _next_milestone(roadmap_ids, completed),
            "completed": completed,
            "evidence": evidence_paths,
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": None,
        }

    if out.get("status") == "DONE":
        out["next_milestone"] = _next_milestone(roadmap_ids, completed)
        out["completed"] = completed

    return finalize(out=out, state_before=state_before, state_after=state)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.roadmap.orchestrator")
    ap.add_argument("--roadmap", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--until", default=None)
    ap.add_argument("--max-steps", type=int, default=1)
    ap.add_argument("--dry-run-mode", default="readonly", choices=["simulate", "readonly"])
    ap.add_argument("--no-apply", default="false", help="true|false (default: false)")
    ap.add_argument("--state-path", default=None, help="Optional explicit state path.")
    ap.add_argument("--force-unquarantine", action="store_true")
    args = ap.parse_args(argv)

    no_apply_raw = str(args.no_apply).strip().lower()
    if no_apply_raw not in {"true", "false"}:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        payload = follow(
            roadmap_path=Path(str(args.roadmap)),
            workspace_root=Path(str(args.workspace_root)),
            until=(str(args.until) if args.until else None),
            max_steps=int(args.max_steps),
            dry_run_mode=str(args.dry_run_mode),
            no_apply=(no_apply_raw == "true"),
            state_path=(Path(str(args.state_path)) if args.state_path else None),
            force_unquarantine=bool(args.force_unquarantine),
        )
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error_code": "ORCHESTRATOR_ERROR", "message": str(e)[:300]}, ensure_ascii=False, sort_keys=True))
        return 2

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
