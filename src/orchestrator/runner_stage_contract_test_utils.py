from __future__ import annotations

import io
import json
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.orchestrator.runner_execute import run_envelope
from src.orchestrator.runner_inputs import ReplayContext

_WORKSPACE_DIRS = (
    "schemas",
    "policies",
    "orchestrator",
    "workflows",
    "registry",
    "governor",
    "fixtures",
)

_RESULT_KEYS = (
    "exit_code",
    "summary_status",
    "summary_result_state",
    "summary_reason",
    "summary_policy_violation_code",
    "summary_budget_hit",
    "summary_quota_hit",
    "dlq_stage",
    "dlq_error_code",
    "stdout_status",
)

STAGE_SCENARIO_IDS: dict[str, tuple[str, ...]] = {
    "validate": ("schema_missing_intent", "budget_schema_invalid"),
    "governor": ("governor_quarantined_intent", "governor_concurrency_lock"),
    "routing_workflow": ("unknown_intent_blocked", "strategy_invalid_routes_type", "workflow_invalid_structure"),
    "idempotency": ("idempotent_hit_second_run",),
    "quota_autonomy": ("quota_runs_exceeded",),
    "execute_finalize": ("completed_low_risk", "suspended_high_risk", "budget_tokens_exceeded"),
}


def all_scenario_ids() -> tuple[str, ...]:
    ordered: list[str] = []
    for ids in STAGE_SCENARIO_IDS.values():
        for scenario_id in ids:
            if scenario_id not in ordered:
                ordered.append(scenario_id)
    return tuple(ordered)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _snapshot_path() -> Path:
    return Path(__file__).with_name("runner_execute_behavior_freeze_snapshots.v1.json")


def _latest_json(paths: list[Path]) -> dict[str, Any] | None:
    if not paths:
        return None
    latest = sorted(paths, key=lambda p: (p.stat().st_mtime_ns, p.name))[-1]
    return json.loads(latest.read_text(encoding="utf-8"))


