from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class DebtPolicy:
    enabled: bool
    max_items: int
    outdir: str


def _load_debt_policy(core_root: Path, workspace_root: Path) -> DebtPolicy:
    defaults = DebtPolicy(enabled=False, max_items=3, outdir=".cache/debt_chg")
    ws_policy = workspace_root / "policies" / "policy_debt.v1.json"
    core_policy = core_root / "policies" / "policy_debt.v1.json"
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
    try:
        max_items = int(obj.get("max_items", defaults.max_items))
    except Exception:
        max_items = defaults.max_items
    outdir = obj.get("outdir", defaults.outdir)
    if not isinstance(outdir, str) or not outdir.strip():
        outdir = defaults.outdir
    return DebtPolicy(enabled=enabled, max_items=max(0, max_items), outdir=str(outdir))


def _schema_path(core_root: Path) -> Path:
    return core_root / "schemas" / "chg-debt.schema.json"


def _validate_chg(core_root: Path, chg: dict[str, Any]) -> list[str]:
    schema_path = _schema_path(core_root)
    if not schema_path.exists():
        return ["SCHEMA_MISSING"]
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(chg)
    return []


def _next_chg_id(outdir: Path) -> str:
    date_str = _now_date()
    existing = sorted(outdir.glob(f"CHG-{date_str}-*.json"))
    next_idx = 1
    for path in existing:
        stem = path.stem
        parts = stem.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            next_idx = max(next_idx, int(parts[-1]) + 1)
    return f"CHG-{date_str}-{next_idx:03d}"


def _system_status_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "system_status.v1.json"


def _advisor_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"


def _actions_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "roadmap_actions.v1.json"


def _actions_from_system_status(system_status: dict[str, Any]) -> list[dict[str, Any]]:
    sections = system_status.get("sections") if isinstance(system_status, dict) else {}
    actions = sections.get("actions") if isinstance(sections, dict) else None
    top = actions.get("top") if isinstance(actions, dict) else None
    return top if isinstance(top, list) else []


