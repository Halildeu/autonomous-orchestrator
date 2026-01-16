from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
import subprocess

SECRET_KEY_HINTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "access_key",
    "private_key",
    "credential",
)

ALLOWED_EXTS = {".json", ".jsonl", ".md"}
NOTE_ID_RE = re.compile(r"^NOTE-[0-9a-f]{64}$")
THREAD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
CHAT_TYPES = {"NOTE", "OP_CALL", "DECISION_APPLY", "OVERRIDE_SET", "HELP", "RESULT"}
CHAT_MAX_LINES = 2000
CHAT_MAX_RETURN = 200
OVERRIDE_NAME_RE = re.compile(r"^policy_[a-z0-9_]+\.override\.v1\.json$")
SETTINGS_NAME_RE = re.compile(r"^[a-z0-9_]+\.override\.v1\.json$")
EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_OVERRIDE_FILES = {
    "policy_auto_mode.override.v1.json",
    "policy_airunner.override.v1.json",
    "policy_auto_loop.override.v1.json",
    "policy_doc_graph.override.v1.json",
    "policy_autopilot_apply.override.v1.json",
}

OP_DEFAULTS = {
    "system-status": {"dry_run": "false"},
    "ui-snapshot-bundle": {},
    "decision-inbox-show": {"chat": "false"},
    "extension-registry": {},
    "extension-help": {},
    "work-intake-check": {"mode": "strict", "chat": "false", "detail": "false"},
    "doc-nav-check": {"strict": "true", "detail": "false", "chat": "false"},
    "smoke-full-triage": {"detail": "false", "chat": "false"},
    "smoke-fast-triage": {"detail": "false", "chat": "false"},
    "auto-loop": {"budget_seconds": "120", "chat": "false"},
    "airrunner-run": {"ticks": "2", "mode": "no_wait", "budget_seconds": "0", "chat": "false"},
    "planner-chat-send": {"thread": "default", "title": "", "body": "", "tags": "", "links_json": "[]"},
    "overrides-write": {"name": "", "json": ""},
}

OP_ARG_MAP = {
    "system-status": {"dry_run": "--dry-run"},
    "ui-snapshot-bundle": {"out": "--out"},
    "decision-inbox-show": {"chat": "--chat"},
    "extension-registry": {},
    "extension-help": {},
    "work-intake-check": {"mode": "--mode", "detail": "--detail", "chat": "--chat"},
    "doc-nav-check": {"strict": "--strict", "detail": "--detail", "chat": "--chat"},
    "smoke-full-triage": {"job_id": "--job-id", "detail": "--detail", "chat": "--chat"},
    "smoke-fast-triage": {"job_id": "--job-id", "detail": "--detail", "chat": "--chat"},
    "auto-loop": {"budget_seconds": "--budget_seconds", "chat": "--chat"},
    "airrunner-run": {"ticks": "--ticks", "mode": "--mode", "budget_seconds": "--budget_seconds", "chat": "--chat"},
    "planner-chat-send": {"thread": None, "title": None, "body": None, "tags": None, "links_json": None},
    "overrides-write": {"name": None, "json": None},
}


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _is_secret_key(key: str) -> bool:
    key_lower = key.lower()
    return any(hint in key_lower for hint in SECRET_KEY_HINTS)


def _presence_value(value: Any) -> dict[str, bool]:
    return {"present": bool(value)}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(key, str) and _is_secret_key(key):
                out[key] = _presence_value(value)
            else:
                out[key] = _redact(value)
        return out
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _safe_resolve_path(raw_path: str, repo_root: Path, ws_root: Path, allow_roots: list[Path]) -> Path | None:
    if not raw_path or not isinstance(raw_path, str):
        return None
    if ".." in raw_path.replace("\\", "/").split("/"):
        return None
    try:
        path = Path(raw_path)
    except Exception:
        return None
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    if path.suffix.lower() not in ALLOWED_EXTS:
        return None
    for root in allow_roots:
        try:
            path.relative_to(root)
            return path
        except Exception:
            continue
    return None


def _allow_roots(repo_root: Path, ws_root: Path) -> list[Path]:
    return [
        (ws_root / ".cache" / "reports").resolve(),
        (ws_root / ".cache" / "index").resolve(),
        (ws_root / ".cache" / "airunner").resolve(),
        (ws_root / ".cache" / "github_ops").resolve(),
        (ws_root / ".cache" / "policy_overrides").resolve(),
        (ws_root / ".cache" / "chat_console").resolve(),
        (repo_root / ".cache" / "script_budget").resolve(),
    ]


def _notes_root(ws_root: Path) -> Path:
    return ws_root / ".cache" / "notes" / "planner"


