from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.orchestrator.runner_utils import safe_float


@dataclass
class RunContext:
    governor_mode_used: str
    governor_concurrency_limit_hit: bool
    writes_allowed: bool
    governor_quarantine_hit: str | None = None

    request_id: str = ""
    tenant_id: str = ""
    intent: str = ""
    risk_score: float = 0.0
    dry_run: bool = False
    idempotency_key: Any = None
    workflow_id: str | None = None

    def ingest_envelope(self, envelope: dict[str, Any]) -> None:
        intent_raw = envelope.get("intent")
        self.intent = intent_raw if isinstance(intent_raw, str) else ""
        self.risk_score = safe_float(envelope.get("risk_score", 0.0), default=0.0)
        self.dry_run = bool(envelope.get("dry_run", False))
        self.request_id = str(envelope.get("request_id", ""))
        self.tenant_id = str(envelope.get("tenant_id", ""))
        self.idempotency_key = envelope.get("idempotency_key")

