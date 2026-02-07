from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _parse_csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in str(value).split(",")]
    return sorted({part for part in parts if part})


def _emit_airunner_chat(payload: dict[str, Any], *, title: str) -> None:
    evidence = []
    for key in ("report_path", "report_md_path", "heartbeat_path", "jobs_index_path", "watchdog_state_path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            evidence.append(value)
    evidence = sorted(set(evidence))

    print("PREVIEW:")  # AUTOPILOT CHAT
    print(f"- {title} program-led run")
    print("RESULT:")
    print(f"- status={payload.get('status')}")
    if payload.get("error_code"):
        print(f"- error_code={payload.get('error_code')}")
    print("EVIDENCE:")
    if evidence:
        for path in evidence:
            print(f"- {path}")
    else:
        print("- (none)")
    print("ACTIONS:")
    print("- Check work-intake + system-status if status WARN/FAIL")
    print("NEXT:")
    print("- Devam et / Durumu göster / Duraklat")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _emit_airunner_proof_bundle_chat(payload: dict[str, Any]) -> None:
    evidence = []
    for key in ("report_path", "report_md_path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            evidence.append(value)
    evidence = sorted(set(evidence))

    missing = payload.get("missing_inputs")
    missing_list = sorted([str(item) for item in missing if isinstance(item, str)]) if isinstance(missing, list) else []

    print("PREVIEW:")  # AUTOPILOT CHAT
    print("- airrunner-proof-bundle program-led run")
    print("RESULT:")
    print(f"- status={payload.get('status')}")
    if payload.get("error_code"):
        print(f"- error_code={payload.get('error_code')}")
    print("EVIDENCE:")
    if evidence:
        for path in evidence:
            print(f"- {path}")
    else:
        print("- (none)")
    if missing_list:
        print("ACTIONS:")
        print("- Missing inputs detected; run airunner-baseline, airunner-run, and seed/proof as needed")
    else:
        print("ACTIONS:")
        print("- Verify proof bundle via UI snapshot if needed")
    print("NEXT:")
    if missing_list:
        print("- Run seed/proof inputs / Durumu göster / Duraklat")
    else:
        print("- Devam et / Durumu göster / Duraklat")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _emit_planner_show_plan_chat(payload: dict[str, Any]) -> None:
    evidence = []
    for key in ("plan_path", "summary_path", "selection_path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            evidence.append(value)
    evidence = sorted(set(evidence))

    print("PREVIEW:")  # AUTOPILOT CHAT
    print("- planner-show-plan program-led run")
    print("RESULT:")
    print(f"- status={payload.get('status')}")
    if payload.get("error_code"):
        print(f"- error_code={payload.get('error_code')}")
    if payload.get("plan_id"):
        print(f"- plan_id={payload.get('plan_id')}")
    print("EVIDENCE:")
    if evidence:
        for path in evidence:
            print(f"- {path}")
    else:
        print("- (none)")
    print("ACTIONS:")
    print("- Apply plan or continue to next step")
    print("NEXT:")
    print("- Devam et / Durumu göster / Duraklat")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _resolve_workspace_root(args: argparse.Namespace) -> Path | None:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return None
    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return None
    return ws