def _note_id_valid(note_id: str) -> bool:
    return bool(NOTE_ID_RE.match(note_id or ""))


def _thread_id_valid(thread_id: str) -> bool:
    return bool(THREAD_ID_RE.match(thread_id or ""))


def _thread_tag(thread_id: str) -> str:
    return f"thread:{thread_id}"


def _parse_tags_value(raw: Any) -> list[str]:
    if isinstance(raw, list):
        items = [str(v).strip() for v in raw if str(v).strip()]
    else:
        text = str(raw or "")
        items = [part.strip() for part in text.replace("\n", ",").split(",") if part.strip()]
    return sorted(set(items))


def _parse_links_value(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _chat_store_path(ws_root: Path) -> Path:
    return ws_root / ".cache" / "chat_console" / "chat_log.v1.jsonl"


def _json_dumps_pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _sanitize_text(text: str) -> str:
    redacted = re.sub(
        r"(?i)(secret|token|password|api_key|access_key|private_key|credential)\\s*[:=]\\s*\\S+",
        r"\\1=<redacted>",
        text,
    )
    return redacted


def _chat_append(ws_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    store = _chat_store_path(ws_root)
    store.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if store.exists():
        lines = [line for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    seq = len(lines) + 1
    content = json.dumps(entry, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    msg_id = f"CHAT-{_hash_text(f'{seq}|{content}')}"
    entry_out = dict(entry)
    entry_out["msg_id"] = msg_id
    entry_out["seq"] = seq
    lines.append(json.dumps(entry_out, ensure_ascii=True, sort_keys=True))
    if len(lines) > CHAT_MAX_LINES:
        lines = lines[-CHAT_MAX_LINES:]
    _atomic_write_text(store, "\n".join(lines) + "\n")
    return entry_out


def _chat_read(ws_root: Path, limit: int = CHAT_MAX_RETURN) -> list[dict[str, Any]]:
    store = _chat_store_path(ws_root)
    if not store.exists():
        return []
    items = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    if limit > 0:
        items = items[-limit:]
    return items


def _policy_overrides_dir(ws_root: Path) -> Path:
    return ws_root / ".cache" / "policy_overrides"


def _override_path(ws_root: Path, name: str) -> Path | None:
    if not OVERRIDE_NAME_RE.match(name or ""):
        return None
    return _policy_overrides_dir(ws_root) / name


def _schema_path_for_override(repo_root: Path, name: str) -> Path | None:
    if not OVERRIDE_NAME_RE.match(name or ""):
        return None
    base_name = name.replace(".override.", ".")
    if not base_name.startswith("policy_"):
        return None
    policy_stub = base_name[len("policy_") :].replace(".v1.json", "").replace("_", "-")
    schema_path = repo_root / "schemas" / f"policy-{policy_stub}.schema.v1.json"
    return schema_path if schema_path.exists() else None


def _base_policy_path(repo_root: Path, name: str) -> Path | None:
    if not OVERRIDE_NAME_RE.match(name or ""):
        return None
    base_name = name.replace(".override.", ".")
    base_path = repo_root / "policies" / base_name
    return base_path if base_path.exists() else None


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for key, value in override.items():
            out[key] = _deep_merge(base.get(key), value)
        return out
    return override


def _validate_against_schema(schema_path: Path, payload: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return []
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception:
        return ["schema_read_failed"]
    validator = Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(payload)]
    return [str(e) for e in errors if e]


def _extension_override_path(ws_root: Path) -> Path:
    return ws_root / ".cache" / "extension_overrides" / "extension_overrides.v1.json"


def _read_extension_overrides(ws_root: Path) -> dict[str, Any]:
    path = _extension_override_path(ws_root)
    if not path.exists():
        return {"version": "v1", "overrides": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": "v1", "overrides": {}}
    return obj if isinstance(obj, dict) else {"version": "v1", "overrides": {}}


def _write_extension_overrides(ws_root: Path, payload: dict[str, Any]) -> None:
    path = _extension_override_path(ws_root)
    _atomic_write_text(path, _json_dumps_pretty(payload))


def _list_overrides(ws_root: Path) -> list[dict[str, Any]]:
    overrides_dir = _policy_overrides_dir(ws_root)
    items: list[dict[str, Any]] = []
    if not overrides_dir.exists():
        return items
    for path in sorted(overrides_dir.glob("*.json")):
        name = path.name
        if not OVERRIDE_NAME_RE.match(name):
            continue
        items.append(
            {
                "name": name,
                "path": str(path),
                "mtime": int(path.stat().st_mtime),
                "size": int(path.stat().st_size),
            }
        )
    return items


def _read_override(ws_root: Path, name: str) -> dict[str, Any] | None:
    path = _override_path(ws_root, name)
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_extension_registry(ws_root: Path) -> dict[str, Any]:
    path = ws_root / ".cache" / "index" / "extension_registry.v1.json"
    data, exists, json_valid = _read_json_file(path)
    entries = data.get("extensions") if isinstance(data, dict) else []
    items = entries if isinstance(entries, list) else []
    return {"path": str(path), "exists": exists, "json_valid": json_valid, "items": items}


def _extension_manifest(repo_root: Path, manifest_path: str) -> dict[str, Any] | None:
    if not manifest_path:
        return None
    path = Path(manifest_path)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    try:
        path.relative_to(repo_root)
    except Exception:
        return None
    if not path.exists():
        return None
    if path.suffix.lower() != ".json":
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _list_notes(ws_root: Path) -> list[dict[str, Any]]:
    notes_dir = _notes_root(ws_root)
    items: list[dict[str, Any]] = []
    if not notes_dir.exists():
        return items
    for path in sorted(notes_dir.glob("NOTE-*.v1.json")):
        try:
            note = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        note_id = str(note.get("note_id") or "")
        title = str(note.get("title") or "")
        body = str(note.get("body") or "")
        tags = note.get("tags") if isinstance(note.get("tags"), list) else []
        links = note.get("links") if isinstance(note.get("links"), list) else []
        created_at = str(note.get("created_at") or "")
        updated_at = str(note.get("updated_at") or "")
        try:
            rel_path = path.resolve().relative_to(ws_root.resolve()).as_posix()
        except Exception:
            rel_path = str(path)
        items.append(
            {
                "note_id": note_id,
                "title": title,
                "body_excerpt": body[:160] if body else "",
                "tags": tags,
                "links": links,
                "created_at": created_at,
                "updated_at": updated_at,
                "path": rel_path,
            }
        )
    items.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("note_id") or "")), reverse=True)
    return items


def _note_thread_id(tags: list[str]) -> str | None:
    for tag in tags or []:
        value = str(tag or "")
        if value.startswith("thread:"):
            thread_id = value.split("thread:", 1)[-1].strip()
            if _thread_id_valid(thread_id):
                return thread_id
    return None


def _list_planner_threads(ws_root: Path) -> list[dict[str, Any]]:
    notes_root = _notes_root(ws_root)
    threads: dict[str, dict[str, Any]] = {}
    if notes_root.exists():
        for path in sorted(notes_root.glob("NOTE-*.v1.json")):
            try:
                note = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            tags = note.get("tags") if isinstance(note.get("tags"), list) else []
            thread_id = _note_thread_id([str(t) for t in tags])
            if not thread_id:
                continue
            created_at = str(note.get("created_at") or "")
            updated_at = str(note.get("updated_at") or "")
            thread = threads.setdefault(thread_id, {"thread_id": thread_id, "count": 0, "last_ts": ""})
            thread["count"] = int(thread.get("count", 0)) + 1
            last = max(created_at, updated_at)
            if last and last > str(thread.get("last_ts") or ""):
                thread["last_ts"] = last
    threads.setdefault("default", {"thread_id": "default", "count": 0, "last_ts": ""})
    return sorted(threads.values(), key=lambda item: str(item.get("thread_id") or ""))


def _list_planner_messages(ws_root: Path, thread_id: str) -> list[dict[str, Any]]:
    notes_root = _notes_root(ws_root)
    items: list[dict[str, Any]] = []
    if not notes_root.exists():
        return items
    tag_value = _thread_tag(thread_id)
    for path in sorted(notes_root.glob("NOTE-*.v1.json")):
        try:
            note = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        tags = note.get("tags") if isinstance(note.get("tags"), list) else []
        if tag_value not in [str(t) for t in tags]:
            continue
        items.append(note)
    items.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("note_id") or "")))
    return items


