from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.prj_kernel_api.adapter import handle_request as kernel_handle_request
from src.prj_kernel_api.dotenv_loader import resolve_env_value
try:
    from src.prj_kernel_api.prompt_registry import load_prompt_registry, resolve_prompt_entry
except Exception:
    def load_prompt_registry(*, workspace_root: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
        return {}

    def resolve_prompt_entry(registry: dict[str, Any], key: str) -> dict[str, Any]:
        _ = (registry, key)
        return {}
from src.orchestrator.memory.adapters import resolve_memory_port
from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable, deterministic_record_id

SECRET_KEY_HINTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "access_key",
    "private_key",
    "credential",
)

ALLOWED_EXTS = {".json", ".jsonl", ".md", ".py", ".txt", ".toml", ".yaml", ".yml"}
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
    "policy_north_star_subject_plan.override.v1.json",
    "policy_north_star_subject_plan_scoring.override.v1.json",
    COCKPIT_LITE_OVERRIDE_NAME,
}

SEARCH_NAMESPACE_BASE = "codex_repo_search"
SEARCH_INDEX_DIR_REL = ".cache/search"
SEARCH_ALLOWED_EXTS = {".md", ".txt", ".py", ".json", ".toml", ".yaml", ".yml"}
SEARCH_SKIP_DIRS = {
    ".git",
    ".cache",
    ".venv",
    "__pycache__",
    "dist",
    "vendor_packs",
    "evidence",
    "node_modules",
}

SEARCH_DEFAULT_MAX_FILES = 600
SEARCH_DEFAULT_MAX_BYTES = 6_000_000
SEARCH_DEFAULT_CHUNK = 1200
RG_MAX_FILESIZE = "5M"
MANAGED_REPOS_MANIFEST_REL = Path(".cache") / "managed_repos.v1.json"
PLANNER_ASSISTANT_SYSTEM_FALLBACK = (
    "Sen Cockpit Planner asistanısın. "
    "Yanıtları Türkçe, kısa, net ve uygulanabilir üret. "
    "Gereksiz tekrar yapma; belirsizlik varsa açıkça belirt."
)
TERMINAL_RESULT_STATUSES = {"OK", "FAIL", "CANCELLED", "TIMEOUT"}

SSOT_SEARCH_ROOTS = (
    "AGENTS.md",
    "docs/OPERATIONS",
    "docs/LAYER-MODEL-LOCK.v1.md",
    "docs/ROADMAP.md",
    "policies",
    "schemas",
    "registry",
    "roadmaps",
    "extensions",
    "src/ops",
)

WS_SEARCH_ROOTS_REL = (
    ".cache/reports",
    ".cache/index",
    ".cache/state",
)

OP_DEFAULTS = {
    "system-status": {"dry_run": "false"},
    "ui-snapshot-bundle": {},
    "decision-inbox-show": {"chat": "false"},
    "extension-registry": {},
    "extension-help": {},
    "work-intake-check": {"mode": "strict", "chat": "false", "detail": "false"},
    "work-intake-claim": {"mode": "claim", "ttl_seconds": "3600", "owner_tag": "", "force": "false"},
    "work-intake-close": {"mode": "close", "reason": "", "owner_tag": "", "force": "false"},
    "work-intake-purpose-generate": {
        "intake_id": "",
        "mode": "missing_only",
        "status": "OPEN",
        "provider_id": "openai",
        "model": "",
        "limit": "50",
        "dry_run": "false",
    },
    "north-star-theme-seed": {
        "subject_id": "",
        "provider_id": "openai",
        "model": "gpt-5.2",
        "max_tokens": "5000",
    },
    "north-star-theme-consult": {
        "subject_id": "",
        "providers": "",
        "focus_type": "",
        "focus_id": "",
        "comment": "",
        "max_tokens": "2500",
    },
    "north-star-theme-suggestion-apply": {
        "suggestion_id": "",
        "action": "",
        "comment": "",
        "merge_target": "",
    },
    "north-star-subject-plan-profile-run": {
        "subject_id": "",
        "profile": "C",
        "run_set": "abc",
        "mode": "plan_first",
        "out": "latest",
        "persist_profile": "true",
    },
    "north-star-profile-order-compare": {
        "subject_id": "",
        "orders": "BCA;ACB;CAB",
        "mode": "plan_first",
        "out": "latest",
        "report_path": ".cache/reports/north_star_profile_order_ab_compare.v1.json",
    },
    "doc-nav-check": {"strict": "true", "detail": "false", "chat": "false"},
    "smoke-full-triage": {"detail": "false", "chat": "false"},
    "smoke-fast-triage": {"detail": "false", "chat": "false"},
    "auto-loop": {"budget_seconds": "120", "chat": "false"},
    "airrunner-run": {"ticks": "2", "mode": "no_wait", "budget_seconds": "0", "chat": "false"},
    "planner-notes-create": {"title": "", "body": "", "tags": "", "links_json": "[]"},
    "planner-chat-send": {"thread": "default", "title": "", "body": "", "tags": "", "links_json": "[]"},
    "planner-chat-send-llm": {
        "thread": "default",
        "title": "",
        "body": "",
        "tags": "",
        "provider_id": "",
        "model": "",
        "profile": "",
    },
    "overrides-write": {"name": "", "json": ""},
}

