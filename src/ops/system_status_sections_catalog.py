from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iso_core_status(workspace_root: Path) -> tuple[str, list[str], list[str]]:
    base = workspace_root / "tenant" / "TENANT-DEFAULT"
    names = ["context.v1.md", "stakeholders.v1.md", "scope.v1.md", "criteria.v1.md"]
    paths = [str(Path("tenant") / "TENANT-DEFAULT" / n) for n in names]
    missing = [p for p, n in zip(paths, names) if not (base / n).exists()]
    status = "OK" if not missing else "WARN"
    return (status, missing, paths)


def _catalog_status(workspace_root: Path) -> tuple[str, list[str]]:
    path = workspace_root / ".cache" / "index" / "catalog.v1.json"
    if not path.exists():
        return ("WARN", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [])
    packs = obj.get("packs") if isinstance(obj, dict) else None
    ids: list[str] = []
    if isinstance(packs, list):
        for p in packs:
            if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
                ids.append(p["pack_id"])
    ids = sorted(set(ids))
    return ("OK", ids)
