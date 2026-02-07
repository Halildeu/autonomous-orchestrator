from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _job_time(job: dict[str, Any]) -> datetime:
    for key in ("updated_at", "created_at", "started_at"):
        raw = job.get(key)
        ts = _parse_iso(str(raw)) if raw else None
        if ts:
            return ts
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _normalize_core_path(core_root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (core_root / path).resolve()
    else:
        path = path.resolve()
    return path if _is_within_root(path, core_root) else None


def _find_auto_heal_report(core_root: Path, workspace_root: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates: list[Path] = []
    hint_path = workspace_root / ".cache" / "last_finish_evidence.v1.txt"
    if hint_path.exists():
        try:
            for line in hint_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                resolved = _normalize_core_path(core_root, line)
                if resolved is not None:
                    candidates.append(resolved)
                break
        except Exception:
            pass

    evidence_root = core_root / "evidence" / "roadmap_finish"
    if evidence_root.exists():
        dirs = [d for d in evidence_root.iterdir() if d.is_dir()]
        dirs.sort(key=lambda p: p.name, reverse=True)
        candidates.extend(dirs[:50])

    seen: set[Path] = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        report_path = base / "artifact_completeness_report.json"
        if not report_path.exists():
            continue
        try:
            obj = _load_json(report_path)
        except Exception:
            continue
        if isinstance(obj, dict):
            return (obj, report_path)
    return (None, None)
