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


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"extension_run_dispatch_map_contract_test failed: {message}")


def _run_case(*, run_extension_run, ws: Path, extension_id: str, expected_gate: str) -> dict:
    payload = run_extension_run(
        workspace_root=ws,
        extension_id=extension_id,
        mode="report",
        chat=False,
    )
    _must(isinstance(payload, dict), f"payload must be dict for {extension_id}")
    _must(str(payload.get("selected_single_gate") or "") == expected_gate, f"selected gate mismatch for {extension_id}")
    _must(payload.get("single_gate_dispatched") is True, f"single gate not dispatched for {extension_id}")
    _must(expected_gate in (payload.get("actions_executed") or []), f"actions_executed missing {expected_gate}")

    gate_status = str(payload.get("single_gate_status") or "")
    allowed = {"OK", "WARN", "FAIL", "BLOCKED", "IDLE", "UNKNOWN", "SKIPPED"}
    _must(gate_status in allowed, f"unexpected single_gate_status={gate_status} for {extension_id}")

    report_path = ws / ".cache" / "reports" / f"extension_run.{extension_id}.v1.json"
    _must(report_path.exists(), f"extension_run report missing for {extension_id}")

    report_obj = json.loads(report_path.read_text(encoding="utf-8"))
    _must(report_obj.get("selected_single_gate") == expected_gate, f"report gate mismatch for {extension_id}")
    _must(report_obj.get("single_gate_dispatched") is True, f"report single_gate_dispatched mismatch for {extension_id}")
    return payload


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.extension_run import run_extension_run

    ws = repo_root / ".cache" / "ws_extension_run_dispatch_map_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    search_payload = _run_case(
        run_extension_run=run_extension_run,
        ws=ws,
        extension_id="PRJ-SEARCH",
        expected_gate="search-check",
    )
    github_payload = _run_case(
        run_extension_run=run_extension_run,
        ws=ws,
        extension_id="PRJ-GITHUB-OPS",
        expected_gate="github-ops-check",
    )

    print(
        json.dumps(
            {
                "status": "OK",
                "cases": [
                    {"extension_id": "PRJ-SEARCH", "single_gate_status": search_payload.get("single_gate_status")},
                    {"extension_id": "PRJ-GITHUB-OPS", "single_gate_status": github_payload.get("single_gate_status")},
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
