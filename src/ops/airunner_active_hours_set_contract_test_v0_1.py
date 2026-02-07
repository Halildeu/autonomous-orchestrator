from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.extension_cmds import cmd_airunner_active_hours_set

    ws_root = repo_root / ".cache" / "ws_airunner_active_hours_set_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / ".cache" / "policy_overrides").mkdir(parents=True, exist_ok=True)

    missing_end_args = argparse.Namespace(
        workspace_root=str(ws_root),
        end="",
        start="01:23",
        tz="Europe/Istanbul",
        chat="false",
    )
    res_missing = cmd_airunner_active_hours_set(missing_end_args)
    _assert(res_missing != 0, "expected non-zero for missing end")

    ok_args = argparse.Namespace(
        workspace_root=str(ws_root),
        end="23:45",
        start="01:23",
        tz="Europe/Istanbul",
        chat="false",
    )
    res_ok = cmd_airunner_active_hours_set(ok_args)
    _assert(res_ok == 0, "expected success for valid start/end")

    override_path = ws_root / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    _assert(override_path.exists(), "override not written")
    override = json.loads(override_path.read_text(encoding="utf-8"))
    schedule = override.get("schedule") if isinstance(override.get("schedule"), dict) else {}
    active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
    _assert(active_hours.get("enabled") is True, "active_hours.enabled not true")
    _assert(active_hours.get("start") == "01:23", "start mismatch")
    _assert(active_hours.get("end") == "23:45", "end mismatch")
    _assert(active_hours.get("tz") == "Europe/Istanbul", "tz mismatch")

    report_path = ws_root / ".cache" / "reports" / "airunner_active_hours_set.v1.json"
    _assert(report_path.exists(), "report not written")

    print("OK")


if __name__ == "__main__":
    main()