def _read_json_file(path: Path) -> tuple[dict[str, Any], bool, bool]:
    if not path.exists():
        return {}, False, False
    try:
        if path.suffix == ".jsonl":
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
            return {"items": rows}, True, True
        if path.suffix == ".md":
            return {"text": path.read_text(encoding="utf-8")}, True, True
        return json.loads(path.read_text(encoding="utf-8")), True, True
    except Exception:
        return {}, True, False


def _watch_paths(repo_root: Path, ws_root: Path) -> list[Path]:
    return [
        ws_root / ".cache" / "reports" / "system_status.v1.json",
        ws_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json",
        ws_root / ".cache" / "index" / "work_intake.v1.json",
        ws_root / ".cache" / "index" / "decision_inbox.v1.json",
        ws_root / ".cache" / "doer" / "doer_loop_lock.v1.json",
        ws_root / ".cache" / "reports" / "RUN-CARD-LOCAL.v1.json",
        ws_root / ".cache" / "github_ops" / "jobs_index.v1.json",
        ws_root / ".cache" / "airunner" / "jobs_index.v1.json",
        ws_root / ".cache" / "notes" / "planner",
        ws_root / ".cache" / "notes" / "planner" / "notes_index.v1.json",
        ws_root / ".cache" / "policy_overrides",
        ws_root / ".cache" / "chat_console" / "chat_log.v1.jsonl",
        ws_root / ".cache" / "extension_overrides",
        repo_root / ".cache" / "script_budget" / "report.json",
        ws_root / ".cache" / "reports",
        ws_root / ".cache" / "index",
    ]


