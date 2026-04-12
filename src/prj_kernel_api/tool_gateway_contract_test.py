"""Contract tests for tool_gateway — authorization, cycle detection, dispatch."""

from __future__ import annotations

from src.prj_kernel_api.tool_gateway import (
    ToolCallPolicy,
    ToolGateway,
    ToolPermission,
)


def _make_policy(**overrides) -> ToolCallPolicy:
    defaults = {
        "enabled": True,
        "max_tool_calls_per_request": 5,
        "max_tool_rounds": 3,
        "allowed_tools": ["system-status", "policy-check"],
        "blocked_tools": [],
        "tool_permissions": {"default": "read_only", "mutating_requires_confirmation": True},
        "cycle_detection": {"enabled": True, "max_identical_calls": 2},
        "fail_action": "block",
    }
    defaults.update(overrides)
    return ToolCallPolicy(defaults)


def _make_registry() -> list[ToolPermission]:
    return [
        ToolPermission("system-status", "read_only", "system-status", {}, "Get status"),
        ToolPermission("policy-check", "read_only", "policy-check", {}, "Check policies"),
        ToolPermission("work-intake", "mutating", "work-intake", {}, "Create work item"),
    ]


class TestToolCallPolicy:
    def test_disabled_blocks_all(self) -> None:
        policy = _make_policy(enabled=False)
        allowed, reason = policy.authorize_call("system-status", {}, [])
        assert allowed is False
        assert reason == "tool_calling_disabled"

    def test_allowed_tool(self) -> None:
        policy = _make_policy()
        allowed, reason = policy.authorize_call("system-status", {}, [])
        assert allowed is True
        assert reason == "authorized"

    def test_not_allowed_tool(self) -> None:
        policy = _make_policy()
        allowed, reason = policy.authorize_call("unknown-tool", {}, [])
        assert allowed is False
        assert "not_allowed" in reason

    def test_blocked_tool_overrides_allowed(self) -> None:
        policy = _make_policy(blocked_tools=["system-status"])
        allowed, reason = policy.authorize_call("system-status", {}, [])
        assert allowed is False
        assert "blocked" in reason

    def test_empty_allowed_blocks_all(self) -> None:
        policy = _make_policy(allowed_tools=[])
        allowed, reason = policy.authorize_call("system-status", {}, [])
        assert allowed is False
        assert reason == "no_tools_allowed"

    def test_max_calls_exceeded(self) -> None:
        policy = _make_policy(max_tool_calls_per_request=2)
        history = [
            {"name": "system-status", "input": {}},
            {"name": "system-status", "input": {}},
        ]
        allowed, reason = policy.authorize_call("system-status", {}, history)
        assert allowed is False
        assert "max_calls" in reason

    def test_cycle_detection(self) -> None:
        policy = _make_policy()
        same_input = {"workspace_root": ".cache"}
        history = [
            {"name": "system-status", "input": same_input},
            {"name": "system-status", "input": same_input},
        ]
        allowed, reason = policy.authorize_call("system-status", same_input, history)
        assert allowed is False
        assert "cycle_detected" in reason

    def test_different_inputs_no_cycle(self) -> None:
        policy = _make_policy()
        history = [
            {"name": "system-status", "input": {"workspace_root": ".cache/a"}},
            {"name": "system-status", "input": {"workspace_root": ".cache/b"}},
        ]
        allowed, reason = policy.authorize_call("system-status", {"workspace_root": ".cache/c"}, history)
        assert allowed is True

    def test_cycle_detection_disabled(self) -> None:
        policy = _make_policy(cycle_detection={"enabled": False, "max_identical_calls": 2})
        same_input = {"workspace_root": ".cache"}
        history = [{"name": "system-status", "input": same_input}] * 5
        allowed, reason = policy.authorize_call("system-status", same_input, history)
        assert allowed is False  # Still blocked by max_calls_per_request=5


class TestToolGateway:
    def test_dispatch_blocked(self) -> None:
        policy = _make_policy(allowed_tools=[])
        gateway = ToolGateway(_make_registry(), policy)
        result = gateway.dispatch(
            "system-status", {},
            workspace_root=".cache/ws",
            request_id="r1",
            call_history=[],
        )
        assert result["status"] == "BLOCKED"
        assert result["authorization"] == "no_tools_allowed"

    def test_dispatch_tool_not_in_registry(self) -> None:
        policy = _make_policy(allowed_tools=["nonexistent"])
        gateway = ToolGateway(_make_registry(), policy)
        result = gateway.dispatch(
            "nonexistent", {},
            workspace_root=".cache/ws",
            request_id="r2",
            call_history=[],
        )
        assert result["status"] == "FAIL"
        assert "not found" in result["error"]

    def test_mutating_requires_confirmation(self) -> None:
        policy = _make_policy(allowed_tools=["work-intake"])
        gateway = ToolGateway(_make_registry(), policy)
        result = gateway.dispatch(
            "work-intake", {},
            workspace_root=".cache/ws",
            request_id="r3",
            call_history=[],
        )
        assert result["status"] == "CONFIRMATION_REQUIRED"

    def test_max_rounds_property(self) -> None:
        policy = _make_policy(max_tool_rounds=5)
        assert policy.max_rounds == 5

    def test_enabled_property(self) -> None:
        assert _make_policy(enabled=True).enabled is True
        assert _make_policy(enabled=False).enabled is False
