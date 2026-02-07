from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path


def run_ci_smoke(repo_root: Path) -> None:
    runpy.run_path(str(repo_root / "ci" / "smoke_test.py"), run_name="__main__")


def print_timer(phase: str, start_ts: float) -> None:
    elapsed = time.monotonic() - start_ts
    print(f"SMOKE_TIMER: phase={phase} seconds={elapsed:.2f}")


def run_cmd(
    *,
    repo_root: Path,
    argv: list[str],
    env: dict[str, str],
    fail_msg: str,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    python_dir = str(Path(sys.executable).resolve().parent)
    if python_dir and python_dir not in env.get("PATH", ""):
        env = env.copy()
        env["PATH"] = python_dir + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(argv, cwd=repo_root, text=True, capture_output=capture, env=env)
    if proc.returncode != 0:
        if capture:
            msg = proc.stderr or proc.stdout or ""
            raise SystemExit(fail_msg + "\n" + msg)
        raise SystemExit(fail_msg)
    return proc


def prepare_workspace(*, repo_root: Path, name: str, prereq_milestones: list[str]) -> Path:
    ws = repo_root / ".cache" / name
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    env.setdefault("SMOKE_MODE", "1")
    env["SMOKE_LEVEL"] = "fast"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg=f"Smoke test failed: workspace-bootstrap failed ({name}).",
    )
    if prereq_milestones:
        milestones_csv = ",".join(prereq_milestones)
        run_cmd(
            repo_root=repo_root,
            argv=[
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                "roadmaps/SSOT/roadmap.v1.json",
                "--milestones",
                milestones_csv,
                "--workspace-root",
                str(ws.relative_to(repo_root)),
                "--dry-run",
                "false",
            ],
            env=env,
            fail_msg=f"Smoke test failed: prerequisite apply failed for {milestones_csv} ({name}).",
        )
    return ws


def write_completeness_state(
    *,
    ws: Path,
    roadmap_path: Path,
    roadmap_sha: str,
    milestone_ids: list[str],
) -> None:
    state_path = ws / ".cache" / "roadmap_state.v1.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "roadmap_path": str(roadmap_path),
                "workspace_root": str(ws.resolve()),
                "roadmap_sha256": roadmap_sha,
                "last_roadmap_sha256": None,
                "drift_detected": False,
                "completed_milestones_meta": {},
                "bootstrapped": True,
                "completed_milestones": milestone_ids,
                "current_milestone": None,
                "attempts": {},
                "last_result": {"status": "OK", "milestone": None, "evidence_path": None, "error_code": None},
                "quarantine": {"milestone": None, "until": None, "reason": None},
                "backoff": {"seconds": 0, "next_try_at": None},
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def assert_system_status_auto_heal(
    *,
    repo_root: Path,
    workspace_root: Path,
    env: dict[str, str],
    evidence_path: str,
) -> int:
    hint_path = workspace_root / ".cache" / "last_finish_evidence.v1.txt"
    hint_path.parent.mkdir(parents=True, exist_ok=True)
    hint_path.write_text(f"{evidence_path}\n", encoding="utf-8")
    proc_status = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "system-status",
            "--workspace-root",
            str(workspace_root.relative_to(repo_root)),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: completeness system-status failed.",
        capture=True,
    )
    try:
        status_out = json.loads(proc_status.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: completeness system-status must print JSON.") from e
    if not isinstance(status_out, dict) or status_out.get("status") in {"FAIL", None}:
        raise SystemExit("Smoke test failed: completeness system-status must succeed.")
    status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    if not status_path.exists():
        raise SystemExit("Smoke test failed: system status JSON missing after completeness run.")
    status_obj = json.loads(status_path.read_text(encoding="utf-8"))
    auto_heal = status_obj.get("sections", {}).get("auto_heal") if isinstance(status_obj, dict) else None
    if not isinstance(auto_heal, dict):
        raise SystemExit("Smoke test failed: system status must include auto_heal section.")
    healed_count = auto_heal.get("healed_count") if isinstance(auto_heal.get("healed_count"), int) else 0
    if healed_count < 1:
        raise SystemExit("Smoke test failed: auto-heal healed_count must be >= 1.")
    status_md = workspace_root / ".cache" / "reports" / "system_status.v1.md"
    if not status_md.exists():
        raise SystemExit("Smoke test failed: system status MD missing after completeness run.")
    if "Auto-heal" not in status_md.read_text(encoding="utf-8"):
        raise SystemExit("Smoke test failed: system status MD missing Auto-heal heading.")
    return healed_count


def prepare_debt_autopilot_fixture(ws: Path) -> None:
    policy_dir = ws / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    debt_policy_path = policy_dir / "policy_debt.v1.json"
    debt_policy_obj = {
        "version": "v1",
        "enabled": True,
        "mode": "safe_apply",
        "max_items": 3,
        "outdir": ".cache/debt_chg",
        "max_auto_apply_per_finish": 1,
        "safe_action_kinds": ["DOC_NOTE", "TEMPLATE_ADD", "ADD_IGNORE"],
        "require_sanitize_pass": True,
        "recheck_system_status": True,
        "on_apply_fail": "warn",
    }
    debt_policy_path.write_text(
        json.dumps(debt_policy_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    chg_dir = ws / ".cache" / "debt_chg"
    chg_dir.mkdir(parents=True, exist_ok=True)
    chg_id = "CHG-20000101-001"
    chg_path = chg_dir / f"{chg_id}.json"
    chg_obj = {
        "id": chg_id,
        "version": "v1",
        "source": "REPO_HYGIENE",
        "target_debt_kind": "REPO_HYGIENE",
        "workspace_root": str(ws),
        "actions": [
            {
                "kind": "DOC_NOTE",
                "file_relpath": f"notes/{chg_id}.md",
                "note": {"text": "Repo hygiene note (safe apply)."},
            }
        ],
        "safety": {
            "apply_scope": "INCUBATOR_ONLY",
            "destructive": False,
            "requires_review": True,
        },
    }
    chg_path.write_text(json.dumps(chg_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def assert_debt_autopilot_applied(*, ws: Path, run_dir: Path) -> None:
    debt_apply_report = run_dir / "debt_apply_report.json"
    if not debt_apply_report.exists():
        raise SystemExit("Smoke test failed: debt auto-apply report missing.")
    try:
        debt_apply_obj = json.loads(debt_apply_report.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: debt auto-apply report must be JSON.") from e
    if not isinstance(debt_apply_obj, dict) or debt_apply_obj.get("status") not in {"OK", "WOULD_APPLY"}:
        raise SystemExit("Smoke test failed: debt auto-apply must be OK.")
    actions_path = ws / ".cache" / "roadmap_actions.v1.json"
    if actions_path.exists():
        actions_obj = json.loads(actions_path.read_text(encoding="utf-8"))
        actions = actions_obj.get("actions") if isinstance(actions_obj, dict) else None
        if isinstance(actions, list):
            if not any(isinstance(a, dict) and a.get("kind") == "DEBT_AUTO_APPLIED" for a in actions):
                raise SystemExit("Smoke test failed: action register must include DEBT_AUTO_APPLIED.")
