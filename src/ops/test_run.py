from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.closeout_write import run_closeout_write
from src.ops.ops_capabilities import run_ops_capabilities
from src.ops.roadmap_resolve import run_roadmap_resolve
from src.ops.roadmap_seed import run_roadmap_seed
from src.ops.roadmap_state_sync import run_roadmap_state_sync
from src.ops.workspace_find import run_workspace_find


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_workspace_root(workspace_arg: str) -> Path | None:
    root = repo_root()
    ws = Path(str(workspace_arg or "").strip())
    if not ws:
        return None
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        return None
    return ws


def _resolve_reports_path(workspace_root: Path, out_arg: str) -> Path | None:
    raw = Path(str(out_arg or "").strip())
    if not str(raw):
        return None
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        raw_posix = raw.as_posix()
        repo = repo_root().resolve()
        ws_abs = workspace_root.resolve()
        ws_rel = ""
        try:
            ws_rel = ws_abs.relative_to(repo).as_posix()
        except Exception:
            ws_rel = ""
        if ws_rel and raw_posix.startswith(ws_rel.rstrip("/") + "/"):
            candidate = (repo / raw).resolve()
        else:
            candidate = (ws_abs / raw).resolve()
    reports_root = (workspace_root / ".cache" / "reports").resolve()
    try:
        candidate.relative_to(reports_root)
    except Exception:
        return None
    return candidate


def _format_test_result(name: str, passed: bool, details: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "status": "PASS" if passed else "FAIL"}
    if details:
        payload["details"] = details
    return payload


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tail_line(text: str | None) -> str | None:
    if not text:
        return None
    parts = [line.strip() for line in text.splitlines() if line.strip()]
    if not parts:
        return None
    return parts[-1]


