from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SAFE_EXTENSION_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(v) for v in value if isinstance(v, str) and v})


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _validate_extension_id(extension_id: str) -> bool:
    return bool(extension_id and SAFE_EXTENSION_ID.match(extension_id))


def _load_policy(core_root: Path) -> tuple[dict[str, Any] | None, str | None]:
    policy_path = core_root / "policies" / "policy_extension_isolation.v1.json"
    if not policy_path.exists():
        return (None, "policy_missing")
    try:
        obj = _load_json(policy_path)
    except Exception:
        return (None, "policy_invalid_json")
    if not isinstance(obj, dict):
        return (None, "policy_invalid_object")
    return (obj, None)


def _load_manifest_for_extension(core_root: Path, extension_id: str) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    ext_root = core_root / "extensions"
    if not ext_root.exists():
        return (None, None, "manifest_root_missing")
    for manifest_path in sorted(ext_root.rglob("extension.manifest.v1.json")):
        try:
            obj = _load_json(manifest_path)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        manifest_ext_id = str(obj.get("extension_id") or "").strip()
        if manifest_ext_id == extension_id:
            return (obj, manifest_path, None)
    return (None, None, "manifest_not_found")


def _normalize_path_for_report(path_value: Any, workspace_root: Path, core_root: Path) -> str:
    if not isinstance(path_value, str) or not path_value:
        return ""
    p = Path(path_value)
    if not p.is_absolute():
        return path_value
    try:
        return str(p.relative_to(workspace_root).as_posix())
    except Exception:
        pass
    try:
        return str(p.relative_to(core_root).as_posix())
    except Exception:
        return str(p.as_posix())


def _capture_callable(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, str]:
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        payload = func(*args, **kwargs)
    traces = []
    out = stdout_buf.getvalue().strip()
    err = stderr_buf.getvalue().strip()
    if out:
        traces.append(out)
    if err:
        traces.append(err)
    return (payload, "\n".join(traces))


