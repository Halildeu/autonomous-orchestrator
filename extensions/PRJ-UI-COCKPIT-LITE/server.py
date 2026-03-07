from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
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
from keyword_search import KeywordIndexManager
from server_timeline import TIMELINE_SUMMARY_REL, derive_timeline_dashboard, run_timeline_watchdog
from server_north_star import build_north_star_payload
from server_get import handle_do_get


def _short_str(value: Any, limit: int = 300) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def _normalize_jsonable(obj: Any, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return _short_str(obj)
    if isinstance(obj, dict):
        return {str(key): _normalize_jsonable(value, depth + 1, max_depth) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_normalize_jsonable(item, depth + 1, max_depth) for item in obj]
    if isinstance(obj, (tuple, set)):
        return [_normalize_jsonable(item, depth + 1, max_depth) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return _short_str(obj)


FRONTEND_TELEMETRY_ALLOWED_TYPES = {"runtime_error", "unhandled_rejection", "console_error"}
FRONTEND_TELEMETRY_EVENTS_REL = Path(".cache") / "reports" / "cockpit_frontend_telemetry.v1.jsonl"
FRONTEND_TELEMETRY_SUMMARY_REL = Path(".cache") / "reports" / "cockpit_frontend_telemetry_summary.v1.json"


def _sanitize_frontend_telemetry_text(value: Any, *, limit: int = 400, preserve_newlines: bool = False) -> str:
    text = _sanitize_text(str(value or ""))
    text = re.sub(
        r"(?i)\b(secret|token|password|api_key|access_key|private_key|credential)\b\s*[:=]\s*\S+",
        r"\1=<redacted>",
        text,
    )
    if preserve_newlines:
        lines = [line.strip() for line in text.replace("\r", "\n").splitlines()]
        text = "\n".join(line for line in lines if line)
    else:
        text = " ".join(text.split())
    return _short_str(text, limit=limit)


def _safe_nonnegative_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except Exception:
        return 0


def _workspace_rel(ws_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(ws_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _record_frontend_telemetry(ws_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("event_type") or "").strip().lower()
    if event_type not in FRONTEND_TELEMETRY_ALLOWED_TYPES:
        raise ValueError("EVENT_TYPE_INVALID")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    message = _sanitize_frontend_telemetry_text(payload.get("message"), limit=500)
    if not message:
        raise ValueError("MESSAGE_REQUIRED")

    source = _sanitize_frontend_telemetry_text(payload.get("source"), limit=240)
    href = _sanitize_frontend_telemetry_text(payload.get("href"), limit=400)
    stack = _sanitize_frontend_telemetry_text(payload.get("stack"), limit=1800, preserve_newlines=True)
    user_agent = _sanitize_frontend_telemetry_text(payload.get("user_agent"), limit=240)
    line = _safe_nonnegative_int(payload.get("line"))
    column = _safe_nonnegative_int(payload.get("column"))

    record = {
        "version": "v1",
        "ts": now,
        "event_type": event_type,
        "message": message,
        "source": source,
        "href": href,
        "line": line,
        "column": column,
    }
    if stack:
        record["stack"] = stack
    if user_agent:
        record["user_agent"] = user_agent

    events_path = ws_root / FRONTEND_TELEMETRY_EVENTS_REL
    summary_path = ws_root / FRONTEND_TELEMETRY_SUMMARY_REL
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")

    previous_summary: dict[str, Any] = {}
    if summary_path.exists():
        try:
            raw_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(raw_summary, dict):
                previous_summary = raw_summary
        except Exception:
            previous_summary = {}

    summary = {
        "version": "v1",
        "status": "WARN",
        "generated_at": now,
        "events_path": FRONTEND_TELEMETRY_EVENTS_REL.as_posix(),
        "total_events": int(previous_summary.get("total_events") or 0) + 1,
        "runtime_error_count": int(previous_summary.get("runtime_error_count") or 0),
        "console_error_count": int(previous_summary.get("console_error_count") or 0),
        "unhandled_rejection_count": int(previous_summary.get("unhandled_rejection_count") or 0),
        "last_event_at": now,
        "last_event_type": event_type,
        "last_message": message,
        "last_source": source,
        "last_href": href,
    }
    if event_type == "runtime_error":
        summary["runtime_error_count"] += 1
    elif event_type == "console_error":
        summary["console_error_count"] += 1
    elif event_type == "unhandled_rejection":
        summary["unhandled_rejection_count"] += 1

    _atomic_write_text(summary_path, _json_dumps_pretty(summary))
    return {
        "events_path": _workspace_rel(ws_root, events_path),
        "summary_path": _workspace_rel(ws_root, summary_path),
        "event_type": event_type,
    }


class CockpitHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    @staticmethod
    def _is_client_disconnect(exc: Exception) -> bool:
        if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
            return True
        if isinstance(exc, OSError):
            if getattr(exc, "errno", None) in {32, 54, 104}:
                return True
        return False

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = _json_dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            if self._is_client_disconnect(exc):
                return
            raise

    def _send_text(self, status: int, content: str, content_type: str) -> None:
        data = content.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            if self._is_client_disconnect(exc):
                return
            raise

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
        repo_root = self.server.repo_root
        ws_root = self.server.workspace_root
        allow_roots = self.server.allow_roots
        parsed = urlparse(self.path)
        handle_do_get(self, repo_root=repo_root, ws_root=ws_root, allow_roots=allow_roots, parsed=parsed)

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

        if parsed.path == "/api/decision_mark":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            intake_id = str(payload.get("intake_id") or "").strip()
            selected_option = str(payload.get("selected_option") or "").strip().upper()
            note = str(payload.get("note") or "").strip()
            if not intake_id or not intake_id.startswith("INTAKE-") or len(intake_id) > 120:
                self._send_json(400, {"status": "FAIL", "error": "INTAKE_ID_INVALID"})
                return
            if selected_option not in {"A", "B", "C", "D"}:
                self._send_json(400, {"status": "FAIL", "error": "SELECTED_OPTION_INVALID"})
                return
            if len(note) > 800:
                self._send_json(400, {"status": "FAIL", "error": "NOTE_TOO_LONG"})
                return

            user_marks_path = ws_root / ".cache" / "index" / "cockpit_decision_user_marks.v1.json"
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            try:
                obj: dict[str, Any] = {}
                if user_marks_path.exists():
                    try:
                        obj = json.loads(user_marks_path.read_text(encoding="utf-8"))
                    except Exception:
                        obj = {}
                if not isinstance(obj, dict):
                    obj = {}
                items = obj.get("items")
                if not isinstance(items, dict):
                    items = {}
                items[intake_id] = {
                    "selected_option": selected_option,
                    "note": note,
                    "at": now,
                    "user": "local",
                }
                obj["schema"] = "cockpit_decision_user_marks.v1"
                obj["generated_at"] = now
                obj["workspace_root"] = str(Path(".cache") / "ws_customer_default")
                obj["items"] = {k: items[k] for k in sorted(items.keys())}
                _atomic_write_text(user_marks_path, _json_dumps_pretty(obj))
            except Exception as exc:
                self._send_json(500, {"status": "FAIL", "error": "USER_MARKS_WRITE_FAIL", "detail": _short_str(exc)})
                return

            self._send_json(
                200,
                {
                    "status": "OK",
                    "ok": True,
                    "saved": True,
                    "intake_id": intake_id,
                    "selected_option": selected_option,
                    "path": str(user_marks_path),
                },
            )
            return

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

        if parsed.path == "/api/frontend_telemetry":
            try:
                with self.server.frontend_telemetry_lock:
                    saved = _record_frontend_telemetry(ws_root, payload)
            except ValueError as exc:
                self._send_json(400, {"status": "FAIL", "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(
                    500,
                    {"status": "FAIL", "error": "FRONTEND_TELEMETRY_WRITE_FAIL", "detail": _short_str(exc)},
                )
                return

            evidence_paths = [str(saved["events_path"]), str(saved["summary_path"])]
            self._send_json(
                200,
                {
                    "status": "OK",
                    "accepted": True,
                    "event_type": saved["event_type"],
                    "evidence_paths": evidence_paths,
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
        self.frontend_telemetry_lock = threading.Lock()
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
    server.keyword_index = KeywordIndexManager(repo_root, workspace_root)
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
    "work-intake-purpose-generate",
    "north-star-theme-seed",
    "north-star-theme-consult",
    "north-star-theme-suggestion-apply",
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

    op_call_row = _append_op_call(ws_root, op=op, args=merged, trace_meta=trace_meta, call_type="OP_CALL")
    op_call_seq = int(op_call_row.get("seq") or 0)

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
        payload_out: dict[str, Any] = {
            "status": "FAIL",
            "op": op,
            "trace_meta": trace_meta,
            "evidence_paths": [],
            "error_code": "UNHANDLED_EXCEPTION",
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "OP_ASYNC=true"],
        }
        result_emitted = False
        try:
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

            payload_out = {
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
        except Exception as exc:
            payload_out = {
                "status": "FAIL",
                "op": op,
                "trace_meta": trace_meta,
                "evidence_paths": [],
                "error_code": "UNHANDLED_EXCEPTION",
                "error": str(exc)[:220],
                "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "OP_ASYNC=true"],
            }
        finally:
            if not result_emitted:
                _append_terminal_result(
                    ws_root,
                    op=op,
                    status=payload_out.get("status"),
                    error_code=payload_out.get("error") or payload_out.get("error_code"),
                    trace_meta=trace_meta,
                    evidence_paths=payload_out.get("evidence_paths", []),
                    result_for_seq=op_call_seq if op_call_seq > 0 else None,
                )
                result_emitted = True
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


def _pin_workspace_root(repo_root: Path, ws_root: Path) -> Path:
    default_ws = (repo_root / ".cache" / "ws_customer_default").resolve()
    pin = os.getenv("COCKPIT_WS_PIN", "1").strip().lower() not in {"0", "false", "no"}
    if pin:
        return default_ws
    if ws_root.exists():
        return ws_root
    return default_ws


def _bootstrap_extension_registry(repo_root: Path, ws_root: Path) -> dict[str, Any]:
    registry_path = ws_root / ".cache" / "index" / "extension_registry.v1.json"
    data, exists, json_valid = _read_json_file(registry_path)
    status = "OK" if exists and json_valid else "MISSING_OR_INVALID"
    action = "noop"
    exit_code: int | None = None
    stdout_tail = ""
    stderr_tail = ""
    if not (exists and json_valid):
        action = "rebuild_report"
        cmd = [
            sys.executable,
            "-m",
            "src.ops.extension_registry",
            "--workspace-root",
            str(ws_root),
            "--mode",
            "report",
            "--chat",
            "false",
        ]
        try:
            res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=60)
            exit_code = res.returncode
            stdout_tail = (res.stdout or "")[-2000:]
            stderr_tail = (res.stderr or "")[-2000:]
        except Exception as exc:
            exit_code = -1
            stderr_tail = str(exc)
        data, exists, json_valid = _read_json_file(registry_path)
        status = "OK" if exists and json_valid else "FAIL"
    report = {
        "version": "v1",
        "ts": int(time.time()),
        "workspace_root": str(ws_root),
        "registry_path": str(registry_path),
        "action": action,
        "status": status,
        "exists": bool(exists),
        "json_valid": bool(json_valid),
        "exit_code": exit_code,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    out = ws_root / ".cache" / "reports" / "extension_registry_bootstrap.v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json_dumps(report), encoding="utf-8")
    return report


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
    ws = _pin_workspace_root(repo_root, ws)
    _bootstrap_extension_registry(repo_root, ws)
    try:
        port = int(str(args.port))
    except Exception:
        port = 8787
    run_server(ws, str(args.host), port, poll_interval=1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
