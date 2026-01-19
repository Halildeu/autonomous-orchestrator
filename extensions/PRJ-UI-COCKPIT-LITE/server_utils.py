from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
COCKPIT_LITE_OVERRIDE_NAME = "policy_cockpit_lite.override.v1.json"
SAFE_OVERRIDE_FILES = {
    "policy_auto_mode.override.v1.json",
    "policy_airunner.override.v1.json",
    "policy_auto_loop.override.v1.json",
    "policy_doc_graph.override.v1.json",
    "policy_autopilot_apply.override.v1.json",
    COCKPIT_LITE_OVERRIDE_NAME,
}

OP_DEFAULTS = {
    "system-status": {"dry_run": "false"},
    "ui-snapshot-bundle": {},
    "decision-inbox-show": {"chat": "false"},
    "extension-registry": {},
    "extension-help": {},
    "doer-loop-lock-status": {},
    "doer-loop-lock-clear": {},
    "work-intake-check": {"mode": "strict", "chat": "false", "detail": "false"},
    "work-intake-claim": {"mode": "claim", "ttl_seconds": "3600", "owner_tag": "", "force": "false"},
    "work-intake-close": {"mode": "close", "reason": "", "owner_tag": "", "force": "false"},
    "doc-nav-check": {"strict": "true", "detail": "false", "chat": "false"},
    "smoke-full-triage": {"detail": "false", "chat": "false"},
    "smoke-fast-triage": {"detail": "false", "chat": "false"},
    "auto-loop": {"budget_seconds": "120", "chat": "false"},
    "airrunner-run": {"ticks": "2", "mode": "no_wait", "budget_seconds": "0", "chat": "false"},
    "planner-notes-create": {"title": "", "body": "", "tags": "", "links_json": "[]"},
    "planner-chat-send": {"thread": "default", "title": "", "body": "", "tags": "", "links_json": "[]"},
    "overrides-write": {"name": "", "json": ""},
}

OP_ARG_MAP = {
    "system-status": {"dry_run": "--dry-run"},
    "ui-snapshot-bundle": {"out": "--out"},
    "decision-inbox-show": {"chat": "--chat"},
    "extension-registry": {},
    "extension-help": {},
    "doer-loop-lock-status": {},
    "doer-loop-lock-clear": {},
    "work-intake-check": {"mode": "--mode", "detail": "--detail", "chat": "--chat"},
    "work-intake-claim": {
        "mode": "--mode",
        "intake_id": "--intake-id",
        "ttl_seconds": "--ttl-seconds",
        "owner_tag": "--owner-tag",
        "force": "--force",
    },
    "work-intake-close": {
        "mode": "--mode",
        "intake_id": "--intake-id",
        "reason": "--reason",
        "owner_tag": "--owner-tag",
        "force": "--force",
    },
    "doc-nav-check": {"strict": "--strict", "detail": "--detail", "chat": "--chat"},
    "smoke-full-triage": {"job_id": "--job-id", "detail": "--detail", "chat": "--chat"},
    "smoke-fast-triage": {"job_id": "--job-id", "detail": "--detail", "chat": "--chat"},
    "auto-loop": {"budget_seconds": "--budget_seconds", "chat": "--chat"},
    "airrunner-run": {"ticks": "--ticks", "mode": "--mode", "budget_seconds": "--budget_seconds", "chat": "--chat"},
    "planner-notes-create": {"title": "--title", "body": "--body", "tags": "--tags", "links_json": "--links-json"},
    "planner-chat-send": {"thread": None, "title": None, "body": None, "tags": None, "links_json": None},
    "overrides-write": {"name": None, "json": None},
    "inbox-draft-create": {},
    "inbox-draft-batch-generate": {},
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


def _load_json_dict(path: Path) -> dict[str, Any]:
    data, exists, valid = _read_json_file(path)
    return data if exists and valid and isinstance(data, dict) else {}


def _safe_preview(text: str, limit: int = 480) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 1)] + "…"


def _draft_templates(bucket: str, *, requires_core: bool) -> tuple[list[str], list[str]]:
    from server_inbox_drafts import _draft_templates as _impl

    return _impl(bucket, requires_core=requires_core)