OP_ARG_MAP = {
    "system-status": {"dry_run": "--dry-run"},
    "ui-snapshot-bundle": {"out": "--out"},
    "decision-inbox-show": {"chat": "--chat"},
    "extension-registry": {},
    "extension-help": {},
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
    "work-intake-purpose-generate": {
        "intake_id": "--intake-id",
        "mode": "--mode",
        "status": "--status",
        "provider_id": "--provider-id",
        "model": "--model",
        "limit": "--limit",
        "dry_run": "--dry-run",
    },
    "north-star-theme-seed": {
        "subject_id": "--subject-id",
        "provider_id": "--provider-id",
        "model": "--model",
        "max_tokens": "--max-tokens",
    },
    "north-star-theme-consult": {
        "subject_id": "--subject-id",
        "providers": "--providers",
        "focus_type": "--focus-type",
        "focus_id": "--focus-id",
        "comment": "--comment",
        "max_tokens": "--max-tokens",
    },
    "north-star-theme-suggestion-apply": {
        "suggestion_id": "--suggestion-id",
        "action": "--action",
        "comment": "--comment",
        "merge_target": "--merge-target",
    },
    "north-star-subject-plan-profile-run": {
        "subject_id": "--subject-id",
        "profile": "--profile",
        "run_set": "--run-set",
        "mode": "--mode",
        "out": "--out",
        "persist_profile": "--persist-profile",
    },
    "north-star-profile-order-compare": {
        "subject_id": "--subject-id",
        "orders": "--orders",
        "mode": "--mode",
        "out": "--out",
        "report_path": "--report-path",
    },
    "doc-nav-check": {"strict": "--strict", "detail": "--detail", "chat": "--chat"},
    "smoke-full-triage": {"job_id": "--job-id", "detail": "--detail", "chat": "--chat"},
    "smoke-fast-triage": {"job_id": "--job-id", "detail": "--detail", "chat": "--chat"},
    "auto-loop": {"budget_seconds": "--budget_seconds", "chat": "--chat"},
    "airrunner-run": {"ticks": "--ticks", "mode": "--mode", "budget_seconds": "--budget_seconds", "chat": "--chat"},
    "planner-notes-create": {"title": "--title", "body": "--body", "tags": "--tags", "links_json": "--links-json"},
    "planner-chat-send": {"thread": None, "title": None, "body": None, "tags": None, "links_json": None},
    "planner-chat-send-llm": {
        "thread": None,
        "title": None,
        "body": None,
        "tags": None,
        "provider_id": None,
        "model": None,
        "profile": None,
    },
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
    raw_path = str(raw_path).strip()
    raw_path = re.sub(r"#L\d+(?::\d+)?$", "", raw_path)
    raw_path = re.sub(r":\d+(?::\d+)?$", "", raw_path)
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
        repo_root.resolve(),
        (ws_root / ".cache" / "reports").resolve(),
        (ws_root / ".cache" / "index").resolve(),
        (ws_root / ".cache" / "state").resolve(),
        (ws_root / ".cache" / "airunner").resolve(),
        (ws_root / ".cache" / "github_ops").resolve(),
        (ws_root / ".cache" / "policy_overrides").resolve(),
        (ws_root / ".cache" / "chat_console").resolve(),
        (ws_root / ".cache" / "providers").resolve(),
        (ws_root / "policies").resolve(),
        (repo_root / "policies").resolve(),
        (repo_root / "docs" / "OPERATIONS").resolve(),
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


def _manifest_base_candidates(ws_root: Path) -> list[Path]:
    candidates: list[Path] = []
    candidates.append(ws_root)
    if ws_root.parent != ws_root:
        candidates.append(ws_root.parent)
    return candidates


def _managed_repos_manifest_candidates(ws_root: Path) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for base in _manifest_base_candidates(ws_root):
        path = (base / MANAGED_REPOS_MANIFEST_REL).resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _read_managed_repos_manifest(ws_root: Path) -> dict[str, Any]:
    for path in _managed_repos_manifest_candidates(ws_root):
        if path.exists():
            data, exists, json_valid = _read_json_file(path)
            return {
                "path": str(path),
                "exists": bool(exists),
                "json_valid": bool(json_valid),
                "data": data if isinstance(data, dict) else {},
                "source": "file",
            }
    return {
        "path": str(_managed_repos_manifest_candidates(ws_root)[0]),
        "exists": False,
        "json_valid": False,
        "data": {},
        "source": "fallback",
    }


def _as_sorted_unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        if not path:
            continue
        try:
            norm = str(path.resolve())
        except Exception:
            norm = str(path)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(path)
    out.sort(key=lambda p: str(p))
    return out


def _collect_managed_repo_entries(ws_root: Path) -> list[dict[str, Any]]:
    manifest = _read_managed_repos_manifest(ws_root)
    raw = manifest.get("data", {}) if isinstance(manifest.get("data"), dict) else {}
    repo_rows = raw.get("repos")
    if not isinstance(repo_rows, list):
        repo_rows = raw.get("managed_repos")
    if not isinstance(repo_rows, list):
        repo_rows = raw.get("entries")
    if not isinstance(repo_rows, list):
        repo_rows = []

    items: list[dict[str, Any]] = []
    manifest_base = Path(manifest.get("path", "")).resolve().parent if manifest.get("path") else ws_root

    def add_entry(raw_entry: Any) -> None:
        if isinstance(raw_entry, str):
            entry = {"repo_root": raw_entry.strip()}
        elif isinstance(raw_entry, dict):
            entry = raw_entry
        else:
            return

        repo_root_raw = str(entry.get("repo_root") or entry.get("repo") or "").strip()
        ws_root_raw = str(entry.get("workspace_root") or entry.get("workspace") or entry.get("ws_root") or "").strip()

        repo_root_path = Path(repo_root_raw).expanduser().resolve() if repo_root_raw else None
        if ws_root_raw:
            if Path(ws_root_raw).is_absolute():
                workspace_root_path = Path(ws_root_raw).expanduser().resolve()
            else:
                workspace_root_path = (manifest_base / ws_root_raw).resolve()
        else:
            workspace_root_path = None

        if not workspace_root_path and entry.get("workspace_id"):
            workspace_id = str(entry.get("workspace_id") or "").strip()
            candidates = [p for p in _manifest_base_candidates(ws_root) if p.exists()]
            for parent in candidates:
                candidate = parent / workspace_id
                if candidate.exists():
                    workspace_root_path = candidate
                    break

        if not workspace_root_path:
            return

        repo_slug = str(
            entry.get("repo_slug")
            or entry.get("slug")
            or (repo_root_path.name if repo_root_path else workspace_root_path.name)
        ).strip()
        repo_id = str(entry.get("repo_id") or entry.get("id") or workspace_root_path.name).strip()

        items.append(
            {
                "workspace_root": str(workspace_root_path),
                "workspace_root_path": workspace_root_path,
                "repo_root": str(repo_root_path) if repo_root_path else "",
                "repo_slug": repo_slug,
                "repo_id": repo_id,
                "source": "manifest",
            }
        )

    for raw_entry in repo_rows:
        add_entry(raw_entry)

    if not items:
        fallback_roots = _as_sorted_unique_paths(list({d for d in {ws_root.parent, ws_root} if d is not None and d.exists()}))
        workspace_roots: list[Path] = []
        for root in fallback_roots:
            workspace_roots.extend(
                [child for child in root.iterdir() if child.is_dir() and child.name.startswith("repo-")],
            )
            if root.name.startswith("repo-"):
                workspace_roots.append(root)
        workspace_roots = _as_sorted_unique_paths(workspace_roots)
        for workspace_root_path in workspace_roots:
            if not workspace_root_path.exists():
                continue
            items.append(
                {
                    "workspace_root": str(workspace_root_path),
                    "workspace_root_path": workspace_root_path,
                    "repo_root": "",
                    "repo_slug": workspace_root_path.name,
                    "repo_id": workspace_root_path.name,
                    "source": "fallback",
                }
            )

    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        workspace_root = str(item.get("workspace_root") or "").strip()
        if not workspace_root:
            continue
        existing = deduped.get(workspace_root)
        if existing is None:
            deduped[workspace_root] = item
            continue
        if (existing.get("source") == "fallback") and (item.get("source") == "manifest"):
            deduped[workspace_root] = item

    return sorted(deduped.values(), key=lambda item: str(item.get("repo_id") or item.get("workspace_root")))


def _managed_repo_path_map(ws_root: Path) -> dict[str, Path]:
    entries = _collect_managed_repo_entries(ws_root)
    out: dict[str, Path] = {}
    for item in entries:
        ws_entry = str(item.get("workspace_root") or "").strip()
        if not ws_entry:
            continue
        try:
            out[ws_entry] = Path(ws_entry).resolve()
        except Exception:
            continue
    return out


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


def _shorten_text(text: str, limit: int = 240) -> str:
    raw = str(text or "")
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 3)] + "..."


