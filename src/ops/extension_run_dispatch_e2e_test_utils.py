from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"extension_run_dispatch_e2e_contract_test failed: {message}")


def run_dispatch_case(
    *,
    test_name: str,
    extension_id: str,
    expected_gate: str,
    required_output_keys: list[str] | None = None,
) -> dict:
    repo_root = find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.ops.extension_run import run_extension_run

    ws = repo_root / ".cache" / f"ws_{test_name}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    payload = run_extension_run(
        workspace_root=ws,
        extension_id=extension_id,
        mode="report",
        chat=False,
    )

    must(isinstance(payload, dict), f"payload must be dict for {extension_id}")
    must(
        str(payload.get("selected_single_gate") or "") == expected_gate,
        f"selected gate mismatch for {extension_id}",
    )
    must(payload.get("single_gate_dispatched") is True, f"single gate not dispatched for {extension_id}")
    must(expected_gate in (payload.get("actions_executed") or []), f"actions_executed missing {expected_gate}")
    must(not str(payload.get("single_gate_error_code") or ""), f"single_gate_error_code present for {extension_id}")

    gate_status = str(payload.get("single_gate_status") or "")
    allowed = {"OK", "WARN", "FAIL", "BLOCKED", "IDLE", "UNKNOWN", "SKIPPED"}
    must(gate_status in allowed, f"unexpected single_gate_status={gate_status} for {extension_id}")

    report_path = ws / ".cache" / "reports" / f"extension_run.{extension_id}.v1.json"
    must(report_path.exists(), f"extension_run report missing for {extension_id}")
    report_obj = json.loads(report_path.read_text(encoding="utf-8"))
    must(report_obj.get("selected_single_gate") == expected_gate, f"report gate mismatch for {extension_id}")
    must(
        report_obj.get("single_gate_dispatched") is True,
        f"report single_gate_dispatched mismatch for {extension_id}",
    )

    outputs = payload.get("single_gate_outputs") if isinstance(payload.get("single_gate_outputs"), dict) else {}
    if required_output_keys:
        for key in required_output_keys:
            val = outputs.get(key)
            must(isinstance(val, str) and bool(val.strip()), f"missing output key={key} for {extension_id}")
    else:
        must(outputs is not None, f"single_gate_outputs missing for {extension_id}")

    return payload
