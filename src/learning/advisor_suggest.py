from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    # src/learning/advisor_suggest.py -> repo root
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


def _sha_id(seed: str) -> str:
    return sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class AdvisorPolicy:
    enabled: bool
    public_candidates_path: str
    ops_run_index_path: str
    ops_dlq_index_path: str
    action_register_path: str
    output_path: str
    max_suggestions: int
    min_confidence_to_emit: float
    on_fail: str
    forbid_kinds: list[str]


def _load_policy(core_root: Path, workspace_root: Path) -> AdvisorPolicy:
    defaults = AdvisorPolicy(
        enabled=True,
        public_candidates_path=".cache/learning/public_candidates.v1.json",
        ops_run_index_path=".cache/index/run_index.v1.json",
        ops_dlq_index_path=".cache/index/dlq_index.v1.json",
        action_register_path=".cache/roadmap_actions.v1.json",
        output_path=".cache/learning/advisor_suggestions.v1.json",
        max_suggestions=50,
        min_confidence_to_emit=0.2,
        on_fail="warn",
        forbid_kinds=["SECRET_HINT", "TENANT_IDENTITY"],
    )

    ws_policy = workspace_root / "policies" / "policy_advisor.v1.json"
    core_policy = core_root / "policies" / "policy_advisor.v1.json"
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
    inputs = obj.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}

    def _path_or_default(key: str, dflt: str) -> str:
        raw = inputs.get(key, dflt)
        return str(raw) if isinstance(raw, str) and raw.strip() else dflt

    public_candidates_path = _path_or_default("public_candidates_path", defaults.public_candidates_path)
    ops_run_index_path = _path_or_default("ops_run_index_path", defaults.ops_run_index_path)
    ops_dlq_index_path = _path_or_default("ops_dlq_index_path", defaults.ops_dlq_index_path)
    action_register_path = _path_or_default("action_register_path", defaults.action_register_path)

    output_path = obj.get("output_path", defaults.output_path)
    if not isinstance(output_path, str) or not output_path.strip():
        output_path = defaults.output_path

    def _int_or_default(val: Any, dflt: int) -> int:
        try:
            return max(0, int(val))
        except Exception:
            return dflt

    max_suggestions = _int_or_default(obj.get("max_suggestions", defaults.max_suggestions), defaults.max_suggestions)

    try:
        min_conf = float(obj.get("min_confidence_to_emit", defaults.min_confidence_to_emit))
    except Exception:
        min_conf = defaults.min_confidence_to_emit
    if not (0 <= min_conf <= 1):
        min_conf = defaults.min_confidence_to_emit

    on_fail = obj.get("on_fail", defaults.on_fail)
    if on_fail not in {"warn", "block"}:
        on_fail = defaults.on_fail

    raw_forbid = obj.get("forbid_kinds", defaults.forbid_kinds)
    forbid_kinds = (
        [str(x) for x in raw_forbid if isinstance(x, str) and x.strip()] if isinstance(raw_forbid, list) else []
    )
    if not forbid_kinds:
        forbid_kinds = defaults.forbid_kinds

    return AdvisorPolicy(
        enabled=enabled,
        public_candidates_path=public_candidates_path,
        ops_run_index_path=ops_run_index_path,
        ops_dlq_index_path=ops_dlq_index_path,
        action_register_path=action_register_path,
        output_path=str(output_path),
        max_suggestions=max_suggestions,
        min_confidence_to_emit=min_conf,
        on_fail=str(on_fail),
        forbid_kinds=forbid_kinds,
    )


def _safe_load(path: Path) -> tuple[Any | None, str | None]:
    if not path.exists():
        return (None, "MISSING")
    try:
        return (_load_json(path), None)
    except Exception:
        return (None, "INVALID_JSON")


def _resolve_workspace_path(workspace_root: Path, rel: str) -> Path | None:
    path = (workspace_root / rel).resolve()
    return path if _is_within_root(path, workspace_root) else None


