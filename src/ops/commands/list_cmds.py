from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.evidence.integrity_verify import MANIFEST_NAME, verify_run_dir
from src.ops.commands.common import load_json_file, parse_iso8601_ts, print_table, repo_root, warn


def cmd_runs(args: argparse.Namespace) -> int:
    root = repo_root()
    evidence_dir = root / "evidence"
    limit = max(0, int(args.limit))

    items: list[dict[str, Any]] = []
    skipped = 0

    if evidence_dir.exists():
        for summary_path in sorted(evidence_dir.rglob("summary.json")):
            if summary_path.name != "summary.json":
                continue
            run_dir = summary_path.parent
            if not (run_dir / "request.json").exists():
                continue

            summary, err = load_json_file(summary_path)
            if not isinstance(summary, dict):
                skipped += 1
                continue

            run_id = summary.get("run_id") if isinstance(summary.get("run_id"), str) else run_dir.name
            result_state = summary.get("result_state") if isinstance(summary.get("result_state"), str) else summary.get("status")
            if not isinstance(result_state, str):
                result_state = ""

            intent = summary.get("intent") if isinstance(summary.get("intent"), str) else ""
            tenant_id = summary.get("tenant_id") if isinstance(summary.get("tenant_id"), str) else ""
            workflow_id = summary.get("workflow_id") if isinstance(summary.get("workflow_id"), str) else ""
            finished_at = summary.get("finished_at") if isinstance(summary.get("finished_at"), str) else ""
            started_at = summary.get("started_at") if isinstance(summary.get("started_at"), str) else ""

            replay_of = summary.get("replay_of") if isinstance(summary.get("replay_of"), str) else None
            replay_warnings = summary.get("replay_warnings") if isinstance(summary.get("replay_warnings"), list) else []
            replay_short = (replay_of[:6] + "..") if replay_of else ""

            sort_ts = parse_iso8601_ts(finished_at) or parse_iso8601_ts(started_at)

            items.append(
                {
                    "run_id": run_id,
                    "result_state": result_state,
                    "intent": intent,
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "finished_at": finished_at,
                    "started_at": started_at,
                    "run_dir": run_dir,
                    "replay_of": replay_of,
                    "replay_warnings": replay_warnings,
                    "replay_short": replay_short,
                    "_sort_ts": sort_ts,
                }
            )

    items.sort(key=lambda x: (-float(x.get("_sort_ts", 0.0)), str(x.get("run_id", ""))))
    out = items[:limit] if limit else items

    def integrity_status(run_dir: Any) -> str:
        if not isinstance(run_dir, Path):
            return "NO_MANIFEST"
        if not (run_dir / MANIFEST_NAME).exists():
            return "NO_MANIFEST"
        try:
            payload = verify_run_dir(run_dir)
        except Exception:
            return "MISMATCH"
        status = payload.get("status")
        return status if status in {"OK", "MISSING", "MISMATCH"} else "MISMATCH"

    def provenance_info(run_dir: Any) -> tuple[str, str | None]:
        if not isinstance(run_dir, Path):
            return ("NO_PROV", None)
        p = run_dir / "provenance.v1.json"
        if not p.exists():
            return ("NO_PROV", None)
        obj, _ = load_json_file(p)
        if not isinstance(obj, dict):
            return ("NO_PROV", None)
        created_at = obj.get("created_at") if isinstance(obj.get("created_at"), str) else None
        return ("OK", created_at)

    if args.json:
        payload = [
            {
                "run_id": i.get("run_id"),
                "result_state": i.get("result_state"),
                "intent": i.get("intent"),
                "tenant_id": i.get("tenant_id"),
                "workflow_id": i.get("workflow_id"),
                "finished_at": i.get("finished_at"),
                "integrity": integrity_status(i.get("run_dir")),
                "provenance_status": provenance_info(i.get("run_dir"))[0],
                "provenance_created_at": provenance_info(i.get("run_dir"))[1],
                "replay_of": i.get("replay_of"),
                "replay_warnings": i.get("replay_warnings") if isinstance(i.get("replay_warnings"), list) else [],
            }
            for i in out
        ]
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        rows = [
            [
                str(i.get("run_id", "")),
                str(i.get("result_state", "")),
                str(i.get("intent", "")),
                str(i.get("tenant_id", "")),
                str(i.get("workflow_id", "")),
                str(i.get("finished_at", "")),
                str(integrity_status(i.get("run_dir"))),
                str(provenance_info(i.get("run_dir"))[0]),
                str(i.get("replay_short", "")),
            ]
            for i in out
        ]
        print_table(
            ["run_id", "result_state", "intent", "tenant_id", "workflow_id", "finished_at", "integrity", "prov", "replay"],
            rows,
        )
        if skipped:
            warn(f"WARN: runs skipped_invalid_json={skipped}")

    return 0


