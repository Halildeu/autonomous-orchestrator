from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _rel_to_repo(path: Path, repo_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return None


def _pointer_for_path(
    *,
    path: Path,
    workspace_root: Path,
    repo_root: Path,
    kind: str | None = None,
    label: str | None = None,
) -> dict[str, Any] | None:
    rel_ws = _rel_to_workspace(path, workspace_root)
    if rel_ws:
        return {
            "scope": "workspace",
            "path": rel_ws,
            "kind": kind or "file",
            "label": label or "",
        }
    rel_repo = _rel_to_repo(path, repo_root)
    if rel_repo:
        return {
            "scope": "core",
            "path": rel_repo,
            "kind": kind or "file",
            "label": label or "",
        }
    return {
        "scope": "external",
        "path": str(path),
        "kind": kind or "file",
        "label": label or "",
    }


def _pointer_for_external(path: str, *, kind: str | None = None, label: str | None = None) -> dict[str, Any]:
    return {
        "scope": "external",
        "path": path,
        "kind": kind or "pointer",
        "label": label or "",
    }


def _normalize_pointer(pointer: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        "scope": pointer.get("scope"),
        "path": pointer.get("path"),
    }
    kind = pointer.get("kind")
    label = pointer.get("label")
    if isinstance(kind, str) and kind:
        cleaned["kind"] = kind
    if isinstance(label, str) and label:
        cleaned["label"] = label
    return cleaned


def _sort_pointers(pointers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = [_normalize_pointer(p) for p in pointers if isinstance(p, dict)]
    return sorted(
        cleaned,
        key=lambda p: (str(p.get("scope")), str(p.get("path")), str(p.get("kind", "")), str(p.get("label", ""))),
    )


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "routing": {
            "buckets": ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"],
            "default_bucket": "TICKET",
            "incident_rules": [
                {"if": "doc_nav.critical_nav_gaps>0", "then": "INCIDENT"},
                {"if": "integrity.status==FAIL", "then": "INCIDENT"},
                {"if": "script_budget.hard_exceeded>0", "then": "INCIDENT"},
                {"if": "pdca.regression_count>0", "then": "INCIDENT"},
            ],
            "ticket_rules": [
                {"if": "manual_request.kind in ['support','question','minor_fix']", "then": "TICKET"},
                {"if": "gap.severity in ['LOW'] and gap.effort in ['S']", "then": "TICKET"},
                {"if": "script_budget.soft_only and target_path in ['docs/','ci/']", "then": "TICKET"},
            ],
            "project_rules": [
                {"if": "manual_request.kind in ['feature','refactor','new_project']", "then": "PROJECT"},
                {"if": "gap.severity in ['MEDIUM','HIGH']", "then": "PROJECT"},
                {"if": "script_budget.soft_only and target_path in ['src/ops/','src/orchestrator/']", "then": "PROJECT"},
            ],
            "roadmap_rules": [
                {"if": "manual_request.kind in ['strategy','multi-quarter']", "then": "ROADMAP"},
            ],
        },
        "context_pack": {
            "max_bytes_preview": 4096,
            "pointer_only": True,
            "include_sections": [
                "define",
                "measure_raw",
                "integrity",
                "eval",
                "gap",
                "pdca",
                "guardrails",
                "routing",
            ],
            "redaction": {
                "enabled": True,
                "deny_patterns": ["API_KEY", "PASSWORD", "SECRET"],
                "max_preview_chars": 800,
            },
        },
    }


def _load_policy(repo_root: Path) -> dict[str, Any]:
    policy_path = repo_root / "policies" / "policy_context_pack_router.v1.json"
    if policy_path.exists():
        try:
            obj = _load_json(policy_path)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return _policy_defaults()
    return _policy_defaults()


def _load_manual_request(workspace_root: Path, request_id: str | None) -> tuple[dict[str, Any] | None, str | None, str | None]:
    manual_dir = workspace_root / ".cache" / "index" / "manual_requests"
    if not manual_dir.exists():
        return None, None, None
    if request_id:
        path = manual_dir / f"{request_id}.v1.json"
        if not path.exists():
            return None, None, None
        try:
            obj = _load_json(path)
            return obj if isinstance(obj, dict) else None, request_id, str(path)
        except Exception:
            return None, None, None
    paths = sorted([p for p in manual_dir.glob("*.v1.json") if p.is_file()], key=lambda p: p.as_posix())
    if not paths:
        return None, None, None
    path = paths[-1]
    try:
        obj = _load_json(path)
    except Exception:
        return None, None, None
    if not isinstance(obj, dict):
        return None, None, None
    req_id = obj.get("request_id") if isinstance(obj.get("request_id"), str) else path.stem
    return obj, req_id, str(path)


def _load_doc_nav(workspace_root: Path) -> dict[str, Any]:
    strict_path = workspace_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    summary_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    target = strict_path if strict_path.exists() else summary_path
    if not target.exists():
        return {"critical_nav_gaps": 0}
    try:
        obj = _load_json(target)
    except Exception:
        return {"critical_nav_gaps": 0}
    doc_graph = obj.get("doc_graph") if isinstance(obj, dict) else None
    if not isinstance(doc_graph, dict):
        return {"critical_nav_gaps": 0}
    return {"critical_nav_gaps": int(doc_graph.get("critical_nav_gaps", 0))}


def _load_integrity(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    if not path.exists():
        return {"status": "MISSING"}
    try:
        obj = _load_json(path)
    except Exception:
        return {"status": "INVALID"}
    status = obj.get("status") if isinstance(obj, dict) else None
    return {"status": status if isinstance(status, str) else "UNKNOWN"}


def _load_script_budget(repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_path = workspace_root / ".cache" / "script_budget" / "report.json"
    core_path = repo_root / ".cache" / "script_budget" / "report.json"
    path = ws_path if ws_path.exists() else core_path
    if not path.exists():
        return {"hard_exceeded": 0, "soft_only": False}
    try:
        obj = _load_json(path)
    except Exception:
        return {"hard_exceeded": 0, "soft_only": False}
    hard = obj.get("exceeded_hard") if isinstance(obj.get("exceeded_hard"), list) else []
    soft = obj.get("exceeded_soft") if isinstance(obj.get("exceeded_soft"), list) else []
    hard_count = len([e for e in hard if isinstance(e, dict)])
    soft_count = len([e for e in soft if isinstance(e, dict)])
    return {
        "hard_exceeded": int(hard_count),
        "soft_only": bool(soft_count > 0 and hard_count == 0),
    }


def _load_pdca(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    if not path.exists():
        return {"regression_count": 0}
    try:
        obj = _load_json(path)
    except Exception:
        return {"regression_count": 0}
    regs = obj.get("regressions") if isinstance(obj, dict) else None
    return {"regression_count": len(regs) if isinstance(regs, list) else 0}


def _load_gap_summary(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    if not path.exists():
        return {"severity": "LOW", "effort": "S"}
    try:
        obj = _load_json(path)
    except Exception:
        return {"severity": "LOW", "effort": "S"}
    gaps = obj.get("gaps") if isinstance(obj, dict) else None
    if not isinstance(gaps, list) or not gaps:
        return {"severity": "LOW", "effort": "S"}

    def sev_rank(val: str) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(val.upper(), 0)

    def eff_rank(val: str) -> int:
        return {"S": 0, "LOW": 0, "MEDIUM": 1, "M": 1, "HIGH": 2, "L": 2}.get(val.upper(), 1)

    top_sev = "LOW"
    top_eff = "S"
    for g in gaps:
        if not isinstance(g, dict):
            continue
        sev = str(g.get("severity") or "low").upper()
        eff = str(g.get("effort") or "s").upper()
        if sev_rank(sev) > sev_rank(top_sev):
            top_sev = sev
        if eff_rank(eff) > eff_rank(top_eff):
            top_eff = eff
    return {"severity": top_sev, "effort": top_eff}


def _target_path_from_request(req: dict[str, Any]) -> str:
    attachments = req.get("attachments") if isinstance(req.get("attachments"), list) else []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        if att.get("kind") == "path" and isinstance(att.get("value"), str):
            return str(att.get("value"))
    return ""


def _get_context_value(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _parse_in_list(raw: str) -> list[str]:
    try:
        value = ast.literal_eval(raw)
    except Exception:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if isinstance(x, (str, int))]
    return []


def _eval_clause(clause: str, context: dict[str, Any]) -> bool:
    clause = clause.strip()
    if not clause:
        return False
    if " in " in clause:
        left, right = clause.split(" in ", 1)
        left = left.strip()
        values = _parse_in_list(right.strip())
        current = _get_context_value(context, left)
        if left == "target_path":
            return any(isinstance(current, str) and current.startswith(str(v)) for v in values)
        return str(current) in [str(v) for v in values]
    if "==" in clause:
        left, right = clause.split("==", 1)
        current = _get_context_value(context, left.strip())
        right_val = right.strip().strip("'\"")
        return str(current) == right_val
    if ">" in clause:
        left, right = clause.split(">", 1)
        current = _get_context_value(context, left.strip())
        try:
            return int(current) > int(right.strip())
        except Exception:
            return False
    current = _get_context_value(context, clause)
    return bool(current)


def _eval_expr(expr: str, context: dict[str, Any]) -> bool:
    parts = [p.strip() for p in expr.split(" and ") if p.strip()]
    if not parts:
        return False
    return all(_eval_clause(p, context) for p in parts)


def route_request(*, policy: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    routing = policy.get("routing") if isinstance(policy.get("routing"), dict) else {}
    incident_rules = routing.get("incident_rules") if isinstance(routing.get("incident_rules"), list) else []
    roadmap_rules = routing.get("roadmap_rules") if isinstance(routing.get("roadmap_rules"), list) else []
    project_rules = routing.get("project_rules") if isinstance(routing.get("project_rules"), list) else []
    ticket_rules = routing.get("ticket_rules") if isinstance(routing.get("ticket_rules"), list) else []
    default_bucket = routing.get("default_bucket") if isinstance(routing.get("default_bucket"), str) else "TICKET"

    for rules in (incident_rules, roadmap_rules, project_rules, ticket_rules):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            expr = rule.get("if") if isinstance(rule.get("if"), str) else ""
            if not expr:
                continue
            if _eval_expr(expr, context):
                bucket = rule.get("then") if isinstance(rule.get("then"), str) else default_bucket
                return bucket, [expr]

    return default_bucket, []


def _bucket_defaults(bucket: str) -> tuple[str, str, str]:
    bucket = bucket or "TICKET"
    severity_map = {"INCIDENT": "S1", "PROJECT": "S2", "ROADMAP": "S2", "TICKET": "S3"}
    priority_map = {"INCIDENT": "P1", "PROJECT": "P2", "ROADMAP": "P2", "TICKET": "P3"}
    action_map = {"INCIDENT": "APPLY_SAFE_ONLY", "PROJECT": "PLAN", "ROADMAP": "PLAN", "TICKET": "PLAN"}
    return severity_map.get(bucket, "S3"), priority_map.get(bucket, "P3"), action_map.get(bucket, "PLAN")


def _context_pack_id(request_id: str, refs: list[str]) -> str:
    base = request_id + "|" + "|".join(sorted(refs))
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return f"CP-{digest[:16]}"


def _select_format_ids(workspace_root: Path) -> list[str]:
    formats_path = workspace_root / ".cache" / "index" / "formats.v1.json"
    if not formats_path.exists():
        return []
    try:
        obj = _load_json(formats_path)
    except Exception:
        return []
    formats = obj.get("formats") if isinstance(obj, dict) else None
    if not isinstance(formats, list):
        return []
    ids = []
    for f in formats:
        if isinstance(f, dict) and isinstance(f.get("id"), str):
            ids.append(f.get("id"))
    return sorted(set([i for i in ids if i]))


def _build_define_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, list[dict[str, Any]]]:
    tenant_root = workspace_root / "tenant" / "TENANT-DEFAULT"
    def _maybe(path: Path, label: str) -> list[dict[str, Any]]:
        if path.exists():
            ptr = _pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="doc", label=label)
            return [ptr] if ptr else []
        return []

    refs = {
        "context_refs": _maybe(tenant_root / "context.v1.md", "context"),
        "stakeholders_refs": _maybe(tenant_root / "stakeholders.v1.md", "stakeholders"),
        "scope_refs": _maybe(tenant_root / "scope.v1.md", "scope"),
        "criteria_refs": _maybe(tenant_root / "criteria.v1.md", "criteria"),
        "architecture_refs": [],
        "decision_refs": _maybe(tenant_root / "decision-bundle.v1.json", "decision_bundle"),
    }
    layer_doc = repo_root / "docs" / "LAYER-MODEL-LOCK.v1.md"
    if layer_doc.exists():
        ptr = _pointer_for_path(path=layer_doc, workspace_root=workspace_root, repo_root=repo_root, kind="doc", label="layer_model")
        if ptr:
            refs["architecture_refs"].append(ptr)
    return refs


def _build_gap_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    gap_ptr = _pointer_for_path(path=gap_path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label="gap_register") if gap_path.exists() else None
    top_gap_ids: list[str] = []
    if gap_path.exists():
        try:
            obj = _load_json(gap_path)
        except Exception:
            obj = {}
        gaps = obj.get("gaps") if isinstance(obj, dict) else None
        if isinstance(gaps, list):
            def sev_rank(val: str) -> int:
                return {"high": 0, "medium": 1, "low": 2}.get(val, 2)
            def risk_rank(val: str) -> int:
                return {"high": 0, "medium": 1, "low": 2}.get(val, 2)
            def eff_rank(val: str) -> int:
                return {"low": 0, "medium": 1, "high": 2}.get(val, 1)
            sortable = []
            for g in gaps:
                if not isinstance(g, dict):
                    continue
                gid = g.get("id") if isinstance(g.get("id"), str) else ""
                if not gid:
                    continue
                sev = str(g.get("severity") or "low").lower()
                risk = str(g.get("risk_class") or sev).lower()
                eff = str(g.get("effort") or "medium").lower()
                sortable.append((sev_rank(sev), risk_rank(risk), eff_rank(eff), gid))
            sortable.sort()
            top_gap_ids = [gid for _, _, _, gid in sortable[:5]]
    return {
        "gap_register_ref": gap_ptr,
        "top_gap_ids": top_gap_ids,
    }


def _build_measure_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    def _ptr(rel: str, label: str) -> dict[str, Any] | None:
        path = workspace_root / rel
        if not path.exists():
            return None
        return _pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label=label)

    return {
        "assessment_raw_ref": _ptr(".cache/index/assessment_raw.v1.json", "assessment_raw"),
        "integrity_ref": _ptr(".cache/reports/integrity_verify.v1.json", "integrity"),
        "north_star_ref": _ptr(".cache/index/north_star_catalog.v1.json", "north_star"),
    }


def _build_eval_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    def _ptr(rel: str, label: str) -> dict[str, Any] | None:
        path = workspace_root / rel
        if not path.exists():
            return None
        return _pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label=label)

    return {
        "assessment_eval_ref": _ptr(".cache/index/assessment_eval.v1.json", "assessment_eval"),
        "bp_catalog_ref": _ptr(".cache/index/bp_catalog.v1.json", "bp_catalog"),
        "trend_catalog_ref": _ptr(".cache/index/trend_catalog.v1.json", "trend_catalog"),
        "scorecard_ref": _ptr(".cache/reports/benchmark_scorecard.v1.json", "benchmark_scorecard"),
    }


def _build_pdca_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    def _ptr(rel: str, label: str) -> dict[str, Any] | None:
        path = workspace_root / rel
        if not path.exists():
            return None
        return _pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label=label)

    return {
        "regression_index_ref": _ptr(".cache/index/regression_index.v1.json", "regression_index"),
        "pdca_cursor_ref": _ptr(".cache/index/pdca_cursor.v1.json", "pdca_cursor"),
        "recheck_report_ref": _ptr(".cache/reports/pdca_recheck_report.v1.json", "pdca_recheck"),
    }


def _build_intake_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    intake_ptr = _pointer_for_path(path=intake_path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label="work_intake") if intake_path.exists() else None
    chosen_ids: list[str] = []
    if intake_path.exists():
        try:
            obj = _load_json(intake_path)
        except Exception:
            obj = {}
        summary = obj.get("summary") if isinstance(obj, dict) else None
        top = summary.get("top_next_actions") if isinstance(summary, dict) else None
        if isinstance(top, list):
            for item in top[:5]:
                if isinstance(item, dict) and isinstance(item.get("intake_id"), str):
                    chosen_ids.append(item.get("intake_id"))
    return {"work_intake_ref": intake_ptr, "chosen_intake_ids": chosen_ids}


def _guardrails_snapshot(*, workspace_root: Path) -> dict[str, Any]:
    status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    core_lock = "UNKNOWN"
    layer_boundary = "UNKNOWN"
    if status_path.exists():
        try:
            obj = _load_json(status_path)
        except Exception:
            obj = {}
        sections = obj.get("sections") if isinstance(obj, dict) else None
        if isinstance(sections, dict):
            core = sections.get("core_lock") if isinstance(sections.get("core_lock"), dict) else {}
            layer = sections.get("layer_boundary") if isinstance(sections.get("layer_boundary"), dict) else {}
            if isinstance(core.get("status"), str):
                core_lock = str(core.get("status"))
            if isinstance(layer.get("status"), str):
                layer_boundary = str(layer.get("status"))
    return {
        "core_lock": core_lock,
        "layer_boundary": layer_boundary,
        "network_allowed": False,
        "side_effect_max": "workspace_only",
    }


def build_context_pack(*, workspace_root: Path, request_id: str | None, mode: str = "summary") -> dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    policy = _load_policy(repo_root)

    request_obj, resolved_id, request_path = _load_manual_request(workspace_root, request_id)
    if not request_obj or not resolved_id or not request_path:
        return {"status": "IDLE", "error_code": "REQUEST_NOT_FOUND"}

    request_rel = _rel_to_workspace(Path(request_path), workspace_root) or request_path
    request_ptr = {
        "request_id": resolved_id,
        "scope": "workspace",
        "path": request_rel,
        "kind": "manual_request",
    }

    request_meta = {
        "artifact_type": str(request_obj.get("artifact_type") or "request"),
        "domain": str(request_obj.get("domain") or "general"),
        "kind": str(request_obj.get("kind") or "unspecified"),
        "source_type": str((request_obj.get("source") or {}).get("type") or "human"),
        "created_at": str(request_obj.get("created_at") or _now_iso()),
        "text_bytes": len(str(request_obj.get("text") or "").encode("utf-8")),
    }
    tenant_id = request_obj.get("tenant_id") if isinstance(request_obj.get("tenant_id"), str) else None
    if tenant_id:
        request_meta["tenant_id"] = tenant_id
    attachments = request_obj.get("attachments") if isinstance(request_obj.get("attachments"), list) else []
    request_meta["attachments_count"] = len([a for a in attachments if isinstance(a, dict)])

    define_refs = _build_define_refs(repo_root=repo_root, workspace_root=workspace_root)
    measure_refs = _build_measure_refs(repo_root=repo_root, workspace_root=workspace_root)
    eval_refs = _build_eval_refs(repo_root=repo_root, workspace_root=workspace_root)
    gap_refs = _build_gap_refs(repo_root=repo_root, workspace_root=workspace_root)
    pdca_refs = _build_pdca_refs(repo_root=repo_root, workspace_root=workspace_root)
    intake_refs = _build_intake_refs(repo_root=repo_root, workspace_root=workspace_root)

    pointers: list[dict[str, Any]] = []
    for group in (define_refs.values(), measure_refs.values(), eval_refs.values(), pdca_refs.values(), intake_refs.values()):
        for ptr in group:
            if isinstance(ptr, dict):
                pointers.append(ptr)
    if isinstance(gap_refs.get("gap_register_ref"), dict):
        pointers.append(gap_refs.get("gap_register_ref"))

    for att in attachments:
        if not isinstance(att, dict):
            continue
        kind_val = att.get("kind")
        value = att.get("value")
        if not isinstance(value, str) or not value:
            continue
        if kind_val == "path":
            path_val = Path(value)
            if not path_val.is_absolute():
                path_val = workspace_root / path_val
            ptr = _pointer_for_path(path=path_val, workspace_root=workspace_root, repo_root=repo_root, kind="attachment", label="request_attachment")
            if ptr:
                pointers.append(ptr)
        elif kind_val == "url":
            pointers.append(_pointer_for_external(value, kind="attachment", label="request_attachment"))

    pointer_paths = [str(p.get("path")) for p in pointers if isinstance(p, dict) and p.get("path")]
    context_pack_id = _context_pack_id(resolved_id, pointer_paths)

    _, _, default_action = _bucket_defaults(policy.get("routing", {}).get("default_bucket", "TICKET"))
    routing = {
        "chosen_bucket": policy.get("routing", {}).get("default_bucket", "TICKET"),
        "chosen_action": default_action,
        "recommended_ops": ["work-intake-check", "context-pack-route", "system-status"],
        "output_format_ids": _select_format_ids(workspace_root),
    }

    guardrails = _guardrails_snapshot(workspace_root=workspace_root)

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "context_pack_id": context_pack_id,
        "workspace_root": str(workspace_root),
        "request_ref": request_ptr,
        "request_meta": request_meta,
        "define": define_refs,
        "measure_raw": {k: v for k, v in measure_refs.items() if v},
        "eval": {k: v for k, v in eval_refs.items() if v},
        "gap": {k: v for k, v in gap_refs.items() if v},
        "pdca": {k: v for k, v in pdca_refs.items() if v},
        "intake": {k: v for k, v in intake_refs.items() if v},
        "routing": routing,
        "guardrails": guardrails,
        "evidence_refs": _sort_pointers(pointers),
        "notes": ["PROGRAM_LED=true", "pointer_only=true"],
    }

    out_dir = workspace_root / ".cache" / "index" / "context_packs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{context_pack_id}.v1.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    summary_path = workspace_root / ".cache" / "reports" / "context_pack_summary.v1.md"
    if mode == "summary":
        lines = [
            "# Context Pack Summary",
            "",
            f"Request: {resolved_id}",
            f"Context pack: {context_pack_id}",
            "",
            "Sections:",
            f"- define: {sum(len(v) for v in define_refs.values())} refs",
            f"- measure_raw: {len([v for v in measure_refs.values() if v])} refs",
            f"- eval: {len([v for v in eval_refs.values() if v])} refs",
            f"- gap: {len([v for v in gap_refs.values() if v])} refs",
            f"- pdca: {len([v for v in pdca_refs.values() if v])} refs",
        ]
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "status": "OK",
        "request_id": resolved_id,
        "context_pack_id": context_pack_id,
        "context_pack_path": str(Path(".cache") / "index" / "context_packs" / f"{context_pack_id}.v1.json"),
        "summary_path": str(Path(".cache") / "reports" / "context_pack_summary.v1.md") if mode == "summary" else "",
    }


