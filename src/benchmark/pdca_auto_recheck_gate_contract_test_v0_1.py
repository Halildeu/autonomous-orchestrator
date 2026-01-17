from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import _load_pdca_cursor_signal, _maybe_auto_pdca_recheck

    ws = repo_root / ".cache" / "ws_pdca_auto_recheck_gate_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now_iso = _now_iso()
    old_iso = "2000-01-01T00:00:00Z"

    _write_json(
        ws / ".cache" / "index" / "gap_register.v1.json",
        {"version": "v1", "generated_at": now_iso, "gaps": []},
    )
    _write_json(
        ws / ".cache" / "index" / "pdca_cursor.v1.json",
        {"version": "v1", "generated_at": old_iso, "last_run_at": old_iso, "hashes": {}},
    )

    # Budget gate: hard_exceeded > 0 must block auto recheck.
    _maybe_auto_pdca_recheck(
        core_root=repo_root,
        workspace_root=ws,
        script_budget_signal={"hard_exceeded": 1, "report_path": "in-memory"},
        dry_run=False,
    )
    blocked_signal = _load_pdca_cursor_signal(workspace_root=ws)
    if blocked_signal.get("last_updated") != old_iso:
        raise SystemExit(
            "pdca_auto_recheck_gate_contract_test failed: expected budget gate to block cursor update"
        )

    # Allowed path: stale cursor + budget OK triggers recheck, clearing staleness.
    _maybe_auto_pdca_recheck(
        core_root=repo_root,
        workspace_root=ws,
        script_budget_signal={"hard_exceeded": 0, "report_path": "in-memory"},
        dry_run=False,
    )
    updated_signal = _load_pdca_cursor_signal(workspace_root=ws)
    if updated_signal.get("last_updated") == old_iso:
        raise SystemExit("pdca_auto_recheck_gate_contract_test failed: expected cursor last_updated to change")
    stale_hours = float(updated_signal.get("stale_hours", 0.0) or 0.0)
    if stale_hours >= 1.0:
        raise SystemExit(
            "pdca_auto_recheck_gate_contract_test failed: "
            f"expected stale_hours < 1.0 after recheck, got {stale_hours}"
        )

    print(json.dumps({"status": "OK", "blocked": blocked_signal, "updated": updated_signal}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