def cmd_dlq(args: argparse.Namespace) -> int:
    root = repo_root()
    dlq_dir = root / "dlq"
    limit = max(0, int(args.limit))

    if args.show:
        requested = Path(str(args.show)).name
        path = dlq_dir / requested
        if not path.exists():
            warn(f"ERROR: DLQ file not found: {requested}")
            return 2
        try:
            print(path.read_text(encoding="utf-8").rstrip("\n"))
            return 0
        except Exception as e:
            warn(f"ERROR: Failed to read DLQ file: {requested}: {e}")
            return 2

    items: list[dict[str, Any]] = []
    skipped = 0

    if dlq_dir.exists():
        for path in sorted(dlq_dir.glob("*.json"), reverse=True):
            obj, err = load_json_file(path)
            if not isinstance(obj, dict):
                skipped += 1
                continue
            env = obj.get("envelope") if isinstance(obj.get("envelope"), dict) else {}
            message = obj.get("message")
            if not isinstance(message, str):
                message = ""
            message_one_line = " ".join(message.split())
            items.append(
                {
                    "file": path.name,
                    "stage": obj.get("stage") if isinstance(obj.get("stage"), str) else "",
                    "error_code": obj.get("error_code") if isinstance(obj.get("error_code"), str) else "",
                    "message": message_one_line,
                    "request_id": env.get("request_id") if isinstance(env.get("request_id"), str) else "",
                    "tenant_id": env.get("tenant_id") if isinstance(env.get("tenant_id"), str) else "",
                    "intent": env.get("intent") if isinstance(env.get("intent"), str) else "",
                }
            )

    out = items[:limit] if limit else items
    rows = [
        [
            str(i.get("file", "")),
            str(i.get("stage", "")),
            str(i.get("error_code", "")),
            str(i.get("message", "")),
            str(i.get("request_id", "")),
            str(i.get("tenant_id", "")),
            str(i.get("intent", "")),
        ]
        for i in out
    ]
    print_table(["file", "stage", "error_code", "message", "request_id", "tenant_id", "intent"], rows)
    if skipped:
        warn(f"WARN: dlq skipped_invalid_json={skipped}")

    return 0


def cmd_suspends(args: argparse.Namespace) -> int:
    root = repo_root()
    evidence_dir = root / "evidence"
    limit = max(0, int(args.limit))

    items: list[dict[str, Any]] = []
    skipped_suspend = 0
    skipped_summary = 0

    if evidence_dir.exists():
        for suspend_path in sorted(evidence_dir.rglob("suspend.json")):
            if suspend_path.name != "suspend.json":
                continue
            run_dir = suspend_path.parent
            run_id = run_dir.name

            suspend, err = load_json_file(suspend_path)
            if not isinstance(suspend, dict):
                skipped_suspend += 1
                continue

            summary_path = run_dir / "summary.json"
            summary_ts = 0.0
            if summary_path.exists():
                summary, _ = load_json_file(summary_path)
                if isinstance(summary, dict):
                    finished_at = summary.get("finished_at") if isinstance(summary.get("finished_at"), str) else ""
                    started_at = summary.get("started_at") if isinstance(summary.get("started_at"), str) else ""
                    summary_ts = parse_iso8601_ts(finished_at) or parse_iso8601_ts(started_at)
                else:
                    skipped_summary += 1
            else:
                skipped_summary += 1

            run_id = suspend.get("run_id") if isinstance(suspend.get("run_id"), str) else run_id
            reason = suspend.get("reason") if isinstance(suspend.get("reason"), str) else ""
            risk_score = suspend.get("risk_score")
            threshold_used = suspend.get("threshold_used")
            next_action_hint = suspend.get("next_action_hint") if isinstance(suspend.get("next_action_hint"), str) else ""

            items.append(
                {
                    "run_id": run_id,
                    "reason": reason,
                    "risk_score": risk_score,
                    "threshold_used": threshold_used,
                    "next_action_hint": next_action_hint,
                    "_sort_ts": summary_ts,
                }
            )

    items.sort(key=lambda x: (-float(x.get("_sort_ts", 0.0)), str(x.get("run_id", ""))))
    out = items[:limit] if limit else items

    if args.json:
        payload = [
            {
                "run_id": i.get("run_id"),
                "reason": i.get("reason"),
                "risk_score": i.get("risk_score"),
                "threshold_used": i.get("threshold_used"),
                "next_action_hint": i.get("next_action_hint"),
            }
            for i in out
        ]
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        rows = [
            [
                str(i.get("run_id", "")),
                str(i.get("reason", "")),
                str(i.get("risk_score", "")),
                str(i.get("threshold_used", "")),
                str(i.get("next_action_hint", "")),
            ]
            for i in out
        ]
        print_table(["run_id", "reason", "risk_score", "threshold_used", "next_action_hint"], rows)
        if skipped_suspend:
            warn(f"WARN: suspends skipped_invalid_suspend_json={skipped_suspend}")
        if skipped_summary:
            warn(f"WARN: suspends skipped_missing_or_invalid_summary={skipped_summary}")

    return 0


def register_list_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_runs = parent.add_parser("runs", help="List evidence runs (summary.json).")
    ap_runs.add_argument("--limit", type=int, default=20)
    ap_runs.add_argument("--json", action="store_true")
    ap_runs.set_defaults(func=cmd_runs)

    ap_dlq = parent.add_parser("dlq", help="List DLQ items.")
    ap_dlq.add_argument("--limit", type=int, default=20)
    ap_dlq.add_argument("--show", help="Show a full DLQ JSON by filename.")
    ap_dlq.set_defaults(func=cmd_dlq)

    ap_susp = parent.add_parser("suspends", help="List SUSPENDED runs (suspend.json).")
    ap_susp.add_argument("--limit", type=int, default=20)
    ap_susp.add_argument("--json", action="store_true")
    ap_susp.set_defaults(func=cmd_suspends)
