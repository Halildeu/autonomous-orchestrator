from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BudgetSpec:
    max_attempts: int
    max_time_ms: int
    max_tokens: int


@dataclass
class BudgetUsage:
    attempts_used: int = 0
    elapsed_ms: int = 0
    est_tokens_used: int = 0


@dataclass
class NodeResult:
    node_id: str
    status: str  # COMPLETED | SUSPENDED | SKIPPED | FAILED
    output: dict[str, Any]
