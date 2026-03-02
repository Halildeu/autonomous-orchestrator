from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def rel_to_repo(path: Path, repo_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return None


def pointer_for_path(
    *,
    path: Path,
    workspace_root: Path,
    repo_root: Path,
    kind: str | None = None,
    label: str | None = None,
) -> dict[str, Any] | None:
    rel_ws = rel_to_workspace(path, workspace_root)
    if rel_ws:
        return {
            "scope": "workspace",
            "path": rel_ws,
            "kind": kind or "file",
            "label": label or "",
        }
    rel_repo = rel_to_repo(path, repo_root)
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


def pointer_for_external(path: str, *, kind: str | None = None, label: str | None = None) -> dict[str, Any]:
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


def sort_pointers(pointers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = [_normalize_pointer(p) for p in pointers if isinstance(p, dict)]
    return sorted(
        cleaned,
        key=lambda p: (str(p.get("scope")), str(p.get("path")), str(p.get("kind", "")), str(p.get("label", ""))),
    )


def policy_defaults() -> dict[str, Any]:
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


def load_policy(repo_root: Path) -> dict[str, Any]:
    policy_path = repo_root / "policies" / "policy_context_pack_router.v1.json"
    if policy_path.exists():
        try:
            obj = load_json(policy_path)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return policy_defaults()
    return policy_defaults()


def load_manual_request(workspace_root: Path, request_id: str | None) -> tuple[dict[str, Any] | None, str | None, str | None]:
    manual_dir = workspace_root / ".cache" / "index" / "manual_requests"
    if not manual_dir.exists():
        return None, None, None
    if request_id:
        path = manual_dir / f"{request_id}.v1.json"
        if not path.exists():
            return None, None, None
        try:
            obj = load_json(path)
            return obj if isinstance(obj, dict) else None, request_id, str(path)
        except Exception:
            return None, None, None
    paths = sorted([p for p in manual_dir.glob("*.v1.json") if p.is_file()], key=lambda p: p.as_posix())
    if not paths:
        return None, None, None
    path = paths[-1]
    try:
        obj = load_json(path)
    except Exception:
        return None, None, None
    if not isinstance(obj, dict):
        return None, None, None
    req_id = obj.get("request_id") if isinstance(obj.get("request_id"), str) else path.stem
    return obj, req_id, str(path)


def load_doc_nav(workspace_root: Path) -> dict[str, Any]:
    strict_path = workspace_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    summary_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    target = strict_path if strict_path.exists() else summary_path
    if not target.exists():
        return {"critical_nav_gaps": 0}
    try:
        obj = load_json(target)
    except Exception:
        return {"critical_nav_gaps": 0}
    doc_graph = obj.get("doc_graph") if isinstance(obj, dict) else None
    if not isinstance(doc_graph, dict):
        return {"critical_nav_gaps": 0}
    return {"critical_nav_gaps": int(doc_graph.get("critical_nav_gaps", 0))}


def load_integrity(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    if not path.exists():
        return {"status": "MISSING"}
    try:
        obj = load_json(path)
    except Exception:
        return {"status": "INVALID"}
    status = obj.get("status") if isinstance(obj, dict) else None
    return {"status": status if isinstance(status, str) else "UNKNOWN"}


def load_script_budget(repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_path = workspace_root / ".cache" / "script_budget" / "report.json"
    core_path = repo_root / ".cache" / "script_budget" / "report.json"
    path = ws_path if ws_path.exists() else core_path
    if not path.exists():
        return {"hard_exceeded": 0, "soft_only": False}
    try:
        obj = load_json(path)
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


def load_pdca(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    if not path.exists():
        return {"regression_count": 0}
    try:
        obj = load_json(path)
    except Exception:
        return {"regression_count": 0}
    regs = obj.get("regressions") if isinstance(obj, dict) else None
    return {"regression_count": len(regs) if isinstance(regs, list) else 0}


def load_gap_summary(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    if not path.exists():
        return {"severity": "LOW", "effort": "S"}
    try:
        obj = load_json(path)
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


def target_path_from_request(req: dict[str, Any]) -> str:
    attachments = req.get("attachments") if isinstance(req.get("attachments"), list) else []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        if att.get("kind") == "path" and isinstance(att.get("value"), str):
            return str(att.get("value"))
    return ""


def context_pack_id(request_id: str, refs: list[str]) -> str:
    base = request_id + "|" + "|".join(sorted(refs))
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return f"CP-{digest[:16]}"


def select_format_ids(workspace_root: Path) -> list[str]:
    formats_path = workspace_root / ".cache" / "index" / "formats.v1.json"
    if not formats_path.exists():
        return []
    try:
        obj = load_json(formats_path)
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


def _tenant_context_schema(repo_root: Path) -> Draft202012Validator | None:
    schema_path = repo_root / "schemas" / "tenant-context.schema.v1.json"
    if not schema_path.exists():
        return None
    try:
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except Exception:
        return None


def tenant_context_validation_notes(*, repo_root: Path, workspace_root: Path, tenant_id: str = "TENANT-DEFAULT") -> list[str]:
    ws_path = workspace_root / "tenant" / tenant_id / "context.v1.json"
    core_path = repo_root / "tenant" / tenant_id / "context.v1.json"
    path = ws_path if ws_path.exists() else core_path
    if not path.exists():
        return ["tenant_context_json_missing_workspace_and_core"]
    validator = _tenant_context_schema(repo_root)
    if validator is None:
        return ["tenant_context_schema_missing"]
    try:
        obj = load_json(path)
    except Exception:
        return ["tenant_context_json_invalid"]
    errors = sorted(validator.iter_errors(obj), key=lambda e: e.json_path)
    if errors:
        return ["tenant_context_schema_invalid"]
    return []


def build_define_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, list[dict[str, Any]]]:
    tenant_root = workspace_root / "tenant" / "TENANT-DEFAULT"
    core_tenant_root = repo_root / "tenant" / "TENANT-DEFAULT"

    def _maybe(path: Path, label: str) -> list[dict[str, Any]]:
        if path.exists():
            ptr = pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="doc", label=label)
            return [ptr] if ptr else []
        return []

    context_refs: list[dict[str, Any]] = []
    context_refs.extend(_maybe(tenant_root / "context.v1.json", "context_json"))
    context_refs.extend(_maybe(tenant_root / "context.v1.md", "context"))
    if not context_refs:
        context_refs.extend(_maybe(core_tenant_root / "context.v1.json", "context_json_core"))
        context_refs.extend(_maybe(core_tenant_root / "context.v1.md", "context_core"))

    refs = {
        "context_refs": context_refs,
        "stakeholders_refs": _maybe(tenant_root / "stakeholders.v1.md", "stakeholders"),
        "scope_refs": _maybe(tenant_root / "scope.v1.md", "scope"),
        "criteria_refs": _maybe(tenant_root / "criteria.v1.md", "criteria"),
        "architecture_refs": [],
        "decision_refs": _maybe(tenant_root / "decision-bundle.v1.json", "decision_bundle"),
    }
    layer_doc = repo_root / "docs" / "LAYER-MODEL-LOCK.v1.md"
    if layer_doc.exists():
        ptr = pointer_for_path(path=layer_doc, workspace_root=workspace_root, repo_root=repo_root, kind="doc", label="layer_model")
        if ptr:
            refs["architecture_refs"].append(ptr)
    return refs


def build_gap_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    gap_ptr = pointer_for_path(path=gap_path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label="gap_register") if gap_path.exists() else None
    top_gap_ids: list[str] = []
    if gap_path.exists():
        try:
            obj = load_json(gap_path)
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


def build_measure_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    def _ptr(rel: str, label: str) -> dict[str, Any] | None:
        path = workspace_root / rel
        if not path.exists():
            return None
        return pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label=label)

    return {
        "assessment_raw_ref": _ptr(".cache/index/assessment_raw.v1.json", "assessment_raw"),
        "integrity_ref": _ptr(".cache/reports/integrity_verify.v1.json", "integrity"),
        "north_star_ref": _ptr(".cache/index/north_star_catalog.v1.json", "north_star"),
    }


def build_eval_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    def _ptr(rel: str, label: str) -> dict[str, Any] | None:
        path = workspace_root / rel
        if not path.exists():
            return None
        return pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label=label)

    return {
        "assessment_eval_ref": _ptr(".cache/index/assessment_eval.v1.json", "assessment_eval"),
        "bp_catalog_ref": _ptr(".cache/index/bp_catalog.v1.json", "bp_catalog"),
        "trend_catalog_ref": _ptr(".cache/index/trend_catalog.v1.json", "trend_catalog"),
        "scorecard_ref": _ptr(".cache/reports/benchmark_scorecard.v1.json", "benchmark_scorecard"),
    }


def build_pdca_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    def _ptr(rel: str, label: str) -> dict[str, Any] | None:
        path = workspace_root / rel
        if not path.exists():
            return None
        return pointer_for_path(path=path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label=label)

    return {
        "regression_index_ref": _ptr(".cache/index/regression_index.v1.json", "regression_index"),
        "pdca_cursor_ref": _ptr(".cache/index/pdca_cursor.v1.json", "pdca_cursor"),
        "recheck_report_ref": _ptr(".cache/reports/pdca_recheck_report.v1.json", "pdca_recheck"),
    }


def build_intake_refs(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    intake_ptr = pointer_for_path(path=intake_path, workspace_root=workspace_root, repo_root=repo_root, kind="index", label="work_intake") if intake_path.exists() else None
    chosen_ids: list[str] = []
    if intake_path.exists():
        try:
            obj = load_json(intake_path)
        except Exception:
            obj = {}
        summary = obj.get("summary") if isinstance(obj, dict) else None
        top = summary.get("top_next_actions") if isinstance(summary, dict) else None
        if isinstance(top, list):
            for item in top[:5]:
                if isinstance(item, dict) and isinstance(item.get("intake_id"), str):
                    chosen_ids.append(item.get("intake_id"))
    return {"work_intake_ref": intake_ptr, "chosen_intake_ids": chosen_ids}


def guardrails_snapshot(*, workspace_root: Path) -> dict[str, Any]:
    status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    core_lock = "UNKNOWN"
    layer_boundary = "UNKNOWN"
    if status_path.exists():
        try:
            obj = load_json(status_path)
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


def redaction_settings(policy: dict[str, Any]) -> tuple[bool, list[str], int]:
    context_pack_cfg = policy.get("context_pack") if isinstance(policy.get("context_pack"), dict) else {}
    redaction_cfg = context_pack_cfg.get("redaction") if isinstance(context_pack_cfg.get("redaction"), dict) else {}
    enabled = bool(redaction_cfg.get("enabled", True))
    deny_patterns_raw = redaction_cfg.get("deny_patterns") if isinstance(redaction_cfg.get("deny_patterns"), list) else []
    deny_patterns = [str(p).upper() for p in deny_patterns_raw if isinstance(p, str) and p.strip()]
    max_chars_raw = redaction_cfg.get("max_preview_chars", 800)
    try:
        max_chars = max(64, int(max_chars_raw))
    except Exception:
        max_chars = 800
    return enabled, deny_patterns, max_chars


def is_sensitive_text(text: str, deny_patterns: list[str]) -> bool:
    upper = str(text or "").upper()
    return any(pattern in upper for pattern in deny_patterns)


def trimmed_text_bytes(text: str, max_chars: int) -> int:
    sample = str(text or "")[:max_chars]
    return len(sample.encode("utf-8"))


def context_pack_fingerprint(
    *,
    request_obj: dict[str, Any],
    request_id: str,
    pointer_paths: list[str],
    mode: str,
    policy: dict[str, Any],
    extra_inputs: dict[str, Any] | None = None,
) -> str:
    policy_version = str(policy.get("version") or "v1")
    request_sig = {
        "artifact_type": str(request_obj.get("artifact_type") or ""),
        "domain": str(request_obj.get("domain") or ""),
        "kind": str(request_obj.get("kind") or ""),
        "source_type": str((request_obj.get("source") or {}).get("type") or ""),
        "text_hash": sha256_text(str(request_obj.get("text") or "")),
        "attachments_hash": sha256_text(canonical_json(request_obj.get("attachments") if isinstance(request_obj.get("attachments"), list) else [])),
        "constraints_hash": sha256_text(canonical_json(request_obj.get("constraints") if isinstance(request_obj.get("constraints"), dict) else {})),
    }
    payload = {
        "request_id": request_id,
        "request_sig": request_sig,
        "pointer_paths": sorted([str(p) for p in pointer_paths if p]),
        "mode": str(mode or "summary"),
        "policy_version": policy_version,
        "extra_inputs": extra_inputs if isinstance(extra_inputs, dict) else {},
    }
    return sha256_text(canonical_json(payload))
