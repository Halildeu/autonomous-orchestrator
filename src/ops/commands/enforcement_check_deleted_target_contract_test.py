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


def main() -> int:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    import src.ops.commands.enforcement_check as enforcement_check

    outdir = repo_root / ".cache" / "ws_enforcement_deleted_target_test" / ".cache" / "reports" / "enforcement"
    if outdir.parent.parent.parent.exists():
        shutil.rmtree(outdir.parent.parent.parent)

    called = {"run_semgrep": False}
    original_git_diff_paths = enforcement_check._git_diff_paths
    original_run_semgrep = enforcement_check._run_semgrep

    try:
        enforcement_check._git_diff_paths = lambda root, baseline_ref: (
            ["extensions/release-automation/tests/contract_test.py"],
            None,
        )

        def _unexpected_run_semgrep(**kwargs):  # type: ignore[no-untyped-def]
            called["run_semgrep"] = True
            return ({"results": [], "errors": []}, [])

        enforcement_check._run_semgrep = _unexpected_run_semgrep

        result = enforcement_check.run_enforcement_check(
            outdir=outdir,
            ruleset=repo_root / "extensions" / "PRJ-ENFORCEMENT-PACK" / "semgrep" / "rules",
            profile="strict",
            baseline="git:HEAD~1",
            intake_id="INTAKE-DELETED-TARGET",
            chat=False,
        )
    finally:
        enforcement_check._git_diff_paths = original_git_diff_paths
        enforcement_check._run_semgrep = original_run_semgrep

    if called["run_semgrep"]:
        raise SystemExit("enforcement_check_deleted_target_contract_test failed: semgrep should not run for deleted-only targets")
    if result.get("status") != "OK":
        raise SystemExit("enforcement_check_deleted_target_contract_test failed: deleted-only targets must not block")

    stdout_path = Path(str(result.get("semgrep_stdout") or ""))
    if not stdout_path.exists():
        raise SystemExit("enforcement_check_deleted_target_contract_test failed: semgrep stdout missing")
    stdout_text = stdout_path.read_text(encoding="utf-8")
    if "NO_SCANNABLE_DELTA_TARGETS" not in stdout_text:
        raise SystemExit("enforcement_check_deleted_target_contract_test failed: deleted target note missing")

    print(json.dumps({"status": "OK", "semgrep_called": called["run_semgrep"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
