from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.ops.context_pack_loaders import (
    build_define_refs,
    build_eval_refs,
    build_gap_refs,
    build_intake_refs,
    build_measure_refs,
    build_pdca_refs,
    canonical_json,
    context_pack_fingerprint,
    context_pack_id,
    find_repo_root,
    guardrails_snapshot,
    is_sensitive_text,
    load_doc_nav,
    load_gap_summary,
    load_integrity,
    load_json,
    load_manual_request,
    load_pdca,
    load_policy,
    load_script_budget,
    now_iso,
    pointer_for_external,
    pointer_for_path,
    redaction_settings,
    rel_to_workspace,
    select_format_ids,
    sha256_text,
    sort_pointers,
    target_path_from_request,
    tenant_context_validation_notes,
    trimmed_text_bytes,
)
from src.ops.context_pack_routing import bucket_defaults, route_request
from src.session.cross_session_context import build_cross_session_context


CACHE_REL_PATH = Path(".cache") / "index" / "context_pack_cache.v1.json"
ACTIVE_CONTEXT_PACK_REL_PATH = Path(".cache") / "index" / "context_pack.v1.json"


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": "v1", "entries": {}}
    try:
        obj = load_json(path)
    except Exception:
        return {"version": "v1", "entries": {}}
    if not isinstance(obj, dict):
        return {"version": "v1", "entries": {}}
    entries = obj.get("entries") if isinstance(obj.get("entries"), dict) else {}
    return {"version": "v1", "entries": entries}


