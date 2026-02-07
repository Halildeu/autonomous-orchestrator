from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.prj_kernel_api.adapter import handle_request as kernel_handle_request
from src.prj_kernel_api.dotenv_loader import resolve_env_value

from server_utils import (
    OP_ARG_MAP,
    OP_DEFAULTS,
    OVERRIDE_NAME_RE,
    SAFE_OVERRIDE_FILES,
    _REPO_ROOT,
    _append_op_call,
    _append_terminal_result,
    _atomic_write_text,
    _base_policy_path,
    _chat_append,
    _deep_merge,
    _json_dumps_pretty,
    _list_planner_messages,
    _override_path,
    _parse_links_value,
    _parse_tags_value,
    _safe_arg_value,
    _schema_path_for_override,
    _thread_id_valid,
    _thread_tag,
    _trace_meta_for_op,
    _validate_against_schema,
    load_prompt_registry,
    resolve_prompt_entry,
)


def _run_op(repo_root: Path, ws_root: Path, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if payload.get("confirm") is not True:
        return 400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"}

    op = str(payload.get("op") or "").strip()
    if op not in OP_ARG_MAP:
        return 400, {"status": "FAIL", "error": "OP_NOT_ALLOWED"}

    args = payload.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return 400, {"status": "FAIL", "error": "ARGS_INVALID"}

    if op == "overrides-write":
        name = str(args.get("name") or "").strip()
        if name not in SAFE_OVERRIDE_FILES:
            return 400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"}
        if not OVERRIDE_NAME_RE.match(name):
            return 400, {"status": "FAIL", "error": "OVERRIDE_NAME_INVALID"}
        override_obj = args.get("json")
        if not isinstance(override_obj, dict):
            return 400, {"status": "FAIL", "error": "OVERRIDE_JSON_INVALID"}
        schema_path = _schema_path_for_override(repo_root, name)
        base_path = _base_policy_path(repo_root, name)
        merged_obj = override_obj
        if base_path and base_path.exists():
            try:
                base_obj = json.loads(base_path.read_text(encoding="utf-8"))
                merged_obj = _deep_merge(base_obj, override_obj)
            except Exception:
                return 400, {"status": "FAIL", "error": "BASE_POLICY_INVALID"}
        if schema_path:
            errors = _validate_against_schema(schema_path, merged_obj if isinstance(merged_obj, dict) else {})
            if errors:
                return 400, {"status": "FAIL", "error": "SCHEMA_INVALID", "errors": errors[:20]}
        path = _override_path(ws_root, name)
        if path is None:
            return 400, {"status": "FAIL", "error": "OVERRIDE_PATH_INVALID"}
        _atomic_write_text(path, _json_dumps_pretty(override_obj))
        trace_meta = _trace_meta_for_op(op, {"name": name}, ws_root)
        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "OVERRIDE_SET",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "filename": name,
                "trace_meta": trace_meta,
                "evidence_paths": [str(path)],
            },
        )
        _append_terminal_result(
            ws_root,
            op=op,
            status="OK",
            error_code="",
            trace_meta=trace_meta,
            evidence_paths=[str(path)],
        )
        return 200, {
            "status": "OK",
            "op": op,
            "trace_meta": trace_meta,
            "evidence_paths": [str(path)],
            "schema_path": str(schema_path) if schema_path else "",
        }

    actual_op = op
    allowed_args = OP_ARG_MAP.get(op, {})
    merged = dict(OP_DEFAULTS.get(op, {}))

    if op == "planner-chat-send-llm":
        thread = str(args.get("thread") or "default").strip().lower()
        if not _thread_id_valid(thread):
            return 400, {"status": "FAIL", "error": "THREAD_ID_INVALID"}
        body_raw = str(args.get("body") or "")
        title_raw = str(args.get("title") or "")
        body = _safe_arg_value(body_raw, max_len=4000, allow_newlines=True)
        title = _safe_arg_value(title_raw, max_len=200, allow_newlines=False)
        if body is None or title is None:
            return 400, {"status": "FAIL", "error": "ARG_INVALID"}
        if not title and body:
            title = body.strip().splitlines()[0][:80]
        if not title and not body:
            return 400, {"status": "FAIL", "error": "TITLE_OR_BODY_REQUIRED"}
        provider_raw = str(args.get("provider_id") or "")
        model_raw = str(args.get("model") or "")
        profile_raw = str(args.get("profile") or "")
        provider_id = (_safe_arg_value(provider_raw, max_len=40, allow_newlines=False) or "").strip().lower()
        model = (_safe_arg_value(model_raw, max_len=120, allow_newlines=False) or "").strip()
        profile = (_safe_arg_value(profile_raw, max_len=40, allow_newlines=False) or "").strip()
        if not provider_id or not model:
            return 400, {"status": "FAIL", "error": "PROVIDER_OR_MODEL_REQUIRED"}

        tags = _parse_tags_value(args.get("tags"))
        tags.append(_thread_tag(thread))
        tags.append("role:user")
        if profile:
            tags.append(f"profile:{profile}")
        tags.append(f"provider:{provider_id}")
        tags.append(f"model:{model}")
        tags = sorted(set(tags))
        merged = {
            "title": title,
            "body": body,
            "tags": ",".join(tags),
            "links_json": "[]",
        }
        actual_op = "planner-notes-create"
        allowed_args = {"title": "--title", "body": "--body", "tags": "--tags", "links_json": "--links-json"}

        trace_meta = _trace_meta_for_op(op, merged, ws_root)
        op_call_row = _append_op_call(ws_root, op=op, args=merged, trace_meta=trace_meta, call_type="OP_CALL")
        op_call_seq = int(op_call_row.get("seq") or 0)
        result_emitted = False
        payload_out: dict[str, Any] = {
            "status": "FAIL",
            "op": op,
            "trace_meta": trace_meta,
            "evidence_paths": [],
            "error_code": "UNHANDLED_EXCEPTION",
        }
        try:
            cmd = [sys.executable, "-m", "src.ops.manage", actual_op, "--workspace-root", str(ws_root)]
            for key, flag in allowed_args.items():
                if key in merged:
                    cmd.extend([flag, str(merged[key])])
            user_proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
            if user_proc.returncode != 0:
                payload_out = {"status": "FAIL", "op": op, "error": "USER_NOTE_CREATE_FAIL", "trace_meta": trace_meta}
                _append_terminal_result(
                    ws_root,
                    op=op,
                    status=payload_out.get("status"),
                    error_code="USER_NOTE_CREATE_FAIL",
                    trace_meta=trace_meta,
                    evidence_paths=[],
                    result_for_seq=op_call_seq,
                )
                result_emitted = True
                return 200, payload_out

            history = _list_planner_messages(ws_root, thread)
            messages = []
            system_prompt = ""
            try:
                registry = load_prompt_registry(workspace_root=ws_root, repo_root=_REPO_ROOT)
                entry = resolve_prompt_entry(registry, "planner_assistant.system")
                if isinstance(entry, dict):
                    system_prompt = str(entry.get("system") or "").strip()
            except Exception:
                system_prompt = ""
            if not system_prompt:
                system_prompt = PLANNER_ASSISTANT_SYSTEM_FALLBACK
            messages.append({"role": "system", "content": system_prompt})
            for note in history[-12:]:
                note_tags = note.get("tags") if isinstance(note.get("tags"), list) else []
                note_role = "assistant" if any(str(t).lower().startswith("role:assistant") for t in note_tags) else "user"
                content = str(note.get("body") or note.get("title") or "").strip()
                if content:
                    messages.append({"role": note_role, "content": content})
            if not messages or messages[-1].get("content") != body:
                messages.append({"role": "user", "content": body})

            auth_present, auth_value = resolve_env_value("KERNEL_API_TOKEN", str(ws_root), env_mode="dotenv")
            req = {
                "version": "v1",
                "kind": "llm_call_live",
                "workspace_root": str(ws_root),
                "env_mode": "dotenv",
                "params": {
                    "provider_id": provider_id,
                    "model": model,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 2000,
                    "dry_run": False,
                },
            }
            if auth_present and auth_value:
                req["params"]["auth_token"] = auth_value
            try:
                llm_resp = kernel_handle_request(req)
            except Exception as exc:
                llm_resp = {
                    "status": "FAIL",
                    "error_code": "KERNEL_REQUEST_EXCEPTION",
                    "message": str(exc)[:220],
                    "payload": {},
                }
            if not isinstance(llm_resp, dict):
                llm_resp = {
                    "status": "FAIL",
                    "error_code": "KERNEL_RESPONSE_INVALID",
                    "message": "Kernel API yanıtı geçersiz.",
                    "payload": {},
                }
            llm_status = str(llm_resp.get("status") or "FAIL")
            llm_payload = llm_resp.get("payload") if isinstance(llm_resp.get("payload"), dict) else {}
            output_preview = str(llm_payload.get("output_preview") or "").strip()
            output_truncated = bool(llm_payload.get("output_truncated"))
            approx_tokens = max(1, int(len(output_preview) / 4)) if output_preview else 0
            if llm_status != "OK" or not output_preview:
                error_code = str(llm_resp.get("error_code") or "")
                message = str(llm_resp.get("message") or "")
                http_status = llm_payload.get("http_status")
                http_status_int = int(http_status) if isinstance(http_status, int) else None
                error_detail = str(llm_payload.get("error_detail") or "").strip()
                parts = [f"[LLM_FAIL] {error_code}"]
                if http_status_int is not None:
                    parts.append(f"HTTP {http_status_int}")
                if message:
                    parts.append(message)
                if error_detail:
                    parts.append(f"detay: {error_detail[:220]}")
                if provider_id == "openai" and http_status_int == 429:
                    parts.append("OpenAI kota/rate limit aşıldı; plan/kota kontrolü yapın veya başka sağlayıcı seçin.")
                output_preview = " | ".join([p for p in parts if p]).strip()
            if not output_preview:
                output_preview = "[LLM_FAIL] Yanıt üretilemedi."
            assistant_body = output_preview[:3500]

            assistant_tags = [f"provider:{provider_id}", f"model:{model}", "role:assistant", _thread_tag(thread)]
            if profile:
                assistant_tags.append(f"profile:{profile}")
            if approx_tokens:
                assistant_tags.append(f"tokens_estimate:{approx_tokens}")
            if output_truncated:
                assistant_tags.append("output_truncated:true")
            assistant_payload = {
                "title": "Assistant",
                "body": assistant_body,
                "tags": ",".join(sorted(set(assistant_tags))),
                "links_json": "[]",
            }
            cmd_assistant = [sys.executable, "-m", "src.ops.manage", "planner-notes-create", "--workspace-root", str(ws_root)]
            for key, flag in allowed_args.items():
                if key in assistant_payload:
                    cmd_assistant.extend([flag, str(assistant_payload[key])])
            assistant_error_code = llm_resp.get("error_code")
            assistant_proc = None
            try:
                assistant_proc = subprocess.run(cmd_assistant, cwd=repo_root, capture_output=True, text=True)
            except Exception:
                assistant_proc = None
            if assistant_proc is None or assistant_proc.returncode != 0:
                assistant_error_code = assistant_error_code or "ASSISTANT_NOTE_CREATE_FAIL"

            payload_out = {
                "status": llm_status,
                "op": op,
                "trace_meta": trace_meta,
                "evidence_paths": [],
                "error_code": assistant_error_code,
                "http_status": llm_payload.get("http_status"),
            }
            _append_terminal_result(
                ws_root,
                op=op,
                status=llm_status,
                error_code=assistant_error_code,
                trace_meta=trace_meta,
                evidence_paths=[],
                result_for_seq=op_call_seq,
            )
            result_emitted = True
            return 200, payload_out
        except Exception as exc:
            payload_out = {
                "status": "FAIL",
                "op": op,
                "trace_meta": trace_meta,
                "evidence_paths": [],
                "error_code": "UNHANDLED_EXCEPTION",
                "message": str(exc)[:220],
            }
            if not result_emitted:
                _append_terminal_result(
                    ws_root,
                    op=op,
                    status="FAIL",
                    error_code="UNHANDLED_EXCEPTION",
                    trace_meta=trace_meta,
                    evidence_paths=[],
                    result_for_seq=op_call_seq,
                )
                result_emitted = True
            return 200, payload_out
        finally:
            if not result_emitted:
                _append_terminal_result(
                    ws_root,
                    op=op,
                    status=payload_out.get("status"),
                    error_code=payload_out.get("error_code") or payload_out.get("error") or "MISSING_RESULT_GUARD",
                    trace_meta=trace_meta,
                    evidence_paths=[],
                    result_for_seq=op_call_seq,
                )

    if op == "planner-chat-send":
        thread = str(args.get("thread") or "default").strip().lower()
        if not _thread_id_valid(thread):
            return 400, {"status": "FAIL", "error": "THREAD_ID_INVALID"}
        title = str(args.get("title") or "")
        body = str(args.get("body") or "")
        if not title and not body:
            return 400, {"status": "FAIL", "error": "TITLE_OR_BODY_REQUIRED"}
        tags = _parse_tags_value(args.get("tags"))
        tags.append(_thread_tag(thread))
        tags = sorted(set(tags))
        links = _parse_links_value(args.get("links"))
        if not links:
            links = _parse_links_value(args.get("links_json"))
        merged = {
            "title": title,
            "body": body,
            "tags": ",".join(tags),
            "links_json": json.dumps(links, ensure_ascii=True, sort_keys=True),
        }
        actual_op = "planner-notes-create"
        allowed_args = {"title": "--title", "body": "--body", "tags": "--tags", "links_json": "--links-json"}
    else:
        for key, value in args.items():
            if key not in allowed_args:
                return 400, {"status": "FAIL", "error": "ARG_NOT_ALLOWED"}
            max_len = 200
            allow_newlines = False
            if op == "planner-notes-create":
                if key == "body":
                    max_len = 4000
                    allow_newlines = True
                elif key == "links_json":
                    max_len = 2000
                elif key == "tags":
                    max_len = 500
            if op in {"north-star-theme-consult", "north-star-theme-suggestion-apply"} and key == "comment":
                max_len = 4000
                allow_newlines = True
            safe_value = _safe_arg_value(value, max_len=max_len, allow_newlines=allow_newlines)
            if safe_value is None:
                return 400, {"status": "FAIL", "error": "ARG_INVALID"}
            merged[key] = safe_value

    if op == "work-intake-check":
        merged["mode"] = "strict"
    if op == "auto-loop":
        merged["budget_seconds"] = str(merged.get("budget_seconds") or "120")
    if op == "airrunner-run":
        merged["mode"] = "no_wait"
        merged["ticks"] = str(merged.get("ticks") or "2")

    if op in {"smoke-full-triage", "smoke-fast-triage"} and "job_id" not in merged:
        return 400, {"status": "FAIL", "error": "JOB_ID_REQUIRED"}

    trace_meta = _trace_meta_for_op(op, merged, ws_root)
    call_type = "NOTE" if op == "planner-chat-send" else "OP_CALL"
    op_call_row = _append_op_call(ws_root, op=op, args=merged, trace_meta=trace_meta, call_type=call_type)
    op_call_seq = int(op_call_row.get("seq") or 0) if call_type == "OP_CALL" else 0

    cmd = [sys.executable, "-m", "src.ops.manage", actual_op, "--workspace-root", str(ws_root)]
    for key, flag in allowed_args.items():
        if key in merged:
            cmd.extend([flag, str(merged[key])])

    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)

    status = "OK" if proc.returncode == 0 else "FAIL"
    evidence_paths: list[str] = []

    parsed = None
    for line in proc.stdout.splitlines()[::-1]:
        line = line.strip()
        if not line:
            continue
        try:
            candidate = json.loads(line)
        except Exception:
            continue
        if isinstance(candidate, dict):
            parsed = candidate
            break

    if isinstance(parsed, dict):
        status = str(parsed.get("status") or status)
        ev = parsed.get("evidence_paths")
        if isinstance(ev, list):
            evidence_paths = [str(p) for p in ev if isinstance(p, str)]

    return_code = 200
    payload_out = {
        "status": status,
        "op": op,
        "trace_meta": trace_meta,
        "evidence_paths": sorted(set(evidence_paths)),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    if proc.returncode != 0 and status not in {"WARN", "IDLE"}:
        payload_out["status"] = "FAIL"

    _append_terminal_result(
        ws_root,
        op=op,
        status=payload_out.get("status"),
        error_code=payload_out.get("error") or payload_out.get("error_code"),
        trace_meta=trace_meta,
        evidence_paths=payload_out.get("evidence_paths", []),
        result_for_seq=op_call_seq if op_call_seq > 0 else None,
    )
    return return_code, payload_out
