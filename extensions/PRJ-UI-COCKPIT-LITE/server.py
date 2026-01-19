from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from server_utils import *  # noqa: F403
from server_routes_get import do_GET as _cockpit_do_GET  # noqa: N802


class CockpitHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = _json_dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: int, content: str, content_type: str) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})
            return
        self._send_text(200, path.read_text(encoding="utf-8"), content_type)

    def _wrap_file(self, path: Path) -> dict[str, Any]:
        data, exists, json_valid = _read_json_file(path)
        return {
            "path": str(path),
            "exists": bool(exists),
            "json_valid": bool(json_valid),
            "data": _redact(data),
        }

    def do_GET(self) -> None:  # noqa: N802
        return _cockpit_do_GET(self)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0

        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"status": "FAIL", "error": "INVALID_JSON"})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"status": "FAIL", "error": "INVALID_PAYLOAD"})
            return

        repo_root = self.server.repo_root
        ws_root = self.server.workspace_root

        if parsed.path == "/api/op":
            op = str(payload.get("op") or "").strip()
            op_cfg = _effective_op_job_config(ws_root)
            async_ops = op_cfg["async_ops"]
            if op in async_ops:
                code, out = _start_op_job(self.server, repo_root, ws_root, payload, op=op, async_ops=async_ops)
                self._send_json(code, out)
                return
            code, out = _run_op(repo_root, ws_root, payload)
            self._send_json(code, out)
            return

        if parsed.path == "/api/inbox/triage_apply_ai":
            code, out = _inbox_triage_apply_ai(ws_root, payload)
            self._send_json(code, out)
            return

        if parsed.path == "/api/inbox/triage_set":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return

            request_id = str(payload.get("request_id") or "").strip()
            state_value = str(payload.get("state") or "").strip().upper()
            rationale = str(payload.get("rationale") or "").strip()
            classification_raw = payload.get("classification")
            links_raw = payload.get("links")

            if not request_id or not request_id.startswith("REQ-") or len(request_id) > 80:
                self._send_json(400, {"status": "FAIL", "error": "REQUEST_ID_INVALID"})
                return

            allowed_states = {
                "NEW",
                "NEEDS_INFO",
                "DISMISSED",
                "ROUTE_TO_TICKET",
                "ROUTE_TO_ROADMAP",
                "ROUTE_TO_PROJECT",
                "CONVERT_TO_PROJECT",
            }
            if state_value not in allowed_states:
                self._send_json(400, {"status": "FAIL", "error": "STATE_INVALID", "allowed": sorted(allowed_states)})
                return

            classification: dict[str, str] = {}
            if classification_raw is None:
                classification_raw = {}
            if not isinstance(classification_raw, dict):
                self._send_json(400, {"status": "FAIL", "error": "CLASSIFICATION_INVALID"})
                return
            allowed_classification_keys = {
                "route_bucket",
                "theme_id",
                "milestone",
                "milestone_id",
                "owner_project",
                "project_id",
                "decision",
            }
            for key, value in classification_raw.items():
                k = str(key or "").strip()
                if not k:
                    continue
                if k not in allowed_classification_keys:
                    self._send_json(400, {"status": "FAIL", "error": "CLASSIFICATION_KEY_NOT_ALLOWED", "key": k})
                    return
                v = str(value or "").strip()
                if not v:
                    continue
                if len(v) > 240:
                    self._send_json(400, {"status": "FAIL", "error": "CLASSIFICATION_VALUE_TOO_LONG", "key": k})
                    return
                classification[k] = v

            expected_bucket = None
            if state_value == "ROUTE_TO_ROADMAP":
                expected_bucket = "ROADMAP"
            elif state_value in {"ROUTE_TO_PROJECT", "CONVERT_TO_PROJECT"}:
                expected_bucket = "PROJECT"
            elif state_value in {"ROUTE_TO_TICKET", "DISMISSED"}:
                expected_bucket = "TICKET"

            if expected_bucket:
                if "route_bucket" not in classification:
                    classification["route_bucket"] = expected_bucket
                elif str(classification.get("route_bucket") or "").upper() != expected_bucket:
                    self._send_json(
                        400,
                        {
                            "status": "FAIL",
                            "error": "ROUTE_BUCKET_MISMATCH",
                            "expected": expected_bucket,
                            "got": classification.get("route_bucket"),
                        },
                    )
                    return

            inbox_path = ws_root / ".cache" / "index" / "input_inbox.v0.1.json"
            inbox_obj, inbox_exists, inbox_valid = _read_json_file(inbox_path)
            if not inbox_exists or not inbox_valid or not isinstance(inbox_obj, dict):
                self._send_json(409, {"status": "FAIL", "error": "INBOX_INDEX_UNAVAILABLE"})
                return
            inbox_items = inbox_obj.get("items")
            inbox_list = inbox_items if isinstance(inbox_items, list) else []

            source_item: dict[str, Any] | None = None
            for it in inbox_list:
                if isinstance(it, dict) and str(it.get("request_id") or "").strip() == request_id:
                    source_item = it
                    break
            if source_item is None:
                self._send_json(404, {"status": "FAIL", "error": "REQUEST_ID_NOT_FOUND"})
                return
            evidence_path = str(source_item.get("evidence_path") or "").strip()
            if not evidence_path.startswith(".cache/index/manual_requests/") and "/.cache/index/manual_requests/" not in evidence_path:
                self._send_json(400, {"status": "FAIL", "error": "REQUEST_NOT_TRIAGEABLE"})
                return
            intake = source_item.get("intake") if isinstance(source_item.get("intake"), dict) else {}
            intake_id = str(intake.get("intake_id") or "").strip()

            updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            triage_path = ws_root / ".cache" / "index" / "manual_request_triage.v0.1.json"
            triage_obj, triage_exists, triage_valid = _read_json_file(triage_path)
            triage_data: dict[str, Any] = {}
            if triage_exists and triage_valid and isinstance(triage_obj, dict):
                triage_data = triage_obj
            else:
                triage_data = {"generated_at": updated_at, "items": []}

            triage_items = triage_data.get("items")
            triage_list = triage_items if isinstance(triage_items, list) else []
            triage_data["items"] = triage_list

            entry: dict[str, Any] | None = None
            for it in triage_list:
                if isinstance(it, dict) and str(it.get("request_id") or "").strip() == request_id:
                    entry = it
                    break

            links: dict[str, Any] = {}
            if entry and isinstance(entry.get("links"), dict):
                links = dict(entry.get("links") or {})
            if evidence_path:
                links.setdefault("evidence_path", evidence_path)
            if intake_id:
                links.setdefault("intake_id", intake_id)
            if isinstance(links_raw, dict):
                for k in ["evidence_path", "intake_id", "triage_note_id"]:
                    v = str(links_raw.get(k) or "").strip()
                    if v:
                        links[k] = v

            new_entry = {
                "request_id": request_id,
                "state": state_value,
                "rationale": rationale,
                "classification": classification,
                "updated_at": updated_at,
                "links": links,
            }
            if entry is None:
                triage_list.append(new_entry)
            else:
                entry.clear()
                entry.update(new_entry)

            triage_data["generated_at"] = updated_at
            _atomic_write_text(triage_path, json.dumps(triage_data, ensure_ascii=False, indent=2) + "\n")

            trace_meta = _trace_meta_for_op("inbox-triage-set", {"request_id": request_id, "state": state_value}, ws_root)
            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "OP_CALL",
                    "ts": ts,
                    "op": "inbox-triage-set",
                    "args": _redact({"request_id": request_id, "state": state_value, "classification": classification, "rationale": rationale}),
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(triage_path)],
                },
            )
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": ts,
                    "op": "inbox-triage-set",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(triage_path)],
                },
            )

            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "inbox-triage-set",
                    "request_id": request_id,
                    "triage": _redact(new_entry),
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(triage_path)],
                },
            )
            return

        if parsed.path == "/api/settings/set_override":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            name = str(payload.get("filename") or "")
            if name not in SAFE_OVERRIDE_FILES:
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"})
                return
            if not OVERRIDE_NAME_RE.match(name):
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NAME_INVALID"})
                return
            override_obj = payload.get("json")
            if not isinstance(override_obj, dict):
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_JSON_INVALID"})
                return
            schema_path = _schema_path_for_override(repo_root, name)
            base_path = _base_policy_path(repo_root, name)
            merged_obj = override_obj
            if base_path and base_path.exists():
                try:
                    base_obj = json.loads(base_path.read_text(encoding="utf-8"))
                    merged_obj = _deep_merge(base_obj, override_obj)
                except Exception:
                    self._send_json(400, {"status": "FAIL", "error": "BASE_POLICY_INVALID"})
                    return
            if schema_path:
                errors = _validate_against_schema(schema_path, merged_obj if isinstance(merged_obj, dict) else {})
                if errors:
                    self._send_json(400, {"status": "FAIL", "error": "SCHEMA_INVALID", "errors": errors[:20]})
                    return
            path = _override_path(ws_root, name)
            if path is None:
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_PATH_INVALID"})
                return
            _atomic_write_text(path, _json_dumps_pretty(override_obj))
            trace_meta = _trace_meta_for_op("settings-set-override", {"filename": name}, ws_root)
            entry = {
                "version": "v1",
                "type": "OVERRIDE_SET",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "settings-set-override",
                "filename": name,
                "trace_meta": trace_meta,
                "evidence_paths": [str(path)],
            }
            _chat_append(ws_root, entry)
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "settings-set-override",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(path)],
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "settings-set-override",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(path)],
                    "schema_path": str(schema_path) if schema_path else "",
                },
            )
            return

        if parsed.path == "/api/run_card/set":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            run_card_obj = payload.get("json")
            if not isinstance(run_card_obj, dict):
                self._send_json(400, {"status": "FAIL", "error": "RUN_CARD_INVALID"})
                return
            run_card_path = ws_root / ".cache" / "reports" / "RUN-CARD-LOCAL.v1.json"
            _atomic_write_text(run_card_path, _json_dumps_pretty(run_card_obj))
            trace_meta = _trace_meta_for_op("run-card-set", {}, ws_root)
            entry = {
                "version": "v1",
                "type": "OVERRIDE_SET",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "run-card-set",
                "trace_meta": trace_meta,
                "evidence_paths": [str(run_card_path)],
            }
            _chat_append(ws_root, entry)
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "run-card-set",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(run_card_path)],
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "run-card-set",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(run_card_path)],
                },
            )
            return

        if parsed.path == "/api/extensions/toggle":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            extension_id = str(payload.get("extension_id") or "").strip()
            enabled = payload.get("enabled")
            if not EXTENSION_ID_RE.match(extension_id):
                self._send_json(400, {"status": "FAIL", "error": "EXTENSION_ID_INVALID"})
                return
            if not isinstance(enabled, bool):
                self._send_json(400, {"status": "FAIL", "error": "ENABLED_REQUIRED"})
                return
            overrides = _read_extension_overrides(ws_root)
            overrides.setdefault("version", "v1")
            overrides.setdefault("overrides", {})
            ov = overrides.get("overrides") if isinstance(overrides.get("overrides"), dict) else {}
            ov[extension_id] = {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            overrides["overrides"] = {k: ov[k] for k in sorted(ov.keys())}
            _write_extension_overrides(ws_root, overrides)
            trace_meta = _trace_meta_for_op("extension-toggle", {"extension_id": extension_id}, ws_root)
            evidence_paths = [str(_extension_override_path(ws_root))]
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "OVERRIDE_SET",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "extension-toggle",
                    "extension_id": extension_id,
                    "enabled": enabled,
                    "trace_meta": trace_meta,
                    "evidence_paths": evidence_paths,
                },
            )
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "extension-toggle",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": evidence_paths,
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "extension-toggle",
                    "trace_meta": trace_meta,
                    "evidence_paths": evidence_paths,
                },
            )
            return

        if parsed.path == "/api/chat":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            msg_type = str(payload.get("type") or "NOTE").strip().upper()
            if msg_type not in {"NOTE", "HELP"}:
                self._send_json(400, {"status": "FAIL", "error": "CHAT_TYPE_INVALID"})
                return
            raw_text = payload.get("text") if msg_type == "NOTE" else payload.get("text", "")
            text = _sanitize_text(str(raw_text or ""))
            if msg_type == "NOTE" and not text:
                self._send_json(400, {"status": "FAIL", "error": "NOTE_TEXT_REQUIRED"})
                return
            trace_meta = _trace_meta_for_op("chat-note", {"type": msg_type}, ws_root)
            entry = {
                "version": "v1",
                "type": msg_type,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "text": text,
                "trace_meta": trace_meta,
                "evidence_paths": [str(_chat_store_path(ws_root))],
            }
            entry_out = _chat_append(ws_root, entry)
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "chat-note",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(_chat_store_path(ws_root))],
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(_chat_store_path(ws_root))],
                    "message": _redact(entry_out),
                },
            )
            return

        self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