def route_context_pack(
    *,
    workspace_root: Path,
    context_pack_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    policy = _load_policy(repo_root)

    if context_pack_path is None:
        return {"status": "IDLE", "error_code": "CONTEXT_PACK_MISSING"}
    if not context_pack_path.exists():
        return {"status": "IDLE", "error_code": "CONTEXT_PACK_MISSING"}

    try:
        pack = _load_json(context_pack_path)
    except Exception:
        return {"status": "WARN", "error_code": "CONTEXT_PACK_INVALID"}
    if not isinstance(pack, dict):
        return {"status": "WARN", "error_code": "CONTEXT_PACK_INVALID"}

    request_ref = pack.get("request_ref") if isinstance(pack.get("request_ref"), dict) else {}
    request_id = request_ref.get("request_id") if isinstance(request_ref.get("request_id"), str) else ""
    request_obj, _, request_path = _load_manual_request(workspace_root, request_id)
    if not request_obj:
        return {"status": "WARN", "error_code": "REQUEST_NOT_FOUND"}

    doc_nav = _load_doc_nav(workspace_root)
    integrity = _load_integrity(workspace_root)
    script_budget = _load_script_budget(repo_root, workspace_root)
    pdca = _load_pdca(workspace_root)
    gap = _load_gap_summary(workspace_root)
    target_path = _target_path_from_request(request_obj)

    context = {
        "doc_nav": doc_nav,
        "integrity": integrity,
        "script_budget": script_budget,
        "pdca": pdca,
        "gap": gap,
        "manual_request": {
            "kind": str(request_obj.get("kind") or "unspecified"),
        },
        "target_path": target_path,
    }

    bucket, reasons = route_request(policy=policy, context=context)
    severity, priority, action = _bucket_defaults(bucket)

    constraints = request_obj.get("constraints") if isinstance(request_obj.get("constraints"), dict) else {}
    requires_core_change = bool(constraints.get("requires_core_change", False))
    if str(constraints.get("layer", "")).strip() in {"L0", "L1"}:
        requires_core_change = True
    if requires_core_change:
        action = "APPLY_REQUIRES_UNLOCK"

    router_result = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "request_id": request_id,
        "context_pack_id": str(pack.get("context_pack_id") or ""),
        "status": "OK" if reasons or bucket else "WARN",
        "bucket": bucket,
        "action": action,
        "severity": severity,
        "priority": priority,
        "reasons": reasons,
        "next_actions": ["work-intake-check", "system-status", "context-pack-build"],
        "evidence_paths": [
            str(Path(".cache") / "reports" / "context_pack_router_result.v1.json"),
            str(Path(".cache") / "index" / "context_packs" / context_pack_path.name),
        ],
        "notes": ["PROGRAM_LED=true"],
    }

    out_path = workspace_root / ".cache" / "reports" / "context_pack_router_result.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(router_result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    pack.setdefault("routing", {})
    if isinstance(pack.get("routing"), dict):
        pack["routing"]["chosen_bucket"] = bucket
        pack["routing"]["chosen_action"] = action
        pack["routing"]["recommended_ops"] = ["work-intake-check", "context-pack-route", "system-status"]
        pack["routing"]["output_format_ids"] = _select_format_ids(workspace_root)
        pack["routing"]["router_result_ref"] = {
            "scope": "workspace",
            "path": str(Path(".cache") / "reports" / "context_pack_router_result.v1.json"),
            "kind": "report",
            "label": "context_router_result",
        }
        context_pack_path.write_text(json.dumps(pack, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return router_result
