from __future__ import annotations

from pathlib import Path

from src.orchestrator.workflow_exec_contracts import BudgetSpec, BudgetUsage, NodeResult
from src.orchestrator.workflow_exec_policy import read_approval_threshold
from src.orchestrator.workflow_exec_steps import BudgetTracker, execute_mod_b_only, execute_workflow


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
