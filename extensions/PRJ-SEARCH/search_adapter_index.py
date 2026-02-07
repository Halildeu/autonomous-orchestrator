from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any

from search_adapter_core import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    REPO_ALLOWED_EXTS,
    SSOT_ALLOWED_EXTS,
    ScopeSpec,
    _atomic_write_json,
    _ensure_fts_db,
    _iter_files,
    _now_iso,
    _safe_int,
)


def paths(manager: Any, scope: str) -> dict[str, Path]:
    scope_norm = str(scope or "ssot").strip().lower()
    base = manager.workspace_root / ".cache" / "state" / "keyword_search"
    return {
        "db": base / f"keyword_index.{scope_norm}.v1.sqlite3",
        "manifest": base / f"keyword_index.{scope_norm}.manifest.v1.json",
        "history": base / f"keyword_index.{scope_norm}.history.v1.json",
    }


def scope_spec(manager: Any, scope: str, *, max_file_bytes: int) -> ScopeSpec:
    scope_norm = str(scope or "ssot").strip().lower()
    ws = manager.workspace_root
    rr = manager.repo_root

    if scope_norm == "repo":
        roots = [rr]
        allowed_exts = set(REPO_ALLOWED_EXTS)
    else:
        roots = [
            ws / ".cache" / "reports",
            ws / ".cache" / "index",
            ws / ".cache" / "state",
            rr / "docs" / "OPERATIONS",
            rr / "schemas",
            rr / "policies",
            rr / "registry",
            rr / "roadmaps" / "SSOT",
            rr / "docs" / "ROADMAP.md",
            rr / "docs" / "LAYER-MODEL-LOCK.v1.md",
            rr / "AGENTS.md",
            rr / ".pre-commit-config.yaml",
            rr / ".github" / "workflows",
        ]
        allowed_exts = set(SSOT_ALLOWED_EXTS)

    exclude_dir_names = set(DEFAULT_EXCLUDE_DIR_NAMES)
    if scope_norm != "repo":
        exclude_dir_names |= {"extensions", "PROJECTS"}

    return ScopeSpec(
        scope=scope_norm,
        roots=roots,
        allowed_exts=allowed_exts,
        exclude_dir_names=exclude_dir_names,
        max_file_bytes=int(max_file_bytes),
    )


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def update_history(history_path: Path, *, manifest: dict[str, Any]) -> dict[str, Any]:
    prev = read_json_if_exists(history_path) or {}
    duration_ms = _safe_int(manifest.get("duration_ms"), 0, min_value=1)
    indexed_files = _safe_int(manifest.get("indexed_files"), 0, min_value=0)
    indexed_bytes = _safe_int(manifest.get("indexed_bytes"), 0, min_value=0)

    seconds = max(0.001, duration_ms / 1000.0)
    fps = float(indexed_files) / seconds if indexed_files else 0.0
    bps = float(indexed_bytes) / seconds if indexed_bytes else 0.0

    alpha = 0.35
    prev_fps = float(prev.get("ema_files_per_sec") or 0.0)
    prev_bps = float(prev.get("ema_bytes_per_sec") or 0.0)
    ema_fps = fps if prev_fps <= 0 else (alpha * fps + (1.0 - alpha) * prev_fps)
    ema_bps = bps if prev_bps <= 0 else (alpha * bps + (1.0 - alpha) * prev_bps)

    samples = _safe_int(prev.get("samples"), 0, min_value=0) + 1
    out = {
        "version": "v1",
        "scope": str(manifest.get("scope") or ""),
        "samples": samples,
        "ema_files_per_sec": round(ema_fps, 3),
        "ema_bytes_per_sec": round(ema_bps, 3),
        "last_built_at": str(manifest.get("built_at") or ""),
        "last_duration_ms": int(duration_ms),
        "last_indexed_files": int(indexed_files),
        "last_indexed_bytes": int(indexed_bytes),
    }
    _atomic_write_json(history_path, out)
    return out


def predict_eta_seconds(*, manifest: dict[str, Any] | None, history: dict[str, Any] | None) -> int | None:
    if not manifest or not history:
        return None
    ema_fps = float(history.get("ema_files_per_sec") or 0.0)
    ema_bps = float(history.get("ema_bytes_per_sec") or 0.0)
    files_total = _safe_int(manifest.get("indexed_files"), 0, min_value=0)
    bytes_total = _safe_int(manifest.get("indexed_bytes"), 0, min_value=0)
    eta_files = (float(files_total) / ema_fps) if ema_fps > 0 and files_total > 0 else 0.0
    eta_bytes = (float(bytes_total) / ema_bps) if ema_bps > 0 and bytes_total > 0 else 0.0
    eta = max(eta_files, eta_bytes)
    if eta <= 0:
        return None
    return max(1, int(math.ceil(eta)))


