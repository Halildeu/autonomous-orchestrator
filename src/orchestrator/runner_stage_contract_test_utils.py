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

_STAGE_SNAPSHOT_FILES: dict[str, str] = {
    "validate": "runner_stage_validate.snapshots.v1.json",
    "governor": "runner_stage_governor.snapshots.v1.json",
    "routing_workflow": "runner_stage_routing_workflow.snapshots.v1.json",
    "idempotency": "runner_stage_idempotency.snapshots.v1.json",
    "quota_autonomy": "runner_stage_quota_autonomy.snapshots.v1.json",
    "execute_finalize": "runner_stage_execute_finalize.snapshots.v1.json",
}


def stage_names() -> tuple[str, ...]:
    return tuple(_STAGE_SNAPSHOT_FILES.keys())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _stage_snapshot_path(stage_name: str) -> Path:
    file_name = _STAGE_SNAPSHOT_FILES.get(stage_name)
    if not isinstance(file_name, str) or not file_name:
        raise SystemExit(f"runner_stage_contract_test_utils failed: unknown_stage={stage_name}")
    return Path(__file__).with_name(file_name)


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


def _load_stage_scenarios(stage_name: str) -> list[dict[str, Any]]:
    path = _stage_snapshot_path(stage_name)
    payload = json.loads(path.read_text(encoding="utf-8"))
    declared_stage = payload.get("stage")
    if isinstance(declared_stage, str) and declared_stage and declared_stage != stage_name:
        raise SystemExit(
            "runner_stage_contract_test_utils failed: "
            + f"stage_mismatch expected={stage_name} declared={declared_stage} file={path.name}"
        )
    scenarios = payload.get("scenarios") if isinstance(payload.get("scenarios"), list) else []
    if not scenarios:
        raise SystemExit(f"runner_stage_contract_test_utils failed: scenarios missing in {path.name}")
    typed: list[dict[str, Any]] = []
    for item in scenarios:
        if isinstance(item, dict):
            typed.append(item)
    if not typed:
        raise SystemExit(f"runner_stage_contract_test_utils failed: scenarios invalid in {path.name}")
    return typed


def _load_all_stage_scenarios() -> dict[str, list[dict[str, Any]]]:
    all_map: dict[str, list[dict[str, Any]]] = {}
    seen_ids: set[str] = set()
    for stage_name in stage_names():
        scenarios = _load_stage_scenarios(stage_name)
        for sc in scenarios:
            scenario_id = str(sc.get("id", "")).strip()
            if not scenario_id:
                raise SystemExit(
                    "runner_stage_contract_test_utils failed: "
                    + f"empty_scenario_id stage={stage_name} file={_stage_snapshot_path(stage_name).name}"
                )
            if scenario_id in seen_ids:
                raise SystemExit(
                    "runner_stage_contract_test_utils failed: "
                    + f"duplicate_scenario_id={scenario_id}"
                )
            seen_ids.add(scenario_id)
        all_map[stage_name] = scenarios
    return all_map


def all_scenario_ids() -> tuple[str, ...]:
    all_map = _load_all_stage_scenarios()
    ordered: list[str] = []
    for stage_name in stage_names():
        for sc in all_map.get(stage_name, []):
            scenario_id = str(sc.get("id", "")).strip()
            if scenario_id:
                ordered.append(scenario_id)
    return tuple(ordered)


def _build_stage_scenario_ids() -> dict[str, tuple[str, ...]]:
    all_map = _load_all_stage_scenarios()
    result: dict[str, tuple[str, ...]] = {}
    for stage_name in stage_names():
        scenario_ids: list[str] = []
        for sc in all_map.get(stage_name, []):
            scenario_id = str(sc.get("id", "")).strip()
            if scenario_id:
                scenario_ids.append(scenario_id)
        result[stage_name] = tuple(scenario_ids)
    return result


STAGE_SCENARIO_IDS: dict[str, tuple[str, ...]] = _build_stage_scenario_ids()


def _run_selected_contract(*, test_name: str, selected: list[dict[str, Any]]) -> None:
    root = _repo_root()
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


def run_stage_contract_test(*, test_name: str, stage_name: str) -> None:
    scenarios = _load_stage_scenarios(stage_name)
    _run_selected_contract(test_name=test_name, selected=scenarios)


def run_all_contract_test(*, test_name: str) -> None:
    all_map = _load_all_stage_scenarios()
    selected: list[dict[str, Any]] = []
    for stage_name in stage_names():
        selected.extend(all_map.get(stage_name, []))
    _run_selected_contract(test_name=test_name, selected=selected)


def run_contract_test(*, test_name: str, scenario_ids: tuple[str, ...]) -> None:
    all_map = _load_all_stage_scenarios()
    all_scenarios: list[dict[str, Any]] = []
    for stage_name in stage_names():
        all_scenarios.extend(all_map.get(stage_name, []))

    wanted = set(scenario_ids)
    selected = [sc for sc in all_scenarios if str(sc.get("id", "")) in wanted]
    missing = sorted(wanted.difference({str(sc.get("id", "")) for sc in selected}))
    if missing:
        raise SystemExit(f"{test_name} failed: missing_scenarios={json.dumps(missing, ensure_ascii=True)}")
    _run_selected_contract(test_name=test_name, selected=selected)
