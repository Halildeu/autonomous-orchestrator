"""Canonical status vocabulary for the autonomous-orchestrator control-plane.

This module is the Python SSOT for all status enum families. Schemas define
the JSON-side contract (status-vocabulary.schema.v1.json); this module defines
the Python-side constants and validation helpers.

Usage::

    from src.shared.status import NODE_COMPLETED, validate_status, NODE_STATUSES

    result_status = validate_status(raw_status, NODE_STATUSES)
"""

from __future__ import annotations

# ── Report Status ────────────────────────────────────────────────────
# Used by CI gates, ops commands, and report outputs.

REPORT_OK = "OK"
REPORT_WARN = "WARN"
REPORT_IDLE = "IDLE"
REPORT_FAIL = "FAIL"
REPORT_STATUSES: frozenset[str] = frozenset({REPORT_OK, REPORT_WARN, REPORT_IDLE, REPORT_FAIL})


# ── Work Item Status (PM) ───────────────────────────────────────────
# Matches pm-work-item.schema.v1.json status enum.

WI_OPEN = "OPEN"
WI_IN_PROGRESS = "IN_PROGRESS"
WI_BLOCKED = "BLOCKED"
WI_DONE = "DONE"
WI_DEFERRED = "DEFERRED"
WORK_ITEM_STATUSES: frozenset[str] = frozenset({WI_OPEN, WI_IN_PROGRESS, WI_BLOCKED, WI_DONE, WI_DEFERRED})


# ── Work Item Lifecycle ─────────────────────────────────────────────
# Orchestrator pipeline lifecycle (state_machine.v1.json work_item machine).

WL_OPEN = "OPEN"
WL_PLANNED = "PLANNED"
WL_IN_PROGRESS = "IN_PROGRESS"
WL_APPLIED = "APPLIED"
WL_CLOSED = "CLOSED"
WL_NOOP = "NOOP"
WORK_ITEM_LIFECYCLE: frozenset[str] = frozenset({
    WL_OPEN, WL_PLANNED, WL_IN_PROGRESS, WL_APPLIED, WL_CLOSED, WL_NOOP,
})
WORK_ITEM_TERMINAL: frozenset[str] = frozenset({WL_APPLIED, WL_CLOSED, WL_NOOP})


# ── Node Execution Status ───────────────────────────────────────────
# Matches workflow_exec_contracts.py NodeResult.status.

NODE_COMPLETED = "COMPLETED"
NODE_SUSPENDED = "SUSPENDED"
NODE_SKIPPED = "SKIPPED"
NODE_FAILED = "FAILED"
NODE_STATUSES: frozenset[str] = frozenset({NODE_COMPLETED, NODE_SUSPENDED, NODE_SKIPPED, NODE_FAILED})


# ── Run Result Status ───────────────────────────────────────────────
# Overall orchestrator run result.

RUN_COMPLETED = "COMPLETED"
RUN_FAILED = "FAILED"
RUN_SUSPENDED = "SUSPENDED"
RUN_RESULT_STATUSES: frozenset[str] = frozenset({RUN_COMPLETED, RUN_FAILED, RUN_SUSPENDED})


# ── Intake Action Status ────────────────────────────────────────────
# Work intake exec ticket entry statuses.

INTAKE_APPLIED = "APPLIED"
INTAKE_PLANNED = "PLANNED"
INTAKE_IDLE = "IDLE"
INTAKE_SKIPPED = "SKIPPED"
INTAKE_IGNORED = "IGNORED"
INTAKE_ACTION_STATUSES: frozenset[str] = frozenset({
    INTAKE_APPLIED, INTAKE_PLANNED, INTAKE_IDLE, INTAKE_SKIPPED, INTAKE_IGNORED,
})


# ── Validation ──────────────────────────────────────────────────────


