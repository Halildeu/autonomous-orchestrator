from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.evidence.writer import EvidenceWriter
from src.orchestrator.workflow_exec import BudgetTracker


class ExecutorPort(Protocol):
    adapter_id: str

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
    ) -> dict[str, Any]: ...
