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


__all__ = [
    "_core_root",
    "_now_utc",
    "_iso8601",
    "_load_json",
    "_to_canonical_json",
    "_sha256_hex",
    "_git_status_porcelain",
    "_git_status_lines",
    "_git_status_paths",
    "_core_paths_allowed",
    "_sha256_file",
    "_is_sha256_hex",
    "_snapshot_tree",
    "_load_governor_global_mode",
    "_load_and_validate_roadmap",
    "_roadmap_milestones",
    "_next_milestone",
    "_check_iso_core_presence",
    "_parse_iso8601",
    "_actions_path",
    "_atomic_write_json",
    "_atomic_write_text",
    "_load_action_register",
    "_action_id",
    "_placeholder_milestones_from_roadmap",
    "_self_heal_placeholder_actions",
    "_supported_step_types",
    "_parse_unknown_step_types",
    "_self_heal_unknown_step_actions",
    "_milestone_has_apply_only_steps",
    "_action_register_has_placeholder",
    "_m0_m1_markers_present",
    "_remove_completed_milestone",
    "_detect_roadmap_drift_and_update_state",
    "_script_budget_action_id",
    "_upsert_actions",
    "_add_actions",
    "_known_step_types",
    "_step_target_summary",
    "_risk_reasons_for_step",
    "_eval_level_for_step",
    "_render_deep_analysis",
    "_compile_preview_plan",
    "_build_milestone_preview",
    "_derive_actions_for_milestone",
    "_derive_actions_from_script_budget",
    "_run_script_budget_checker",
    "_run_quality_gate_checker",
    "_quality_gate_warn_action_from_report",
    "_run_ops_index_builder",
    "_ops_index_action_from_report",
    "_ArtifactCheck",
    "_pack_manifest_sha_map",
    "_pack_list_sha",
    "_pack_validation_report_path",
    "_run_pack_validation",
    "_pack_conflict_action",
    "_DebtPolicy",
    "_load_debt_policy",
    "_CoreImmutabilityPolicy",
    "_load_core_immutability_policy",
    "_core_unlock_requested",
    "_core_immutability_check",
    "_core_touched_action",
    "_system_status_include_repo_hygiene_suggestions",
    "_system_status_snapshot_from_result",
    "_extract_repo_hygiene_count",
    "_extract_quality_status",
    "_load_artifact_completeness_policy",
    "_promotion_outputs_exist",
    "_incubator_has_files",
    "_ensure_promotion_seed_note",
    "_artifact_missing",
    "_artifact_missing_action",
    "_artifact_heal_failed_action",
    "_script_budget_actions_from_report",
    "_mk_orchestrator_run_id",
    "_mk_finish_run_id",
    "_CmdResult",
    "_run_cmd",
    "_enforce_readonly_clean",
]

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