def status(manager: Any, scope: str) -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    path_map = paths(manager, scope_norm)
    manifest = read_json_if_exists(path_map["manifest"])
    history = read_json_if_exists(path_map["history"])

    spec = scope_spec(
        manager,
        scope_norm,
        max_file_bytes=_safe_int((manifest or {}).get("max_file_bytes"), 524288, min_value=4096),
    )
    config_sig = spec.signature()
    index_present = path_map["db"].exists()

    with manager._lock:
        job = dict(manager._jobs.get(scope_norm) or {})

    stale = False
    if manifest and isinstance(manifest.get("config_sig"), str) and manifest.get("config_sig") != config_sig:
        stale = True
    predicted = predict_eta_seconds(manifest=manifest, history=history)
    index_obj: dict[str, Any] = {
        "indexed_at": str((manifest or {}).get("built_at") or ""),
        "file_count": _safe_int((manifest or {}).get("indexed_files"), 0, min_value=0),
        "record_count": _safe_int((manifest or {}).get("indexed_files"), 0, min_value=0),
        "adapter_id": "fts5+rg",
        "scope": scope_norm,
        "stale": bool(stale),
        "predicted_eta_seconds": predicted,
        "paths": {k: str(v) for k, v in path_map.items()},
    }

    if job and str(job.get("job_status") or "") == "BUILDING":
        started_mono = float(job.get("started_mono") or 0.0)
        elapsed = max(0.001, time.monotonic() - started_mono) if started_mono else 0.0
        processed_files = _safe_int(job.get("processed_files"), 0, min_value=0)
        processed_bytes = _safe_int(job.get("processed_bytes"), 0, min_value=0)
        total_files = _safe_int(job.get("total_files"), 0, min_value=0)
        total_bytes = _safe_int(job.get("total_bytes"), 0, min_value=0)

        ema_fps = float((history or {}).get("ema_files_per_sec") or 0.0)
        ema_bps = float((history or {}).get("ema_bytes_per_sec") or 0.0)
        cur_fps = (float(processed_files) / elapsed) if elapsed > 0 and processed_files > 0 else 0.0
        cur_bps = (float(processed_bytes) / elapsed) if elapsed > 0 and processed_bytes > 0 else 0.0

        alpha = 0.5
        eff_fps = cur_fps if ema_fps <= 0 else (alpha * cur_fps + (1.0 - alpha) * ema_fps)
        eff_bps = cur_bps if ema_bps <= 0 else (alpha * cur_bps + (1.0 - alpha) * ema_bps)

        remaining_files = max(0, total_files - processed_files)
        remaining_bytes = max(0, total_bytes - processed_bytes)
        eta_files = (float(remaining_files) / eff_fps) if eff_fps > 0 and remaining_files > 0 else 0.0
        eta_bytes = (float(remaining_bytes) / eff_bps) if eff_bps > 0 and remaining_bytes > 0 else 0.0
        eta = max(eta_files, eta_bytes)
        eta_seconds = max(1, int(math.ceil(eta))) if eta > 0 else None

        index_obj.update(
            {
                "build_status": "BUILDING",
                "build_started_at": str(job.get("started_at") or ""),
                "build_phase": str(job.get("phase") or ""),
                "build_progress": {
                    "processed_files": processed_files,
                    "total_files": total_files,
                    "processed_bytes": processed_bytes,
                    "total_bytes": total_bytes,
                },
                "build_eta_seconds": eta_seconds,
                "eta_source": "history+progress" if eta_seconds is not None else "unknown",
            }
        )
        return {
            "status": "BUILDING",
            "scope": scope_norm,
            "job_id": str(job.get("job_id") or ""),
            "index": index_obj,
            "index_present": bool(index_present),
            "config_sig": config_sig,
            "manifest": manifest or {},
            "history": history or {},
        }

    return {
        "status": "OK" if index_present and not stale else ("STALE" if index_present else "MISSING"),
        "scope": scope_norm,
        "index_present": bool(index_present),
        "index": index_obj,
        "config_sig": config_sig,
        "manifest": manifest or {},
        "history": history or {},
    }