def _save_cache(path: Path, cache_obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache_obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _schema_validator(repo_root: Path, schema_name: str) -> Draft202012Validator | None:
    schema_path = repo_root / "schemas" / schema_name
    if not schema_path.exists():
        return None
    try:
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except Exception:
        return None


def _validate_payload(repo_root: Path, schema_name: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    validator = _schema_validator(repo_root, schema_name)
    if validator is None:
        return False, "SCHEMA_MISSING"
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        return False, f"{where}: {errors[0].message}"
    return True, None


def _write_summary(*, summary_path: Path, request_id: str, context_pack_id: str, sections: dict[str, int], cache_hit: bool) -> None:
    lines = [
        "# Context Pack Summary",
        "",
        f"Request: {request_id}",
        f"Context pack: {context_pack_id}",
        f"Cache hit: {'true' if cache_hit else 'false'}",
        "",
        "Sections:",
        f"- define: {sections.get('define', 0)} refs",
        f"- measure_raw: {sections.get('measure_raw', 0)} refs",
        f"- eval: {sections.get('eval', 0)} refs",
        f"- gap: {sections.get('gap', 0)} refs",
        f"- pdca: {sections.get('pdca', 0)} refs",
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sync_active_context_pack(*, workspace_root: Path, payload: dict[str, Any]) -> str:
    active_rel = ACTIVE_CONTEXT_PACK_REL_PATH.as_posix()
    active_path = workspace_root / ACTIVE_CONTEXT_PACK_REL_PATH
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return active_rel


def build_context_pack(*, workspace_root: Path, request_id: str | None, mode: str = "summary") -> dict[str, Any]:
    repo_root = find_repo_root(Path(__file__).resolve())
    policy = load_policy(repo_root)

    request_obj, resolved_id, request_path = load_manual_request(workspace_root, request_id)
    if not request_obj or not resolved_id or not request_path:
        return {"status": "IDLE", "error_code": "REQUEST_NOT_FOUND"}

    redaction_enabled, deny_patterns, max_preview_chars = redaction_settings(policy)
    request_rel = rel_to_workspace(Path(request_path), workspace_root) or request_path
    request_ptr = {
        "request_id": resolved_id,
        "scope": "workspace",
        "path": request_rel,
        "kind": "manual_request",
    }

    request_text = str(request_obj.get("text") or "")
    request_meta = {
        "artifact_type": str(request_obj.get("artifact_type") or "request"),
        "domain": str(request_obj.get("domain") or "general"),
        "kind": str(request_obj.get("kind") or "unspecified"),
        "source_type": str((request_obj.get("source") or {}).get("type") or "human"),
        "created_at": str(request_obj.get("created_at") or now_iso()),
        "text_bytes": trimmed_text_bytes(request_text, max_preview_chars),
    }
    tenant_id = request_obj.get("tenant_id") if isinstance(request_obj.get("tenant_id"), str) else None
    if tenant_id:
        request_meta["tenant_id"] = tenant_id
    attachments = request_obj.get("attachments") if isinstance(request_obj.get("attachments"), list) else []
    request_meta["attachments_count"] = len([a for a in attachments if isinstance(a, dict)])

    define_refs = build_define_refs(repo_root=repo_root, workspace_root=workspace_root)
    measure_refs = build_measure_refs(repo_root=repo_root, workspace_root=workspace_root)
    eval_refs = build_eval_refs(repo_root=repo_root, workspace_root=workspace_root)
    gap_refs = build_gap_refs(repo_root=repo_root, workspace_root=workspace_root)
    pdca_refs = build_pdca_refs(repo_root=repo_root, workspace_root=workspace_root)
    intake_refs = build_intake_refs(repo_root=repo_root, workspace_root=workspace_root)

    cross_session_res = build_cross_session_context(workspace_root=workspace_root)
    cross_session_rel = cross_session_res.get("report_path") if isinstance(cross_session_res, dict) else None
    cross_session_hash = ""
    if isinstance(cross_session_rel, str) and cross_session_rel:
        cross_path = (workspace_root / cross_session_rel).resolve()
        if cross_path.exists():
            try:
                cross_session_hash = sha256_text(canonical_json(load_json(cross_path)))
            except Exception:
                cross_session_hash = ""
            ptr = pointer_for_path(
                path=cross_path,
                workspace_root=workspace_root,
                repo_root=repo_root,
                kind="index",
                label="session_cross_context",
            )
            if ptr:
                define_refs.setdefault("decision_refs", []).append(ptr)

    pointers: list[dict[str, Any]] = []
    for group in (define_refs.values(), measure_refs.values(), eval_refs.values(), pdca_refs.values(), intake_refs.values()):
        for ptr in group:
            if isinstance(ptr, dict):
                pointers.append(ptr)
    if isinstance(gap_refs.get("gap_register_ref"), dict):
        pointers.append(gap_refs.get("gap_register_ref"))

    redacted_attachments = 0
    for att in attachments:
        if not isinstance(att, dict):
            continue
        kind_val = att.get("kind")
        value = att.get("value")
        if not isinstance(value, str) or not value:
            continue
        if redaction_enabled and is_sensitive_text(value, deny_patterns):
            redacted_attachments += 1
            continue
        if kind_val == "path":
            path_val = Path(value)
            if not path_val.is_absolute():
                path_val = workspace_root / path_val
            ptr = pointer_for_path(path=path_val, workspace_root=workspace_root, repo_root=repo_root, kind="attachment", label="request_attachment")
            if ptr:
                pointers.append(ptr)
        elif kind_val == "url":
            pointers.append(pointer_for_external(value, kind="attachment", label="request_attachment"))

    pointer_paths = [str(p.get("path")) for p in pointers if isinstance(p, dict) and p.get("path")]
    cache_fingerprint = context_pack_fingerprint(
        request_obj=request_obj,
        request_id=resolved_id,
        pointer_paths=pointer_paths,
        mode=mode,
        policy=policy,
        extra_inputs={"session_cross_hash": cross_session_hash},
    )

    cache_path = workspace_root / CACHE_REL_PATH
    cache_obj = _load_cache(cache_path)
    entry = cache_obj.get("entries", {}).get(cache_fingerprint) if isinstance(cache_obj.get("entries"), dict) else None
    summary_rel = str(Path(".cache") / "reports" / "context_pack_summary.v1.md")
    if isinstance(entry, dict):
        cached_rel = entry.get("context_pack_path") if isinstance(entry.get("context_pack_path"), str) else ""
        cached_id = entry.get("context_pack_id") if isinstance(entry.get("context_pack_id"), str) else ""
        cached_abs = (workspace_root / cached_rel).resolve() if cached_rel else None
        if isinstance(cached_abs, Path) and cached_abs.exists() and cached_id:
            try:
                cached_obj = load_json(cached_abs)
            except Exception:
                cached_obj = {}
            if isinstance(cached_obj, dict):
                _sync_active_context_pack(workspace_root=workspace_root, payload=cached_obj)
            if mode == "summary":
                define_obj = cached_obj.get("define") if isinstance(cached_obj, dict) else {}
                measure_obj = cached_obj.get("measure_raw") if isinstance(cached_obj, dict) else {}
                eval_obj = cached_obj.get("eval") if isinstance(cached_obj, dict) else {}
                gap_obj = cached_obj.get("gap") if isinstance(cached_obj, dict) else {}
                pdca_obj = cached_obj.get("pdca") if isinstance(cached_obj, dict) else {}
                _write_summary(
                    summary_path=workspace_root / summary_rel,
                    request_id=resolved_id,
                    context_pack_id=cached_id,
                    sections={
                        "define": sum(len(v) for v in define_obj.values()) if isinstance(define_obj, dict) else 0,
                        "measure_raw": len([v for v in measure_obj.values() if v]) if isinstance(measure_obj, dict) else 0,
                        "eval": len([v for v in eval_obj.values() if v]) if isinstance(eval_obj, dict) else 0,
                        "gap": len([v for v in gap_obj.values() if v]) if isinstance(gap_obj, dict) else 0,
                        "pdca": len([v for v in pdca_obj.values() if v]) if isinstance(pdca_obj, dict) else 0,
                    },
                    cache_hit=True,
                )
            return {
                "status": "OK",
                "request_id": resolved_id,
                "context_pack_id": cached_id,
                "context_pack_path": cached_rel,
                "summary_path": summary_rel if mode == "summary" else "",
                "cache_hit": True,
            }

    pack_id = context_pack_id(resolved_id, pointer_paths)

    _, _, default_action = bucket_defaults(policy.get("routing", {}).get("default_bucket", "TICKET"))
    routing = {
        "chosen_bucket": policy.get("routing", {}).get("default_bucket", "TICKET"),
        "chosen_action": default_action,
        "recommended_ops": ["work-intake-check", "context-pack-route", "system-status"],
        "output_format_ids": select_format_ids(workspace_root),
    }

    guardrails = guardrails_snapshot(workspace_root=workspace_root)

    notes = ["PROGRAM_LED=true", "pointer_only=true", f"cache_fingerprint={cache_fingerprint}"]
    if redacted_attachments > 0:
        notes.append(f"redacted_attachments={redacted_attachments}")
    tenant_notes = tenant_context_validation_notes(repo_root=repo_root, workspace_root=workspace_root)
    notes.extend([f"tenant_context={n}" for n in tenant_notes])
    shared_keys = cross_session_res.get("shared_keys_total") if isinstance(cross_session_res, dict) else 0
    notes.append(f"session_shared_keys={int(shared_keys or 0)}")

    payload = {
        "version": "v1",
        "generated_at": now_iso(),
        "context_pack_id": pack_id,
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
        "evidence_refs": sort_pointers(pointers),
        "notes": sorted(set(notes)),
    }

    ok, err = _validate_payload(repo_root, "context-pack.schema.v1.json", payload)
    if not ok:
        return {
            "status": "WARN",
            "error_code": "CONTEXT_PACK_SCHEMA_INVALID",
            "message": err,
            "request_id": resolved_id,
        }

    out_dir = workspace_root / ".cache" / "index" / "context_packs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_rel = str(Path(".cache") / "index" / "context_packs" / f"{pack_id}.v1.json")
    out_path = workspace_root / out_rel
    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _sync_active_context_pack(workspace_root=workspace_root, payload=payload)

    if mode == "summary":
        _write_summary(
            summary_path=workspace_root / summary_rel,
            request_id=resolved_id,
            context_pack_id=pack_id,
            sections={
                "define": sum(len(v) for v in define_refs.values()),
                "measure_raw": len([v for v in measure_refs.values() if v]),
                "eval": len([v for v in eval_refs.values() if v]),
                "gap": len([v for v in gap_refs.values() if v]),
                "pdca": len([v for v in pdca_refs.values() if v]),
            },
            cache_hit=False,
        )

    entries = cache_obj.setdefault("entries", {}) if isinstance(cache_obj, dict) else {}
    if isinstance(entries, dict):
        entries[cache_fingerprint] = {
            "context_pack_id": pack_id,
            "context_pack_path": out_rel,
            "updated_at": now_iso(),
        }
    _save_cache(cache_path, cache_obj)

    return {
        "status": "OK",
        "request_id": resolved_id,
        "context_pack_id": pack_id,
        "context_pack_path": out_rel,
        "summary_path": summary_rel if mode == "summary" else "",
        "cache_hit": False,
    }


def route_context_pack(
    *,
    workspace_root: Path,
    context_pack_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = find_repo_root(Path(__file__).resolve())
    policy = load_policy(repo_root)

    if context_pack_path is None:
        return {"status": "IDLE", "error_code": "CONTEXT_PACK_MISSING"}
    if not context_pack_path.exists():
        return {"status": "IDLE", "error_code": "CONTEXT_PACK_MISSING"}

    try:
        pack = load_json(context_pack_path)
    except Exception:
        return {"status": "WARN", "error_code": "CONTEXT_PACK_INVALID"}
    if not isinstance(pack, dict):
        return {"status": "WARN", "error_code": "CONTEXT_PACK_INVALID"}
    ok, _ = _validate_payload(repo_root, "context-pack.schema.v1.json", pack)
    if ok:
        _sync_active_context_pack(workspace_root=workspace_root, payload=pack)

    request_ref = pack.get("request_ref") if isinstance(pack.get("request_ref"), dict) else {}
    request_id = request_ref.get("request_id") if isinstance(request_ref.get("request_id"), str) else ""
    request_obj, _, _ = load_manual_request(workspace_root, request_id)
    if not request_obj:
        return {"status": "WARN", "error_code": "REQUEST_NOT_FOUND"}

    doc_nav = load_doc_nav(workspace_root)
    integrity = load_integrity(workspace_root)
    script_budget = load_script_budget(repo_root, workspace_root)
    pdca = load_pdca(workspace_root)
    gap = load_gap_summary(workspace_root)
    target_path = target_path_from_request(request_obj)

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
    severity, priority, action = bucket_defaults(bucket)

    constraints = request_obj.get("constraints") if isinstance(request_obj.get("constraints"), dict) else {}
    requires_core_change = bool(constraints.get("requires_core_change", False))
    if str(constraints.get("layer", "")).strip() in {"L0", "L1"}:
        requires_core_change = True
    if requires_core_change:
        action = "APPLY_REQUIRES_UNLOCK"

    router_result = {
        "version": "v1",
        "generated_at": now_iso(),
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

    ok, err = _validate_payload(repo_root, "context-pack-router-result.schema.v1.json", router_result)
    if not ok:
        return {"status": "WARN", "error_code": "ROUTER_RESULT_SCHEMA_INVALID", "message": err}

    out_path = workspace_root / ".cache" / "reports" / "context_pack_router_result.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(router_result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    pack.setdefault("routing", {})
    if isinstance(pack.get("routing"), dict):
        pack["routing"]["chosen_bucket"] = bucket
        pack["routing"]["chosen_action"] = action
        pack["routing"]["recommended_ops"] = ["work-intake-check", "context-pack-route", "system-status"]
        pack["routing"]["output_format_ids"] = select_format_ids(workspace_root)
        pack["routing"]["router_result_ref"] = {
            "scope": "workspace",
            "path": str(Path(".cache") / "reports" / "context_pack_router_result.v1.json"),
            "kind": "report",
            "label": "context_router_result",
        }
        context_pack_path.write_text(json.dumps(pack, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    # Persist routing decision to session context for cross-session continuity
    _persist_routing_to_session(
        workspace_root=workspace_root,
        context_pack_id=pack.get("context_pack_id", ""),
        bucket=bucket,
        action=action,
    )

    return router_result


def _persist_routing_to_session(
    *,
    workspace_root: Path,
    context_pack_id: str,
    bucket: str,
    action: str,
) -> None:
    """Record routing decision in session context (fail-open)."""
    try:
        from src.session.context_store import (
            SessionContextError,
            SessionPaths,
            load_context,
            save_context_atomic,
            upsert_decision,
        )
    except Exception:
        return

    sp = SessionPaths(workspace_root=workspace_root, session_id="default")
    if not sp.context_path.exists():
        return

    try:
        ctx = load_context(sp.context_path)
        upsert_decision(
            ctx,
            key=f"route:{context_pack_id}",
            value={"bucket": bucket, "action": action},
            source="agent",
        )
        save_context_atomic(sp.context_path, ctx)
    except (SessionContextError, Exception):
        pass  # fail-open
