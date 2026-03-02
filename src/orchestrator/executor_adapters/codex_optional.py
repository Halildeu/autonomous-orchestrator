from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator.executor_port import ExecutorPort
from src.orchestrator.workflow_exec import BudgetTracker, execute_workflow
from src.providers.openai_provider import DeterministicStubProvider, get_provider


def _env_true(key: str) -> bool:
    v = os.environ.get(key)
    if not isinstance(v, str):
        return False
    return v.strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class CodexOptionalExecutor(ExecutorPort):
    workspace: Path
    adapter_id: str = "codex_optional"

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
        network_mode = os.environ.get("ORCH_NETWORK_MODE", "OFF").strip().upper()
        codex_enabled = _env_true("ORCH_EXECUTOR_CODEX_ENABLED") or _env_true("CODEX_EXECUTOR_ENABLED")

        provider = DeterministicStubProvider()
        if codex_enabled and network_mode == "ON":
            provider = get_provider()

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