def _build_suggestions(
    *,
    public_candidates: dict[str, Any] | None,
    run_index: dict[str, Any] | None,
    dlq_index: dict[str, Any] | None,
    actions_obj: dict[str, Any] | None,
    min_conf: float,
    max_suggestions: int,
    forbid_kinds: list[str],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    notes: list[str] = []
    forbidden_hits: list[str] = []
    suggestions: list[dict[str, Any]] = []

    actions = actions_obj.get("actions") if isinstance(actions_obj, dict) else None
    action_list = [a for a in actions if isinstance(a, dict)] if isinstance(actions, list) else []
    action_kinds = [a.get("kind") for a in action_list if isinstance(a.get("kind"), str)]
    action_kinds_set = set(action_kinds)

    # Maintainability suggestion (script budget debt).
    if action_kinds_set.intersection({"SCRIPT_BUDGET", "MAINTAINABILITY_DEBT", "MAINTAINABILITY_BLOCKER"}):
        suggestions.append(
            {
                "kind": "MAINTAINABILITY",
                "title": "Reduce oversized Python modules",
                "details": "Script budget warnings indicate large modules; consider splitting into smaller components.",
                "confidence": 0.6,
                "evidence_refs": [".cache/roadmap_actions.v1.json"],
                "recommended_action": "Plan a refactor under M0 to reduce LOC without changing behavior.",
            }
        )

    # Quality suggestion.
    if "QUALITY_GATE_WARN" in action_kinds_set:
        suggestions.append(
            {
                "kind": "QUALITY",
                "title": "Address quality gate warnings",
                "details": "Quality gate warnings indicate missing ISO/format checks or required sections.",
                "confidence": 0.5,
                "evidence_refs": [".cache/roadmap_actions.v1.json"],
                "recommended_action": "Close quality gaps and re-run the quality gate under M6.",
            }
        )

    # Placeholder milestone suggestions.
    for a in action_list:
        if a.get("kind") != "PLACEHOLDER_MILESTONE":
            continue
        milestone = a.get("milestone_hint") or a.get("target_milestone")
        if not isinstance(milestone, str) or not milestone:
            continue
        suggestions.append(
            {
                "kind": "NEXT_MILESTONE",
                "title": f"Make {milestone} runnable",
                "details": f"Milestone {milestone} is still placeholder-only; define minimal runnable steps.",
                "confidence": 0.7,
                "evidence_refs": [".cache/roadmap_actions.v1.json"],
                "recommended_action": "Define a minimal runnable step set and update the SSOT roadmap.",
            }
        )

    # Public candidates hints.
    candidates = public_candidates.get("candidates") if isinstance(public_candidates, dict) else None
    candidates_list = [c for c in candidates if isinstance(c, dict)] if isinstance(candidates, list) else []
    for cand in candidates_list:
        kind = cand.get("kind")
        if kind == "PACK_HINT":
            pack_ids = []
            val = cand.get("value")
            if isinstance(val, dict):
                ids = val.get("pack_ids")
                if isinstance(ids, list):
                    pack_ids = [str(x) for x in ids if isinstance(x, str)]
            details = f"Pack candidates present: {', '.join(pack_ids) or 'unknown'}."
            suggestions.append(
                {
                    "kind": "PACK",
                    "title": "Review pack candidates",
                    "details": details,
                    "confidence": 0.3,
                    "evidence_refs": [".cache/learning/public_candidates.v1.json"],
                    "recommended_action": "Review pack candidates and decide if any should be promoted.",
                }
            )
        if kind == "FORMAT_HINT":
            fmt_ids = []
            val = cand.get("value")
            if isinstance(val, dict):
                ids = val.get("format_ids")
                if isinstance(ids, list):
                    fmt_ids = [str(x) for x in ids if isinstance(x, str)]
            details = f"Format candidates present: {', '.join(fmt_ids) or 'unknown'}."
            suggestions.append(
                {
                    "kind": "FORMAT",
                    "title": "Review format candidates",
                    "details": details,
                    "confidence": 0.3,
                    "evidence_refs": [".cache/learning/public_candidates.v1.json"],
                    "recommended_action": "Review format candidates and align with output standards.",
                }
            )

    # DLQ quality suggestion (counts only).
    dlq_items = dlq_index.get("items") if isinstance(dlq_index, dict) else None
    dlq_list = [d for d in dlq_items if isinstance(d, dict)] if isinstance(dlq_items, list) else []
    if dlq_list:
        exec_count = sum(1 for d in dlq_list if d.get("stage") == "EXECUTION")
        policy_count = sum(1 for d in dlq_list if d.get("error_code") == "POLICY_VIOLATION")
        if exec_count or policy_count:
            suggestions.append(
                {
                    "kind": "QUALITY",
                    "title": "Review execution/policy failures",
                    "details": f"DLQ shows EXECUTION={exec_count}, POLICY_VIOLATION={policy_count}.",
                    "confidence": 0.5,
                    "evidence_refs": [".cache/index/dlq_index.v1.json"],
                    "recommended_action": "Review failure patterns and update guardrails or fixtures.",
                }
            )

    filtered: list[dict[str, Any]] = []
    for s in suggestions:
        kind = s.get("kind")
        if isinstance(kind, str) and kind in forbid_kinds:
            forbidden_hits.append(kind)
            continue
        try:
            conf = float(s.get("confidence", 0))
        except Exception:
            conf = 0.0
        if conf < min_conf:
            continue
        filtered.append(s)

    if forbidden_hits:
        notes.append("FORBIDDEN_KIND_FILTERED")

    # Deterministic ordering + IDs.
    stable: list[dict[str, Any]] = []
    for s in filtered:
        kind = str(s.get("kind") or "")
        title = str(s.get("title") or "")
        details = str(s.get("details") or "")
        refs = s.get("evidence_refs") if isinstance(s.get("evidence_refs"), list) else []
        refs_str = ",".join(str(x) for x in refs)
        sug_id = "SUG-" + _sha_id(f"{kind}|{title}|{details}|{refs_str}")
        s_out = dict(s)
        s_out["id"] = sug_id
        stable.append(s_out)

    stable.sort(key=lambda s: (str(s.get("kind") or ""), str(s.get("title") or ""), str(s.get("id") or "")))
    if max_suggestions > 0:
        stable = stable[: int(max_suggestions)]

    return (stable, notes, forbidden_hits)


def build_advisor_bundle(*, workspace_root: Path, core_root: Path | None = None) -> tuple[dict[str, Any], list[str]]:
    core_root = core_root or _repo_root()
    policy = _load_policy(core_root, workspace_root)

    warnings: list[str] = []
    pc_path = _resolve_workspace_path(workspace_root, policy.public_candidates_path)
    run_path = _resolve_workspace_path(workspace_root, policy.ops_run_index_path)
    dlq_path = _resolve_workspace_path(workspace_root, policy.ops_dlq_index_path)
    actions_path = _resolve_workspace_path(workspace_root, policy.action_register_path)

    public_candidates, pc_err = _safe_load(pc_path) if pc_path else (None, "OUTSIDE_ROOT")
    run_index, run_err = _safe_load(run_path) if run_path else (None, "OUTSIDE_ROOT")
    dlq_index, dlq_err = _safe_load(dlq_path) if dlq_path else (None, "OUTSIDE_ROOT")
    actions_obj, act_err = _safe_load(actions_path) if actions_path else (None, "OUTSIDE_ROOT")

    if pc_err:
        warnings.append("PUBLIC_CANDIDATES_" + pc_err)
    if run_err:
        warnings.append("RUN_INDEX_" + run_err)
    if dlq_err:
        warnings.append("DLQ_INDEX_" + dlq_err)
    if act_err:
        warnings.append("ACTIONS_" + act_err)

    candidates_count = 0
    if isinstance(public_candidates, dict):
        cands = public_candidates.get("candidates")
        if isinstance(cands, list):
            candidates_count = len(cands)

    runs_count = 0
    if isinstance(run_index, dict):
        items = run_index.get("items")
        if isinstance(items, list):
            runs_count = len(items)

    dlq_count = 0
    if isinstance(dlq_index, dict):
        items = dlq_index.get("items")
        if isinstance(items, list):
            dlq_count = len(items)

    actions_count = 0
    if isinstance(actions_obj, dict):
        items = actions_obj.get("actions")
        if isinstance(items, list):
            actions_count = len(items)

    suggestions, safety_notes, forbid_hits = _build_suggestions(
        public_candidates=public_candidates if isinstance(public_candidates, dict) else None,
        run_index=run_index if isinstance(run_index, dict) else None,
        dlq_index=dlq_index if isinstance(dlq_index, dict) else None,
        actions_obj=actions_obj if isinstance(actions_obj, dict) else None,
        min_conf=float(policy.min_confidence_to_emit),
        max_suggestions=int(policy.max_suggestions),
        forbid_kinds=policy.forbid_kinds,
    )

    safety_status = "OK"
    notes = safety_notes + warnings
    if forbid_hits:
        safety_status = "FAIL"
    elif notes:
        safety_status = "WARN"

    bundle = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "inputs_summary": {
            "public_candidates_present": public_candidates is not None,
            "run_index_present": run_index is not None,
            "dlq_index_present": dlq_index is not None,
            "actions_present": actions_obj is not None,
            "counts": {
                "candidates": int(candidates_count),
                "runs": int(runs_count),
                "dlq": int(dlq_count),
                "actions": int(actions_count),
            },
        },
        "suggestions": suggestions,
        "safety": {
            "status": safety_status,
            "notes": sorted(set(str(x) for x in notes if isinstance(x, str) and x)),
        },
    }
    return (bundle, forbid_hits)


