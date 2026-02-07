from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"ops_wiring_contract_test failed: JSON object expected: {path}")
    return obj


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.extension_run import run_extension_run

    ws = repo_root / ".cache" / "ws_enforcement_ops_wiring_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    payload = run_extension_run(
        workspace_root=ws,
        extension_id="PRJ-ENFORCEMENT-PACK",
        mode="report",
        chat=False,
    )

    status = str(payload.get("status") or "")
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit(f"ops_wiring_contract_test failed: invalid status={status}")

    selected_gate = str(payload.get("selected_single_gate") or "")
    if selected_gate != "enforcement-check":
        raise SystemExit("ops_wiring_contract_test failed: selected_single_gate must be enforcement-check")

    if payload.get("single_gate_dispatched") is not True:
        raise SystemExit("ops_wiring_contract_test failed: single_gate_dispatched must be true")

    single_gate_status = str(payload.get("single_gate_status") or "")
    if single_gate_status not in {"OK", "WARN", "BLOCKED", "FAIL", "IDLE", "UNKNOWN"}:
        raise SystemExit("ops_wiring_contract_test failed: unexpected single_gate_status")

    outputs = payload.get("single_gate_outputs") if isinstance(payload.get("single_gate_outputs"), dict) else {}
    contract_json_rel = str(outputs.get("contract_json") or "")
    if not contract_json_rel:
        raise SystemExit("ops_wiring_contract_test failed: missing contract_json output")
    contract_json_abs = ws / contract_json_rel
    if not contract_json_abs.exists():
        raise SystemExit("ops_wiring_contract_test failed: contract_json path missing")

    report_path = ws / ".cache" / "reports" / "extension_run.PRJ-ENFORCEMENT-PACK.v1.json"
    if not report_path.exists():
        raise SystemExit("ops_wiring_contract_test failed: extension_run report missing")
    report_obj = _load_json(report_path)
    if report_obj.get("selected_single_gate") != "enforcement-check":
        raise SystemExit("ops_wiring_contract_test failed: report selected_single_gate mismatch")

    print(json.dumps({"status": "OK", "single_gate_status": single_gate_status}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
