from __future__ import annotations

BOARD_TITLE_DEFAULT = "autonomous-orchestrator Governance Board"
WORKSPACE_DEFAULT = ".cache/ws_customer_default"

STATUSES = {"Backlog", "Todo", "In Progress", "Blocked", "Needs Verify", "Done"}
TRACKS = {"core", "ops", "github-ops", "pm-suite", "work-intake", "ui", "managed-repo"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
KINDS = {"umbrella", "milestone", "gate", "risk", "issue"}

REQUIRED_FIELDS = ("Status", "Faz", "Track", "Priority", "Kind")
REQUIRED_LABELS = (
    "project-roadmap",
    "risk",
    "gate",
    "needs-verification",
    "blocked",
    "security",
    "quality",
)

DRIFT_CODES = {
    "MISSING_BOARD_ITEM",
    "UNEXPECTED_BOARD_ITEM",
    "MISSING_FIELD",
    "INVALID_FIELD_VALUE",
    "AGENT_STATE_MISSING",
    "CLAIM_CONFLICT",
    "NEEDS_VERIFY_LABEL_MISMATCH",
    "BLOCKED_STATE_MISMATCH",
    "FORBIDDEN_DONE",
    "FORBIDDEN_CLOSE_KEYWORD",
    "SSOT_REF_MISSING",
    "DIGEST_MISMATCH",
}

EVIDENCE_DOES_NOT_PROVE = (
    "Live GitHub Project mutation has not been applied.",
    "Runtime/live acceptance is not proven by board dry-run output.",
    "Issue closure remains deliberate and out of scope.",
)

