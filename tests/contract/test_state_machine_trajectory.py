"""Contract test: state machine trajectory validation.

Validates that:
1. state_machine.v1.json is not a placeholder
2. All transitions are between declared states
3. Forward-only enforcement: terminal states have no outgoing transitions
4. Full happy-path trajectory works for each machine
5. Invalid transitions are rejected
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SM_PATH = REPO_ROOT / "orchestrator" / "state_machine.v1.json"


@pytest.fixture(scope="module")
def state_machine() -> dict:
    raw = json.loads(SM_PATH.read_text(encoding="utf-8"))
    assert "machines" in raw, "state_machine.v1.json must contain 'machines' key (not a placeholder)"
    return raw


def _get_machine(state_machine: dict, name: str) -> dict:
    machines = state_machine["machines"]
    assert name in machines, f"Machine '{name}' not found in state_machine.v1.json"
    return machines[name]


def _transition(machine: dict, current: str, trigger: str) -> str | None:
    """Return target state for a valid transition, or None if invalid."""
    for t in machine["transitions"]:
        if t["from"] == current and t["trigger"] == trigger:
            return t["to"]
    return None


# ── Structure tests ──────────────────────────────────────────────────


def test_not_placeholder(state_machine: dict):
    """state_machine.v1.json must not be a placeholder."""
    assert "note" not in state_machine or "placeholder" not in state_machine.get("note", "").lower()
    assert len(state_machine["machines"]) >= 2


def test_all_transitions_reference_declared_states(state_machine: dict):
    """Every transition 'from' and 'to' must reference a declared state."""
    for name, machine in state_machine["machines"].items():
        state_ids = {s["id"] for s in machine["states"]}
        for t in machine["transitions"]:
            assert t["from"] in state_ids, f"{name}: transition from unknown state '{t['from']}'"
            assert t["to"] in state_ids, f"{name}: transition to unknown state '{t['to']}'"


def test_initial_state_is_declared(state_machine: dict):
    """Initial state must be a declared state."""
    for name, machine in state_machine["machines"].items():
        state_ids = {s["id"] for s in machine["states"]}
        assert machine["initial"] in state_ids, f"{name}: initial '{machine['initial']}' not in states"


def test_terminal_states_are_declared(state_machine: dict):
    """Terminal states must be declared states."""
    for name, machine in state_machine["machines"].items():
        state_ids = {s["id"] for s in machine["states"]}
        for ts in machine["terminal"]:
            assert ts in state_ids, f"{name}: terminal '{ts}' not in states"


def test_terminal_states_have_no_outgoing(state_machine: dict):
    """Terminal states must not have outgoing transitions (forward-only)."""
    for name, machine in state_machine["machines"].items():
        terminal = set(machine["terminal"])
        for t in machine["transitions"]:
            assert t["from"] not in terminal, (
                f"{name}: terminal state '{t['from']}' has outgoing transition "
                f"via trigger '{t['trigger']}' to '{t['to']}'"
            )


# ── Trajectory tests ────────────────────────────────────────────────


def test_work_item_happy_path(state_machine: dict):
    """OPEN → PLANNED → IN_PROGRESS → APPLIED → CLOSED"""
    m = _get_machine(state_machine, "work_item")
    state = m["initial"]
    assert state == "OPEN"

    state = _transition(m, state, "plan")
    assert state == "PLANNED"

    state = _transition(m, state, "start")
    assert state == "IN_PROGRESS"

    state = _transition(m, state, "apply")
    assert state == "APPLIED"

    state = _transition(m, state, "close")
    assert state == "CLOSED"


def test_work_item_noop_path(state_machine: dict):
    """OPEN → NOOP (skip)"""
    m = _get_machine(state_machine, "work_item")
    state = _transition(m, m["initial"], "skip")
    assert state == "NOOP"


def test_work_item_fail_retry(state_machine: dict):
    """OPEN → PLANNED → IN_PROGRESS → (fail) → OPEN"""
    m = _get_machine(state_machine, "work_item")
    state = _transition(m, "OPEN", "plan")
    state = _transition(m, state, "start")
    state = _transition(m, state, "fail")
    assert state == "OPEN"


def test_run_execution_happy_path(state_machine: dict):
    """PENDING → RUNNING → COMPLETED"""
    m = _get_machine(state_machine, "run_execution")
    state = m["initial"]
    assert state == "PENDING"

    state = _transition(m, state, "acquire_lock")
    assert state == "RUNNING"

    state = _transition(m, state, "finalize")
    assert state == "COMPLETED"


def test_run_execution_suspend_resume(state_machine: dict):
    """PENDING → RUNNING → SUSPENDED → RUNNING → COMPLETED"""
    m = _get_machine(state_machine, "run_execution")
    state = _transition(m, "PENDING", "acquire_lock")
    state = _transition(m, state, "suspend")
    assert state == "SUSPENDED"

    state = _transition(m, state, "resume")
    assert state == "RUNNING"

    state = _transition(m, state, "finalize")
    assert state == "COMPLETED"


def test_run_execution_reject(state_machine: dict):
    """PENDING → FAILED (reject)"""
    m = _get_machine(state_machine, "run_execution")
    state = _transition(m, "PENDING", "reject")
    assert state == "FAILED"


def test_node_execution_happy_path(state_machine: dict):
    """PENDING → RUNNING → COMPLETED"""
    m = _get_machine(state_machine, "node_execution")
    state = _transition(m, "PENDING", "start")
    assert state == "RUNNING"

    state = _transition(m, state, "succeed")
    assert state == "COMPLETED"


# ── Invalid transition tests ────────────────────────────────────────


def test_invalid_transition_returns_none(state_machine: dict):
    """Transitions not in the matrix must return None."""
    m = _get_machine(state_machine, "work_item")
    assert _transition(m, "OPEN", "apply") is None
    assert _transition(m, "CLOSED", "plan") is None
    assert _transition(m, "NOOP", "start") is None


def test_invalid_run_transition(state_machine: dict):
    m = _get_machine(state_machine, "run_execution")
    assert _transition(m, "COMPLETED", "resume") is None
    assert _transition(m, "FAILED", "finalize") is None
