"""Contract tests for tool_calling — provider-native format build + response parsing."""

from __future__ import annotations

import json

from src.prj_kernel_api.tool_calling import (
    build_tool_result,
    build_tools_param,
    build_tools_param_claude,
    build_tools_param_openai,
    extract_tool_calls,
    extract_tool_calls_claude,
    extract_tool_calls_openai,
)

SAMPLE_TOOLS = [
    {"name": "system-status", "description": "Get system status", "parameters": {"type": "object", "properties": {}}},
    {"name": "policy-check", "description": "Check policies", "parameters": {"type": "object", "properties": {"source": {"type": "string"}}}},
]


class TestBuildToolsParam:
    def test_claude_format(self) -> None:
        result = build_tools_param_claude(SAMPLE_TOOLS)
        assert len(result) == 2
        assert result[0]["name"] == "system-status"
        assert "input_schema" in result[0]
        assert "type" not in result[0]  # Claude doesn't use type wrapper

    def test_openai_format(self) -> None:
        result = build_tools_param_openai(SAMPLE_TOOLS)
        assert len(result) == 2
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "system-status"
        assert "parameters" in result[0]["function"]

    def test_dispatch_claude(self) -> None:
        result = build_tools_param("claude", SAMPLE_TOOLS)
        assert "input_schema" in result[0]

    def test_dispatch_openai(self) -> None:
        result = build_tools_param("openai", SAMPLE_TOOLS)
        assert result[0]["type"] == "function"

    def test_dispatch_xai(self) -> None:
        result = build_tools_param("xai", SAMPLE_TOOLS)
        assert result[0]["type"] == "function"  # xAI uses OpenAI format


class TestExtractToolCalls:
    def test_claude_tool_use(self) -> None:
        resp = json.dumps({
            "content": [
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "toolu_1", "name": "system-status", "input": {"workspace_root": ".cache/ws"}},
            ],
        }).encode()
        calls = extract_tool_calls_claude(resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "toolu_1"
        assert calls[0]["name"] == "system-status"
        assert calls[0]["input"]["workspace_root"] == ".cache/ws"

    def test_openai_tool_calls(self) -> None:
        resp = json.dumps({
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {"name": "system-status", "arguments": '{"workspace_root": ".cache"}'},
                    }],
                },
            }],
        }).encode()
        calls = extract_tool_calls_openai(resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "call_1"
        assert calls[0]["name"] == "system-status"
        assert calls[0]["arguments"]["workspace_root"] == ".cache"

    def test_openai_responses_api_function_call(self) -> None:
        resp = json.dumps({
            "output": [
                {"type": "function_call", "call_id": "fc_1", "name": "policy-check", "arguments": '{"source": "both"}'},
            ],
        }).encode()
        calls = extract_tool_calls_openai(resp)
        assert len(calls) == 1
        assert calls[0]["name"] == "policy-check"
        assert calls[0]["arguments"]["source"] == "both"

    def test_extract_normalized_claude(self) -> None:
        resp = json.dumps({
            "content": [{"type": "tool_use", "id": "t1", "name": "test", "input": {"a": 1}}],
        }).encode()
        calls = extract_tool_calls("claude", resp)
        assert calls[0]["input"] == {"a": 1}

    def test_extract_normalized_openai(self) -> None:
        resp = json.dumps({
            "choices": [{"message": {"tool_calls": [{"id": "c1", "function": {"name": "test", "arguments": '{"a": 1}'}}]}}],
        }).encode()
        calls = extract_tool_calls("openai", resp)
        assert calls[0]["input"] == {"a": 1}  # 'arguments' normalized to 'input'

    def test_no_tool_calls(self) -> None:
        resp = json.dumps({"content": [{"type": "text", "text": "No tools needed."}]}).encode()
        assert extract_tool_calls("claude", resp) == []

    def test_empty_bytes(self) -> None:
        assert extract_tool_calls("claude", b"") == []

    def test_invalid_json(self) -> None:
        assert extract_tool_calls("openai", b"not json") == []


class TestBuildToolResult:
    def test_claude_tool_result(self) -> None:
        result = build_tool_result("claude", "toolu_1", {"status": "OK"})
        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "toolu_1"
        assert '"status"' in result["content"]

    def test_openai_tool_result(self) -> None:
        result = build_tool_result("openai", "call_1", {"status": "OK"})
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_1"
        assert '"status"' in result["content"]

    def test_xai_uses_openai_format(self) -> None:
        result = build_tool_result("xai", "call_2", {"data": "test"})
        assert result["role"] == "tool"
