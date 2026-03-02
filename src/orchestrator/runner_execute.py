from __future__ import annotations

from pathlib import Path
from typing import Any

from src.orchestrator import runner_config
from src.orchestrator.runner_inputs import ReplayContext
from src.orchestrator.runner_stages import (
    ExecutionContext,
    StageContext,
    execute_and_finalize_stage,
    governor_stage,
    idempotency_stage,
    quota_autonomy_stage,
    routing_and_workflow_stage,
    validate_envelope_stage,
)


def run_envelope(
    *,
    envelope: dict[str, Any],
    envelope_path: Path,
    workspace: Path,
    out_dir: Path,
    replay_ctx: ReplayContext,
) -> None:
    stage_ctx = StageContext(
        envelope=envelope,
        envelope_path=envelope_path,
        workspace=workspace,
        out_dir=out_dir,
        replay_of=replay_ctx.replay_of,
        replay_provenance=replay_ctx.replay_provenance,
        replay_warnings=replay_ctx.replay_warnings,
        force_new_run=replay_ctx.force_new_run,
        replay_force_new_run=replay_ctx.replay_force_new_run,
    )

    validate_envelope_stage(stage_ctx=stage_ctx)

    lock_path = workspace / ".cache" / "governor_lock"
    lock_acquired = False

    try:
        run_ctx, quarantined_workflows, lock_path, lock_acquired = governor_stage(stage_ctx=stage_ctx)
        routing_state = routing_and_workflow_stage(
            stage_ctx=stage_ctx,
            run_ctx=run_ctx,
            quarantined_workflows=quarantined_workflows,
        )

        idempotency_state = idempotency_stage(
            stage_ctx=stage_ctx,
            run_ctx=run_ctx,
            workflow_fingerprint=routing_state.workflow_fingerprint,
            approval_threshold_used=routing_state.approval_threshold_used,
        )
        if idempotency_state is None:
            return

        quota_autonomy_state = quota_autonomy_stage(
            stage_ctx=stage_ctx,
            run_ctx=run_ctx,
            run_id=idempotency_state.run_id,
            routing_state=routing_state,
            idempotency_state=idempotency_state,
        )

        exec_ctx = ExecutionContext(
            run_ctx=run_ctx,
            run_id=idempotency_state.run_id,
            routing_state=routing_state,
            idempotency_state=idempotency_state,
            quota_autonomy_state=quota_autonomy_state,
        )
        execute_and_finalize_stage(stage_ctx=stage_ctx, exec_ctx=exec_ctx)
    finally:
        if lock_acquired:
            runner_config.release_governor_lock(lock_path)
