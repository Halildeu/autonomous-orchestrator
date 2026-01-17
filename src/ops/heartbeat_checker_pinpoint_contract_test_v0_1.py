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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.heartbeat_checker_pinpoint import run_heartbeat_checker_pinpoint

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "heartbeat_pinpoint_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    reports = ws_root / ".cache" / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    probe = reports / "heartbeat_checker_code_probe.v0.1-r2.json"
    _write_json(
        probe,
        {
            "version": "v0.1-r2",
            "hits": [
                {
                    "path": "src/ops/operability_heartbeat_reconcile.py",
                    "match": "heartbeat",
                    "snippet": "heartbeat",
                }
            ],
        },
    )

    result = run_heartbeat_checker_pinpoint(
        workspace_root=ws_root,
        probe_path=".cache/reports/heartbeat_checker_code_probe.v0.1-r2.json",
        out_json=".cache/reports/heartbeat_checker_pinpoint.contract.v1.json",
        out_md=".cache/reports/heartbeat_checker_pinpoint.contract.v1.md",
        max_files=3,
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = reports / "heartbeat_checker_pinpoint.contract.v1.json"
    out_md = reports / "heartbeat_checker_pinpoint.contract.v1.md"
    _assert(out_json.exists(), "JSON report not written")
    _assert(out_md.exists(), "MD report not written")

    bad_out = run_heartbeat_checker_pinpoint(
        workspace_root=ws_root,
        probe_path=".cache/reports/heartbeat_checker_code_probe.v0.1-r2.json",
        out_json="heartbeat_checker_pinpoint.bad.json",
        out_md=".cache/reports/heartbeat_checker_pinpoint.bad.md",
    )
    _assert(bad_out.get("status") == "FAIL", "expected FAIL for invalid out_json")
    _assert(bad_out.get("error_code") == "OUT_PATH_INVALID", f"unexpected error_code: {bad_out}")

    bad_probe = run_heartbeat_checker_pinpoint(
        workspace_root=ws_root,
        probe_path="heartbeat_checker_code_probe.v0.1-r2.json",
        out_json=".cache/reports/heartbeat_checker_pinpoint.bad2.json",
        out_md=".cache/reports/heartbeat_checker_pinpoint.bad2.md",
    )
    _assert(bad_probe.get("status") == "FAIL", "expected FAIL for invalid probe path")
    _assert(bad_probe.get("error_code") == "PROBE_PATH_INVALID", f"unexpected error_code: {bad_probe}")

    print("OK")


if __name__ == "__main__":
    main()
