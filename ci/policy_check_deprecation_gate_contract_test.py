from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _summary_from_stdout(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.splitlines()):
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
    raise SystemExit("policy_check_deprecation_gate_contract_test failed: summary JSON not found in stdout")


def _assert_north_star_contract_surface(summary: dict[str, object], *, mode: str) -> None:
    schema_ref = str(summary.get("north_star_subject_plan_contract_schema") or "")
    if schema_ref != "schemas/north-star-subject-plan.schema.v1.json":
        raise SystemExit(
            "policy_check_deprecation_gate_contract_test failed: "
            + f"{mode} summary missing contract schema path"
        )
    if not bool(summary.get("north_star_subject_plan_contract_schema_exists", False)):
        raise SystemExit(
            "policy_check_deprecation_gate_contract_test failed: "
            + f"{mode} summary contract schema must exist"
        )
    if not bool(summary.get("north_star_subject_plan_contract_schema_valid", False)):
        raise SystemExit(
            "policy_check_deprecation_gate_contract_test failed: "
            + f"{mode} summary contract schema must be valid"
        )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())

    pass_cmd = [
        sys.executable,
        "-m",
        "src.ops.manage",
        "policy-check",
        "--source",
        "fixtures",
        "--outdir",
        ".cache/policy_check_gate_contract_pass",
        "--max-deprecation-warnings",
        "1",
    ]
    pass_proc = subprocess.run(pass_cmd, cwd=repo_root, text=True, capture_output=True)
    if pass_proc.returncode != 0:
        raise SystemExit(
            "policy_check_deprecation_gate_contract_test failed: threshold=1 should pass.\n"
            + (pass_proc.stderr or pass_proc.stdout or "")
        )
    pass_summary = _summary_from_stdout(pass_proc.stdout or "")
    dep_count_pass = int(pass_summary.get("deprecation_warning_count", -1))
    if dep_count_pass < 0:
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: missing deprecation_warning_count")
    if dep_count_pass > 1:
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: expected <=1 warning in pass mode")
    if bool(pass_summary.get("deprecation_gate_exceeded", False)):
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: gate_exceeded should be false in pass mode")
    _assert_north_star_contract_surface(pass_summary, mode="pass")

    fail_cmd = [
        sys.executable,
        "-m",
        "src.ops.manage",
        "policy-check",
        "--source",
        "fixtures",
        "--outdir",
        ".cache/policy_check_gate_contract_fail",
        "--max-deprecation-warnings",
        "0",
    ]
    fail_proc = subprocess.run(fail_cmd, cwd=repo_root, text=True, capture_output=True)
    if fail_proc.returncode == 0:
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: threshold=0 should fail")
    fail_summary = _summary_from_stdout(fail_proc.stdout or "")
    dep_count_fail = int(fail_summary.get("deprecation_warning_count", -1))
    if dep_count_fail < 1:
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: expected warning count >=1 in fail mode")
    if fail_summary.get("error_code") != "DEPRECATION_WARNING_THRESHOLD_EXCEEDED":
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: error_code mismatch")
    if not bool(fail_summary.get("deprecation_gate_exceeded", False)):
        raise SystemExit("policy_check_deprecation_gate_contract_test failed: gate_exceeded should be true in fail mode")
    _assert_north_star_contract_surface(fail_summary, mode="fail")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