def _priority_candidates(
    *,
    system_status: dict[str, Any],
    advisor: dict[str, Any] | None,
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sections = system_status.get("sections") if isinstance(system_status, dict) else {}
    quality = sections.get("quality_gate") if isinstance(sections, dict) else None
    repo_hygiene = sections.get("repo_hygiene") if isinstance(sections, dict) else None

    if isinstance(quality, dict) and quality.get("status") in {"WARN", "FAIL"}:
        candidates.append(
            {
                "source": "QUALITY_GATE",
                "target_debt_kind": "QUALITY_GATE_WARN",
                "kind": "FORMAT_FIX",
                "note": "Quality gate warning detected; consider re-running the owning milestone or fixing format index generation.",
            }
        )

    if isinstance(repo_hygiene, dict):
        tracked = repo_hygiene.get("tracked_generated_files")
        if isinstance(tracked, int) and tracked > 0:
            candidates.append(
                {
                    "source": "REPO_HYGIENE",
                    "target_debt_kind": "REPO_HYGIENE",
                    "kind": "ADD_IGNORE",
                    "note": "Tracked generated files detected; add ignores or relocate to .cache/ (manual).",
                }
            )

    for act in actions:
        if not isinstance(act, dict):
            continue
        if act.get("kind") in {"MAINTAINABILITY_DEBT", "MAINTAINABILITY_BLOCKER"}:
            candidates.append(
                {
                    "source": "SCRIPT_BUDGET",
                    "target_debt_kind": "SCRIPT_BUDGET",
                    "kind": "REFACTOR_HINT",
                    "note": "Script budget soft limit exceeded; plan a refactor to split large modules.",
                }
            )
            break

    if isinstance(advisor, dict):
        suggestions = advisor.get("suggestions") if isinstance(advisor.get("suggestions"), list) else []
        for sug in suggestions:
            if not isinstance(sug, dict):
                continue
            if sug.get("kind") == "NEXT_MILESTONE":
                candidates.append(
                    {
                        "source": "ADVISOR",
                        "target_debt_kind": "PLACEHOLDER_MILESTONE",
                        "kind": "DOC_NOTE",
                        "note": f"Advisor suggests next milestone: {sug.get('title', 'NEXT_MILESTONE')}.",
                    }
                )
                break

    return candidates


def _action_template(chg_id: str, kind: str, note_text: str) -> dict[str, Any]:
    if kind == "ADD_IGNORE":
        rel = f"patches/.gitignore.patch"
    elif kind in {"REFACTOR_HINT", "FORMAT_FIX"}:
        rel = f"plans/{chg_id}.md"
    else:
        rel = f"notes/{chg_id}.md"
    return {
        "kind": kind,
        "file_relpath": rel,
        "note": {"text": note_text},
    }


def _build_chg(
    *,
    chg_id: str,
    source: str,
    target_debt_kind: str,
    workspace_root: str,
    action_kind: str,
    note_text: str,
) -> dict[str, Any]:
    return {
        "id": chg_id,
        "version": "v1",
        "source": source,
        "target_debt_kind": target_debt_kind,
        "workspace_root": workspace_root,
        "actions": [_action_template(chg_id, action_kind, note_text)],
        "safety": {"apply_scope": "INCUBATOR_ONLY", "destructive": False, "requires_review": True},
    }


def run_debt_drafter(
    *,
    workspace_root: Path,
    core_root: Path,
    outdir: Path,
    max_items: int,
) -> dict[str, Any]:
    system_status_path = _system_status_path(workspace_root)
    if not system_status_path.exists():
        return {"status": "WARN", "reason": "SYSTEM_STATUS_MISSING", "drafted": 0, "outdir": str(outdir)}

    system_status = _load_json(system_status_path)
    if not isinstance(system_status, dict):
        return {"status": "WARN", "reason": "SYSTEM_STATUS_INVALID", "drafted": 0, "outdir": str(outdir)}

    advisor_obj: dict[str, Any] | None = None
    advisor_path = _advisor_path(workspace_root)
    if advisor_path.exists():
        try:
            obj = _load_json(advisor_path)
            advisor_obj = obj if isinstance(obj, dict) else None
        except Exception:
            advisor_obj = None

    actions = []
    actions_path = _actions_path(workspace_root)
    if actions_path.exists():
        try:
            actions_obj = _load_json(actions_path)
            actions = actions_obj.get("actions") if isinstance(actions_obj, dict) else []
        except Exception:
            actions = []
    if not isinstance(actions, list):
        actions = []

    candidates = _priority_candidates(system_status=system_status, advisor=advisor_obj, actions=actions)
    if max_items > 0:
        candidates = candidates[:max_items]
    if not candidates:
        return {"status": "WARN", "reason": "NO_DEBT_FOUND", "drafted": 0, "outdir": str(outdir)}

    outdir.mkdir(parents=True, exist_ok=True)
    chg_files: list[str] = []
    for cand in candidates:
        chg_id = _next_chg_id(outdir)
        chg = _build_chg(
            chg_id=chg_id,
            source=str(cand.get("source")),
            target_debt_kind=str(cand.get("target_debt_kind")),
            workspace_root=str(workspace_root),
            action_kind=str(cand.get("kind")),
            note_text=str(cand.get("note")),
        )
        errors = _validate_chg(core_root, chg)
        if errors:
            return {"status": "FAIL", "error_code": "CHG_INVALID", "errors": errors[:3], "drafted": len(chg_files)}
        out_path = outdir / f"{chg_id}.json"
        out_path.write_text(_dump_json(chg), encoding="utf-8")
        chg_files.append(out_path.as_posix())

    return {
        "status": "OK",
        "drafted": len(chg_files),
        "outdir": str(outdir),
        "chg_files": chg_files,
    }


def action_from_debt_draft_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    status = str(result.get("status") or "FAIL")
    drafted = int(result.get("drafted") or 0)
    outdir = result.get("outdir") if isinstance(result.get("outdir"), str) else ""
    title = "Debt draft created" if status in {"OK", "WARN"} else "Debt draft failed"
    action_id = sha256(f"DEBT_DRAFT|{status}|{outdir}|{drafted}".encode("utf-8")).hexdigest()[:16]
    severity = "INFO" if status in {"OK", "WARN"} else "WARN"
    kind = "DEBT_DRAFTED" if status in {"OK", "WARN"} else "DEBT_DRAFT_FAIL"
    msg = f"Debt drafts: {drafted} in {outdir}" if outdir else f"Debt drafts: {drafted}"
    return {
        "action_id": action_id,
        "severity": severity,
        "kind": kind,
        "milestone_hint": "M0",
        "source": "DEBT_DRAFTER",
        "title": title,
        "details": {
            "status": status,
            "drafted": drafted,
            "outdir": outdir,
            "error_code": result.get("error_code"),
        },
        "message": msg,
        "resolved": status in {"OK", "WARN"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.debt_drafter", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--outdir", default=".cache/debt_chg")
    ap.add_argument("--max-items", default="5")
    args = ap.parse_args(argv)

    core_root = _repo_root()
    ws_root = Path(str(args.workspace_root)).resolve()
    if not ws_root.exists():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        max_items = max(0, int(args.max_items))
    except Exception:
        max_items = 5

    outdir = Path(str(args.outdir))
    if not outdir.is_absolute():
        outdir = (ws_root / outdir).resolve()

    res = run_debt_drafter(
        workspace_root=ws_root,
        core_root=core_root,
        outdir=outdir,
        max_items=max_items,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