def _mtime_sig(paths: list[Path]) -> dict[str, tuple[int, int]]:
    sig: dict[str, tuple[int, int]] = {}
    for path in paths:
        try:
            stat = path.stat()
            sig[str(path)] = (int(stat.st_mtime), int(stat.st_size))
        except Exception:
            sig[str(path)] = (0, 0)
    return sig


def _last_modified(sig: dict[str, tuple[int, int]]) -> int:
    latest = 0
    for mtime, _size in sig.values():
        latest = max(latest, int(mtime))
    return latest


def _safe_arg_value(value: Any, *, max_len: int = 200, allow_newlines: bool = False) -> str | None:
    text = str(value)
    if not allow_newlines and ("\n" in text or "\r" in text):
        return None
    if len(text) > max_len:
        return None
    return text


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trace_meta_for_op(op: str, args: dict[str, Any], ws_root: Path) -> dict[str, Any]:
    owner_tag = os.environ.get("CODEX_CHAT_TAG", "").strip() or "unknown"
    payload = {
        "op": op,
        "args": {str(k): str(v) for k, v in sorted(args.items())},
        "workspace_root": str(ws_root),
        "owner_tag": owner_tag,
    }
    run_id = _hash_text(json.dumps(payload, sort_keys=True))
    return {
        "run_id": run_id,
        "work_item_id": f"op:{op}",
        "work_item_kind": "OP",
        "workspace_root": str(ws_root),
        "owner_tag": owner_tag,
    }


