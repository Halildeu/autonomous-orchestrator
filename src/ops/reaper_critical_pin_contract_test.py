from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _touch_old(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{\"status\":\"ok\"}\n", encoding="utf-8")
    path.touch()
    old_ts = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
    path.chmod(0o644)
    path.parent.chmod(0o755)
    import os

    os.utime(path, (old_ts, old_ts))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.ops.reaper import compute_reaper_report

    ws = repo_root / ".cache" / "ws_reaper_critical_pin_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / "policies" / "policy_retention.v1.json",
        {
            "version": "v1",
            "evidence_days": 0,
            "dlq_days": 0,
            "cache_days": 0,
            "allow_critical_cache_delete": False,
            "cache_exclude_paths": [],
            "cache_exclude_globs": [],
        },
    )

    critical_file = ws / ".cache" / "ws_customer_default" / ".cache" / "index" / "mechanisms.registry.v1.json"
    _touch_old(critical_file)

    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    report_locked = compute_reaper_report(root=ws, dry_run=True, now=now)
    cache_locked = report_locked.get("cache") if isinstance(report_locked.get("cache"), dict) else {}
    candidate_paths_locked = cache_locked.get("paths") if isinstance(cache_locked.get("paths"), list) else []
    critical_locked_paths = cache_locked.get("critical_locked_paths") if isinstance(cache_locked.get("critical_locked_paths"), list) else []
    critical_rel = ".cache/ws_customer_default/.cache/index/mechanisms.registry.v1.json"
    if critical_rel in candidate_paths_locked:
        raise SystemExit("reaper_critical_pin_contract_test failed: critical file entered candidates while lock is enabled")
    if critical_rel not in critical_locked_paths:
        raise SystemExit("reaper_critical_pin_contract_test failed: critical file missing from critical_locked_paths")

    _write_json(
        ws / ".cache" / "ws_customer_default" / ".cache" / "policy_overrides" / "policy_retention.override.v1.json",
        {
            "version": "v1",
            "allow_critical_cache_delete": True,
        },
    )

    report_unlocked = compute_reaper_report(root=ws, dry_run=True, now=now)
    cache_unlocked = report_unlocked.get("cache") if isinstance(report_unlocked.get("cache"), dict) else {}
    candidate_paths_unlocked = cache_unlocked.get("paths") if isinstance(cache_unlocked.get("paths"), list) else []
    if critical_rel not in candidate_paths_unlocked:
        raise SystemExit("reaper_critical_pin_contract_test failed: critical file not candidate after explicit override")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
