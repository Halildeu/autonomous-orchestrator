from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunContext:
    workspace: Path
    out_dir: Path
    envelope: dict[str, Any]
    envelope_path: Path | None
    workflow_id: str
    workflow_path: Path
    workflow_fingerprint: str
    run_id: str
    approval_threshold_used: float
    governor_mode_used: str
    writes_allowed: bool
    governor_quarantine_hit: str | None
    governor_concurrency_limit_hit: bool
    idempotency_key_hash: str | None