def _clone_workspace(*, root: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in _WORKSPACE_DIRS:
        shutil.copytree(root / rel, workspace / rel)


def _apply_mutations(*, scenario_id: str, envelope: dict[str, Any], workspace: Path) -> dict[str, Any]:
    mutated = dict(envelope)
    if scenario_id == "schema_missing_intent":
        mutated.pop("intent", None)
    elif scenario_id == "budget_schema_invalid":
        budget = mutated.get("budget") if isinstance(mutated.get("budget"), dict) else {}
        budget = dict(budget)
        budget["max_tokens"] = "oops"
        mutated["budget"] = budget
    elif scenario_id == "unknown_intent_blocked":
        mutated["intent"] = "urn:unknown:intent"
    elif scenario_id == "governor_quarantined_intent":
        governor_path = workspace / "governor" / "health_brain.v1.json"
        governor = json.loads(governor_path.read_text(encoding="utf-8"))
        quarantine = governor.get("quarantine") if isinstance(governor.get("quarantine"), dict) else {}
        intents = quarantine.get("intents") if isinstance(quarantine.get("intents"), list) else []
        intents = [x for x in intents if isinstance(x, str)]
        intents.append(str(mutated.get("intent", "")))
        governor["quarantine"] = {"intents": intents, "workflows": []}
        governor_path.write_text(json.dumps(governor, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    elif scenario_id == "governor_concurrency_lock":
        lock_path = workspace / ".cache" / "governor_lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("lock\n", encoding="utf-8")
    elif scenario_id == "strategy_invalid_routes_type":
        strategy_path = workspace / "orchestrator" / "strategy_table.v1.json"
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        strategy["routes"] = {}
        strategy_path.write_text(json.dumps(strategy, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    elif scenario_id == "workflow_invalid_structure":
        workflow_path = workspace / "workflows" / "wf_core.v1.json"
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow["steps"] = []
        workflow_path.write_text(json.dumps(workflow, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    elif scenario_id == "quota_runs_exceeded":
        quota_policy_path = workspace / "policies" / "policy_quota.v1.json"
        quota_policy = json.loads(quota_policy_path.read_text(encoding="utf-8"))
        quota_policy["default"] = {"max_runs_per_day": 1, "max_est_tokens_per_day": 10_000_000}
        quota_policy["overrides"] = {"TENANT-LOCAL": {"max_runs_per_day": 1, "max_est_tokens_per_day": 10_000_000}}
        quota_policy_path.write_text(
            json.dumps(quota_policy, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

        date_key = datetime.now(timezone.utc).date().isoformat()
        quota_store = {date_key: {"TENANT-LOCAL": {"runs_used": 1, "est_tokens_used": 0}}}
        quota_store_path = workspace / ".cache" / "tenant_quota_store.v1.json"
        quota_store_path.parent.mkdir(parents=True, exist_ok=True)
        quota_store_path.write_text(
            json.dumps(quota_store, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    return mutated


def _run_scenario(*, root: Path, scenario: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="runner-freeze-") as td:
        workspace = Path(td) / "ws"
        _clone_workspace(root=root, workspace=workspace)

        fixture_name = str(scenario.get("fixture", "")).strip()
        fixture_path = root / "fixtures" / "envelopes" / fixture_name
        envelope = json.loads(fixture_path.read_text(encoding="utf-8"))
        scenario_id = str(scenario.get("id", "")).strip()
        envelope = _apply_mutations(scenario_id=scenario_id, envelope=envelope, workspace=workspace)

        envelope_dir = workspace / "fixtures" / "envelopes"
        envelope_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = envelope_dir / f"{scenario_id}.json"
        envelope_path.write_text(json.dumps(envelope, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        replay_ctx = ReplayContext(
            replay_of=None,
            replay_provenance=None,
            replay_warnings=[],
            replay_force_new_run=False,
            force_new_run=False,
        )

        repeat_runs_raw = scenario.get("repeat_runs", 1)
        try:
            repeat_runs = int(repeat_runs_raw)
        except Exception:
            repeat_runs = 1
        if repeat_runs < 1:
            repeat_runs = 1

        exit_code = 0
        stdout_status: str | None = None
        for idx in range(repeat_runs):
            sink_out = io.StringIO()
            sink_err = io.StringIO()
            try:
                with redirect_stdout(sink_out), redirect_stderr(sink_err):
                    run_envelope(
                        envelope=envelope,
                        envelope_path=envelope_path,
                        workspace=workspace,
                        out_dir=workspace / "evidence",
                        replay_ctx=replay_ctx,
                    )
            except SystemExit as exc:
                code = exc.code
                exit_code = int(code) if isinstance(code, int) else 1

            if idx == repeat_runs - 1 and repeat_runs > 1:
                out_text = sink_out.getvalue().strip()
                if out_text:
                    try:
                        out_obj = json.loads(out_text)
                    except Exception:
                        out_obj = None
                    if isinstance(out_obj, dict):
                        raw_status = out_obj.get("status")
                        stdout_status = raw_status if isinstance(raw_status, str) else None

        summary_obj = _latest_json(list((workspace / "evidence").glob("*/summary.json")))
        dlq_obj = _latest_json(list((workspace / "dlq").glob("*.json")))

        return {
            "exit_code": exit_code,
            "summary_status": summary_obj.get("status") if isinstance(summary_obj, dict) else None,
            "summary_result_state": summary_obj.get("result_state") if isinstance(summary_obj, dict) else None,
            "summary_reason": summary_obj.get("reason") if isinstance(summary_obj, dict) else None,
            "summary_policy_violation_code": (
                summary_obj.get("policy_violation_code") if isinstance(summary_obj, dict) else None
            ),
            "summary_budget_hit": summary_obj.get("budget_hit") if isinstance(summary_obj, dict) else None,
            "summary_quota_hit": summary_obj.get("quota_hit") if isinstance(summary_obj, dict) else None,
            "dlq_stage": dlq_obj.get("stage") if isinstance(dlq_obj, dict) else None,
            "dlq_error_code": dlq_obj.get("error_code") if isinstance(dlq_obj, dict) else None,
            "stdout_status": stdout_status,
        }


def _load_snapshot_scenarios() -> list[dict[str, Any]]:
    snapshot = json.loads(_snapshot_path().read_text(encoding="utf-8"))
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), list) else []
    if not scenarios:
        raise SystemExit("runner_stage_contract_test_utils failed: snapshot scenarios missing")
    typed: list[dict[str, Any]] = []
    for item in scenarios:
        if isinstance(item, dict):
            typed.append(item)
    return typed


def run_contract_test(*, test_name: str, scenario_ids: tuple[str, ...]) -> None:
    root = _repo_root()
    scenarios = _load_snapshot_scenarios()
    wanted = set(scenario_ids)
    selected = [sc for sc in scenarios if str(sc.get("id", "")) in wanted]

    missing = sorted(wanted.difference({str(sc.get("id", "")) for sc in selected}))
    if missing:
        raise SystemExit(f"{test_name} failed: missing_scenarios={json.dumps(missing, ensure_ascii=True)}")

    failures: list[dict[str, Any]] = []
    for sc in selected:
        expected = sc.get("expected") if isinstance(sc.get("expected"), dict) else {}
        actual = _run_scenario(root=root, scenario=sc)
        mismatch = {}
        for key in _RESULT_KEYS:
            if expected.get(key) != actual.get(key):
                mismatch[key] = {"expected": expected.get(key), "actual": actual.get(key)}
        if mismatch:
            failures.append({"id": sc.get("id"), "mismatch": mismatch})

    if failures:
        raise SystemExit(test_name + " failed: " + json.dumps(failures, ensure_ascii=True, sort_keys=True))

    print(f"{test_name} ok=true scenarios={len(selected)}")