def _validate_bundle(core_root: Path, bundle: dict[str, Any]) -> list[str]:
    schema_path = core_root / "schemas" / "advisor-suggestions.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING:schemas/advisor-suggestions.schema.json"]
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(bundle), key=lambda e: e.json_path)
    msgs: list[str] = []
    for err in errors[:25]:
        where = err.json_path or "$"
        msgs.append(f"{where}: {err.message}")
    return msgs


def run_advisor_for_workspace(*, workspace_root: Path, core_root: Path | None = None, dry_run: bool) -> dict[str, Any]:
    core_root = core_root or _repo_root()
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        return {"status": "OK", "note": "POLICY_DISABLED"}

    out_path = _resolve_workspace_path(workspace_root, policy.output_path)
    if out_path is None:
        return {"status": "FAIL", "error_code": "OUTSIDE_WORKSPACE_ROOT"}

    bundle, forbid_hits = build_advisor_bundle(workspace_root=workspace_root, core_root=core_root)
    suggestions = bundle.get("suggestions") if isinstance(bundle, dict) else None
    suggestions_count = len(suggestions) if isinstance(suggestions, list) else 0

    errors = _validate_bundle(core_root, bundle)
    if errors:
        return {
            "status": "FAIL",
            "error_code": "SCHEMA_INVALID",
            "errors": errors[:10],
            "suggestions": int(suggestions_count),
            "out": str(out_path),
            "on_fail": policy.on_fail,
        }

    if forbid_hits:
        return {
            "status": "FAIL",
            "error_code": "FORBIDDEN_KIND",
            "forbidden_kinds": sorted(set(forbid_hits)),
            "suggestions": int(suggestions_count),
            "out": str(out_path),
            "on_fail": policy.on_fail,
        }

    if dry_run:
        payload = _dump_json(bundle)
        return {
            "status": "WOULD_WRITE",
            "suggestions": int(suggestions_count),
            "bytes_estimate": len(payload.encode("utf-8")),
            "out": str(out_path),
            "on_fail": policy.on_fail,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_dump_json(bundle), encoding="utf-8")
    return {
        "status": "OK",
        "suggestions": int(suggestions_count),
        "out": str(out_path),
        "on_fail": policy.on_fail,
    }


