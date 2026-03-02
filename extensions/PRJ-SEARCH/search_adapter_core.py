from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n")


def _sha256_json(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_int(raw: Any, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        value = int(str(raw).strip())
    except Exception:
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


DEFAULT_EXCLUDE_DIR_NAMES = {
    ".cache",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "keyword_search",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
}

SSOT_ALLOWED_EXTS = {".md", ".json", ".jsonl", ".toml", ".yaml", ".yml"}
REPO_ALLOWED_EXTS = SSOT_ALLOWED_EXTS | {".py", ".txt", ".js", ".ts", ".tsx", ".html", ".css", ".sh"}

SEARCH_ADAPTER_CONTRACT_ID = "search_adapter_contract.v1"
SEARCH_ADAPTER_KEYWORD_FTS5_RG = "keyword_fts5_rg"
SEARCH_ADAPTER_KEYWORD_PYTHON = "keyword_python_fallback"
SEARCH_ADAPTER_SEMANTIC_PGVECTOR = "semantic_pgvector"


def _detect_mode_auto(query: str) -> str:
    if re.search(r"[\[\]().*+?{}|^$]", query):
        return "regex"
    return "fixed"


def _extract_fts_tokens(query: str, *, max_tokens: int = 6) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9]{2,}", query or "")
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        normalized = token.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= max_tokens:
            break
    return out


def _iter_files(
    roots: list[Path],
    *,
    allowed_exts: set[str],
    exclude_dir_names: set[str],
    max_file_bytes: int,
    max_files: int = 0,
) -> tuple[list[Path], dict[str, int]]:
    seen: set[str] = set()
    files: list[Path] = []
    stats = {
        "considered": 0,
        "selected": 0,
        "skipped_too_large": 0,
        "skipped_ext": 0,
        "skipped_missing": 0,
    }

    def _maybe_add(path: Path) -> None:
        stats["considered"] += 1
        try:
            st = path.stat()
        except Exception:
            stats["skipped_missing"] += 1
            return
        if path.suffix.lower() not in allowed_exts:
            stats["skipped_ext"] += 1
            return
        if int(st.st_size) > int(max_file_bytes):
            stats["skipped_too_large"] += 1
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        files.append(path.resolve())
        stats["selected"] += 1

    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            _maybe_add(root)
        else:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in exclude_dir_names]
                for name in filenames:
                    path = Path(dirpath) / name
                    _maybe_add(path)
                    if max_files > 0 and len(files) >= max_files:
                        return files, stats
    return files, stats


def _ensure_fts_db(db_path: Path, *, recreate: bool) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if recreate and db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=OFF;")
    con.execute("PRAGMA synchronous=OFF;")
    con.execute("PRAGMA temp_store=MEMORY;")
    con.execute("PRAGMA cache_size=-20000;")
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path, content, tokenize='unicode61');")
    return con


def _fts_query_from_tokens(tokens: list[str]) -> str:
    return " AND ".join([f'"{token}"' for token in tokens if token])


def _fts_query_or_from_tokens(tokens: list[str]) -> str:
    return " OR ".join([f'"{token}"' for token in tokens if token])


