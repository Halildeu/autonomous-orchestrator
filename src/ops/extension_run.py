from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_EXTENSION_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


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
        "",
        "Write allowlist:",
    ]
    for rel in report["write_roots_allowlist"]:
        md_lines.append(f"- {rel}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    report["report_path"] = str(out_json.relative_to(workspace_root))
    report["summary_path"] = str(out_md.relative_to(workspace_root))
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
        ]
        evidence_lines = [
            f"extension_run={res.get('report_path')}",
            f"summary={res.get('summary_path')}",
        ]
        actions_line = "no_actions"
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
