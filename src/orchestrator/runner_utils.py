from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def print_error(kind: str, message: str, *, details: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"status": "ERROR", "error_type": kind, "message": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sha256_concat_files(paths: list[Path]) -> str:
    h = sha256()
    for p in paths:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def hash_json_dir(workspace: Path, rel_dir: str) -> str:
    d = workspace / rel_dir
    paths: list[Path] = []
    if d.exists():
        paths = [p for p in d.glob("*.json") if p.is_file()]
    paths = sorted(paths, key=lambda p: p.relative_to(workspace).as_posix())
    return sha256_concat_files(paths)


def replay_forced_run_id(*, replay_of: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")
    suffix = sha256(f"{replay_of}:{ts}".encode("utf-8")).hexdigest()[:8]
    return f"replay-{ts}-{suffix}"
