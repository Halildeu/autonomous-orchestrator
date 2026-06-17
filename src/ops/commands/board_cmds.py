from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.ops.board.models import BOARD_TITLE_DEFAULT, WORKSPACE_DEFAULT
from src.ops.board.reports import dump_json, write_report
from src.ops.board.rules import run_board_command
from src.ops.commands.common import repo_root, resolve_workspace_root_arg, warn
from src.shared.utils import write_json_atomic


def _workspace(args: argparse.Namespace) -> Path | None:
    root = repo_root()
    raw = str(getattr(args, "workspace_root", "") or WORKSPACE_DEFAULT)
    return resolve_workspace_root_arg(root, raw, prefer_customer_workspace=True)


def _run(command: str, args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    payload = run_board_command(command, args)
    out_value = str(getattr(args, "out", "") or "")
    if not out_value:
        out_value = f".cache/reports/{command.replace('-', '_')}.v1.json"
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_json(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _write_projection(*, workspace_root: Path, out_value: str, payload: dict) -> str:
    rel = Path(out_value)
    if rel.is_absolute():
        out_path = rel.resolve()
    else:
        out_path = (workspace_root / rel).resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def _run_projection(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.projection import build_projection_from_fixture

    wrapper, projection = build_projection_from_fixture(
        fixture_path=str(getattr(args, "fixture", "") or ""),
        mode=str(getattr(args, "mode", "report") or "report"),
    )
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_projection.v1.json")
    if projection is not None and out_value.lower() != "none" and wrapper.get("status") in {"OK", "WARN"}:
        try:
            wrapper["projection_path"] = _write_projection(workspace_root=ws, out_value=out_value, payload=projection)
        except Exception as exc:
            wrapper["status"] = "ERROR"
            wrapper.setdefault("blocked_reasons", []).append(f"projection write failed: {exc.__class__.__name__}")
    print(dump_json(wrapper))
    return 0 if wrapper.get("status") in {"OK", "WARN"} else 1


def _run_projection_live(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.live_projection import build_live_projection, dump_board_live_projection

    wrapper, projection = build_live_projection(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_projection_live.v1.json")
    if projection is not None and out_value.lower() != "none" and wrapper.get("status") in {"OK", "WARN"}:
        try:
            wrapper["projection_path"] = _write_projection(workspace_root=ws, out_value=out_value, payload=projection)
        except Exception as exc:
            wrapper["status"] = "ERROR"
            wrapper.setdefault("blocked_reasons", []).append(f"projection write failed: {exc.__class__.__name__}")
    print(dump_board_live_projection(wrapper))
    return 0 if wrapper.get("status") in {"OK", "WARN"} else 1


def _run_pr_merge(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.pr_merge import dump_pr_merge_report, run_pr_merge_command, write_pr_merge_report

    payload = run_pr_merge_command(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_pr_merge_evidence.v1.json")
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_pr_merge_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_pr_merge_report(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _run_board_sync(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.sync import dump_board_sync, run_board_sync, write_board_sync_report

    payload = run_board_sync(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_sync.v1.json")
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_board_sync_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_board_sync(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _run_board_live_probe(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.live_probe import dump_board_live_probe, run_board_live_probe, write_board_live_probe_report

    payload = run_board_live_probe(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_live_probe.v1.json")
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_board_live_probe_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_board_live_probe(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _run_board_setup(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.setup import dump_board_setup, run_board_setup, write_board_setup_report

    payload = run_board_setup(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_setup.v1.json")
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_board_setup_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_board_setup(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _run_board_auth_preflight(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.auth_preflight import (
        dump_board_auth_preflight,
        run_board_auth_preflight,
        write_board_auth_preflight_report,
    )

    payload = run_board_auth_preflight(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_auth_preflight.v1.json")
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_board_auth_preflight_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_board_auth_preflight(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _run_board_seed(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.seed import dump_board_seed, run_board_seed, write_board_seed_report

    payload = run_board_seed(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_seed.v1.json")
    if out_value.lower() != "none":
        try:
            payload["report_path"] = write_board_seed_report(workspace_root=ws, out_value=out_value, payload=payload)
        except Exception as exc:
            payload["status"] = "ERROR"
            payload.setdefault("blocked_reasons", []).append(f"report write failed: {exc.__class__.__name__}")
    print(dump_board_seed(payload))
    return 0 if payload.get("status") in {"OK", "WARN"} else 1


def _run_board_metadata_live(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2
    from src.ops.board.metadata import build_live_metadata, dump_board_metadata, write_board_metadata

    wrapper, metadata = build_live_metadata(args)
    out_value = str(getattr(args, "out", "") or ".cache/reports/board_metadata_live.v1.json")
    if metadata is not None and out_value.lower() != "none" and wrapper.get("status") in {"OK", "WARN"}:
        try:
            wrapper["metadata_path"] = write_board_metadata(workspace_root=ws, out_value=out_value, payload=metadata)
        except Exception as exc:
            wrapper["status"] = "ERROR"
            wrapper.setdefault("blocked_reasons", []).append(f"metadata write failed: {exc.__class__.__name__}")
    print(dump_board_metadata(wrapper))
    return 0 if wrapper.get("status") in {"OK", "WARN"} else 1


def _add_common(ap: argparse.ArgumentParser, *, fixture_required: bool = False) -> None:
    ap.add_argument("--workspace-root", default=WORKSPACE_DEFAULT)
    ap.add_argument("--repo", default="")
    ap.add_argument("--board-title", default=BOARD_TITLE_DEFAULT)
    ap.add_argument("--mode", choices=["report", "dry-run", "apply"], default="report")
    ap.add_argument("--out", default="")
    ap.add_argument("--gh-bin", default="gh")
    ap.add_argument("--apply-confirm", default="", help="Required explicit confirmation string for apply mode")
    ap.add_argument("--token-env", default="GITHUB_TOKEN", help="Token environment variable name for apply mode")
    ap.add_argument(
        "--fixture",
        default="",
        required=fixture_required,
        help="Local fixture JSON path for report/dry-run mode",
    )


def _cmd(command: str):
    def inner(args: argparse.Namespace) -> int:
        return _run(command, args)

    return inner


def register_board_subcommands(parent: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    ap_list = parent.add_parser("board-list", help="Report board-eligible work and board/body drift.")
    _add_common(ap_list)
    ap_list.set_defaults(func=_cmd("board-list"))

    ap_claim = parent.add_parser("board-claim", help="Plan a board issue claim.")
    _add_common(ap_claim)
    ap_claim.add_argument("--issue", type=int, required=True)
    ap_claim.add_argument("--session", required=True)
    ap_claim.add_argument("--agent", required=True)
    ap_claim.add_argument("--worktree", required=True)
    ap_claim.add_argument("--branch", required=True)
    ap_claim.add_argument("--ttl-seconds", type=int, default=3600)
    ap_claim.set_defaults(func=_cmd("board-claim"))

    ap_heartbeat = parent.add_parser("board-heartbeat", help="Plan an active board claim heartbeat.")
    _add_common(ap_heartbeat)
    ap_heartbeat.add_argument("--issue", type=int, required=True)
    ap_heartbeat.add_argument("--session", required=True)
    ap_heartbeat.add_argument("--ttl-seconds", type=int, default=3600)
    ap_heartbeat.set_defaults(func=_cmd("board-heartbeat"))

    ap_release = parent.add_parser("board-release", help="Plan a board issue claim release.")
    _add_common(ap_release)
    ap_release.add_argument("--issue", type=int, required=True)
    ap_release.add_argument("--session", required=True)
    ap_release.add_argument(
        "--reason",
        choices=["completed", "blocked", "lost-race", "manual-handoff", "stale-cleanup"],
        required=True,
    )
    ap_release.set_defaults(func=_cmd("board-release"))

    ap_verify = parent.add_parser("board-verify", help="Plan evidence attachment and Needs Verify transition.")
    _add_common(ap_verify)
    ap_verify.add_argument("--issue", type=int, required=True)
    ap_verify.add_argument("--evidence", required=True)
    ap_verify.add_argument(
        "--evidence-type",
        choices=["source", "desired-state", "runtime-live", "browser-user-path"],
        required=True,
    )
    ap_verify.set_defaults(func=_cmd("board-verify"))

    ap_backlog = parent.add_parser("board-backlog-add", help="Plan a curated board candidate.")
    _add_common(ap_backlog)
    ap_backlog.add_argument("--title", required=True)
    ap_backlog.add_argument("--kind", choices=["milestone", "gate", "risk", "issue", "umbrella"], required=True)
    ap_backlog.add_argument("--faz", required=True)
    ap_backlog.add_argument("--track", required=True)
    ap_backlog.add_argument("--priority", choices=["P0", "P1", "P2", "P3"], required=True)
    ap_backlog.add_argument("--ssot-ref", required=True)
    ap_backlog.add_argument("--next-action", required=True)
    ap_backlog.set_defaults(func=_cmd("board-backlog-add"))

    ap_projection = parent.add_parser("board-projection", help="Generate a board_projection.v1 report and summarize drift.")
    _add_common(ap_projection, fixture_required=True)
    ap_projection.set_defaults(func=_run_projection)

    ap_projection_live = parent.add_parser("board-projection-live", help="Generate a board_projection.v1 report from live GitHub issue and ProjectV2 inventory.")
    _add_common(ap_projection_live)
    ap_projection_live.add_argument("--project-owner", default="", help="GitHub Project owner login. Defaults to repo owner.")
    ap_projection_live.add_argument("--project-number", default="", help="Target GitHub ProjectV2 number.")
    ap_projection_live.set_defaults(func=_run_projection_live)

    ap_pr_merge = parent.add_parser("board-pr-merge", help="Process merged PR Tracked by evidence for board issues.")
    _add_common(ap_pr_merge)
    ap_pr_merge.add_argument("--event", required=True, help="GitHub pull_request event JSON path")
    ap_pr_merge.add_argument("--issue-fixture", default="", help="Fixture with issue metadata for tests or dry-run")
    ap_pr_merge.add_argument("--run-url", default="", help="Workflow run URL to include in evidence")
    ap_pr_merge.set_defaults(func=_run_pr_merge)

    ap_sync = parent.add_parser("board-sync", help="Operator-bound board projection sync apply.")
    _add_common(ap_sync)
    ap_sync.add_argument("--projection", required=True, help="board_projection.v1 JSON path")
    ap_sync.add_argument("--metadata", required=True, help="operator-provided ProjectV2 metadata map JSON path")
    ap_sync.add_argument("--accepted-digest", default="", help="Accepted projection digest value")
    ap_sync.add_argument("--target-board-id", default="", help="Explicit target ProjectV2 board id")
    ap_sync.set_defaults(func=_run_board_sync)

    ap_probe = parent.add_parser("board-live-probe", help="Read-only GitHub ProjectV2 acceptance probe.")
    _add_common(ap_probe)
    ap_probe.add_argument("--project-owner", default="", help="GitHub Project owner login. Defaults to repo owner.")
    ap_probe.add_argument("--project-number", default="", help="Optional GitHub Project number to probe.")
    ap_probe.add_argument("--limit", type=int, default=30, help="Maximum projects to list while resolving target.")
    ap_probe.set_defaults(func=_run_board_live_probe)

    ap_setup = parent.add_parser("board-setup", help="Plan or gated-apply GitHub ProjectV2 board setup.")
    _add_common(ap_setup)
    ap_setup.add_argument("--project-owner", default="", help="GitHub Project owner login. Defaults to repo owner.")
    ap_setup.add_argument("--project-number", default="", help="Optional existing GitHub Project number to reconcile.")
    ap_setup.add_argument("--accepted-digest", default="", help="Accepted board setup dry-run digest required for apply mode.")
    ap_setup.add_argument("--link-repo", action="store_true", help="Plan/apply repository link after ProjectV2 setup.")
    ap_setup.set_defaults(func=_run_board_setup)

    ap_auth = parent.add_parser("board-auth-preflight", help="Report token/auth readiness for live board operations.")
    _add_common(ap_auth)
    ap_auth.add_argument(
        "--allow-keyring-auth",
        action="store_true",
        help="Allow gh keyring auth probing when token env is missing. Default avoids keyring access.",
    )
    ap_auth.add_argument(
        "--gh-timeout-seconds",
        type=float,
        default=20.0,
        help="Timeout for read-only gh auth status preflight calls.",
    )
    ap_auth.set_defaults(func=_run_board_auth_preflight)

    ap_seed = parent.add_parser("board-seed", help="Seed governed GitHub issues and ProjectV2 items through a digest-gated live apply.")
    _add_common(ap_seed)
    ap_seed.add_argument("--seed", required=True, help="board_seed.v1 JSON path")
    ap_seed.add_argument("--project-owner", default="", help="GitHub Project owner login. Defaults to repo owner.")
    ap_seed.add_argument("--project-number", default="", help="Target GitHub ProjectV2 number.")
    ap_seed.add_argument("--project-id", default="", help="Target GitHub ProjectV2 node id for item field edits.")
    ap_seed.add_argument("--accepted-digest", default="", help="Accepted board seed digest required for apply mode.")
    ap_seed.set_defaults(func=_run_board_seed)

    ap_metadata = parent.add_parser("board-metadata-live", help="Generate a live ProjectV2 metadata map for board-sync.")
    _add_common(ap_metadata)
    ap_metadata.add_argument("--project-owner", default="", help="GitHub Project owner login. Defaults to repo owner.")
    ap_metadata.add_argument("--project-number", default="", help="Target GitHub ProjectV2 number.")
    ap_metadata.add_argument("--project-id", default="", help="Target GitHub ProjectV2 node id.")
    ap_metadata.set_defaults(func=_run_board_metadata_live)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_board_subcommands(sub)
    args = parser.parse_args()
    sys.exit(args.func(args))
