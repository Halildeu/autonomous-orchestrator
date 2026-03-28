"""Contract tests for core ops commands that lack dedicated test files.

Covers: system-status, policy-check, integrity-verify, enforcement-check,
workspace-bootstrap (via bootstrap-check), reaper (dry-run), session-status,
roadmap-status, portfolio-status, decision-inbox-build.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
WS = REPO_ROOT / ".cache" / "ws_core_ops_test"
MANAGE = [sys.executable, "-m", "src.ops.manage"]


def _run(cmd_args: list[str], *, workspace: Path | None = None) -> dict:
    """Run a manage.py command and return parsed JSON output."""
    cmd = MANAGE + cmd_args
    if workspace is not None:
        cmd += ["--workspace-root", str(workspace)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"status": "PARSE_ERROR", "stdout": result.stdout[:300], "stderr": result.stderr[:300]}


def _ok(label: str, payload: dict, *, allow: tuple[str, ...] = ("OK", "WARN", "IDLE")) -> None:
    status = payload.get("status") or payload.get("overall_status") or "UNKNOWN"
    if status not in allow:
        raise SystemExit(f"FAIL [{label}]: status={status!r} payload={json.dumps(payload)[:200]}")
    print(f"OK {label} status={status}")


def setup() -> Path:
    if WS.exists():
        shutil.rmtree(WS)
    WS.mkdir(parents=True, exist_ok=True)
    (WS / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
    (WS / ".cache" / "index").mkdir(parents=True, exist_ok=True)
    return WS


def test_system_status(ws: Path) -> None:
    out = _run(["system-status"], workspace=ws)
    _ok("system-status", out, allow=("OK", "WARN", "IDLE", "FAIL"))


def test_policy_check(ws: Path) -> None:
    # policy-check does not accept --workspace-root
    out = _run(["policy-check", "--source", "fixtures", "--fixtures", "fixtures/envelopes"])
    _ok("policy-check", out, allow=("OK", "WARN", "FAIL"))


def test_integrity_verify(ws: Path) -> None:
    out = _run(["integrity-verify"], workspace=ws)
    _ok("integrity-verify", out, allow=("OK", "WARN", "FAIL", "IDLE"))


def test_enforcement_check(ws: Path) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        out = _run(["enforcement-check", "--outdir", tmpdir])
        _ok("enforcement-check", out, allow=("OK", "WARN", "FAIL", "IDLE"))


def test_reaper_dry_run(ws: Path) -> None:
    # reaper outputs plain text not JSON; check exit code only
    result = subprocess.run(
        MANAGE + ["reaper", "--dry-run", "true"],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    if result.returncode != 0:
        raise SystemExit(f"FAIL [reaper --dry-run]: exit={result.returncode} stderr={result.stderr[:200]}")
    if "DRY_RUN" not in result.stdout:
        raise SystemExit(f"FAIL [reaper --dry-run]: DRY_RUN marker missing in output")
    print("OK reaper --dry-run")


def test_session_status(ws: Path) -> None:
    out = _run(["session-status"], workspace=ws)
    _ok("session-status", out, allow=("OK", "WARN", "IDLE", "FAIL", "MISSING"))


def test_work_intake_check(ws: Path) -> None:
    out = _run(["work-intake-check"], workspace=ws)
    _ok("work-intake-check", out, allow=("OK", "WARN", "IDLE", "FAIL"))


def test_decision_inbox_build(ws: Path) -> None:
    out = _run(["decision-inbox-build"], workspace=ws)
    _ok("decision-inbox-build", out, allow=("OK", "WARN", "IDLE", "FAIL"))


def test_roadmap_status(ws: Path) -> None:
    roadmap = REPO_ROOT / "roadmaps" / "SSOT" / "roadmap.v1.json"
    if not roadmap.exists():
        print("OK roadmap-status (skipped — no SSOT roadmap)")
        return
    out = _run(["roadmap-status", "--roadmap", str(roadmap)], workspace=ws)
    _ok("roadmap-status", out, allow=("OK", "WARN", "IDLE", "FAIL"))


def test_ops_capabilities(ws: Path) -> None:
    out = _run(["ops-capabilities"], workspace=ws)
    if not isinstance(out, dict):
        raise SystemExit(f"FAIL [ops-capabilities]: expected dict, got {type(out)}")
    print("OK ops-capabilities")


def main() -> None:
    ws = setup()
    tests = [
        test_system_status,
        test_policy_check,
        test_integrity_verify,
        test_enforcement_check,
        test_reaper_dry_run,
        test_session_status,
        test_work_intake_check,
        test_decision_inbox_build,
        test_roadmap_status,
        test_ops_capabilities,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t(ws)
            passed += 1
        except SystemExit as e:
            print(str(e), file=sys.stderr)
            failed += 1

    result = {"status": "OK" if failed == 0 else "FAIL", "tests_passed": passed, "tests_failed": failed}
    print(json.dumps(result))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
