from __future__ import annotations

import json
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())

    import sys

    sys.path.insert(0, str(repo_root))
    from src.ops.system_status_builder import _airunner_status_for_overall

    idle_disabled = {
        "status": "IDLE",
        "auto_mode": {"auto_mode_effective": False},
        "jobs": {"total": 0},
    }
    if _airunner_status_for_overall(idle_disabled) != "OK":
        raise SystemExit("system_status_airunner_idle_overall_contract_test failed: expected OK for idle+disabled")

    idle_enabled = {
        "status": "IDLE",
        "auto_mode": {"auto_mode_effective": True},
        "jobs": {"total": 0},
    }
    if _airunner_status_for_overall(idle_enabled) != "WARN":
        raise SystemExit("system_status_airunner_idle_overall_contract_test failed: expected WARN for idle+enabled")

    idle_with_jobs = {
        "status": "IDLE",
        "auto_mode": {"auto_mode_effective": False},
        "jobs": {"total": 1},
    }
    if _airunner_status_for_overall(idle_with_jobs) != "WARN":
        raise SystemExit("system_status_airunner_idle_overall_contract_test failed: expected WARN for idle+jobs")

    ok_live = {
        "status": "OK",
        "auto_mode": {"auto_mode_effective": False},
        "jobs": {"total": 0},
    }
    if _airunner_status_for_overall(ok_live) != "OK":
        raise SystemExit("system_status_airunner_idle_overall_contract_test failed: expected OK passthrough")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