def validate_status(value: str, family: frozenset[str]) -> str:
    """Validate that *value* belongs to *family*. Fail-closed.

    Returns the value if valid; raises ``ValueError`` otherwise.
    """
    if value not in family:
        raise ValueError(
            f"Invalid status '{value}', expected one of {sorted(family)}"
        )
    return value


# ── Transition Validation ───────────────────────────────────────────

# Allowed (from_state, to_state) pairs for the work_item lifecycle machine.
# Derived from orchestrator/state_machine.v1.json work_item.transitions.
_WORK_ITEM_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("OPEN", "PLANNED"),
    ("OPEN", "NOOP"),
    ("PLANNED", "IN_PROGRESS"),
    ("PLANNED", "OPEN"),        # replan
    ("IN_PROGRESS", "APPLIED"),
    ("IN_PROGRESS", "OPEN"),    # fail → retry
    ("APPLIED", "CLOSED"),
    # Initial write: new work items may start at any valid lifecycle state
    ("", "OPEN"),
    ("", "PLANNED"),
    ("", "IN_PROGRESS"),
    ("", "APPLIED"),
    ("", "CLOSED"),
    ("", "NOOP"),
})


def validate_transition(from_state: str | None, to_state: str) -> str:
    """Validate a work_item lifecycle state transition. Fail-closed.

    ``from_state`` is None or '' for the initial write (new work item).
    Returns ``to_state`` if valid; raises ``ValueError`` on invalid transition.
    """
    norm_from = str(from_state or "").strip().upper()
    norm_to = str(to_state or "").strip().upper()
    if (norm_from, norm_to) not in _WORK_ITEM_ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Invalid work_item transition: {norm_from!r} → {norm_to!r}. "
            f"Allowed: {sorted(_WORK_ITEM_ALLOWED_TRANSITIONS)}"
        )
    return norm_to


# ── Run Execution Transition Validation ───────────────────────────

# Derived from orchestrator/state_machine.v1.json run_execution.transitions.
_RUN_EXECUTION_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("PENDING", "RUNNING"),
    ("PENDING", "FAILED"),
    ("RUNNING", "COMPLETED"),
    ("RUNNING", "FAILED"),
    ("RUNNING", "SUSPENDED"),
    ("SUSPENDED", "RUNNING"),
    ("SUSPENDED", "FAILED"),
    # Initial write
    ("", "PENDING"),
})


def validate_run_transition(from_state: str | None, to_state: str) -> str:
    """Validate a run_execution state transition. Fail-closed.

    Returns ``to_state`` if valid; raises ``ValueError`` on invalid transition.
    """
    norm_from = str(from_state or "").strip().upper()
    norm_to = str(to_state or "").strip().upper()
    if (norm_from, norm_to) not in _RUN_EXECUTION_ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Invalid run_execution transition: {norm_from!r} → {norm_to!r}. "
            f"Allowed: {sorted(_RUN_EXECUTION_ALLOWED_TRANSITIONS)}"
        )
    return norm_to


# ── Node Execution Transition Validation ──────────────────────────

# Derived from orchestrator/state_machine.v1.json node_execution.transitions.
_NODE_EXECUTION_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("PENDING", "RUNNING"),
    ("PENDING", "SKIPPED"),
    ("RUNNING", "COMPLETED"),
    ("RUNNING", "FAILED"),
    ("RUNNING", "SUSPENDED"),
    ("SUSPENDED", "RUNNING"),
    # Initial write
    ("", "PENDING"),
})


def validate_node_transition(from_state: str | None, to_state: str) -> str:
    """Validate a node_execution state transition. Fail-closed.

    Returns ``to_state`` if valid; raises ``ValueError`` on invalid transition.
    """
    norm_from = str(from_state or "").strip().upper()
    norm_to = str(to_state or "").strip().upper()
    if (norm_from, norm_to) not in _NODE_EXECUTION_ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Invalid node_execution transition: {norm_from!r} → {norm_to!r}. "
            f"Allowed: {sorted(_NODE_EXECUTION_ALLOWED_TRANSITIONS)}"
        )
    return norm_to
