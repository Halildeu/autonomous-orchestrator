from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("phase_all_blocking_reasons_contract_test failed: " + message)


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("run_project_management_3phases_contract", str(path))
    if spec is None or spec.loader is None:
        raise SystemExit("phase_all_blocking_reasons_contract_test failed: module load error")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    script_path = repo_root / "scripts" / "run_project_management_3phases.py"
    _must(script_path.exists(), "scripts/run_project_management_3phases.py missing")
    mod = _load_module(script_path)

    steps = mod._normalize_steps_for_workspace(  # type: ignore[attr-defined]
        [("policy-check", ["--source", "both"]), ("script-budget", []), ("smoke", ["--level", "fast"])],
        workspace_root=Path("/tmp/ws_contract"),
        orchestrator_root=repo_root,
        repo_id="REPO-42",
    )
    steps_map = {name: args for name, args in steps}
    policy_args = steps_map.get("policy-check") or []
    budget_args = steps_map.get("script-budget") or []
    smoke_args = steps_map.get("smoke") or []
    _must("--outdir" in policy_args, "policy-check outdir missing")
    _must("--out" in budget_args, "script-budget out missing")
    _must("--root-cause-out" in smoke_args, "smoke root-cause-out missing")
    _must(".cache/project_management/repo-42/policy_check" in " ".join(policy_args), "policy outdir not stabilized")
    _must(".cache/project_management/repo-42/script_budget/report.json" in " ".join(budget_args), "budget out not stabilized")

    issue = mod._classify_command_issue(  # type: ignore[attr-defined]
        command="policy-check",
        status="FAIL",
        return_code=1,
        payload={"status": "FAIL"},
        stdout="",
        stderr="ValueError: PATH_OUTSIDE_REPO: /tmp/out.json",
    )
    _must(issue.get("blocker_code") == "OUTPUT_PATH_OUTSIDE_REPO", "policy path classification mismatch")
    _must(issue.get("blocker_severity") == "HIGH", "policy path severity mismatch")

    blocking = mod._build_blocking_reasons(  # type: ignore[attr-defined]
        [
            {
                "repo_slug": "repo-a",
                "repo_root": "/tmp/repo-a",
                "workspace_root": "/tmp/ws-a",
                "command_issues": [
                    {
                        "command": "policy-check",
                        "status": "FAIL",
                        "return_code": "1",
                        "error_code": "",
                        "blocker_code": "OUTPUT_PATH_OUTSIDE_REPO",
                        "blocker_category": "CONFIG",
                        "blocker_severity": "HIGH",
                        "source": "stderr:path_outside_repo",
                    }
                ],
            }
        ]
    )
    by_code = blocking.get("by_blocker_code") if isinstance(blocking, dict) else {}
    _must(isinstance(by_code, dict) and by_code.get("OUTPUT_PATH_OUTSIDE_REPO") == 1, "blocking by_code mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