class CockpitServer(ThreadingHTTPServer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.op_jobs: dict[str, dict[str, Any]] = {}
        self.op_job_procs: dict[str, subprocess.Popen[str]] = {}
        self.op_jobs_lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def _cancel_op_jobs(self) -> None:
        with self.op_jobs_lock:
            running = [(job_id, proc) for job_id, proc in self.op_job_procs.items()]
        for job_id, proc in running:
            try:
                if proc.poll() is not None:
                    continue
                if os.name != "nt":
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except Exception:
                        proc.terminate()
                else:
                    proc.terminate()
            except Exception:
                continue
            finally:
                with self.op_jobs_lock:
                    job = self.op_jobs.get(job_id)
                    if isinstance(job, dict) and str(job.get("job_status") or "") in {"PENDING", "RUNNING"}:
                        job["job_status"] = "CANCELLED"
                        job["finished_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    self.op_job_procs.pop(job_id, None)

    def server_close(self) -> None:  # noqa: N802
        try:
            if hasattr(self, "op_jobs_lock"):
                self._cancel_op_jobs()
        finally:
            super().server_close()


def build_server(repo_root: Path, workspace_root: Path, host: str, port: int, poll_interval: float) -> ThreadingHTTPServer:
    server = CockpitServer((host, port), CockpitHandler)
    server.repo_root = repo_root
    server.workspace_root = workspace_root
    server.allow_roots = _allow_roots(repo_root, workspace_root)
    server.watch_paths = _watch_paths(repo_root, workspace_root) + [
        workspace_root / ".cache" / "index" / "input_inbox.v0.1.json",
        workspace_root / ".cache" / "index" / "manual_request_triage.v0.1.json",
    ]
    server.poll_interval = poll_interval
    server.web_root = (repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "web").resolve()
    return server


def _new_op_job_id() -> str:
    seed = f"{time.time_ns()}:{os.getpid()}:{os.urandom(8).hex()}"
    return "OPJOB-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


DEFAULT_ASYNC_OPS = {
    "system-status",
    "ui-snapshot-bundle",
    "auto-loop",
}


def _cockpit_lite_override_template() -> dict[str, Any]:
    ops = sorted(DEFAULT_ASYNC_OPS)
    return {
        "version": "v1",
        "async_ops": ops,
        "notes": [
            "controls which ops are executed as async jobs in Cockpit Lite",
            "unknown ops are ignored and defaults apply if nothing matches",
        ],
    }


def _effective_op_job_config(ws_root: Path) -> dict[str, set[str]]:
    allowed_ops = set(OP_ARG_MAP.keys())
    default_async = set(DEFAULT_ASYNC_OPS) & allowed_ops

    path = _override_path(ws_root, COCKPIT_LITE_OVERRIDE_NAME)
    override: dict[str, Any] = {}
    if path and path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                override = raw
        except Exception:
            override = {}

    async_raw = override.get("async_ops")
    if isinstance(async_raw, list):
        filtered = {
            str(item).strip()
            for item in async_raw
            if isinstance(item, str) and str(item).strip() and str(item).strip() in allowed_ops
        }
        async_ops = filtered or (set() if len(async_raw) == 0 else set(default_async))
    else:
        async_ops = set(default_async)

    return {"async_ops": async_ops}


def _op_job_timeout_seconds(op: str, merged_args: dict[str, Any]) -> int:
    default = 600
    if op == "auto-loop":
        raw = str(merged_args.get("budget_seconds") or "").strip()
        if raw.isdigit():
            budget = int(raw)
            # Add overhead and clamp to avoid runaway jobs.
            return max(default, min(budget + 90, 3600))
    return default


def _start_op_job(
    server: CockpitServer,
    repo_root: Path,
    ws_root: Path,
    payload: dict[str, Any],
    *,
    op: str,
    async_ops: set[str],
) -> tuple[int, dict[str, Any]]:
    if payload.get("confirm") is not True:
        return 400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"}

    op = str(op or "").strip()
    if op not in async_ops:
        return 400, {"status": "FAIL", "error": "OP_NOT_ASYNC"}
    if op not in OP_ARG_MAP:
        return 400, {"status": "FAIL", "error": "OP_NOT_ALLOWED"}

    args = payload.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return 400, {"status": "FAIL", "error": "ARGS_INVALID"}

    merged = dict(OP_DEFAULTS.get(op, {}))
    allowed_args = OP_ARG_MAP.get(op, {})
    for key, value in args.items():
        if key not in allowed_args:
            return 400, {"status": "FAIL", "error": "ARG_NOT_ALLOWED"}
        safe_value = _safe_arg_value(value, max_len=200, allow_newlines=False)
        if safe_value is None:
            return 400, {"status": "FAIL", "error": "ARG_INVALID"}
        merged[key] = safe_value

    if op == "auto-loop":
        merged["budget_seconds"] = str(merged.get("budget_seconds") or "120")

    trace_meta = _trace_meta_for_op(op, merged, ws_root)

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with server.op_jobs_lock:
        for existing_id, existing in server.op_jobs.items():
            if not isinstance(existing, dict):
                continue
            if str(existing.get("op") or "") != op:
                continue
            existing_status = str(existing.get("job_status") or "")
            if existing_status not in {"PENDING", "RUNNING"}:
                continue
            existing_trace = existing.get("trace_meta") if isinstance(existing.get("trace_meta"), dict) else {}
            return (
                200,
                {
                    "status": existing_status,
                    "job_id": existing_id,
                    "job_status": existing_status,
                    "poll_url": f"/api/op_job?job_id={existing_id}",
                    "op": op,
                    "trace_meta": existing_trace,
                    "evidence_paths": [],
                    "notes": [
                        "PROGRAM_LED=true",
                        "NO_NETWORK=true",
                        "OP_ASYNC=true",
                        "SINGLEFLIGHT=true",
                        "JOB_REUSED=true",
                    ],
                },
            )

        job_id = _new_op_job_id()
        server.op_jobs[job_id] = {
            "job_id": job_id,
            "job_status": "PENDING",
            "op": op,
            "trace_meta": trace_meta,
            "created_at": now_iso,
            "started_at": "",
            "finished_at": "",
            "result": None,
        }

    _chat_append(
        ws_root,
        {
            "version": "v1",
            "type": "OP_CALL",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": op,
            "args": _redact(merged),
            "trace_meta": trace_meta,
            "evidence_paths": [],
        },
    )

    cmd = [sys.executable, "-m", "src.ops.manage", op, "--workspace-root", str(ws_root)]
    for key, flag in allowed_args.items():
        if key in merged:
            if not flag:
                continue
            cmd.extend([flag, str(merged[key])])

    def _job_thread() -> None:
        start_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with server.op_jobs_lock:
            job = server.op_jobs.get(job_id)
            if isinstance(job, dict):
                job["job_status"] = "RUNNING"
                job["started_at"] = start_iso

        proc: subprocess.Popen[str] | None = None
        stdout = ""
        stderr = ""
        timed_out = False

        try:
            timeout_seconds = _op_job_timeout_seconds(op, merged)
            proc = subprocess.Popen(
                cmd,
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=(os.name != "nt"),
            )
            with server.op_jobs_lock:
                server.op_job_procs[job_id] = proc

            try:
                stdout, stderr = proc.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    if os.name != "nt":
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except Exception:
                            proc.kill()
                    else:
                        proc.kill()
                except Exception:
                    pass
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                except Exception:
                    stdout = stdout or ""
                    stderr = stderr or ""

            returncode = proc.returncode if proc.returncode is not None else 1
        except Exception as exc:
            timed_out = False
            returncode = 2
            stderr = str(exc)
        finally:
            with server.op_jobs_lock:
                server.op_job_procs.pop(job_id, None)

        status = "OK" if int(returncode) == 0 else "FAIL"
        evidence_paths: list[str] = []
        parsed = None
        for line in str(stdout or "").splitlines()[::-1]:
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

        payload_out: dict[str, Any] = {
            "status": "WARN" if timed_out else status,
            "op": op,
            "trace_meta": trace_meta,
            "evidence_paths": sorted(set(evidence_paths)),
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "OP_ASYNC=true"],
        }
        if timed_out:
            payload_out["error"] = "TIMEOUT"
            payload_out["timeout_seconds"] = _op_job_timeout_seconds(op, merged)

        if int(returncode) != 0 and str(payload_out.get("status") or "") not in {"WARN", "IDLE"}:
            payload_out["status"] = "FAIL"

        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "RESULT",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "status": payload_out.get("status"),
                "error_code": payload_out.get("error") or payload_out.get("error_code"),
                "trace_meta": trace_meta,
                "evidence_paths": payload_out.get("evidence_paths", []),
            },
        )

        finished_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with server.op_jobs_lock:
            job = server.op_jobs.get(job_id)
            if isinstance(job, dict) and str(job.get("job_status") or "") != "CANCELLED":
                job["job_status"] = "DONE"
                job["finished_at"] = finished_iso
                job["result"] = payload_out

    threading.Thread(target=_job_thread, daemon=True).start()

    return (
        200,
        {
            "status": "RUNNING",
            "job_id": job_id,
            "job_status": "RUNNING",
            "poll_url": f"/api/op_job?job_id={job_id}",
            "op": op,
            "trace_meta": trace_meta,
            "evidence_paths": [],
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "OP_ASYNC=true"],
        },
    )


def _write_status_report(ws_root: Path, port: int) -> None:
    out = ws_root / ".cache" / "reports" / "ui_cockpit_lite_status.v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "status": "OK",
        "port": int(port),
        "workspace_root": str(ws_root),
        "started_at": int(time.time()),
    }
    out.write_text(_json_dumps(payload), encoding="utf-8")


def run_server(workspace_root: Path, host: str, port: int, poll_interval: float) -> None:
    _write_status_report(workspace_root, port)
    httpd = build_server(_find_repo_root(Path(__file__).resolve()), workspace_root, host, port, poll_interval)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return
    finally:
        httpd.server_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".cache/ws_customer_default")
    parser.add_argument("--port", default="8787")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = Path(str(args.workspace_root)).expanduser()
    ws = (repo_root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    try:
        port = int(str(args.port))
    except Exception:
        port = 8787
    run_server(ws, str(args.host), port, poll_interval=1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