def action_from_advisor_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    suggestions = result.get("suggestions")
    if not isinstance(suggestions, int):
        suggestions = 0
    title = "Advisor suggestions generated"
    if status == "FAIL":
        title = "Advisor suggestions failed"
    severity = "INFO" if status in {"OK", "WOULD_WRITE"} else "WARN"
    details = {
        "status": status,
        "suggestions": int(suggestions),
        "out": result.get("out"),
        "error_code": result.get("error_code"),
    }
    action_id = _sha_id(f"ADVISOR|{status}|{details.get('out')}")
    return {
        "action_id": action_id,
        "severity": severity,
        "kind": "ADVISOR_SUMMARY" if status in {"OK", "WOULD_WRITE"} else "ADVISOR_FAIL",
        "milestone_hint": "M7",
        "source": "ADVISOR",
        "title": title,
        "details": details,
        "message": f"Advisor suggestions generated: {suggestions}",
        "resolved": status in {"OK", "WOULD_WRITE"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.learning.advisor_suggest", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        dry_run = _parse_bool(str(args.dry_run))
    except Exception:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_DRY_RUN"}, ensure_ascii=False, sort_keys=True))
        return 2

    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        print(json.dumps({"status": "OK", "note": "POLICY_DISABLED"}, ensure_ascii=False, sort_keys=True))
        return 0

    out_rel = str(args.out) if args.out is not None else policy.output_path
    out_path = (workspace_root / out_rel).resolve()
    if not _is_within_root(out_path, workspace_root):
        print(json.dumps({"status": "FAIL", "error_code": "OUTSIDE_WORKSPACE_ROOT"}, ensure_ascii=False, sort_keys=True))
        return 2

    result = run_advisor_for_workspace(workspace_root=workspace_root, core_root=core_root, dry_run=dry_run)
    if isinstance(result, dict):
        result.setdefault("out", str(out_path))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    status = result.get("status") if isinstance(result, dict) else None
    return 0 if status in {"OK", "WOULD_WRITE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
