from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(payload), encoding="utf-8")


def _write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_airunner_proof_bundle(*, workspace_root: Path) -> dict[str, Any]:
    baseline_rel = Path(".cache") / "reports" / "airunner_baseline.v1.json"
    run_rel = Path(".cache") / "reports" / "airunner_run.v1.json"
    deltas_rel = Path(".cache") / "reports" / "airunner_deltas.v1.json"
    tick1_rel = Path(".cache") / "reports" / "airunner_tick_1.v1.json"
    tick2_rel = Path(".cache") / "reports" / "airunner_tick_2.v1.json"
    proof_rel = Path(".cache") / "reports" / "github_ops_no_wait_proof.v2.json"
    seed_audit_rel = Path(".cache") / "reports" / "airunner_seed_audit.v1.json"

    missing: list[str] = []
    proof: dict[str, Any] = {}
    proof_path = workspace_root / proof_rel
    if proof_path.exists():
        try:
            proof = _load_json(proof_path)
        except Exception:
            missing.append(str(proof_rel))
    else:
        missing.append(str(proof_rel))

    seed_path = workspace_root / seed_audit_rel
    if not seed_path.exists():
        missing.append(str(seed_audit_rel))

    tick1_ops = proof.get("tick1", {}).get("ops_called", []) if isinstance(proof.get("tick1"), dict) else []
    tick2_ops = proof.get("tick2", {}).get("ops_called", []) if isinstance(proof.get("tick2"), dict) else []
    deltas = proof.get("deltas") if isinstance(proof.get("deltas"), dict) else {}

    bundle = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "baseline_path": str(baseline_rel),
        "run_path": str(run_rel),
        "deltas_path": str(deltas_rel),
        "tick1_path": str(tick1_rel),
        "tick2_path": str(tick2_rel),
        "proof_path": str(proof_rel),
        "seed_audit_path": str(seed_audit_rel),
        "poll_only_observed": bool(proof.get("poll_only_observed")),
        "start_only_observed": bool(proof.get("start_only_observed")),
        "tick1_ops": [str(op) for op in tick1_ops if isinstance(op, str)],
        "tick2_ops": [str(op) for op in tick2_ops if isinstance(op, str)],
        "jobs_polled_delta": int(deltas.get("jobs_polled_delta", 0) or 0),
        "jobs_started_delta": int(deltas.get("jobs_started_delta", 0) or 0),
        "intake_new_items_delta": int(deltas.get("intake_new_items_delta", 0) or 0),
        "suppressed_delta": int(deltas.get("suppressed_delta", 0) or 0),
    }

    out_rel = Path(".cache") / "reports" / "airunner_proof_bundle.v1.json"
    md_rel = Path(".cache") / "reports" / "airunner_proof_bundle.v1.md"
    _write_json(workspace_root / out_rel, bundle)
    _write_md(
        workspace_root / md_rel,
        [
            "# Airrunner Proof Bundle",
            f"- generated_at: {_now_iso()}",
            f"- poll_only_observed: {bundle['poll_only_observed']}",
            f"- start_only_observed: {bundle['start_only_observed']}",
            f"- jobs_polled_delta: {bundle['jobs_polled_delta']}",
            f"- jobs_started_delta: {bundle['jobs_started_delta']}",
            f"- intake_new_items_delta: {bundle['intake_new_items_delta']}",
            f"- suppressed_delta: {bundle['suppressed_delta']}",
        ],
    )

    return {
        "status": "OK" if not missing else "IDLE",
        "report_path": str(out_rel),
        "report_md_path": str(md_rel),
        "missing_inputs": sorted(set(missing)),
        "error_code": "MISSING_INPUTS" if missing else None,
    }
