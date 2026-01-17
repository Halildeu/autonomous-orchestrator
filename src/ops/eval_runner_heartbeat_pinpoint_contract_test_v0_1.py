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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.eval_runner_heartbeat_pinpoint import run_eval_runner_heartbeat_pinpoint

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "eval_runner_pinpoint_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    reports = ws_root / ".cache" / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    hb_path = ws_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    _write_text(hb_path, "{\"last_tick_at\": \"2026-01-16T00:00:00Z\"}\n")
    test_tmp_hb = (
        ws_root
        / ".cache"
        / "test_tmp"
        / "heartbeat_ws_root"
        / ".cache"
        / "airunner"
        / "airunner_heartbeat.v1.json"
    )
    _write_text(test_tmp_hb, "{\"last_tick_at\": \"2026-01-16T00:00:00Z\"}\n")
    _write_text(
        reports / "heartbeat_real_source_choice.v0.1.json",
        json.dumps(
            {"version": "v0.1", "chosen_path": ".cache/airunner/airunner_heartbeat.v1.json"},
            sort_keys=True,
        ),
    )

    tmp_repo = ws_root / "repo"
    _write_text(tmp_repo / "pyproject.toml", "[tool]\nname = \"eval-runner-pinpoint-test\"\n")
    src_dir = tmp_repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    _write_text(
        src_dir / "eval_runner.py",
        "\n".join(
            [
                "def assess():",
                "    policy = \"policy_north_star_operability.v1.json\"",
                "    rule = \"heartbeat_stale_seconds_gt\"",
                "    thresholds_key = \"heartbeat_stale_seconds_warn\"",
                "    hb_path = \".cache/airunner/airunner_heartbeat.v1.json\"",
                "    key = \"last_tick_at\"",
                "    return rule, thresholds_key, hb_path",
                "",
            ]
        ),
    )

    result = run_eval_runner_heartbeat_pinpoint(
        workspace_root=ws_root,
        out_json=".cache/reports/eval_runner_heartbeat_pinpoint.contract.v1.json",
        out_md=".cache/reports/eval_runner_heartbeat_pinpoint.contract.v1.md",
        max_files=3,
        repo_root_override=tmp_repo,
        now_iso="2026-01-16T00:00:00Z",
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = reports / "eval_runner_heartbeat_pinpoint.contract.v1.json"
    out_md = reports / "eval_runner_heartbeat_pinpoint.contract.v1.md"
    _assert(out_json.exists(), "JSON report not written")
    _assert(out_md.exists(), "MD report not written")

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    _assert(
        payload.get("declared_rule_path") == ".cache/airunner/airunner_heartbeat.v1.json",
        "declared_rule_path missing or incorrect",
    )
    _assert(
        payload.get("eval_runner_read_path") == ".cache/airunner/airunner_heartbeat.v1.json",
        "eval_runner_read_path missing or incorrect",
    )
    _assert(payload.get("eval_runner_read_key") == "last_tick_at", "eval_runner_read_key missing or incorrect")
    _assert(
        payload.get("eval_runner_read_key_source") == "declared_rule_key",
        "eval_runner_read_key_source missing or incorrect",
    )
    _assert(
        payload.get("eval_runner_read_path_source") == "declared_rule_path_resolved",
        "eval_runner_read_path_source missing or incorrect",
    )

    first = json.dumps(payload, sort_keys=True)
    result2 = run_eval_runner_heartbeat_pinpoint(
        workspace_root=ws_root,
        out_json=".cache/reports/eval_runner_heartbeat_pinpoint.contract.v1.json",
        out_md=".cache/reports/eval_runner_heartbeat_pinpoint.contract.v1.md",
        max_files=3,
        repo_root_override=tmp_repo,
        now_iso="2026-01-16T00:00:00Z",
    )
    _assert(result2.get("status") == "OK", f"expected OK, got {result2}")
    second = json.dumps(json.loads(out_json.read_text(encoding="utf-8")), sort_keys=True)
    _assert(first == second, "output not deterministic with fixed timestamp")

    bad_out = run_eval_runner_heartbeat_pinpoint(
        workspace_root=ws_root,
        out_json="eval_runner_heartbeat_pinpoint.bad.json",
        out_md=".cache/reports/eval_runner_heartbeat_pinpoint.bad.md",
        repo_root_override=tmp_repo,
    )
    _assert(bad_out.get("status") == "FAIL", "expected FAIL for invalid out_json")
    _assert(bad_out.get("error_code") == "OUT_PATH_INVALID", f"unexpected error_code: {bad_out}")

    print("OK")


if __name__ == "__main__":
    main()
