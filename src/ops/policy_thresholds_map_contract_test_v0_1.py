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

    from src.ops.policy_thresholds_map import run_policy_thresholds_map

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "policy_thresholds_map_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)

    thresholds_payload = {
        "version": "v1",
        "matches": [
            {
                "path": "thresholds",
                "extracted_subtree": {
                    "heartbeat_stale_seconds_fail": 7200,
                    "heartbeat_stale_seconds_warn": 1800,
                },
            }
        ],
    }
    rule_payload = {
        "version": "v1",
        "matches": [
            {
                "path": "classification.FAIL_if.heartbeat_stale_seconds_gt",
                "extracted_subtree": "heartbeat_stale_seconds_fail",
            },
            {
                "path": "classification.WARN_if.heartbeat_stale_seconds_gt",
                "extracted_subtree": "heartbeat_stale_seconds_warn",
            },
            {
                "path": "gap_rules.heartbeat_stale_seconds_gt",
                "extracted_subtree": "INCIDENT:RUNNER_STALLED",
            },
        ],
    }

    thresholds_path = ws_root / ".cache" / "reports" / "policy_rule_extract.thresholds.contract.v1.json"
    rule_path = ws_root / ".cache" / "reports" / "policy_rule_extract.heartbeat_stale_seconds_gt.contract.v1.json"
    _write_json(thresholds_path, thresholds_payload)
    _write_json(rule_path, rule_payload)

    result = run_policy_thresholds_map(
        workspace_root=ws_root,
        thresholds_path=thresholds_path,
        rule_path=rule_path,
        out_path=".cache/reports/policy_thresholds_map.contract.v1.json",
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = ws_root / ".cache" / "reports" / "policy_thresholds_map.contract.v1.json"
    _assert(out_json.exists(), "report not written")
    report = json.loads(out_json.read_text(encoding="utf-8"))
    resolved = report.get("resolved_threshold_seconds") or {}
    _assert(resolved.get("heartbeat_stale_seconds_fail") == 7200.0, "missing fail threshold")
    _assert(resolved.get("heartbeat_stale_seconds_warn") == 1800.0, "missing warn threshold")

    bad_out = run_policy_thresholds_map(
        workspace_root=ws_root,
        thresholds_path=thresholds_path,
        rule_path=rule_path,
        out_path="policy_thresholds_map.bad.json",
    )
    _assert(bad_out.get("status") == "FAIL", "expected FAIL for invalid out path")
    _assert(bad_out.get("error_code") == "OUT_PATH_INVALID", f"unexpected error_code: {bad_out}")

    print("OK")


if __name__ == "__main__":
    main()
