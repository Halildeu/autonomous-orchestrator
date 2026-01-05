from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


def _sha_id(seed: str) -> str:
    return sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ReadinessPolicy:
    enabled: bool
    output_path: str
    required_files: list[str]
    required_policies: list[str]
    integration_flags: list[str]
    on_fail: str


def _load_policy(core_root: Path, workspace_root: Path) -> ReadinessPolicy:
    defaults = ReadinessPolicy(
        enabled=True,
        output_path=".cache/ops/autopilot_readiness.v1.json",
        required_files=[
            ".cache/index/catalog.v1.json",
            ".cache/index/formats.v1.json",
            ".cache/index/run_index.v1.json",
            ".cache/index/dlq_index.v1.json",
            ".cache/learning/public_candidates.v1.json",
            ".cache/learning/advisor_suggestions.v1.json",
            ".cache/sessions/default/session_context.v1.json",
        ],
        required_policies=[
            "policies/policy_security.v1.json",
            "policies/policy_secrets.v1.json",
            "policies/policy_quality.v1.json",
            "policies/policy_harvest.v1.json",
            "policies/policy_advisor.v1.json",
        ],
        integration_flags=["ORCH_INTEGRATION_MODE"],
        on_fail="warn",
    )

    ws_policy = workspace_root / "policies" / "policy_autopilot_readiness.v1.json"
    core_policy = core_root / "policies" / "policy_autopilot_readiness.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    output_path = obj.get("output_path", defaults.output_path)
    if not isinstance(output_path, str) or not output_path.strip():
        output_path = defaults.output_path

    req_files = obj.get("required_files", defaults.required_files)
    if not isinstance(req_files, list):
        req_files = defaults.required_files
    req_files = [str(x) for x in req_files if isinstance(x, str) and x.strip()]

    req_policies = obj.get("required_policies", defaults.required_policies)
    if not isinstance(req_policies, list):
        req_policies = defaults.required_policies
    req_policies = [str(x) for x in req_policies if isinstance(x, str) and x.strip()]

    flags = obj.get("integration_flags", defaults.integration_flags)
    if not isinstance(flags, list):
        flags = defaults.integration_flags
    flags = [str(x) for x in flags if isinstance(x, str) and x.strip()]

    on_fail = obj.get("on_fail", defaults.on_fail)
    if on_fail not in {"warn", "block"}:
        on_fail = defaults.on_fail

    return ReadinessPolicy(
        enabled=enabled,
        output_path=str(output_path),
        required_files=req_files or defaults.required_files,
        required_policies=req_policies or defaults.required_policies,
        integration_flags=flags or defaults.integration_flags,
        on_fail=str(on_fail),
    )


def _resolve_workspace_path(workspace_root: Path, rel: str) -> Path | None:
    path = (workspace_root / rel).resolve()
    return path if _is_within_root(path, workspace_root) else None


def _validate_output(core_root: Path, obj: dict[str, Any]) -> list[str]:
    schema_path = core_root / "schemas" / "autopilot-readiness.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING"]
    try:
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(obj)
        return []
    except Exception as e:
        return [str(e)[:200]]


