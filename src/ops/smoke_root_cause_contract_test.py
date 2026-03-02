from __future__ import annotations

import json
import sys
from pathlib import Path


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("smoke_root_cause_contract_test failed: " + message)


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.smoke_root_cause import (
        SMOKE_ROOT_CAUSE_TAXONOMY,
        build_smoke_root_cause_report,
        parse_smoke_root_cause_from_output,
    )

    required_codes = {
        "NONE",
        "SCRIPT_BUDGET",
        "READONLY_CMD_NOT_ALLOWED",
        "READONLY_MODE_VIOLATION",
        "CORE_IMMUTABLE_WRITE_BLOCKED",
        "WORKSPACE_ROOT_VIOLATION",
        "SANITIZE_VIOLATION",
        "CONTENT_MISMATCH",
        "CMD_FAILED",
        "SMOKE_ASSERTION_FAILED",
        "UNKNOWN",
    }
    missing = sorted(required_codes.difference(set(SMOKE_ROOT_CAUSE_TAXONOMY.keys())))
    _must(not missing, "taxonomy missing required codes: " + ",".join(missing))

    parsed = parse_smoke_root_cause_from_output(
        "SMOKE_ROOT_CAUSE root_error_code=SCRIPT_BUDGET "
        "failed_step_id=GLOBAL:G:001 "
        "failed_cmd=python ci/check_script_budget.py --out .cache/script_budget/report.json\n"
        "SMOKE_ROOT_STDERR hard limit exceeded"
    )
    _must(parsed.get("root_error_code") == "SCRIPT_BUDGET", "root_error_code parse mismatch")
    _must(parsed.get("failed_step_id") == "GLOBAL:G:001", "failed_step_id parse mismatch")
    _must("check_script_budget.py" in str(parsed.get("failed_cmd") or ""), "failed_cmd parse mismatch")

    report_fail = build_smoke_root_cause_report(
        status="FAIL",
        level="fast",
        reported_root_error_code=str(parsed.get("root_error_code") or ""),
        failed_error_code="CMD_FAILED",
        failed_step_id=str(parsed.get("failed_step_id") or ""),
        failed_cmd=str(parsed.get("failed_cmd") or ""),
        failed_stderr_preview=str(parsed.get("failed_stderr_preview") or ""),
        combined_output="PY_FILE_NO_GROWTH",
    )
    _must(report_fail.get("root_error_code") == "SCRIPT_BUDGET", "classification mismatch for script budget")
    _must(report_fail.get("root_error_severity") == "HIGH", "severity mismatch for script budget")

    report_ok = build_smoke_root_cause_report(status="OK", level="fast")
    _must(report_ok.get("root_error_code") == "NONE", "OK status must classify as NONE")
    _must(report_ok.get("root_error_severity") == "INFO", "OK status severity must be INFO")

    print(
        json.dumps(
            {
                "status": "OK",
                "codes": sorted(SMOKE_ROOT_CAUSE_TAXONOMY.keys()),
                "script_budget_severity": report_fail.get("root_error_severity"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
