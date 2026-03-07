from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _delegate_local_runner(args: list[str]) -> int:
    cmd = [sys.executable, "-m", "src.orchestrator.local_runner", *args]
    proc = subprocess.run(cmd, text=False)
    return int(proc.returncode)


def _delegate_ops_manage(args: list[str]) -> int:
    from src.ops import manage

    return int(manage.main(args))


def _sdk_demo() -> int:
    from src.sdk import OrchestratorClient

    client = OrchestratorClient(workspace=".", evidence_dir="evidence")
    res = client.run(
        intent="urn:core:summary:summary_to_file",
        tenant_id="TENANT-LOCAL",
        dry_run=True,
        side_effect_policy="none",
    )
    # Keep deterministic, no secrets.
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") == "OK" else 2


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("Expected true|false")


def _truncate(s: str, limit: int = 300) -> str:
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 3)] + "..."


def _map_side_effect_policy(value: str) -> str:
    v = str(value).strip().lower()
    if v in {"none"}:
        return "none"
    if v in {"draft", "pr"}:
        return "draft"
    if v in {"allow", "merge", "deploy"}:
        return "allow"
    raise ValueError(f"Unknown side_effect_policy: {value}")


def _cmd_run_shortcut(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="orchestrator run")
    ap.add_argument("--intent", required=True)
    ap.add_argument("--tenant", required=True, dest="tenant_id")
    ap.add_argument("--dry-run", type=_parse_bool, default=True)
    ap.add_argument("--risk-score", type=float, default=0.1)
    ap.add_argument(
        "--side-effect-policy",
        default="none",
        help="none|draft|pr|merge|deploy (mapped to envelope side_effect_policy: none|draft|allow)",
    )
    ap.add_argument("--output-path")
    ap.add_argument("--input-path")
    ap.add_argument("--session-id", default="default")
    ap.add_argument("--use-openai", type=_parse_bool, default=False)
    ap.add_argument("--force-new-run", type=_parse_bool, default=False)
    ap.add_argument("--idempotency-key")
    ap.add_argument("--budget-max-tokens", type=int)
    ap.add_argument("--budget-max-time-ms", type=int)
    ap.add_argument("--budget-max-attempts", type=int)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--evidence", default="evidence")
    args = ap.parse_args(argv)

    if args.risk_score < 0.0 or args.risk_score > 1.0:
        payload = {
            "status": "FAIL",
            "error": "risk_score must be between 0 and 1",
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        side_effect_policy = _map_side_effect_policy(args.side_effect_policy)
    except Exception as e:
        payload = {"status": "FAIL", "error": _truncate(str(e))}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    workspace = Path(str(args.workspace)).resolve()
    evidence_dir = Path(str(args.evidence))
    evidence_dir = (workspace / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir.resolve()

    request_id = f"REQ-{uuid4().hex}"
    tenant_id = str(args.tenant_id)
    intent = str(args.intent)
    idempotency_key = str(args.idempotency_key) if args.idempotency_key else f"{tenant_id}:{intent}:{uuid4().hex}"

    envelope: dict[str, Any] = {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "intent": intent,
        "risk_score": float(args.risk_score),
        "dry_run": bool(args.dry_run),
        "side_effect_policy": side_effect_policy,
        "idempotency_key": idempotency_key,
    }

    context: dict[str, Any] = {}
    if args.input_path:
        context["input_path"] = str(args.input_path)
    if args.output_path:
        context["output_path"] = str(args.output_path)
    if args.session_id:
        context["session_id"] = str(args.session_id)
    if bool(args.use_openai):
        context["use_openai"] = True
    if context:
        envelope["context"] = context

    budget: dict[str, Any] = {}
    if args.budget_max_tokens is not None:
        budget["max_tokens"] = int(args.budget_max_tokens)
    if args.budget_max_time_ms is not None:
        budget["max_time_ms"] = int(args.budget_max_time_ms)
    if args.budget_max_attempts is not None:
        budget["max_attempts"] = int(args.budget_max_attempts)
    if budget:
        envelope["budget"] = budget

    req_dir = workspace / ".cache" / "cli_requests"
    req_dir.mkdir(parents=True, exist_ok=True)
    envelope_path = req_dir / f"{request_id}.json"
    envelope_path.write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "-m",
        "src.orchestrator.local_runner",
        "--envelope",
        str(envelope_path),
        "--workspace",
        str(workspace),
        "--out",
        str(evidence_dir),
    ]
    if bool(args.force_new_run):
        cmd.extend(["--force-new-run", "true"])

    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    runner_obj: dict[str, Any] | None = None
    try:
        runner_obj = json.loads((proc.stdout or "").strip() or "{}")
    except Exception:
        runner_obj = None

    run_id = runner_obj.get("run_id") if isinstance(runner_obj, dict) else None
    if not isinstance(run_id, str) or not run_id:
        # Fail without dumping the whole stdout/stderr.
        msg = (proc.stderr or proc.stdout or "").strip() or "local_runner failed"
        payload = {"status": "FAIL", "error": _truncate(msg)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    run_dir = evidence_dir / run_id
    summary_path = run_dir / "summary.json"
    summary: dict[str, Any] | None = None
    if summary_path.exists():
        try:
            summary_raw = json.loads(summary_path.read_text(encoding="utf-8"))
            summary = summary_raw if isinstance(summary_raw, dict) else None
        except Exception:
            summary = None

    def rel(p: Path) -> str:
        try:
            return p.resolve().relative_to(workspace.resolve()).as_posix()
        except Exception:
            return p.as_posix()

    out_payload: dict[str, Any] = {
        "status": "OK" if proc.returncode == 0 else "FAIL",
        "run_id": run_id,
        "evidence_path": rel(run_dir),
        "result_state": (summary.get("result_state") if isinstance(summary, dict) else runner_obj.get("result_state")),
        "policy_violation_code": (
            summary.get("policy_violation_code") if isinstance(summary, dict) else runner_obj.get("policy_violation_code")
        ),
    }
    if isinstance(summary, dict) and "replay_of" in summary:
        out_payload["replay_of"] = summary.get("replay_of")
    elif isinstance(runner_obj, dict) and "replay_of" in runner_obj:
        out_payload["replay_of"] = runner_obj.get("replay_of")

    print(json.dumps(out_payload, ensure_ascii=False, sort_keys=True))
    return 0 if proc.returncode == 0 else 2


def _cmd_run(args: list[str]) -> int:
    if "--intent" in args:
        return _cmd_run_shortcut(args)

    # Backwards compatible passthrough:
    return _delegate_local_runner(args)


def _read_version_from_pyproject() -> str | None:
    root = _repo_root()
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        import tomllib
    except Exception:
        return None

    try:
        with pyproject.open("rb") as f:
            obj = tomllib.load(f)
    except Exception:
        return None

    project = obj.get("project") if isinstance(obj, dict) else None
    if not isinstance(project, dict):
        return None
    v = project.get("version")
    return v if isinstance(v, str) and v else None


def _resolve_version() -> str:
    installed_version: str | None = None
    try:
        from importlib.metadata import PackageNotFoundError, version

        installed_version = version("autonomous-orchestrator")
    except PackageNotFoundError:
        pass
    except Exception:
        pass

    pyproject_version = _read_version_from_pyproject()

    # Prefer the source tree version when running from the repo checkout.
    # (Local egg-info metadata can lag behind pyproject.toml during development.)
    if pyproject_version and installed_version and installed_version != pyproject_version:
        return pyproject_version

    return installed_version or pyproject_version or "unknown"


def _build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    examples = """Examples:
  # Policy review report (dry-run; no file write)
  python -m src.cli run --intent urn:core:docs:policy_review --tenant TENANT-LOCAL --dry-run true --output-path policy_review.md

  # DLQ triage report (dry-run; no file write)
  python -m src.cli run --intent urn:core:ops:dlq_triage --tenant TENANT-LOCAL --dry-run true --output-path dlq_triage.md

  # Ops: list recent runs + DLQ
  python -m src.cli ops runs --limit 5
  python -m src.cli ops dlq --limit 5

  # Integration check (OpenAI ping; policy+secret gated)
  python -m src.cli ops openai-ping --timeout-ms 5000
"""

    ap = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="autonomous-orchestrator: minimal CLI wrapper (local runner + ops).",
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )

    sub = ap.add_subparsers(dest="command")

    run_epilog = """Modes:
  1) Shortcut mode (recommended):
     python -m src.cli run --intent <URN> --tenant <TENANT_ID> [options]

  2) Passthrough mode (advanced):
     python -m src.cli run <local_runner args...>
     (forwards args to: python -m src.orchestrator.local_runner)

Notes:
  - --side-effect-policy values: none | draft | pr | merge | deploy
  - merge/deploy are intentionally blocked for real side effects (reserved); use none/draft/pr for now.
  - dry_run=true always records plans only (no writes, no PRs).
  - See: docs/OPERATIONS/side-effects.md
"""

    ap_run = sub.add_parser(
        "run",
        help="Run workflows locally (shortcut or passthrough).",
        description="Run workflows locally using the deterministic local runner.",
        epilog=run_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    ap_ops = sub.add_parser(
        "ops",
        help="Operational commands (delegates to src.ops.manage).",
        description="Ops-friendly management CLI (runs/dlq/suspends/policy-check/etc.).",
    )

    sub.add_parser("sdk-demo", help="Run a minimal SDK demo (deterministic).")

    return (ap, ap_run)


def main(argv: list[str] | None = None) -> int:
    ap, ap_run = _build_parser()
    raw_argv = sys.argv[1:] if argv is None else argv
    ns, passthrough = ap.parse_known_args(raw_argv)

    if bool(ns.version):
        print(_resolve_version())
        return 0

    cmd = getattr(ns, "command", None)
    if cmd is None:
        ap.print_help()
        return 0

    if cmd == "run":
        if not passthrough:
            ap_run.print_help()
            return 0
        return _cmd_run([str(x) for x in passthrough])

    if cmd == "ops":
        if not passthrough:
            return _delegate_ops_manage(["--help"])
        return _delegate_ops_manage([str(x) for x in passthrough])

    if cmd == "sdk-demo":
        return _sdk_demo()

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
