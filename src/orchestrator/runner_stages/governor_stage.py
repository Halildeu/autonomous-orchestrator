from __future__ import annotations

from pathlib import Path

from src.orchestrator import dlq, runner_config
from src.orchestrator.runner_context import RunContext
from src.orchestrator.runner_stages.context import StageContext
from src.orchestrator.runner_utils import print_error
from src.tools.gateway import PolicyViolation


def governor_stage(*, stage_ctx: StageContext) -> tuple[RunContext, set[str], Path, bool]:
    governor = runner_config.load_governor(stage_ctx.workspace)
    governor_mode_used = governor.get("global_mode", "normal")
    quarantine = governor.get("quarantine") if isinstance(governor.get("quarantine"), dict) else {}
    quarantined_intents = set(x for x in quarantine.get("intents", []) if isinstance(x, str) and x)
    quarantined_workflows = set(x for x in quarantine.get("workflows", []) if isinstance(x, str) and x)
    conc = governor.get("concurrency") if isinstance(governor.get("concurrency"), dict) else {}
    max_parallel_runs_raw = conc.get("max_parallel_runs", 1)
    try:
        max_parallel_runs = int(max_parallel_runs_raw)
    except Exception:
        max_parallel_runs = 1
    if max_parallel_runs < 1:
        max_parallel_runs = 1

    lock_path = stage_ctx.workspace / ".cache" / "governor_lock"
    lock_acquired = False
    run_ctx = RunContext(
        governor_mode_used=str(governor_mode_used),
        governor_concurrency_limit_hit=False,
        writes_allowed=str(governor_mode_used) != "report_only",
    )
    try:
        lock_path, lock_acquired = runner_config.acquire_governor_lock(
            stage_ctx.workspace, max_parallel_runs=max_parallel_runs
        )
    except PolicyViolation as e:
        run_ctx.governor_concurrency_limit_hit = True
        msg = f"{e.error_code}: {e}"
        if len(msg) > 240:
            msg = msg[:237] + "..."
        dlq_path = dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="GOVERNOR",
            error_code="POLICY_VIOLATION",
            message=msg or "Governor blocked run.",
            envelope=stage_ctx.envelope,
        )
        print_error(
            "GOVERNOR_BLOCK",
            "Governor blocked run.",
            details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
        )
        raise SystemExit(1)

    run_ctx.ingest_envelope(stage_ctx.envelope)
    if run_ctx.intent and run_ctx.intent in quarantined_intents:
        run_ctx.governor_quarantine_hit = "INTENT"
        e = PolicyViolation("QUARANTINED_INTENT", f"Intent is quarantined: {run_ctx.intent}")
        msg = f"{e.error_code}: {e}"
        dlq_path = dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="GOVERNOR",
            error_code="POLICY_VIOLATION",
            message=msg,
            envelope=stage_ctx.envelope,
        )
        print_error(
            "GOVERNOR_BLOCK",
            "Governor blocked run.",
            details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
        )
        raise SystemExit(1)

    return run_ctx, quarantined_workflows, lock_path, lock_acquired
