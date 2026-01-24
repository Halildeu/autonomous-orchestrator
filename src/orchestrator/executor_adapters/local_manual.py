from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator.executor_port import ExecutorPort
from src.orchestrator.workflow_exec import BudgetTracker, execute_workflow
from src.providers.openai_provider import DeterministicStubProvider


@dataclass(frozen=True)
class LocalManualExecutor(ExecutorPort):
    workspace: Path
    adapter_id: str = "local_manual"

    def execute_workflow(
        self,
        *,
        envelope: dict[str, Any],
        workflow: dict[str, Any],
        workspace: Path,
        evidence: EvidenceWriter,
        approval_threshold: float,
        writes_allowed: bool,
        budget: BudgetTracker | None = None,
        force_suspend_reason: str | None = None,
    ) -> dict[str, Any]:
        provider = DeterministicStubProvider()
        return execute_workflow(
            envelope=envelope,
            workflow=workflow,
            provider=provider,
            workspace=workspace,
            evidence=evidence,
            approval_threshold=approval_threshold,
            writes_allowed=bool(writes_allowed),
            budget=budget,
            force_suspend_reason=force_suspend_reason,
        )
