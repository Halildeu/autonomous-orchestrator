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

    from src.ops.policy_rule_extract import run_policy_rule_extract

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "policy_rule_extract_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)

    policy_path = repo_root / ".cache" / "test_tmp" / "policy_rule_extract_policy.v1.json"
    _write_json(
        policy_path,
        {
            "version": "v1",
            "rules": {
                "heartbeat_stale_seconds_gt": {
                    "threshold_seconds": 1800,
                    "input_key": "last_tick_at",
                    "heartbeat_path": ".cache/airunner/airrunner_heartbeat.v1.json",
                }
            },
        },
    )

    result = run_policy_rule_extract(
        workspace_root=ws_root,
        policy_path=str(policy_path.relative_to(repo_root)),
        rule_key="heartbeat_stale_seconds_gt",
        out_path=".cache/reports/policy_rule_extract.contract.v1.json",
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = ws_root / ".cache" / "reports" / "policy_rule_extract.contract.v1.json"
    _assert(out_json.exists(), "report not written")

    bad_out = run_policy_rule_extract(
        workspace_root=ws_root,
        policy_path=str(policy_path.relative_to(repo_root)),
        rule_key="heartbeat_stale_seconds_gt",
        out_path="policy_rule_extract.bad.json",
    )
    _assert(bad_out.get("status") == "FAIL", "expected FAIL for invalid out path")
    _assert(bad_out.get("error_code") == "OUT_PATH_INVALID", f"unexpected error_code: {bad_out}")

    print("OK")


if __name__ == "__main__":
    main()
