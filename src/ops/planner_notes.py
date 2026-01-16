from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.ops.trace_meta import build_run_id, build_trace_meta

NOTE_ID_PREFIX = "NOTE-"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(text: str) -> str:
    raw = str(text or "")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in raw.split("\n")]
    return "\n".join(lines).strip()


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    out = []
    for tag in tags or []:
        value = str(tag or "").strip()
        if value:
            out.append(value)
    return sorted(set(out))


def _normalize_links(links: Iterable[dict[str, Any]] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for link in links or []:
        if not isinstance(link, dict):
            continue
        kind = str(link.get("kind") or "").strip()
        target = str(link.get("id_or_path") or "").strip()
        if not kind or not target:
            continue
        out.append({"kind": kind, "id_or_path": target})
    out.sort(key=lambda item: (item["kind"], item["id_or_path"]))
    return out


def _canonical_note_input(title: str, body: str, tags: list[str], links: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "title": _normalize_text(title),
        "body": _normalize_text(body),
        "tags": tags,
        "links": links,
    }


def _hash_note_input(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _notes_root(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "notes" / "planner"


def _note_path(workspace_root: Path, note_id: str) -> Path:
    return _notes_root(workspace_root) / f"{note_id}.v1.json"


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _note_summary(note: dict[str, Any], rel_path: str) -> dict[str, Any]:
    return {
        "note_id": str(note.get("note_id") or ""),
        "title": str(note.get("title") or ""),
        "tags": note.get("tags") if isinstance(note.get("tags"), list) else [],
        "links": note.get("links") if isinstance(note.get("links"), list) else [],
        "created_at": str(note.get("created_at") or ""),
        "updated_at": str(note.get("updated_at") or ""),
        "path": rel_path,
    }


def _build_notes_index(workspace_root: Path) -> dict[str, Any]:
    notes_root = _notes_root(workspace_root)
    notes: list[dict[str, Any]] = []
    if notes_root.exists():
        for path in sorted(notes_root.glob("NOTE-*.v1.json")):
            try:
                note = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            rel = path.resolve().relative_to(workspace_root.resolve()).as_posix()
            notes.append(_note_summary(note, rel))
    notes.sort(key=lambda item: (item.get("note_id") or ""))
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "notes_count": len(notes),
        "notes": notes,
    }


def run_planner_notes_create(
    *,
    workspace_root: Path,
    title: str,
    body: str,
    tags: Iterable[str] | None,
    links: Iterable[dict[str, Any]] | None,
) -> dict[str, Any]:
    cleaned_tags = _normalize_tags(tags)
    cleaned_links = _normalize_links(links)
    note_input = _canonical_note_input(title, body, cleaned_tags, cleaned_links)
    if not note_input["title"] and not note_input["body"]:
        return {"status": "FAIL", "error": "TITLE_OR_BODY_REQUIRED"}

    note_hash = _hash_note_input(note_input)
    note_id = f"NOTE-{note_hash}"
    note_path = _note_path(workspace_root, note_id)
    _ensure_inside_workspace(workspace_root, note_path)

    created_at = _now_iso()
    if note_path.exists():
        try:
            existing = json.loads(note_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        if isinstance(existing, dict):
            existing_created = existing.get("created_at")
            if isinstance(existing_created, str) and existing_created:
                created_at = existing_created

    inputs = {"note_id": note_id, "action": "create"}
    run_id = build_run_id(workspace_root=workspace_root, op_name="planner-notes-create", inputs=inputs)

    note_rel = note_path.resolve().relative_to(workspace_root.resolve()).as_posix()
    index_path = _notes_root(workspace_root) / "notes_index.v1.json"
    index_rel = index_path.resolve().relative_to(workspace_root.resolve()).as_posix()

    trace_meta = build_trace_meta(
        work_item_id=note_id,
        work_item_kind="PLANNER_NOTE",
        run_id=run_id,
        policy_hash=None,
        evidence_paths=[note_rel, index_rel],
        workspace_root=str(workspace_root),
    )

    note_obj = {
        "version": "v1",
        "note_id": note_id,
        "created_at": created_at,
        "updated_at": _now_iso(),
        "title": note_input["title"],
        "body": note_input["body"],
        "tags": cleaned_tags,
        "links": cleaned_links,
        "trace_meta": trace_meta,
        "evidence_paths": [note_rel],
    }

    _atomic_write(note_path, json.dumps(note_obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    index_payload = _build_notes_index(workspace_root)
    _atomic_write(index_path, json.dumps(index_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    return {
        "status": "OK",
        "note_id": note_id,
        "note_path": note_rel,
        "index_path": index_rel,
        "notes_count": index_payload.get("notes_count", 0),
        "trace_meta": trace_meta,
        "evidence_paths": [note_rel, index_rel],
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }


def run_planner_notes_delete(*, workspace_root: Path, note_id: str) -> dict[str, Any]:
    note_id = str(note_id or "").strip()
    if not note_id:
        return {"status": "FAIL", "error": "NOTE_ID_REQUIRED"}
    if not note_id.startswith(NOTE_ID_PREFIX) or len(note_id) != len(NOTE_ID_PREFIX) + 64:
        return {"status": "FAIL", "error": "NOTE_ID_INVALID"}

    note_path = _note_path(workspace_root, note_id)
    _ensure_inside_workspace(workspace_root, note_path)

    delete_report = workspace_root / ".cache" / "reports" / "planner_notes_delete.v1.json"
    delete_rel = delete_report.resolve().relative_to(workspace_root.resolve()).as_posix()
    index_path = _notes_root(workspace_root) / "notes_index.v1.json"
    index_rel = index_path.resolve().relative_to(workspace_root.resolve()).as_posix()

    inputs = {"note_id": note_id, "action": "delete"}
    run_id = build_run_id(workspace_root=workspace_root, op_name="planner-notes-delete", inputs=inputs)
    trace_meta = build_trace_meta(
        work_item_id=note_id,
        work_item_kind="PLANNER_NOTE",
        run_id=run_id,
        policy_hash=None,
        evidence_paths=[delete_rel, index_rel],
        workspace_root=str(workspace_root),
    )

    deleted = False
    if note_path.exists():
        note_path.unlink()
        deleted = True

    index_payload = _build_notes_index(workspace_root)
    _atomic_write(index_path, json.dumps(index_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    delete_payload = {
        "version": "v1",
        "status": "OK" if deleted else "IDLE",
        "note_id": note_id,
        "deleted": deleted,
        "deleted_at": _now_iso(),
        "trace_meta": trace_meta,
        "evidence_paths": [delete_rel],
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    _atomic_write(delete_report, json.dumps(delete_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    return {
        "status": delete_payload["status"],
        "note_id": note_id,
        "deleted": deleted,
        "delete_report_path": delete_rel,
        "index_path": index_rel,
        "notes_count": index_payload.get("notes_count", 0),
        "trace_meta": trace_meta,
        "evidence_paths": [delete_rel, index_rel],
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
