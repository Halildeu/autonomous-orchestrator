from __future__ import annotations

import os
from pathlib import Path

from src.orchestrator.executor_adapters.codex_optional import CodexOptionalExecutor
from src.orchestrator.executor_adapters.local_manual import LocalManualExecutor
from src.orchestrator.executor_port import ExecutorPort


def resolve_executor_port(*, workspace: Path) -> ExecutorPort:
    adapter_raw = os.environ.get("ORCH_EXECUTOR_ADAPTER", "").strip().lower()
    if adapter_raw in {"codex", "codex_optional", "codex-optional"}:
        return CodexOptionalExecutor(workspace=workspace)
    return LocalManualExecutor(workspace=workspace)
