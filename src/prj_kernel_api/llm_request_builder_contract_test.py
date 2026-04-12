"""Contract tests for llm_request_builder — provider-native request building."""

from __future__ import annotations

import json

from src.prj_kernel_api.llm_request_builder import (
    build_live_request,
    to_anthropic_messages,
)


class TestToAnthropicMessages:
    def test_system_extracted(self) -> None:
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        system, out = to_anthropic_messages(msgs)
        assert system == "You are helpful."
        assert len(out) == 1
        assert out[0]["role"] == "user"

    def test_no_system(self) -> None:
        msgs = [{"role": "user", "content": "Hello"}]
        system, out = to_anthropic_messages(msgs)
        assert system is None
        assert len(out) == 1

    def test_developer_role_as_system(self) -> None:
        msgs = [{"role": "developer", "content": "System instructions"}]
        system, out = to_anthropic_messages(msgs)
        assert system == "System instructions"
        assert len(out) == 0

    def test_unknown_role_becomes_user(self) -> None:
        msgs = [{"role": "tool", "content": "data"}]
        _, out = to_anthropic_messages(msgs)
        assert out[0]["role"] == "user"

    def test_content_block_format(self) -> None:
        msgs = [{"role": "user", "content": "Hi"}]
        _, out = to_anthropic_messages(msgs)
        assert out[0]["content"] == [{"type": "text", "text": "Hi"}]


class TestBuildLiveRequest:
    def test_claude_request(self) -> None:
        result = build_live_request(
            provider_id="claude",
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-test",
            temperature=0.5,
            max_tokens=100,
        )
        assert result["headers"]["x-api-key"] == "sk-test"
        assert result["headers"]["anthropic-version"] == "2023-06-01"
        body = json.loads(result["body_bytes"])
        assert body["model"] == "claude-3-haiku-20240307"
        assert body["max_tokens"] == 100
        assert body["temperature"] == 0.5

    def test_openai_request(self) -> None:
        result = build_live_request(
            provider_id="openai",
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
        )
        assert result["headers"]["Authorization"] == "Bearer sk-test"
        body = json.loads(result["body_bytes"])
        assert body["model"] == "gpt-4o-mini"

    def test_xai_user_agent(self) -> None:
        result = build_live_request(
            provider_id="xai",
            model="grok-4-latest",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.x.ai/v1/chat/completions",
            api_key="xai-test",
        )
        assert "User-Agent" in result["headers"]
        assert result["headers"]["Accept"] == "application/json"

    def test_response_format_claude(self) -> None:
        result = build_live_request(
            provider_id="claude",
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-test",
            response_format={"type": "json_object"},
        )
        body = json.loads(result["body_bytes"])
        assert body["response_format"] == {"type": "json_object"}

    def test_response_format_openai(self) -> None:
        result = build_live_request(
            provider_id="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            response_format={"type": "json_schema", "json_schema": {"name": "r", "schema": {}}},
        )
        body = json.loads(result["body_bytes"])
        assert body["response_format"]["type"] == "json_schema"

    def test_tools_included(self) -> None:
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        result = build_live_request(
            provider_id="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            tools=tools,
            tool_choice="auto",
        )
        body = json.loads(result["body_bytes"])
        assert body["tools"] == tools
        assert body["tool_choice"] == "auto"

    def test_no_optional_params(self) -> None:
        result = build_live_request(
            provider_id="deepseek",
            model="deepseek-chat",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.deepseek.com/v1/chat/completions",
            api_key="sk-test",
        )
        body = json.loads(result["body_bytes"])
        assert "response_format" not in body
        assert "tools" not in body
        assert "tool_choice" not in body
        assert "temperature" not in body

    def test_claude_default_max_tokens(self) -> None:
        result = build_live_request(
            provider_id="claude",
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-test",
        )
        body = json.loads(result["body_bytes"])
        assert body["max_tokens"] == 256