def _summarize_intake(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in items:
        bucket = str(item.get("bucket") or "UNKNOWN")
        counts[bucket] = counts.get(bucket, 0) + 1
    return {"items_count": len(items), "counts_by_bucket": counts}


def _summarize_decisions(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    pending = 0
    for item in items:
        kind = str(item.get("decision_kind") or "UNKNOWN")
        counts[kind] = counts.get(kind, 0) + 1
        if str(item.get("status") or "").upper() in {"PENDING", "OPEN"}:
            pending += 1
    return {"items_count": len(items), "pending": pending, "counts_by_kind": counts}


def _summarize_jobs(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for job in items:
        status = str(job.get("status") or "").upper() or "UNKNOWN"
        kind = str(job.get("kind") or job.get("job_type") or "").upper() or "UNKNOWN"
        by_status[status] = by_status.get(status, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {"jobs_total": len(items), "by_status": by_status, "by_kind": by_kind}


def _parse_iso(ts: str | None) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except Exception:
        return None


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
        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "RESULT",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "status": "OK",
                "trace_meta": trace_meta,
                "evidence_paths": [str(path)],
            },
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
            safe_value = _safe_arg_value(value, max_len=max_len, allow_newlines=allow_newlines)
            if safe_value is None:
                return 400, {"status": "FAIL", "error": "ARG_INVALID"}
            merged[key] = safe_value

    if op == "system-status":
        merged["dry_run"] = "false"
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
    _chat_append(
        ws_root,
        {
            "version": "v1",
            "type": call_type,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": op,
            "args": _redact(merged),
            "trace_meta": trace_meta,
            "evidence_paths": [],
        },
    )

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
    return return_code, payload_out


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
        repo_root = self.server.repo_root
        ws_root = self.server.workspace_root
        allow_roots = self.server.allow_roots
        parsed = urlparse(self.path)

        if parsed.path == "/":
            index_path = self.server.web_root / "index.html"
            self._serve_static(index_path, "text/html; charset=utf-8")
            return

        if parsed.path == "/assets/app.js":
            js_path = self.server.web_root / "assets" / "app.js"
            self._serve_static(js_path, "application/javascript; charset=utf-8")
            return

        if parsed.path == "/api/ws":
            sig = _mtime_sig(self.server.watch_paths)
            payload = {
                "workspace_root": str(ws_root),
                "last_modified_at": _last_modified(sig),
                "watch_paths": sorted(sig.keys()),
            }
            self._send_json(200, payload)
            return

        if parsed.path == "/api/health":
            self._send_json(200, {"status": "OK", "ts": int(time.time())})
            return

        if parsed.path == "/api/overview":
            status_path = ws_root / ".cache" / "reports" / "system_status.v1.json"
            snapshot_path = ws_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json"
            status_payload = self._wrap_file(status_path)
            snapshot_payload = self._wrap_file(snapshot_path)
            status_data = status_payload.get("data") if isinstance(status_payload, dict) else {}
            snapshot_data = snapshot_payload.get("data") if isinstance(snapshot_payload, dict) else {}
            sections = status_data.get("sections") if isinstance(status_data, dict) else {}
            work_intake = sections.get("work_intake") if isinstance(sections, dict) else {}
            decisions = sections.get("decisions") if isinstance(sections, dict) else {}
            auto_loop = sections.get("auto_loop") if isinstance(sections, dict) else {}
            doer = sections.get("doer") if isinstance(sections, dict) else {}
            doer_loop = sections.get("doer_loop") if isinstance(sections, dict) else {}
            summary = {
                "overall_status": status_data.get("overall_status") if isinstance(status_data, dict) else "",
                "work_intake_total": int(work_intake.get("items_count", 0) or 0) if isinstance(work_intake, dict) else 0,
                "work_intake_counts": work_intake.get("counts_by_bucket", {}) if isinstance(work_intake, dict) else {},
                "decision_pending": int(decisions.get("pending_decisions_count", 0) or 0) if isinstance(decisions, dict) else 0,
                "decision_seed_pending": int(decisions.get("seed_pending_count", 0) or 0)
                if isinstance(decisions, dict)
                else 0,
                "last_auto_loop_path": str(auto_loop.get("last_auto_loop_path") or "")
                if isinstance(auto_loop, dict)
                else "",
                "last_airrunner_run_path": str(doer.get("last_run_path") or "") if isinstance(doer, dict) else "",
                "last_exec_ticket_path": str(doer.get("last_exec_report_path") or "") if isinstance(doer, dict) else "",
                "lock_state": str(doer_loop.get("lock_state") or "") if isinstance(doer_loop, dict) else "",
            }
            payload = {
                "summary": summary,
                "system_status": status_payload,
                "ui_snapshot": snapshot_payload,
            }
            self._send_json(200, payload)
            return

        if parsed.path == "/api/status":
            path = ws_root / ".cache" / "reports" / "system_status.v1.json"
            self._send_json(200, self._wrap_file(path))
            return

        if parsed.path == "/api/ui_snapshot":
            path = ws_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json"
            self._send_json(200, self._wrap_file(path))
            return

        if parsed.path == "/api/intake":
            path = ws_root / ".cache" / "index" / "work_intake.v1.json"
            payload = self._wrap_file(path)
            data = payload.get("data") if isinstance(payload, dict) else {}
            items = data.get("items") if isinstance(data, dict) else []
            items_list = items if isinstance(items, list) else []
            payload["summary"] = _summarize_intake(items_list)
            payload["items"] = items_list[:100]
            self._send_json(200, payload)
            return

        if parsed.path == "/api/decisions":
            path = ws_root / ".cache" / "index" / "decision_inbox.v1.json"
            payload = self._wrap_file(path)
            data = payload.get("data") if isinstance(payload, dict) else {}
            items = data.get("items") if isinstance(data, dict) else []
            items_list = items if isinstance(items, list) else []
            payload["summary"] = _summarize_decisions(items_list)
            payload["items"] = items_list[:100]
            self._send_json(200, payload)
            return

        if parsed.path == "/api/extensions":
            qs = parse_qs(parsed.query)
            extension_id = str(qs.get("extension_id", [""])[0]).strip()
            registry = _read_extension_registry(ws_root)
            overrides = _read_extension_overrides(ws_root)
            payload = {
                "registry_path": registry.get("path"),
                "registry_exists": registry.get("exists"),
                "registry_json_valid": registry.get("json_valid"),
                "items": _redact(registry.get("items") if isinstance(registry.get("items"), list) else []),
                "overrides": overrides,
            }
            if extension_id:
                if not EXTENSION_ID_RE.match(extension_id):
                    self._send_json(400, {"status": "FAIL", "error": "EXTENSION_ID_INVALID"})
                    return
                manifest_path = ""
                for entry in registry.get("items", []):
                    if isinstance(entry, dict) and entry.get("extension_id") == extension_id:
                        manifest_path = str(entry.get("manifest_path") or "")
                        break
                manifest = _extension_manifest(repo_root, manifest_path)
                payload["extension_id"] = extension_id
                payload["manifest_path"] = manifest_path
                payload["manifest"] = _redact(manifest) if isinstance(manifest, dict) else {}
            self._send_json(200, payload)
            return

        if parsed.path == "/api/jobs":
            path = ws_root / ".cache" / "github_ops" / "jobs_index.v1.json"
            payload = self._wrap_file(path)
            data = payload.get("data") if isinstance(payload, dict) else {}
            items = data.get("jobs") if isinstance(data, dict) else []
            items_list = items if isinstance(items, list) else []
            payload["summary"] = _summarize_jobs(items_list)
            payload["jobs"] = items_list[:100]
            self._send_json(200, payload)
            return

        if parsed.path == "/api/airunner_jobs":
            path = ws_root / ".cache" / "airunner" / "jobs_index.v1.json"
            payload = self._wrap_file(path)
            data = payload.get("data") if isinstance(payload, dict) else {}
            items = data.get("jobs") if isinstance(data, dict) else []
            items_list = items if isinstance(items, list) else []
            payload["summary"] = _summarize_jobs(items_list)
            payload["jobs"] = items_list[:100]
            self._send_json(200, payload)
            return

        if parsed.path == "/api/locks":
            lock_path = ws_root / ".cache" / "doer" / "doer_loop_lock.v1.json"
            lock_data: dict[str, Any] = {}
            lock_state = "MISSING"
            owner_tag = ""
            owner_session = ""
            expires_at = ""
            run_id = ""
            if lock_path.exists():
                try:
                    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
                except Exception:
                    lock_state = "INVALID"
                else:
                    owner_tag = str(lock_data.get("owner_tag") or "")
                    owner_session = str(lock_data.get("owner_session") or "")
                    expires_at = str(lock_data.get("expires_at") or "")
                    run_id = str(lock_data.get("run_id") or "")
                    expires_dt = _parse_iso(expires_at)
                    now = datetime.now(timezone.utc)
                    lock_state = "LOCKED"
                    if expires_dt and now > expires_dt:
                        lock_state = "STALE"
            lease_summary = {
                "lease_count": 0,
                "active_count": 0,
                "owners_sample": [],
                "path": "",
            }
            leases_json = ws_root / ".cache" / "index" / "work_item_leases.v1.json"
            leases_jsonl = ws_root / ".cache" / "index" / "work_item_leases.v1.jsonl"
            leases_payload = []
            if leases_json.exists():
                try:
                    obj = json.loads(leases_json.read_text(encoding="utf-8"))
                    if isinstance(obj, dict):
                        leases_payload = obj.get("leases") if isinstance(obj.get("leases"), list) else []
                        lease_summary["path"] = str(leases_json)
                except Exception:
                    leases_payload = []
            elif leases_jsonl.exists():
                try:
                    lines = [line for line in leases_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
                    leases_payload = [json.loads(line) for line in lines if line.strip()]
                    lease_summary["path"] = str(leases_jsonl)
                except Exception:
                    leases_payload = []
            if isinstance(leases_payload, list) and leases_payload:
                lease_summary["lease_count"] = len(leases_payload)
                active = [l for l in leases_payload if isinstance(l, dict) and l.get("expires_at")]
                lease_summary["active_count"] = len(active)
                owners = sorted({str(l.get("owner") or "") for l in leases_payload if isinstance(l, dict)})
                lease_summary["owners_sample"] = [o for o in owners if o][:5]
            payload = {
                "lock_state": lock_state,
                "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
                "owner_tag": owner_tag,
                "owner_session": owner_session,
                "expires_at": expires_at,
                "run_id": run_id,
                "lock": _redact(lock_data) if lock_data else {},
                "leases_summary": lease_summary,
            }
            self._send_json(200, payload)
            return

        if parsed.path == "/api/planner_chat/threads":
            threads = _list_planner_threads(ws_root)
            self._send_json(200, {"count": len(threads), "threads": threads})
            return

        if parsed.path == "/api/planner_chat":
            qs = parse_qs(parsed.query)
            thread_id = str(qs.get("thread", ["default"])[0]).strip().lower() or "default"
            if not _thread_id_valid(thread_id):
                self._send_json(400, {"status": "FAIL", "error": "THREAD_ID_INVALID"})
                return
            items = _list_planner_messages(ws_root, thread_id)
            self._send_json(200, {"thread_id": thread_id, "count": len(items), "items": _redact(items)})
            return

        if parsed.path == "/api/notes":
            items = _list_notes(ws_root)
            payload = {
                "notes_count": len(items),
                "items": _redact(items),
            }
            self._send_json(200, payload)
            return

        if parsed.path == "/api/notes/search":
            qs = parse_qs(parsed.query)
            term = str(qs.get("q", [""])[0]).strip().lower()
            items = _list_notes(ws_root)
            if term:
                filtered = []
                for item in items:
                    title = str(item.get("title") or "").lower()
                    body = str(item.get("body_excerpt") or "").lower()
                    tags = " ".join([str(t) for t in item.get("tags", [])]).lower() if isinstance(item.get("tags"), list) else ""
                    links = " ".join(
                        [f"{l.get('kind')}:{l.get('id_or_path')}" for l in item.get("links", []) if isinstance(l, dict)]
                    ).lower() if isinstance(item.get("links"), list) else ""
                    if term in title or term in body or term in tags or term in links:
                        filtered.append(item)
                items = filtered
            payload = {
                "notes_count": len(items),
                "items": _redact(items),
                "query": term,
            }
            self._send_json(200, payload)
            return

        if parsed.path == "/api/notes/get":
            qs = parse_qs(parsed.query)
            note_id = str(qs.get("note_id", [""])[0])
            if not _note_id_valid(note_id):
                self._send_json(400, {"status": "FAIL", "error": "NOTE_ID_INVALID"})
                return
            note_path = _notes_root(ws_root) / f"{note_id}.v1.json"
            payload = self._wrap_file(note_path)
            payload["note_id"] = note_id
            self._send_json(200, payload)
            return

        if parsed.path == "/api/chat":
            qs = parse_qs(parsed.query)
            try:
                limit = int(str(qs.get("limit", [str(CHAT_MAX_RETURN)])[0]))
            except Exception:
                limit = CHAT_MAX_RETURN
            limit = max(1, min(limit, CHAT_MAX_RETURN))
            items = _chat_read(ws_root, limit=limit)
            self._send_json(200, {"count": len(items), "items": _redact(items)})
            return

        if parsed.path == "/api/run_card":
            path = ws_root / ".cache" / "reports" / "RUN-CARD-LOCAL.v1.json"
            payload = self._wrap_file(path)
            payload["template_path"] = "docs/OPERATIONS/RUN-CARD-TEMPLATE.v1.md"
            self._send_json(200, payload)
            return

        if parsed.path == "/api/overrides/list":
            items = []
            for name in sorted(SAFE_OVERRIDE_FILES):
                path = _override_path(ws_root, name)
                exists = bool(path and path.exists())
                items.append(
                    {
                        "name": name,
                        "path": str(path) if path else "",
                        "exists": exists,
                        "mtime": int(path.stat().st_mtime) if exists else None,
                        "size": int(path.stat().st_size) if exists else None,
                    }
                )
            self._send_json(200, {"count": len(items), "items": items})
            return

        if parsed.path == "/api/overrides/get":
            qs = parse_qs(parsed.query)
            name = str(qs.get("name", [""])[0])
            if name not in SAFE_OVERRIDE_FILES:
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"})
                return
            path = _override_path(ws_root, name)
            if path is None or not path.exists():
                self._send_json(404, {"status": "FAIL", "error": "OVERRIDE_NOT_FOUND"})
                return
            payload = self._wrap_file(path)
            payload["name"] = name
            schema_path = _schema_path_for_override(repo_root, name)
            payload["schema_path"] = str(schema_path) if schema_path else ""
            self._send_json(200, payload)
            return

        if parsed.path == "/api/settings/overrides":
            items = [item for item in _list_overrides(ws_root) if item.get("name") in SAFE_OVERRIDE_FILES]
            self._send_json(200, {"count": len(items), "items": items})
            return

        if parsed.path == "/api/settings/get":
            qs = parse_qs(parsed.query)
            name = str(qs.get("name", [""])[0])
            if name not in SAFE_OVERRIDE_FILES:
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"})
                return
            if not OVERRIDE_NAME_RE.match(name or ""):
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NAME_INVALID"})
                return
            path = _override_path(ws_root, name)
            if path is None or not path.exists():
                self._send_json(404, {"status": "FAIL", "error": "OVERRIDE_NOT_FOUND"})
                return
            payload = self._wrap_file(path)
            payload["name"] = name
            schema_path = _schema_path_for_override(repo_root, name)
            payload["schema_path"] = str(schema_path) if schema_path else ""
            self._send_json(200, payload)
            return

        if parsed.path == "/api/budget":
            path = repo_root / ".cache" / "script_budget" / "report.json"
            self._send_json(200, self._wrap_file(path))
            return

        if parsed.path == "/api/reports":
            qs = parse_qs(parsed.query)
            filter_value = str(qs.get("filter", ["closeout"])[0])
            reports_dir = ws_root / ".cache" / "reports"
            items = []
            if reports_dir.exists():
                for p in sorted(reports_dir.glob("*.json")):
                    name = p.name
                    if filter_value and filter_value not in name:
                        continue
                    items.append({
                        "name": name,
                        "path": str(p),
                        "mtime": int(p.stat().st_mtime),
                        "size": int(p.stat().st_size),
                    })
            self._send_json(200, {"items": items})
            return

        if parsed.path == "/api/evidence/list":
            qs = parse_qs(parsed.query)
            filter_value = str(qs.get("filter", ["closeout"])[0])
            evidence_root = ws_root / ".cache" / "reports"
            items = []
            if evidence_root.exists():
                for p in sorted(evidence_root.rglob("*")):
                    if not p.is_file():
                        continue
                    if p.suffix.lower() not in ALLOWED_EXTS:
                        continue
                    rel = str(p.relative_to(evidence_root))
                    if filter_value and filter_value not in rel:
                        continue
                    items.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "relative_path": rel,
                            "mtime": int(p.stat().st_mtime),
                            "size": int(p.stat().st_size),
                        }
                    )
            self._send_json(200, {"items": items})
            return

        if parsed.path == "/api/evidence/read":
            qs = parse_qs(parsed.query)
            raw_path = str(qs.get("path", [""])[0])
            path = _safe_resolve_path(raw_path, repo_root, ws_root, allow_roots)
            if path is None:
                self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
                return
            if ".cache/reports" not in str(path):
                self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
                return
            self._send_json(200, self._wrap_file(path))
            return

        if parsed.path == "/api/evidence/raw":
            qs = parse_qs(parsed.query)
            raw_path = str(qs.get("path", [""])[0])
            path = _safe_resolve_path(raw_path, repo_root, ws_root, allow_roots)
            if path is None:
                self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
                return
            if ".cache/reports" not in str(path):
                self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
                return
            if not path.exists():
                self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})
                return
            content = path.read_text(encoding="utf-8")
            content_type = "text/plain; charset=utf-8"
            if path.suffix.lower() in {".json", ".jsonl"}:
                content_type = "application/json; charset=utf-8"
            elif path.suffix.lower() == ".md":
                content_type = "text/markdown; charset=utf-8"
            self._send_text(200, content, content_type)
            return

        if parsed.path == "/api/file":
            qs = parse_qs(parsed.query)
            raw_path = str(qs.get("path", [""])[0])
            path = _safe_resolve_path(raw_path, repo_root, ws_root, allow_roots)
            if path is None:
                self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
                return
            self._send_json(200, self._wrap_file(path))
            return

        if parsed.path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            last_sig = _mtime_sig(self.server.watch_paths)
            try:
                while True:
                    time.sleep(self.server.poll_interval)
                    sig = _mtime_sig(self.server.watch_paths)
                    if sig != last_sig:
                        changed = [p for p, v in sig.items() if last_sig.get(p) != v]
                        payload = _json_dumps({"paths": sorted(changed), "ts": int(time.time())})
                        event_map = {
                            "overview_tick": any(
                                "system_status.v1.json" in p or "ui_snapshot_bundle.v1.json" in p for p in changed
                            ),
                            "intake_tick": any("work_intake.v1.json" in p for p in changed),
                            "decisions_tick": any("decision_inbox.v1.json" in p for p in changed),
                            "jobs_tick": any("jobs_index.v1.json" in p for p in changed),
                            "locks_tick": any("doer_loop_lock.v1.json" in p for p in changed),
                            "notes_tick": any(".cache/notes/" in p for p in changed),
                            "chat_tick": any(
                                ".cache/notes/planner" in p or ".cache/chat_console" in p for p in changed
                            ),
                            "settings_tick": any(
                                ".cache/policy_overrides" in p
                                or "RUN-CARD-LOCAL.v1.json" in p
                                or ".cache/extension_overrides" in p
                                or ".cache/chat_console" in p
                                for p in changed
                            ),
                        }
                        for event_name in [
                            "overview_tick",
                            "intake_tick",
                            "decisions_tick",
                            "jobs_tick",
                            "locks_tick",
                            "notes_tick",
                            "chat_tick",
                            "settings_tick",
                        ]:
                            if event_map.get(event_name):
                                self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
                                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.write(b"event: changed\n")
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        last_sig = sig
            except Exception:
                return

        self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})

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

        self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def build_server(repo_root: Path, workspace_root: Path, host: str, port: int, poll_interval: float) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), CockpitHandler)
    server.repo_root = repo_root
    server.workspace_root = workspace_root
    server.allow_roots = _allow_roots(repo_root, workspace_root)
    server.watch_paths = _watch_paths(repo_root, workspace_root)
    server.poll_interval = poll_interval
    server.web_root = (repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "web").resolve()
    return server


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
