from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_work_intake_disabled(ws: Path) -> None:
    _write_json(
        ws / "policies" / "policy_work_intake.v2.json",
        {
            "version": "v2",
            "enabled": False,
        },
    )


def _strip_generated(payload: dict) -> dict:
    cleaned = dict(payload)
    cleaned.pop("generated_at", None)
    return cleaned


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.auto_loop import run_auto_loop

    ws = repo_root / ".cache" / "ws_auto_loop_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    _write_work_intake_disabled(ws)

    first = run_auto_loop(workspace_root=ws, budget_seconds=5, chat=False)
    if first.get("status") != "IDLE":
        raise SystemExit("auto_loop_contract_test failed: expected IDLE status")
    counts = first.get("counts") if isinstance(first.get("counts"), dict) else {}
    if any(int(counts.get(k, 0) or 0) > 0 for k in ["decision_pending_before", "decision_pending_after", "bulk_applied_count", "selected_count"]):
        raise SystemExit("auto_loop_contract_test failed: expected zero counts")

    second = run_auto_loop(workspace_root=ws, budget_seconds=5, chat=False)
    if json.dumps(_strip_generated(first), sort_keys=True) != json.dumps(_strip_generated(second), sort_keys=True):
        raise SystemExit("auto_loop_contract_test failed: output not deterministic")


if __name__ == "__main__":
    main()