def _parse_bool_arg(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _search_module():
    import server_utils_search as _search_mod

    return _search_mod


def _classify_search_mode(query: str, mode_hint: str | None) -> str:
    return _search_module()._classify_search_mode(query, mode_hint)


def _normalize_search_scope(scope: str | None) -> str:
    return _search_module()._normalize_search_scope(scope)


def _search_namespace(scope: str | None) -> str:
    return _search_module()._search_namespace(scope)


def _search_index_manifest_path(ws_root: Path, scope: str | None) -> Path:
    return _search_module()._search_index_manifest_path(ws_root, scope)


def _workspace_search_roots(ws_root: Path) -> list[Path]:
    return _search_module()._workspace_search_roots(ws_root)


def _search_roots(repo_root: Path, ws_root: Path, scope: str | None) -> list[Path]:
    return _search_module()._search_roots(repo_root, ws_root, scope)


def _iter_index_files(repo_root: Path, roots: list[Path], max_files: int, max_bytes: int) -> tuple[list[Path], int]:
    return _search_module()._iter_index_files(repo_root, roots, max_files, max_bytes)


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    return _search_module()._chunk_text(text, chunk_size)


def _apply_memory_env(ws_root: Path) -> None:
    _search_module()._apply_memory_env(ws_root)


def _clear_index_records(port: Any, namespace: str, record_ids: list[str]) -> int:
    return _search_module()._clear_index_records(port, namespace, record_ids)


def _build_semantic_index(*, repo_root: Path, ws_root: Path, port: Any, namespace: str, scope: str | None, max_files: int, max_bytes: int, chunk_size: int, rebuild: bool) -> dict[str, Any]:
    return _search_module()._build_semantic_index(
        repo_root=repo_root,
        ws_root=ws_root,
        port=port,
        namespace=namespace,
        scope=scope,
        max_files=max_files,
        max_bytes=max_bytes,
        chunk_size=chunk_size,
        rebuild=rebuild,
    )


def _resolve_rg_bin() -> str | None:
    return _search_module()._resolve_rg_bin()


def _git_grep_search(*, repo_root: Path, roots: list[Path], query: str, limit: int) -> dict[str, Any]:
    return _search_module()._git_grep_search(repo_root=repo_root, roots=roots, query=query, limit=limit)


def _normalize_hit_path(*, repo_root: Path, ws_root: Path, raw_path: str) -> str:
    return _search_module()._normalize_hit_path(repo_root=repo_root, ws_root=ws_root, raw_path=raw_path)


def _rg_search(*, repo_root: Path, ws_root: Path, roots: list[Path], query: str, limit: int) -> dict[str, Any]:
    return _search_module()._rg_search(repo_root=repo_root, ws_root=ws_root, roots=roots, query=query, limit=limit)


def _semantic_search(*, repo_root: Path, ws_root: Path, scope: str | None, query: str, limit: int, rebuild: bool, max_files: int, max_bytes: int, chunk_size: int) -> dict[str, Any]:
    return _search_module()._semantic_search(
        repo_root=repo_root,
        ws_root=ws_root,
        scope=scope,
        query=query,
        limit=limit,
        rebuild=rebuild,
        max_files=max_files,
        max_bytes=max_bytes,
        chunk_size=chunk_size,
    )


def _search_router(*, repo_root: Path, ws_root: Path, query: str, mode_hint: str | None, scope: str | None, limit: int, rebuild: bool, max_files: int, max_bytes: int, chunk_size: int) -> dict[str, Any]:
    return _search_module()._search_router(
        repo_root=repo_root,
        ws_root=ws_root,
        query=query,
        mode_hint=mode_hint,
        scope=scope,
        limit=limit,
        rebuild=rebuild,
        max_files=max_files,
        max_bytes=max_bytes,
        chunk_size=chunk_size,
    )


def _semantic_index_handle(*, repo_root: Path, ws_root: Path, scope: str | None, action: str | None, rebuild: bool, max_files: int, max_bytes: int, chunk_size: int) -> dict[str, Any]:
    return _search_module()._semantic_index_handle(
        repo_root=repo_root,
        ws_root=ws_root,
        scope=scope,
        action=action,
        rebuild=rebuild,
        max_files=max_files,
        max_bytes=max_bytes,
        chunk_size=chunk_size,
    )


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
        if path.suffix in {".md", ".txt", ".py", ".toml", ".yaml", ".yml"}:
            return {"text": path.read_text(encoding="utf-8")}, True, True
        return json.loads(path.read_text(encoding="utf-8")), True, True
    except Exception:
        return {}, True, False


def _watch_paths(repo_root: Path, ws_root: Path) -> list[Path]:
    managed_workspace_map = _managed_repo_path_map(ws_root)
    managed_roots = list(managed_workspace_map.values())
    managed_roots = _as_sorted_unique_paths(managed_roots)
    manifest = _read_managed_repos_manifest(ws_root)

    managed_status_paths = []
    for managed_root in managed_roots:
        managed_status_paths.extend(
            [
                managed_root / ".cache" / "reports" / "system_status.v1.json",
                managed_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json",
                managed_root / ".cache" / "reports" / "codex_timeline_summary.v1.json",
                managed_root / ".cache" / "reports" / "codex_timeline_summary.v1.v1.md",
                managed_root / ".cache" / "index" / "work_intake.v1.json",
                managed_root / ".cache" / "index" / "decision_inbox.v1.json",
            ]
        )

    return [
        ws_root / ".cache" / "reports" / "system_status.v1.json",
        ws_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json",
        ws_root / ".cache" / "reports" / "codex_timeline_summary.v1.json",
        ws_root / ".cache" / "reports" / "codex_timeline_summary.v1.v1.md",
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
        *managed_status_paths,
        Path(manifest.get("path", "")) if manifest.get("path") else ws_root / MANAGED_REPOS_MANIFEST_REL,
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


def _new_call_id() -> str:
    seed = f"{time.time_ns()}|{os.getpid()}|{os.urandom(8).hex()}"
    return f"call_{_hash_text(seed)[:24]}"


def _trace_call_id(trace_meta: dict[str, Any]) -> str:
    raw = trace_meta.get("call_id")
    return str(raw).strip() if isinstance(raw, str) else ""


def _terminal_result_status(status: Any, *, error_code: Any = "") -> str:
    raw_status = str(status or "").strip().upper()
    raw_error = str(error_code or "").strip().upper()
    if raw_status in TERMINAL_RESULT_STATUSES:
        return raw_status
    if raw_error in {"TIMEOUT", "TIME_OUT"}:
        return "TIMEOUT"
    if raw_error in {"CANCELLED", "CANCELED", "ABORTED"}:
        return "CANCELLED"
    if raw_status in {"OK", "WARN", "IDLE", "DONE", "RUNNING", "PENDING"}:
        return "OK"
    return "FAIL"


def _append_op_call(
    ws_root: Path,
    *,
    op: str,
    args: dict[str, Any],
    trace_meta: dict[str, Any],
    call_type: str = "OP_CALL",
    evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "version": "v1",
        "type": call_type,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "op": op,
        "args": _redact(args),
        "trace_meta": trace_meta,
        "evidence_paths": evidence_paths or [],
    }
    call_id = _trace_call_id(trace_meta)
    if call_type == "OP_CALL" and call_id:
        entry["call_id"] = call_id
    return _chat_append(ws_root, entry)


def _append_terminal_result(
    ws_root: Path,
    *,
    op: str,
    status: Any,
    error_code: Any,
    trace_meta: dict[str, Any],
    evidence_paths: list[str] | None = None,
    result_for_seq: int | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_raw = str(status or "")
    status_out = _terminal_result_status(status_raw, error_code=error_code)
    entry: dict[str, Any] = {
        "version": "v1",
        "type": "RESULT",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "op": op,
        "status": status_out,
        "error_code": str(error_code or ""),
        "trace_meta": trace_meta,
        "evidence_paths": evidence_paths or [],
    }
    if status_raw and status_raw.upper() != status_out:
        entry["status_raw"] = status_raw
    call_id = _trace_call_id(trace_meta)
    if call_id:
        entry["call_id"] = call_id
    if isinstance(result_for_seq, int) and result_for_seq > 0:
        entry["result_for_seq"] = int(result_for_seq)
    if isinstance(extra_fields, dict):
        for key, value in extra_fields.items():
            if key in {"status", "status_raw", "error_code", "type", "version", "op", "ts"}:
                continue
            entry[key] = value
    return _chat_append(ws_root, entry)


def _trace_meta_for_op(op: str, args: dict[str, Any], ws_root: Path, *, call_id: str | None = None) -> dict[str, Any]:
    owner_tag = os.environ.get("CODEX_CHAT_TAG", "").strip() or "unknown"
    payload = {
        "op": op,
        "args": {str(k): str(v) for k, v in sorted(args.items())},
        "workspace_root": str(ws_root),
        "owner_tag": owner_tag,
    }
    run_id = _hash_text(json.dumps(payload, sort_keys=True))
    call_id_out = str(call_id or "").strip() or _new_call_id()
    return {
        "run_id": run_id,
        "call_id": call_id_out,
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


def _ops_module():
    import server_utils_ops as _ops_mod

    return _ops_mod


def _run_op(repo_root: Path, ws_root: Path, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return _ops_module()._run_op(repo_root, ws_root, payload)

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
    "_parse_bool_arg",
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
    "_new_call_id",
    "_trace_call_id",
    "_terminal_result_status",
    "_append_op_call",
    "_append_terminal_result",
    "_trace_meta_for_op",
    "_summarize_intake",
    "_summarize_decisions",
    "_summarize_jobs",
    "_manifest_base_candidates",
    "_managed_repos_manifest_candidates",
    "_read_managed_repos_manifest",
    "_collect_managed_repo_entries",
    "_managed_repo_path_map",
    "_parse_iso",
    "_run_op",
    "_search_router",
    "_semantic_index_handle",
    "SEARCH_DEFAULT_MAX_FILES",
    "SEARCH_DEFAULT_MAX_BYTES",
    "SEARCH_DEFAULT_CHUNK",
]
