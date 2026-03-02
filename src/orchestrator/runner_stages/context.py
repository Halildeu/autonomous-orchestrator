from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.orchestrator.runner_context import RunContext

if TYPE_CHECKING:
    from src.orchestrator.runner_stages.idempotency_stage import IdempotencyState
    from src.orchestrator.runner_stages.quota_autonomy_stage import QuotaAutonomyState
    from src.orchestrator.runner_stages.routing_workflow_stage import RoutingWorkflowState


@dataclass
class StageContext:
    envelope: dict[str, Any]
    envelope_path: Path
    workspace: Path
    out_dir: Path
    replay_of: str | None
    replay_provenance: dict[str, Any] | None
    replay_warnings: list[str]
    force_new_run: bool
    replay_force_new_run: bool


@dataclass
class ExecutionContext:
    run_ctx: RunContext
    run_id: str
    routing_state: RoutingWorkflowState
    idempotency_state: IdempotencyState
    quota_autonomy_state: QuotaAutonomyState