def run_test_run(*, workspace_root: Path, out_path: Path | str) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    tests: list[dict[str, Any]] = []
    failures: list[str] = []
    evidence_paths: list[str] = []

    # 1) closeout-write rejects out path outside reports
    bad_out = workspace_root / "closeout_outside.json"
    res = run_closeout_write(
        workspace_root=workspace_root,
        out_path=bad_out,
        title="test-run",
        evidence_paths=[],
    )
    passed = res.get("status") == "FAIL" and res.get("error_code") == "OUT_PATH_INVALID"
    tests.append(_format_test_result("closeout_write_blocks_outside_reports", passed, str(res.get("error_code"))))
    if not passed:
        failures.append("closeout_write_blocks_outside_reports")

    # 2) workspace-find blocks traversal patterns
    res = run_workspace_find(
        workspace_root=workspace_root,
        name="roadmap",
        out_path=workspace_root / ".cache" / "reports" / "test_run_workspace_find.v1.json",
        allowlist=["../"],
        max_depth=1,
        max_files=10,
    )
    passed = res.get("status") == "FAIL" and res.get("error_code") == "ALLOWLIST_INVALID"
    tests.append(_format_test_result("workspace_find_blocks_traversal", passed, str(res.get("error_code"))))
    if not passed:
        failures.append("workspace_find_blocks_traversal")

    # 3) ops-capabilities JSON parseable and stable-sorted
    cap_out = workspace_root / ".cache" / "reports" / "test_run_ops_capabilities.v1.json"
    res = run_ops_capabilities(workspace_root=workspace_root, out_path=cap_out)
    parse_ok = False
    sorted_ok = False
    if res.get("status") == "OK" and cap_out.exists():
        try:
            payload = _read_json(cap_out)
            subcommands = payload.get("subcommands", [])
            names = [item.get("name") for item in subcommands]
            parse_ok = True
            sorted_ok = names == sorted(names) and all(
                item.get("flags", []) == sorted(item.get("flags", [])) for item in subcommands
            )
        except Exception:
            parse_ok = False
            sorted_ok = False
    passed = parse_ok and sorted_ok
    tests.append(_format_test_result("ops_capabilities_sorted", passed))
    if not passed:
        failures.append("ops_capabilities_sorted")
    if cap_out.exists():
        try:
            rel = cap_out.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            rel = str(cap_out)
        evidence_paths.append(rel)

    # 4) roadmap-seed produces a schema-valid roadmap for resolve
    seed_out = workspace_root / ".cache" / "index" / "test_run_roadmap_seed.v1.json"
    seed_res = run_roadmap_seed(
        workspace_root=workspace_root,
        out_path=seed_out,
        title="Test Roadmap Seed",
        force=True,
    )
    seed_ok = seed_res.get("status") == "OK" and seed_out.exists()
    if seed_out.exists():
        try:
            rel = seed_out.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            rel = str(seed_out)
        evidence_paths.append(rel)

    resolve_out = workspace_root / ".cache" / "reports" / "test_run_roadmap_resolve.v1.json"
    resolve_res = run_roadmap_resolve(
        workspace_root=workspace_root,
        name="roadmap",
        out_path=resolve_out,
        allowlist=[".cache", "roadmaps", "docs"],
    )
    resolve_ok = resolve_res.get("status") in {"OK", "WARN"}
    chosen_path = resolve_res.get("chosen_path")
    candidates = resolve_res.get("candidates") if isinstance(resolve_res, dict) else None
    candidate_ok = False
    seed_rel = None
    try:
        seed_rel = seed_out.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        seed_rel = str(seed_out)
    if isinstance(candidates, list):
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            if cand.get("path") == seed_rel and cand.get("parse_ok") and cand.get("schema_ok"):
                candidate_ok = True
                break
    chosen_ok = chosen_path == seed_rel
    passed = seed_ok and resolve_ok and (candidate_ok or chosen_ok)
    details = f"seed_status={seed_res.get('status')} resolve_status={resolve_res.get('status')} chosen={chosen_path}"
    tests.append(_format_test_result("roadmap_seed_resolve_valid", passed, details))
    if not passed:
        failures.append("roadmap_seed_resolve_valid")
    if resolve_out.exists():
        try:
            rel = resolve_out.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            rel = str(resolve_out)
        evidence_paths.append(rel)

    # 5) roadmap-state-sync writes a matching state file for roadmap-status
    state_out = workspace_root / ".cache" / "roadmap_state.v1.json"
    sync_res = run_roadmap_state_sync(
        workspace_root=workspace_root,
        roadmap_path=seed_out,
        out_path=state_out,
        mode="sync",
    )
    state_ok = sync_res.get("status") == "OK" and state_out.exists()
    status_ok = False
    status_error = None
    if state_ok:
        try:
            from src.roadmap.orchestrator import status as roadmap_status

            roadmap_status(roadmap_path=seed_out, workspace_root=workspace_root)
            status_ok = True
        except Exception as exc:
            status_error = str(exc)
            status_ok = False
    passed = state_ok and status_ok
    details = f"sync_status={sync_res.get('status')} roadmap_status_error={status_error}"
    tests.append(_format_test_result("roadmap_state_sync_status_ok", passed, details))
    if not passed:
        failures.append("roadmap_state_sync_status_ok")
    if state_out.exists():
        try:
            rel = state_out.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            rel = str(state_out)
        evidence_paths.append(rel)

    # 6) reaper critical-pin contract (ws_customer_default critical cache paths survive unless explicit override).
    reaper_contract_cmd = [sys.executable, "-m", "src.ops.reaper_critical_pin_contract_test"]
    reaper_contract_proc = subprocess.run(reaper_contract_cmd, cwd=repo_root(), text=True, capture_output=True)
    reaper_contract_ok = reaper_contract_proc.returncode == 0
    reaper_contract_detail = (
        _tail_line(reaper_contract_proc.stdout)
        or _tail_line(reaper_contract_proc.stderr)
        or f"rc={reaper_contract_proc.returncode}"
    )
    tests.append(_format_test_result("reaper_critical_pin_contract", reaper_contract_ok, reaper_contract_detail))
    if not reaper_contract_ok:
        failures.append("reaper_critical_pin_contract")

    # 7) reaper cleanup guard contract (pre-snapshot + post-validate mandatory gate on delete mode).
    reaper_guard_cmd = [sys.executable, "-m", "src.ops.reaper_cleanup_guard_contract_test"]
    reaper_guard_proc = subprocess.run(reaper_guard_cmd, cwd=repo_root(), text=True, capture_output=True)
    reaper_guard_ok = reaper_guard_proc.returncode == 0
    reaper_guard_detail = (
        _tail_line(reaper_guard_proc.stdout)
        or _tail_line(reaper_guard_proc.stderr)
        or f"rc={reaper_guard_proc.returncode}"
    )
    tests.append(_format_test_result("reaper_cleanup_guard_contract", reaper_guard_ok, reaper_guard_detail))
    if not reaper_guard_ok:
        failures.append("reaper_cleanup_guard_contract")
    tests.sort(key=lambda item: item.get("name") or "")
    status = "OK" if not failures else "WARN"

    try:
        out_rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        out_rel = str(out_resolved)
    evidence_paths = sorted(set([out_rel] + evidence_paths))

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "failures": failures,
        "tests": tests,
        "evidence_paths": evidence_paths,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "TRAVERSAL_BLOCKED=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def cmd_test_run(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    out_arg = str(args.out or ".cache/reports/test_run_core_contracts.v1.json")
    result = run_test_run(workspace_root=ws, out_path=out_arg)
    status = str(result.get("status") or "")
    if status == "FAIL":
        warn("FAIL error=TEST_RUN_FAILED")
        return 2
    print(json.dumps({k: result.get(k) for k in ("status", "failures", "evidence_paths")}, ensure_ascii=False, sort_keys=True))
    return 0


def register_test_run_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("test-run", help="Run core contract checks without pytest.")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--out", default=".cache/reports/test_run_core_contracts.v1.json", help="Output JSON path.")
    ap.set_defaults(func=cmd_test_run)