def _build_inbox_draft_v0_2(
    ws_root: Path,
    request_id: str,
    *,
    inbox_index: dict[str, Any] | None = None,
    triage_index: dict[str, Any] | None = None,
) -> tuple[str, str]:
    from server_inbox_drafts import _build_inbox_draft_v0_2 as _impl

    return _impl(ws_root, request_id, inbox_index=inbox_index, triage_index=triage_index)


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

    if op == "inbox-draft-create":
        request_id = str(args.get("request_id") or "").strip()
        if not request_id or not request_id.startswith("REQ-") or len(request_id) > 80:
            return 400, {"status": "FAIL", "error": "REQUEST_ID_INVALID"}

        raw_mode = str(args.get("mode") or "").strip().lower()
        raw_force = str(args.get("force") or "").strip().lower()
        force = raw_mode in {"force", "overwrite", "regenerate"} or raw_force in {"1", "true", "yes"}
        mode = "force" if force else "create_if_missing"

        rel_out = f".cache/reports/inbox_drafts/{request_id}.v0.2.md"
        out_path = ws_root / rel_out
        existed = out_path.exists()

        trace_args = {"request_id": request_id, "mode": mode}
        trace_meta = _trace_meta_for_op(op, trace_args, ws_root)
        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "OP_CALL",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "args": trace_args,
                "trace_meta": trace_meta,
                "evidence_paths": [],
            },
        )

        if existed and not force:
            payload_out = {
                "status": "IDLE",
                "op": op,
                "trace_meta": trace_meta,
                "draft_path": rel_out,
                "evidence_paths": [rel_out],
                "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "DRAFT_EXISTS=true"],
            }
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": op,
                    "status": payload_out.get("status"),
                    "trace_meta": trace_meta,
                    "evidence_paths": payload_out.get("evidence_paths", []),
                },
            )
            return 200, payload_out

        inbox_index = _load_json_dict(ws_root / ".cache" / "index" / "input_inbox.v0.1.json")
        triage_index = _load_json_dict(ws_root / ".cache" / "index" / "manual_request_triage.v0.1.json")
        draft_path, content = _build_inbox_draft_v0_2(ws_root, request_id, inbox_index=inbox_index, triage_index=triage_index)
        _atomic_write_text(ws_root / draft_path, content)

        notes = ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"]
        if force:
            notes.append("FORCE=true")
        if existed:
            notes.append("DRAFT_OVERWRITTEN=true")

        payload_out = {
            "status": "OK",
            "op": op,
            "trace_meta": trace_meta,
            "draft_path": draft_path,
            "evidence_paths": [draft_path],
            "notes": notes,
        }
        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "RESULT",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "status": payload_out.get("status"),
                "trace_meta": trace_meta,
                "evidence_paths": payload_out.get("evidence_paths", []),
            },
        )
        return 200, payload_out

    if op == "inbox-draft-batch-generate":
        raw_mode = str(args.get("mode") or "").strip().lower()
        raw_force = str(args.get("force") or "").strip().lower()
        force = raw_mode in {"force", "overwrite", "regenerate"} or raw_force in {"1", "true", "yes"}
        mode = "force" if force else "create_if_missing"

        try:
            limit = int(str(args.get("limit") or "50"))
        except Exception:
            limit = 50
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200

        target_states = {"ROUTE_TO_ROADMAP", "ROUTE_TO_PROJECT", "CONVERT_TO_PROJECT"}
        trace_args = {"mode": mode, "limit": str(limit), "states": ",".join(sorted(target_states))}
        trace_meta = _trace_meta_for_op(op, trace_args, ws_root)
        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "OP_CALL",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "args": trace_args,
                "trace_meta": trace_meta,
                "evidence_paths": [],
            },
        )

        triage_index = _load_json_dict(ws_root / ".cache" / "index" / "manual_request_triage.v0.1.json")
        inbox_index = _load_json_dict(ws_root / ".cache" / "index" / "input_inbox.v0.1.json")

        request_ids: list[str] = []
        for item in triage_index.get("items") if isinstance(triage_index.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            request_id = str(item.get("request_id") or "").strip()
            if not request_id or not request_id.startswith("REQ-") or len(request_id) > 80:
                continue
            state_value = str(item.get("state") or "").strip().upper()
            if state_value in target_states:
                request_ids.append(request_id)

        request_ids = sorted(set(request_ids))
        candidates_total = len(request_ids)
        truncated = False
        if len(request_ids) > limit:
            truncated = True
            request_ids = request_ids[:limit]

        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for req_id in request_ids:
            try:
                draft_path, content = _build_inbox_draft_v0_2(
                    ws_root,
                    req_id,
                    inbox_index=inbox_index,
                    triage_index=triage_index,
                )
                out_path = ws_root / draft_path
                existed = out_path.exists()
                if existed and not force:
                    skipped.append({"request_id": req_id, "draft_path": draft_path, "reason": "exists"})
                    continue
                _atomic_write_text(out_path, content)
                created.append({"request_id": req_id, "draft_path": draft_path, "overwritten": bool(existed)})
            except Exception as exc:
                errors.append({"request_id": req_id, "error": str(exc)})

        status = "OK" if not errors else "WARN"
        report_rel = ".cache/reports/inbox_drafts_batch_generate.v0.2.v1.json"
        report_obj = {
            "version": "v1",
            "kind": "inbox_drafts_batch_generate",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws_root),
            "status": status,
            "mode": mode,
            "force": bool(force),
            "limit": int(limit),
            "target_states": sorted(target_states),
            "counts": {
                "candidates_total": int(candidates_total),
                "processed": int(len(request_ids)),
                "created": int(len(created)),
                "skipped": int(len(skipped)),
                "errors": int(len(errors)),
            },
            "truncated": bool(truncated),
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"],
        }
        _atomic_write_text(ws_root / report_rel, json.dumps(report_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

        evidence_paths = [report_rel] + [str(item.get("draft_path") or "") for item in created]
        evidence_paths = [p for p in evidence_paths if p]
        if len(evidence_paths) > 60:
            evidence_paths = evidence_paths[:60]

        notes = ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"]
        if force:
            notes.append("FORCE=true")
        if truncated:
            notes.append("TRUNCATED=true")
        if errors:
            notes.append("HAS_ERRORS=true")

        payload_out = {
            "status": status,
            "op": op,
            "trace_meta": trace_meta,
            "report_path": report_rel,
            "created_count": len(created),
            "skipped_count": len(skipped),
            "errors_count": len(errors),
            "evidence_paths": evidence_paths,
            "notes": notes,
        }
        _chat_append(
            ws_root,
            {
                "version": "v1",
                "type": "RESULT",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": op,
                "status": payload_out.get("status"),
                "trace_meta": trace_meta,
                "evidence_paths": payload_out.get("evidence_paths", []),
            },
        )
        return 200, payload_out

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


def _inbox_triage_apply_ai(ws_root: Path, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from server_inbox_triage import _inbox_triage_apply_ai as _impl

    return _impl(ws_root, payload)


__all__ = [
    "SECRET_KEY_HINTS",
    "ALLOWED_EXTS",
    "NOTE_ID_RE",
    "THREAD_ID_RE",
    "CHAT_TYPES",
    "CHAT_MAX_LINES",
    "CHAT_MAX_RETURN",
    "OVERRIDE_NAME_RE",
    "SETTINGS_NAME_RE",
    "EXTENSION_ID_RE",
    "COCKPIT_LITE_OVERRIDE_NAME",
    "SAFE_OVERRIDE_FILES",
    "OP_DEFAULTS",
    "OP_ARG_MAP",
    "_find_repo_root",
    "_json_dumps",
    "_is_secret_key",
    "_presence_value",
    "_redact",
    "_safe_resolve_path",
    "_allow_roots",
    "_notes_root",
    "_note_id_valid",
    "_thread_id_valid",
    "_thread_tag",
    "_parse_tags_value",
    "_parse_links_value",
    "_chat_store_path",
    "_json_dumps_pretty",
    "_atomic_write_text",
    "_sanitize_text",
    "_chat_append",
    "_chat_read",
    "_policy_overrides_dir",
    "_override_path",
    "_schema_path_for_override",
    "_base_policy_path",
    "_deep_merge",
    "_validate_against_schema",
    "_extension_override_path",
    "_read_extension_overrides",
    "_write_extension_overrides",
    "_list_overrides",
    "_read_override",
    "_read_extension_registry",
    "_extension_manifest",
    "_list_notes",
    "_note_thread_id",
    "_list_planner_threads",
    "_list_planner_messages",
    "_read_json_file",
    "_watch_paths",
    "_mtime_sig",
    "_last_modified",
    "_safe_arg_value",
    "_hash_text",
    "_trace_meta_for_op",
    "_summarize_intake",
    "_summarize_decisions",
    "_summarize_jobs",
    "_parse_iso",
    "_inbox_triage_apply_ai",
    "_run_op",
]