def _run_rg_on_files(
    query: str,
    files: list[Path],
    *,
    mode: str,
    limit: int,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    mode_norm = str(mode or "").strip().lower()
    if mode_norm not in {"fixed", "regex"}:
        mode_norm = _detect_mode_auto(query)

    cmd = ["rg", "--json", "--no-heading", "--line-number"]
    if mode_norm == "fixed":
        cmd.append("--fixed-strings")
    else:
        cmd.append("--pcre2")
    cmd.extend(["--max-count", "3"])
    cmd.append(query)
    cmd.extend([str(path) for path in files])

    matches: list[dict[str, Any]] = []
    by_file: dict[str, int] = {}
    truncated = False

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                if not isinstance(evt, dict) or evt.get("type") != "match":
                    continue
                data = evt.get("data") if isinstance(evt.get("data"), dict) else {}
                path_obj = data.get("path") if isinstance(data.get("path"), dict) else {}
                path_text = str(path_obj.get("text") or "")
                line_num = data.get("line_number")
                lines_obj = data.get("lines") if isinstance(data.get("lines"), dict) else {}
                text_line = str(lines_obj.get("text") or "").rstrip("\n")
                submatches = data.get("submatches") if isinstance(data.get("submatches"), list) else []
                col = None
                if submatches and isinstance(submatches[0], dict):
                    try:
                        col = int(submatches[0].get("start")) + 1
                    except Exception:
                        col = None
                matches.append(
                    {
                        "path": path_text,
                        "line": int(line_num) if isinstance(line_num, int) else None,
                        "col": col,
                        "text": text_line,
                    }
                )
                by_file[path_text] = by_file.get(path_text, 0) + 1
                if limit > 0 and len(matches) >= limit:
                    truncated = True
                    break
            if truncated:
                try:
                    proc.terminate()
                except Exception:
                    pass
        finally:
            try:
                proc.communicate(timeout=timeout_s)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        backend = "rg"
    except FileNotFoundError:
        backend = "python_fallback"
        regex = None
        if mode_norm == "regex":
            try:
                regex = re.compile(query)
            except Exception:
                regex = None
        for path in files:
            if limit > 0 and len(matches) >= limit:
                truncated = True
                break
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for idx, raw_line in enumerate(text.splitlines(), start=1):
                if mode_norm == "fixed":
                    pos = raw_line.find(query)
                    matched = pos >= 0
                    col = pos + 1 if pos >= 0 else None
                else:
                    m = regex.search(raw_line) if regex else None
                    matched = m is not None
                    col = (m.start() + 1) if m else None
                if not matched:
                    continue
                path_text = str(path)
                matches.append(
                    {
                        "path": path_text,
                        "line": idx,
                        "col": col,
                        "text": raw_line,
                    }
                )
                by_file[path_text] = by_file.get(path_text, 0) + 1
                if limit > 0 and len(matches) >= limit:
                    truncated = True
                    break

    duration_ms = int((time.monotonic() - started) * 1000)
    stats = {
        "duration_ms": duration_ms,
        "match_count": len(matches),
        "truncated": bool(truncated),
        "backend": backend,
        "matches_by_file_top": sorted(by_file.items(), key=lambda kv: (-kv[1], kv[0]))[:10],
    }
    return matches, stats


@dataclass(frozen=True)
class ScopeSpec:
    scope: str
    roots: list[Path]
    allowed_exts: set[str]
    exclude_dir_names: set[str]
    max_file_bytes: int

    def signature(self) -> str:
        spec = {
            "scope": self.scope,
            "roots": [str(path) for path in self.roots],
            "allowed_exts": sorted(self.allowed_exts),
            "exclude_dir_names": sorted(self.exclude_dir_names),
            "max_file_bytes": int(self.max_file_bytes),
        }
        return _sha256_json(spec)


__all__ = [
    "DEFAULT_EXCLUDE_DIR_NAMES",
    "SSOT_ALLOWED_EXTS",
    "REPO_ALLOWED_EXTS",
    "SEARCH_ADAPTER_CONTRACT_ID",
    "SEARCH_ADAPTER_KEYWORD_FTS5_RG",
    "SEARCH_ADAPTER_KEYWORD_PYTHON",
    "SEARCH_ADAPTER_SEMANTIC_PGVECTOR",
    "ScopeSpec",
    "_now_iso",
    "_atomic_write_json",
    "_sha256_json",
    "_safe_int",
    "_detect_mode_auto",
    "_extract_fts_tokens",
    "_iter_files",
    "_ensure_fts_db",
    "_fts_query_from_tokens",
    "_fts_query_or_from_tokens",
    "_run_rg_on_files",
]
