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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_preflight_stamp(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws),
            "gates": {
                "validate_schemas": "PASS",
                "smoke_fast": "PASS",
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 0, "status": "OK"},
            },
            "overall": "PASS",
            "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    import src.prj_airunner.airrunner_tick as airunner_tick_mod

    ws = repo_root / ".cache" / "ws_airunner_preflight_gate"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json",
        {
            "version": "v1",
            "enabled": True,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "active_hours": {"tz": "UTC", "start": "00:00", "end": "23:59"},
                "weekday_only": False,
            },
            "single_gate": {
                "allowed_ops": [
                    "work-intake-check",
                    "work-intake-exec-ticket",
                    "system-status",
                    "portfolio-status",
                ],
                "require_strict_isolation": True,
            },
        },
    )

    ops_called: list[str] = []

    def _stub_cmd(*, op_name: str, func, args, workspace_root: Path, perf_cfg):
        ops_called.append(op_name)
        if op_name == "work-intake-check":
            _write_json(
                workspace_root / ".cache" / "index" / "work_intake.v1.json",
                {"version": "v1", "generated_at": _now_iso(), "items": []},
            )
            return {"status": "OK", "work_intake_path": ".cache/index/work_intake.v1.json"}
        if op_name == "work-intake-exec-ticket":
            _write_json(
                workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json",
                {
                    "status": "OK",
                    "applied_count": 1,
                    "planned_count": 0,
                    "idle_count": 0,
                    "selected_count": 1,
                    "skipped_count": 0,
                    "decision_needed_count": 0,
                },
            )
            return {"status": "OK", "work_intake_exec_path": ".cache/reports/work_intake_exec_ticket.v1.json"}
        if op_name == "system-status":
            _write_json(workspace_root / ".cache" / "reports" / "system_status.v1.json", {"status": "OK"})
            return {"out_json": str(workspace_root / ".cache" / "reports" / "system_status.v1.json")}
        if op_name == "portfolio-status":
            _write_json(workspace_root / ".cache" / "reports" / "portfolio_status.v1.json", {"status": "OK"})
            return {"report_path": ".cache/reports/portfolio_status.v1.json"}
        if op_name == "ui-snapshot-bundle":
            _write_json(workspace_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json", {"status": "OK"})
            return {"report_path": ".cache/reports/ui_snapshot_bundle.v1.json"}
        return {"status": "OK"}

    original_runner = airunner_tick_mod._run_cmd_json_with_perf
    airunner_tick_mod._run_cmd_json_with_perf = _stub_cmd
    try:
        res_missing = airunner_tick_mod.run_airunner_tick(workspace_root=ws)
        report_missing = _load_json(ws / ".cache" / "reports" / "airunner_tick.v1.json")
        if report_missing.get("preflight_overall") != "MISSING":
            raise SystemExit("airrunner_preflight_gate_contract_test failed: missing stamp not detected")
        if "work-intake-exec-ticket" in report_missing.get("ops_called", []):
            raise SystemExit("airrunner_preflight_gate_contract_test failed: exec-ticket should be blocked")

        _write_preflight_stamp(ws)
        ops_called.clear()
        res_pass = airunner_tick_mod.run_airunner_tick(workspace_root=ws)
        report_pass = _load_json(ws / ".cache" / "reports" / "airunner_tick.v1.json")
        if report_pass.get("preflight_overall") != "PASS":
            raise SystemExit("airrunner_preflight_gate_contract_test failed: expected PASS stamp")
        if "work-intake-exec-ticket" not in report_pass.get("ops_called", []):
            raise SystemExit("airrunner_preflight_gate_contract_test failed: exec-ticket not called")
        if res_missing.get("status") not in {"WARN", "IDLE", "OK"}:
            raise SystemExit("airrunner_preflight_gate_contract_test failed: invalid status")
        if res_pass.get("status") not in {"WARN", "IDLE", "OK"}:
            raise SystemExit("airrunner_preflight_gate_contract_test failed: invalid pass status")
    finally:
        airunner_tick_mod._run_cmd_json_with_perf = original_runner

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
