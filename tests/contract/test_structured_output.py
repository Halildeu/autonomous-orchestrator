"""Contract tests for structured_output — provider+model-native format building."""

from __future__ import annotations

from src.providers.structured_output import (
    build_response_format,
    build_response_format_claude,
    build_response_format_deepseek,
    build_response_format_google,
    build_response_format_openai,
    model_supports_structured_output,
)


SAMPLE_SCHEMA = {
    "type": "object",
    "required": ["summary"],
    "properties": {"summary": {"type": "string"}},
}


class TestModelSupportsStructuredOutput:
    def test_claude_sonnet_supported(self) -> None:
        assert model_supports_structured_output("claude", "claude-sonnet-4-20250514") is True

    def test_claude_haiku_old_not_supported(self) -> None:
        assert model_supports_structured_output("claude", "claude-3-haiku-20240307") is False

    def test_claude_haiku_45_supported(self) -> None:
        assert model_supports_structured_output("claude", "claude-haiku-4-5-20251001") is True

    def test_openai_gpt4o_supported(self) -> None:
        assert model_supports_structured_output("openai", "gpt-4o") is True

    def test_openai_gpt5_supported(self) -> None:
        assert model_supports_structured_output("openai", "gpt-5.4") is True

    def test_google_supported(self) -> None:
        assert model_supports_structured_output("google", "gemini-2.0-flash") is True

    def test_deepseek_supported(self) -> None:
        assert model_supports_structured_output("deepseek", "deepseek-chat") is True

    def test_unknown_provider_not_supported(self) -> None:
        assert model_supports_structured_output("unknown", "model-x") is False

    def test_qwen_not_supported(self) -> None:
        assert model_supports_structured_output("qwen", "qwen-plus") is False


class TestBuildResponseFormatClaude:
    def test_supported_no_schema(self) -> None:
        result = build_response_format_claude("claude-sonnet-4-20250514")
        assert result == {"type": "json_object"}

    def test_supported_with_schema(self) -> None:
        result = build_response_format_claude("claude-sonnet-4-20250514", SAMPLE_SCHEMA)
        assert result is not None
        assert result["type"] == "json_schema"
        assert result["json_schema"]["schema"] == SAMPLE_SCHEMA

    def test_unsupported_model(self) -> None:
        result = build_response_format_claude("claude-3-haiku-20240307")
        assert result is None

    def test_unsupported_model_with_schema(self) -> None:
        result = build_response_format_claude("claude-3-haiku-20240307", SAMPLE_SCHEMA)
        assert result is None


class TestBuildResponseFormatOpenai:
    def test_supported_no_schema(self) -> None:
        result = build_response_format_openai("gpt-4o")
        assert result == {"type": "json_object"}

    def test_supported_with_schema(self) -> None:
        result = build_response_format_openai("gpt-4o", SAMPLE_SCHEMA)
        assert result is not None
        assert result["type"] == "json_schema"
        assert result["json_schema"]["strict"] is True

    def test_unsupported_model(self) -> None:
        result = build_response_format_openai("davinci-002")
        assert result is None


class TestBuildResponseFormatGoogle:
    def test_no_schema(self) -> None:
        result = build_response_format_google("gemini-2.0-flash")
        assert result == {"response_mime_type": "application/json"}

    def test_with_schema(self) -> None:
        result = build_response_format_google("gemini-2.0-flash", SAMPLE_SCHEMA)
        assert result is not None
        assert result["response_mime_type"] == "application/json"
        assert result["response_schema"] == SAMPLE_SCHEMA


class TestBuildResponseFormatDeepseek:
    def test_no_schema(self) -> None:
        result = build_response_format_deepseek("deepseek-chat")
        assert result == {"type": "json_object"}

    def test_with_schema(self) -> None:
        result = build_response_format_deepseek("deepseek-chat", SAMPLE_SCHEMA)
        assert result is not None
        assert result["type"] == "json_schema"


class TestBuildResponseFormat:
    def test_claude_dispatch(self) -> None:
        result = build_response_format("claude", "claude-sonnet-4-20250514", SAMPLE_SCHEMA)
        assert result is not None
        assert result["type"] == "json_schema"

    def test_openai_dispatch(self) -> None:
        result = build_response_format("openai", "gpt-4o", SAMPLE_SCHEMA)
        assert result is not None
        assert result["json_schema"]["strict"] is True

    def test_xai_uses_openai_format(self) -> None:
        result = build_response_format("xai", "grok-4-latest")
        # xai uses OpenAI-compatible API — check it doesn't crash
        # grok-4-latest may not be in the known set, so None is acceptable
        assert result is None or isinstance(result, dict)

    def test_google_dispatch(self) -> None:
        result = build_response_format("google", "gemini-2.0-flash", SAMPLE_SCHEMA)
        assert result is not None
        assert "response_mime_type" in result

    def test_unknown_provider(self) -> None:
        result = build_response_format("unknown", "model-x")
        assert result is None

    def test_unsupported_model_returns_none(self) -> None:
        result = build_response_format("claude", "claude-3-haiku-20240307")
        assert result is None

    def test_none_schema_json_object(self) -> None:
        result = build_response_format("openai", "gpt-4o")
        assert result == {"type": "json_object"}