def build_readiness_report(*, workspace_root: Path, core_root: Path) -> dict[str, Any]:
    policy = _load_policy(core_root, workspace_root)

    missing: list[dict[str, Any]] = []
    notes: list[str] = []
    checks: list[dict[str, Any]] = []

    # Workspace required files
    missing_ws: list[str] = []
    invalid_ws: list[str] = []
    required_ws_paths: list[str] = []
    for rel in policy.required_files:
        resolved = _resolve_workspace_path(workspace_root, rel)
        if resolved is None:
            missing_ws.append(rel)
            missing.append({"path": rel, "category": "WORKSPACE"})
            required_ws_paths.append(rel)
            continue
        required_ws_paths.append(str(resolved.relative_to(workspace_root)))
        if not resolved.exists():
            missing_ws.append(str(resolved.relative_to(workspace_root)))
            missing.append({"path": str(resolved.relative_to(workspace_root)), "category": "WORKSPACE"})
            continue
        if resolved.suffix == ".json":
            try:
                _load_json(resolved)
            except Exception:
                invalid_ws.append(str(resolved.relative_to(workspace_root)))

    ws_status = "OK"
    if missing_ws:
        ws_status = "FAIL"
    elif invalid_ws:
        ws_status = "WARN"
    details_ws = f"missing={len(missing_ws)} invalid_json={len(invalid_ws)}"
    checks.append(
        {
            "id": "CHECK_WORKSPACE_FILES",
            "category": "WORKSPACE",
            "status": ws_status,
            "details": details_ws,
            "paths": required_ws_paths,
        }
    )
    if missing_ws:
        notes.append("WORKSPACE_FILES_MISSING")
    if invalid_ws:
        notes.append("WORKSPACE_JSON_INVALID")

    # Core policy files
    missing_pol: list[str] = []
    required_pol_paths: list[str] = []
    for rel in policy.required_policies:
        p = (core_root / rel).resolve()
        required_pol_paths.append(str(Path(rel)))
        if not p.exists():
            missing_pol.append(str(Path(rel)))
            missing.append({"path": str(Path(rel)), "category": "POLICY"})

    pol_status = "OK" if not missing_pol else "FAIL"
    details_pol = f"missing={len(missing_pol)}"
    checks.append(
        {
            "id": "CHECK_POLICY_FILES",
            "category": "POLICY",
            "status": pol_status,
            "details": details_pol,
            "paths": required_pol_paths,
        }
    )
    if missing_pol:
        notes.append("POLICY_FILES_MISSING")

    # Integration flags
    flagged: list[str] = []
    for flag in policy.integration_flags:
        if os.environ.get(flag) == "1":
            flagged.append(flag)
    integ_status = "OK" if not flagged else "WARN"
    details_integ = "enabled=" + ",".join(flagged) if flagged else "disabled"
    checks.append(
        {
            "id": "CHECK_INTEGRATION_FLAGS",
            "category": "INTEGRATION",
            "status": integ_status,
            "details": details_integ,
            "paths": policy.integration_flags,
        }
    )
    if flagged:
        notes.append("INTEGRATION_ENABLED")

    result_status = "READY"
    if any(c.get("status") in {"WARN", "FAIL"} for c in checks):
        result_status = "NOT_READY"

    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "status": result_status,
        "checks": checks,
        "missing": missing,
        "notes": notes,
    }
    return report


def run_readiness_for_workspace(
    *,
    workspace_root: Path,
    core_root: Path,
    dry_run: bool,
    output_override: str | None = None,
) -> dict[str, Any]:
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        return {"status": "OK", "note": "POLICY_DISABLED", "on_fail": policy.on_fail}

    output_path = output_override if isinstance(output_override, str) and output_override.strip() else policy.output_path
    out_path = _resolve_workspace_path(workspace_root, output_path)
    if out_path is None:
        return {"status": "FAIL", "error_code": "OUTPUT_PATH_INVALID", "on_fail": policy.on_fail}

    report = build_readiness_report(workspace_root=workspace_root, core_root=core_root)
    errors = _validate_output(core_root, report)
    if errors:
        return {"status": "FAIL", "error_code": "SCHEMA_INVALID", "errors": errors[:10], "out": str(out_path), "on_fail": policy.on_fail}

    payload = _dump_json(report)
    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "result_status": report.get("status"),
            "bytes_estimate": len(payload.encode("utf-8")),
            "out": str(out_path),
            "on_fail": policy.on_fail,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8")
    return {
        "status": "OK",
        "result_status": report.get("status"),
        "out": str(out_path),
        "on_fail": policy.on_fail,
    }


def action_from_readiness_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    result_status = result.get("result_status")
    out_path = result.get("out") if isinstance(result.get("out"), str) else None
    severity = "INFO" if status in {"OK", "WOULD_WRITE"} else "WARN"
    title = "Autopilot readiness report generated"
    if status == "FAIL":
        title = "Autopilot readiness report failed"
    action_id = _sha_id(f"AUTOPILOT_READINESS|{status}|{out_path}")
    msg = f"Autopilot readiness: {result_status}" if result_status else "Autopilot readiness report generated"
    return {
        "action_id": action_id,
        "severity": severity,
        "kind": "AUTOPILOT_READINESS" if status in {"OK", "WOULD_WRITE"} else "AUTOPILOT_READINESS_FAIL",
        "milestone_hint": "M8",
        "source": "AUTOPILOT_READINESS",
        "title": title,
        "details": {
            "status": status,
            "result_status": result_status,
            "out": out_path,
            "error_code": result.get("error_code"),
        },
        "message": msg,
        "resolved": status in {"OK", "WOULD_WRITE"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.autopilot.readiness_report", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        dry_run = _parse_bool(str(args.dry_run))
    except Exception:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_DRY_RUN"}, ensure_ascii=False, sort_keys=True))
        return 2

    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        print(json.dumps({"status": "OK", "note": "POLICY_DISABLED"}, ensure_ascii=False, sort_keys=True))
        return 0

    res = run_readiness_for_workspace(
        workspace_root=workspace_root,
        core_root=core_root,
        dry_run=dry_run,
        output_override=str(args.out) if args.out else None,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