def _parse_last_json_line(raw: str) -> dict[str, Any] | None:
    lines = [ln.strip() for ln in str(raw or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        if not ln.startswith("{") or not ln.endswith("}"):
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _run_manage_json_command(core_root: Path, args: list[str]) -> tuple[dict[str, Any], int, str]:
    cmd = [sys.executable, "-m", "src.ops.manage"] + args
    proc = subprocess.run(cmd, cwd=core_root, text=True, capture_output=True)
    merged_output = "\n".join(
        [chunk for chunk in [str(proc.stdout or "").strip(), str(proc.stderr or "").strip()] if chunk]
    )
    payload = _parse_last_json_line(merged_output)
    if not isinstance(payload, dict):
        payload = {"status": "FAIL", "error_code": "SINGLE_GATE_JSON_OUTPUT_MISSING"}
    if proc.returncode != 0 and not isinstance(payload.get("error_code"), str):
        payload["error_code"] = f"SINGLE_GATE_EXEC_FAILED_RC{proc.returncode}"
    return (payload, int(proc.returncode), merged_output)


def _collect_single_gate_outputs(payload: dict[str, Any], workspace_root: Path, core_root: Path) -> dict[str, str]:
    keys: list[str] = []
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, str) or not value:
            continue
        if key.endswith("_path") or key in {
            "out_json",
            "out_md",
            "report_path",
            "report_md_path",
            "contract_json",
            "contract_md",
            "semgrep_json",
            "semgrep_stdout",
            "outdir",
            "jobs_index_path",
            "job_report_path",
            "deploy_plan_path",
            "deploy_report_path",
            "release_plan_path",
            "release_manifest_path",
            "release_notes_path",
            "portfolio_status_path",
            "system_status_path",
            "work_intake_path",
        }:
            keys.append(key)
    out: dict[str, str] = {}
    for key in sorted(set(keys)):
        rel = _normalize_path_for_report(payload.get(key), workspace_root, core_root)
        if rel:
            out[key] = rel
    return out


def _gate_enforcement_check(
    *,
    core_root: Path,
    workspace_root: Path,
    extension_id: str,
    mode: str,
) -> dict[str, Any]:
    from src.ops.commands.enforcement_check import run_enforcement_check

    profile = "strict" if mode == "strict" else "default"
    outdir = workspace_root / ".cache" / "reports" / "enforcement_check" / extension_id
    ruleset = core_root / "extensions" / "PRJ-ENFORCEMENT-PACK" / "semgrep" / "rules"
    intake_id = f"EXT-RUN-{extension_id}"

    gate_result, _ = _capture_callable(
        run_enforcement_check,
        outdir=outdir,
        ruleset=ruleset,
        profile=profile,
        baseline="git:HEAD~1",
        intake_id=intake_id,
        chat=False,
    )
    if not isinstance(gate_result, dict):
        return {"gate": "enforcement-check", "status": "FAIL", "error_code": "SINGLE_GATE_EMPTY_RESULT"}
    payload = dict(gate_result)
    payload.setdefault("gate", "enforcement-check")
    payload.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return payload


def _gate_deploy_check(*, workspace_root: Path) -> dict[str, Any]:
    from src.extensions.prj_deploy.deploy_jobs import run_deploy_check

    gate_result, _ = _capture_callable(run_deploy_check, workspace_root=workspace_root, chat=False)
    if not isinstance(gate_result, dict):
        return {"gate": "deploy-check", "status": "FAIL", "error_code": "SINGLE_GATE_EMPTY_RESULT"}
    payload = dict(gate_result)
    payload.setdefault("gate", "deploy-check")
    payload.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return payload


def _gate_release_check(*, workspace_root: Path) -> dict[str, Any]:
    from src.prj_release_automation.release_engine import run_release_check

    gate_result, _ = _capture_callable(run_release_check, workspace_root=workspace_root, channel=None, chat=False)
    if not isinstance(gate_result, dict):
        return {"gate": "release-check", "status": "FAIL", "error_code": "SINGLE_GATE_EMPTY_RESULT"}
    payload = dict(gate_result)
    payload.setdefault("gate", "release-check")
    payload.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return payload


def _gate_github_ops_check(*, workspace_root: Path) -> dict[str, Any]:
    from src.prj_github_ops.github_ops import run_github_ops_check

    gate_result, _ = _capture_callable(run_github_ops_check, workspace_root=workspace_root, chat=False)
    if not isinstance(gate_result, dict):
        return {"gate": "github-ops-check", "status": "FAIL", "error_code": "SINGLE_GATE_EMPTY_RESULT"}
    payload = dict(gate_result)
    payload.setdefault("gate", "github-ops-check")
    payload.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return payload


def _gate_search_check(*, workspace_root: Path) -> dict[str, Any]:
    from src.extensions.prj_search.search_check import run_search_check

    gate_result, _ = _capture_callable(
        run_search_check,
        workspace_root=workspace_root,
        scope="ssot",
        query="policy",
        mode="keyword",
        chat=False,
    )
    if not isinstance(gate_result, dict):
        return {"gate": "search-check", "status": "FAIL", "error_code": "SINGLE_GATE_EMPTY_RESULT"}
    payload = dict(gate_result)
    payload.setdefault("gate", "search-check")
    payload.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return payload


def _gate_cockpit_healthcheck(*, workspace_root: Path) -> dict[str, Any]:
    from src.ops.cockpit_healthcheck import run_cockpit_healthcheck

    gate_result, _ = _capture_callable(run_cockpit_healthcheck, workspace_root=workspace_root, port=8787)
    if not isinstance(gate_result, dict):
        return {"gate": "cockpit-healthcheck", "status": "FAIL", "error_code": "SINGLE_GATE_EMPTY_RESULT"}
    payload = dict(gate_result)
    payload.setdefault("gate", "cockpit-healthcheck")
    payload.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return payload


def _gate_script_budget(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    report_path = workspace_root / ".cache" / "script_budget" / "report.json"
    cmd = [sys.executable, str(core_root / "ci" / "check_script_budget.py"), "--out", str(report_path)]
    proc = subprocess.run(cmd, cwd=core_root, text=True, capture_output=True)

    report_obj: dict[str, Any] = {}
    if report_path.exists():
        try:
            loaded = _load_json(report_path)
            if isinstance(loaded, dict):
                report_obj = loaded
        except Exception:
            report_obj = {}

    status = str(report_obj.get("status") or ("FAIL" if proc.returncode != 0 else "UNKNOWN"))
    payload: dict[str, Any] = {
        "gate": "script-budget",
        "status": status,
        "report_path": str(report_path),
    }
    if isinstance(report_obj.get("hard_exceeded"), list):
        payload["hard_exceeded"] = len(report_obj.get("hard_exceeded", []))
    if isinstance(report_obj.get("soft_exceeded"), list):
        payload["soft_exceeded"] = len(report_obj.get("soft_exceeded", []))
    return payload


def _gate_work_intake_check(*, core_root: Path, workspace_root: Path, mode: str) -> dict[str, Any]:
    payload, rc, _ = _run_manage_json_command(
        core_root,
        [
            "work-intake-check",
            "--workspace-root",
            str(workspace_root),
            "--mode",
            "strict" if mode == "strict" else "report",
            "--chat",
            "false",
            "--detail",
            "false",
        ],
    )
    payload.setdefault("gate", "work-intake-check")
    payload.setdefault("status", "FAIL" if rc != 0 else "UNKNOWN")
    return payload


def _gate_planner_show_plan(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    payload, rc, _ = _run_manage_json_command(
        core_root,
        [
            "planner-show-plan",
            "--workspace-root",
            str(workspace_root),
            "--latest",
            "true",
            "--chat",
            "false",
        ],
    )
    payload.setdefault("gate", "planner-show-plan")
    payload.setdefault("status", "FAIL" if rc != 0 else "UNKNOWN")
    if rc != 0 and not isinstance(payload.get("error_code"), str):
        payload["error_code"] = "SINGLE_GATE_DISPATCH_UNWIRED"
    return payload


def _dispatch_single_gate_for_extension(
    *,
    core_root: Path,
    workspace_root: Path,
    extension_id: str,
    gate_name: str,
    mode: str,
) -> tuple[dict[str, Any] | None, str | None]:
    gate = str(gate_name or "").strip()
    if not gate:
        return (None, "SINGLE_GATE_EMPTY")

    handlers: dict[str, Callable[[], dict[str, Any]]] = {
        "enforcement-check": lambda: _gate_enforcement_check(
            core_root=core_root,
            workspace_root=workspace_root,
            extension_id=extension_id,
            mode=mode,
        ),
        "deploy-check": lambda: _gate_deploy_check(workspace_root=workspace_root),
        "release-check": lambda: _gate_release_check(workspace_root=workspace_root),
        "github-ops-check": lambda: _gate_github_ops_check(workspace_root=workspace_root),
        "search-check": lambda: _gate_search_check(workspace_root=workspace_root),
        "cockpit-healthcheck": lambda: _gate_cockpit_healthcheck(workspace_root=workspace_root),
        "cockpit-serve": lambda: _gate_cockpit_healthcheck(workspace_root=workspace_root),
        "script-budget": lambda: _gate_script_budget(core_root=core_root, workspace_root=workspace_root),
        "work-intake-check": lambda: _gate_work_intake_check(core_root=core_root, workspace_root=workspace_root, mode=mode),
        "planner-show-plan": lambda: _gate_planner_show_plan(core_root=core_root, workspace_root=workspace_root),
    }
    handler = handlers.get(gate)
    if handler is None:
        return (None, "SINGLE_GATE_DISPATCH_UNWIRED")

    try:
        gate_result = handler()
    except Exception:
        return (None, "SINGLE_GATE_EXEC_EXCEPTION")

    if not isinstance(gate_result, dict):
        return (None, "SINGLE_GATE_EMPTY_RESULT")
    gate_result = dict(gate_result)
    gate_result.setdefault("gate", gate)
    gate_result.setdefault("status", str(gate_result.get("status") or "UNKNOWN"))
    return (gate_result, None)


def build_extension_run_report(
    *,
    workspace_root: Path,
    extension_id: str,
    mode: str,
) -> dict[str, Any]:
    core_root = _repo_root()
    policy, policy_err = _load_policy(core_root)
    notes: list[str] = []
    error_code = None
    status = "OK"

    if policy_err:
        return {
            "status": "IDLE",
            "error_code": policy_err,
            "notes": [policy_err],
        }

    if not _validate_extension_id(extension_id):
        return {
            "status": "FAIL",
            "error_code": "INVALID_EXTENSION_ID",
            "notes": ["invalid_extension_id"],
        }

    extension_root_rel = Path(str(policy.get("extension_workspace_root", ".cache/extensions"))) / extension_id
    extension_root = workspace_root / extension_root_rel
    extension_root.mkdir(parents=True, exist_ok=True)

    manifest_obj, manifest_path_abs, manifest_err = _load_manifest_for_extension(core_root, extension_id)
    manifest_path = ""
    ops_entrypoints: list[str] = []
    ops_single_gate: list[str] = []
    selected_single_gate = ""
    single_gate_dispatched = False
    single_gate_status = "IDLE"
    single_gate_error_code = ""
    single_gate_outputs: dict[str, str] = {}
    actions_executed: list[str] = []

    if isinstance(manifest_obj, dict) and isinstance(manifest_path_abs, Path):
        try:
            manifest_path = str(manifest_path_abs.relative_to(core_root).as_posix())
        except Exception:
            manifest_path = str(manifest_path_abs.as_posix())
        entrypoints = manifest_obj.get("entrypoints") if isinstance(manifest_obj.get("entrypoints"), dict) else {}
        ops_entrypoints = _list_str(entrypoints.get("ops"))
        ops_single_gate = _list_str(entrypoints.get("ops_single_gate"))
        if ops_single_gate:
            selected_single_gate = ops_single_gate[0]
    elif manifest_err:
        notes.append(manifest_err)

    write_roots = policy.get("write_roots_allowlist") if isinstance(policy.get("write_roots_allowlist"), list) else []
    read_roots = policy.get("read_roots_allowlist") if isinstance(policy.get("read_roots_allowlist"), list) else []
    write_roots = [str(p) for p in write_roots if isinstance(p, str) and p]
    read_roots = [str(p) for p in read_roots if isinstance(p, str) and p]

    invalid_allowlist: list[str] = []
    for rel in write_roots:
        if Path(rel).is_absolute() or not _is_under_root(workspace_root / rel, workspace_root):
            invalid_allowlist.append(rel)

    if invalid_allowlist:
        status = "FAIL"
        error_code = "ALLOWLIST_INVALID"
        notes.append("invalid_write_allowlist")

    network_allowed = bool(policy.get("network_allowed", False))
    if network_allowed:
        status = "FAIL"
        error_code = error_code or "NETWORK_NOT_ALLOWED"
        notes.append("network_not_allowed")

    if selected_single_gate:
        actions_executed.append(selected_single_gate)
        gate_payload, gate_err = _dispatch_single_gate_for_extension(
            core_root=core_root,
            workspace_root=workspace_root,
            extension_id=extension_id,
            gate_name=selected_single_gate,
            mode=mode,
        )
        if gate_err:
            single_gate_error_code = gate_err
            single_gate_status = "FAIL"
            notes.append(f"single_gate_dispatch_error={gate_err}")
        elif isinstance(gate_payload, dict):
            single_gate_dispatched = True
            single_gate_status = str(gate_payload.get("status") or "UNKNOWN")
            single_gate_outputs = _collect_single_gate_outputs(gate_payload, workspace_root, core_root)
        else:
            single_gate_error_code = "SINGLE_GATE_EMPTY_RESULT"
            single_gate_status = "FAIL"
            notes.append("single_gate_empty_result")

        if single_gate_error_code:
            status = "FAIL" if mode == "strict" else "WARN"
            error_code = error_code or single_gate_error_code
        elif single_gate_status in {"FAIL", "BLOCKED"}:
            status = "FAIL" if mode == "strict" else "WARN"
            error_code = error_code or "SINGLE_GATE_NOT_OK"
        elif single_gate_status in {"WARN", "UNKNOWN", "SKIPPED"} and status == "OK":
            status = "WARN"
    elif ops_single_gate:
        notes.append("single_gate_not_selected")


    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "extension_id": extension_id,
        "mode": mode,
        "status": status,
        "error_code": error_code,
        "extension_workspace_root": str(extension_root_rel.as_posix()),
        "write_roots_allowlist": sorted(set(write_roots + [str(extension_root_rel.as_posix())])),
        "read_roots_allowlist": sorted(set(read_roots)),
        "manifest_path": manifest_path,
        "entrypoints": {
            "ops": ops_entrypoints,
            "ops_single_gate": ops_single_gate,
        },
        "selected_single_gate": selected_single_gate,
        "single_gate_dispatched": single_gate_dispatched,
        "single_gate_status": single_gate_status,
        "single_gate_outputs": single_gate_outputs,
        "single_gate_error_code": single_gate_error_code,
        "actions_executed": actions_executed,
        "network_allowed": False,
        "notes": notes,
    }

    out_json = workspace_root / ".cache" / "reports" / f"extension_run.{extension_id}.v1.json"
    out_md = workspace_root / ".cache" / "reports" / f"extension_run.{extension_id}.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(_dump_json(report), encoding="utf-8")

    md_lines = [
        "# Extension Run (v1)",
        "",
        f"Extension: {extension_id}",
        f"Status: {status}",
        f"Mode: {mode}",
        f"Workspace root: {workspace_root}",
        f"Extension root: {extension_root_rel.as_posix()}",
        f"Network allowed: false",
        f"Manifest path: {manifest_path or '-'}",
        f"Single gate: {selected_single_gate or '-'}",
        f"Single gate dispatched: {'true' if single_gate_dispatched else 'false'}",
        f"Single gate status: {single_gate_status}",
        "",
        "Write allowlist:",
    ]
    for rel in report["write_roots_allowlist"]:
        md_lines.append(f"- {rel}")
    if single_gate_outputs:
        md_lines.extend(["", "Single gate outputs:"])
        for key in sorted(single_gate_outputs):
            value = single_gate_outputs.get(key)
            if isinstance(value, str) and value:
                md_lines.append(f"- {key}: {value}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    report["report_path"] = str(out_json.relative_to(workspace_root))
    report["summary_path"] = str(out_md.relative_to(workspace_root))
    evidence_paths = [
        report["report_path"],
        report["summary_path"],
    ]
    evidence_paths.extend(single_gate_outputs.values())
    report["evidence_paths"] = sorted({p for p in evidence_paths if isinstance(p, str) and p})
    return report


def run_extension_run(*, workspace_root: Path, extension_id: str, mode: str, chat: bool) -> dict[str, Any]:
    res = build_extension_run_report(workspace_root=workspace_root, extension_id=extension_id, mode=mode)
    status = res.get("status") if isinstance(res, dict) else "WARN"

    if chat:
        preview_lines = [
            "PROGRAM-LED: extension-run; user_command=false",
            f"workspace_root={workspace_root}",
            f"extension_id={extension_id}",
            f"mode={mode}",
        ]
        result_lines = [
            f"status={status}",
            f"network_allowed={res.get('network_allowed', False)}",
            f"single_gate={res.get('selected_single_gate', '')}",
            f"single_gate_status={res.get('single_gate_status', 'IDLE')}",
        ]
        evidence_lines = [
            f"extension_run={res.get('report_path')}",
            f"summary={res.get('summary_path')}",
            f"single_gate_contract={res.get('single_gate_outputs', {}).get('contract_json', '')}",
        ]
        actions = res.get("actions_executed") if isinstance(res.get("actions_executed"), list) else []
        actions_line = "\n".join([str(a) for a in actions if isinstance(a, str) and a]) if actions else "no_actions"
        next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join([str(x) for x in result_lines if x]))
        print("EVIDENCE:")
        print("\n".join([str(x) for x in evidence_lines if x]))
        print("ACTIONS:")
        print(actions_line)
        print("NEXT:")
        print("\n".join(next_lines))
        print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(res, ensure_ascii=False, sort_keys=True))

    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.extension_run")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--extension-id", required=True)
    ap.add_argument("--mode", default="report", help="report|strict (default: report)")
    ap.add_argument("--chat", default="false", help="true|false (default: false)")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    extension_id = str(args.extension_id).strip()
    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_MODE"}, ensure_ascii=False, sort_keys=True))
        return 2

    chat = str(args.chat).strip().lower() in {"1", "true", "yes", "y", "on"}

    res = run_extension_run(workspace_root=workspace_root, extension_id=extension_id, mode=mode, chat=chat)
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