def start_build(
    manager: Any,
    scope: str,
    *,
    force: bool = False,
    max_files: int = 0,
    max_file_bytes: int = 524288,
) -> dict[str, Any]:
    scope_norm = str(scope or "ssot").strip().lower()
    max_files = _safe_int(max_files, 0, min_value=0, max_value=200000)
    max_file_bytes = _safe_int(max_file_bytes, 524288, min_value=4096, max_value=5 * 1024 * 1024)

    with manager._lock:
        existing = dict(manager._jobs.get(scope_norm) or {})
        if existing and str(existing.get("job_status") or "") == "BUILDING":
            return status(manager, scope_norm)

        job_id = f"KWBUILD-{hashlib.sha256(f'{time.time_ns()}:{os.getpid()}'.encode('utf-8')).hexdigest()[:10]}"
        manager._jobs[scope_norm] = {
            "job_id": job_id,
            "job_status": "BUILDING",
            "phase": "scan",
            "started_at": _now_iso(),
            "started_mono": time.monotonic(),
            "processed_files": 0,
            "processed_bytes": 0,
            "total_files": 0,
            "total_bytes": 0,
            "error": "",
        }

    def _thread() -> None:
        path_map = paths(manager, scope_norm)
        spec = scope_spec(manager, scope_norm, max_file_bytes=max_file_bytes)
        tmp_db = path_map["db"].with_suffix(path_map["db"].suffix + ".tmp")
        tmp_db.parent.mkdir(parents=True, exist_ok=True)

        start_mono = time.monotonic()
        total_bytes = 0
        processed_bytes = 0
        processed_files = 0
        skipped = {"read_error": 0}
        try:
            files, file_stats = _iter_files(
                spec.roots,
                allowed_exts=spec.allowed_exts,
                exclude_dir_names=spec.exclude_dir_names,
                max_file_bytes=spec.max_file_bytes,
                max_files=max_files,
            )
            for path in files:
                try:
                    total_bytes += int(path.stat().st_size)
                except Exception:
                    continue

            with manager._lock:
                cur = manager._jobs.get(scope_norm)
                if isinstance(cur, dict):
                    cur["phase"] = "index"
                    cur["total_files"] = len(files)
                    cur["total_bytes"] = int(total_bytes)

            con = _ensure_fts_db(tmp_db, recreate=True)
            con.execute("BEGIN;")
            try:
                for idx, path in enumerate(files):
                    try:
                        text = path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        skipped["read_error"] += 1
                        continue
                    con.execute("INSERT INTO docs(path, content) VALUES(?, ?);", (str(path), text))
                    processed_files += 1
                    try:
                        processed_bytes += int(path.stat().st_size)
                    except Exception:
                        processed_bytes += len(text.encode("utf-8", errors="ignore"))
                    if idx % 20 == 0:
                        with manager._lock:
                            cur = manager._jobs.get(scope_norm)
                            if isinstance(cur, dict):
                                cur["processed_files"] = int(processed_files)
                                cur["processed_bytes"] = int(processed_bytes)
                con.execute("COMMIT;")
            finally:
                con.close()

            if path_map["db"].exists() and force:
                try:
                    path_map["db"].unlink()
                except Exception:
                    pass
            tmp_db.replace(path_map["db"])

            duration_ms = int((time.monotonic() - start_mono) * 1000)
            manifest = {
                "version": "v1",
                "scope": scope_norm,
                "built_at": _now_iso(),
                "duration_ms": duration_ms,
                "indexed_files": int(processed_files),
                "indexed_bytes": int(processed_bytes),
                "max_file_bytes": int(spec.max_file_bytes),
                "max_files": int(max_files),
                "config_sig": spec.signature(),
                "file_stats": file_stats,
                "skipped": skipped,
                "db_path": str(path_map["db"]),
            }
            _atomic_write_json(path_map["manifest"], manifest)
            history = update_history(path_map["history"], manifest=manifest)

            with manager._lock:
                cur = manager._jobs.get(scope_norm)
                if isinstance(cur, dict):
                    cur["job_status"] = "DONE"
                    cur["finished_at"] = _now_iso()
                    cur["duration_ms"] = duration_ms
                    cur["manifest"] = manifest
                    cur["history"] = history
        except Exception as exc:
            with manager._lock:
                cur = manager._jobs.get(scope_norm)
                if isinstance(cur, dict):
                    cur["job_status"] = "FAIL"
                    cur["finished_at"] = _now_iso()
                    cur["error"] = str(exc)
            try:
                if tmp_db.exists():
                    tmp_db.unlink()
            except Exception:
                pass

    threading.Thread(target=_thread, daemon=True).start()
    return status(manager, scope_norm)

