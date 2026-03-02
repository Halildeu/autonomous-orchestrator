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
from src.roadmap.orchestrator_actions import _add_actions, _upsert_actions
from src.roadmap.orchestrator_artifacts import (
    _ArtifactCheck,
    _artifact_heal_failed_action,
    _artifact_missing,
    _artifact_missing_action,
    _reconcile_artifact_missing_actions,
    _ensure_promotion_seed_note,
    _incubator_has_files,
    _load_artifact_completeness_policy,
    _promotion_outputs_exist,
)
from src.roadmap.orchestrator_checks import (
    _ops_index_action_from_report,
    _pack_conflict_action,
    _pack_list_sha,
    _pack_manifest_sha_map,
    _pack_validation_report_path,
    _quality_gate_warn_action_from_report,
    _run_ops_index_builder,
    _run_pack_validation,
    _run_quality_gate_checker,
    _run_script_budget_checker,
)
from src.roadmap.orchestrator_preview import (
    _build_milestone_preview,
    _compile_preview_plan,
    _eval_level_for_step,
    _known_step_types,
    _render_deep_analysis,
    _risk_reasons_for_step,
    _step_target_summary,
)
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
    "_reconcile_artifact_missing_actions",
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
        matched = False
        for pattern in allowed:
            pat = str(pattern)
            if pat.endswith("/"):
                if path.startswith(pat):
                    matched = True
                    break
            if fnmatch.fnmatch(path, pat):
                matched = True
                break
        if not matched:
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
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_core_immutability.override.v1.json"
    if override_path.exists():
        try:
            override_obj = _load_json(override_path)
        except Exception:
            override_obj = {}
        if isinstance(override_obj, dict):
            override_allowlist = override_obj.get("ssot_write_allowlist")
            if isinstance(override_allowlist, list):
                obj = dict(obj)
                obj["ssot_write_allowlist"] = override_allowlist
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
    core_write_mode: str
    ssot_write_allowlist: tuple[str, ...]
    require_unlock_reason: bool
    evidence_required_when_unlocked: bool
    blocked_write_error_code: str
    core_git_required: bool


def _load_core_immutability_policy(*, core_root: Path, workspace_root: Path) -> _CoreImmutabilityPolicy:
    defaults = _CoreImmutabilityPolicy(
        enabled=True,
        default_mode="locked",
        allow_env_var="CORE_UNLOCK",
        allow_env_value="1",
        core_write_mode="locked",
        ssot_write_allowlist=tuple(),
        require_unlock_reason=False,
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
    core_write_mode = obj.get("core_write_mode", defaults.core_write_mode)
    if core_write_mode not in {"locked", "ssot_only_when_unlocked"}:
        core_write_mode = defaults.core_write_mode
    raw_allowlist = obj.get("ssot_write_allowlist", list(defaults.ssot_write_allowlist))
    if not isinstance(raw_allowlist, list):
        raw_allowlist = list(defaults.ssot_write_allowlist)
    ssot_write_allowlist = tuple(sorted({str(x) for x in raw_allowlist if isinstance(x, str) and x.strip()}))
    require_unlock_reason = bool(obj.get("require_unlock_reason", defaults.require_unlock_reason))
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
        core_write_mode=str(core_write_mode),
        ssot_write_allowlist=ssot_write_allowlist,
        require_unlock_reason=require_unlock_reason,
        evidence_required_when_unlocked=evidence_required_when_unlocked,
        blocked_write_error_code=str(blocked_write_error_code),
        core_git_required=core_git_required,
    )


def _core_unlock_requested(policy: _CoreImmutabilityPolicy) -> bool:
    unlock_ok = str(os.environ.get(policy.allow_env_var, "")).strip() == str(policy.allow_env_value)
    if not unlock_ok:
        return False
    if policy.require_unlock_reason:
        return bool(str(os.environ.get("CORE_UNLOCK_REASON", "")).strip())
    return True


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
        if policy.core_write_mode == "ssot_only_when_unlocked":
            paths = _git_status_paths(new_lines)
            if not _core_paths_allowed(paths, policy.ssot_write_allowlist):
                return (False, policy.blocked_write_error_code, new_lines)
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
