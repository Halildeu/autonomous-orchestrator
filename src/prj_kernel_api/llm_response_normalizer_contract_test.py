"""Contract tests for llm_response_normalizer — provider-agnostic response parsing."""

from __future__ import annotations

import json

from src.prj_kernel_api.llm_response_normalizer import (
    extract_llm_output_text,
    extract_usage,
    normalize_response,
)


class TestExtractLlmOutputText:
    def test_anthropic_messages(self) -> None:
        resp = json.dumps({
            "content": [{"type": "text", "text": "Hello world"}],
            "model": "claude-3-haiku",
        }).encode()
        assert extract_llm_output_text(resp) == "Hello world"

    def test_anthropic_multi_block(self) -> None:
        resp = json.dumps({
            "content": [
                {"type": "text", "text": "Part 1"},
                {"type": "text", "text": "Part 2"},
            ],
        }).encode()
        assert extract_llm_output_text(resp) == "Part 1\nPart 2"

    def test_openai_choices(self) -> None:
        resp = json.dumps({
            "choices": [{"message": {"content": "OpenAI response"}}],
        }).encode()
        assert extract_llm_output_text(resp) == "OpenAI response"

    def test_openai_choices_list_content(self) -> None:
        resp = json.dumps({
            "choices": [{"message": {"content": [{"type": "text", "text": "block"}]}}],
        }).encode()
        assert extract_llm_output_text(resp) == "block"

    def test_openai_responses_api(self) -> None:
        resp = json.dumps({
            "output": [{"content": [{"type": "text", "text": "Response API"}]}],
        }).encode()
        assert extract_llm_output_text(resp) == "Response API"

    def test_output_text_field(self) -> None:
        resp = json.dumps({"output_text": "Direct text"}).encode()
        assert extract_llm_output_text(resp) == "Direct text"

    def test_fallback_raw_text(self) -> None:
        assert extract_llm_output_text(b"raw text") == "raw text"

    def test_empty_bytes(self) -> None:
        assert extract_llm_output_text(b"") == ""

    def test_non_dict_json(self) -> None:
        resp = json.dumps(["array"]).encode()
        assert extract_llm_output_text(resp) == '["array"]'

    def test_invalid_json(self) -> None:
        assert extract_llm_output_text(b"not json") == "not json"


class TestExtractUsage:
    def test_anthropic_usage(self) -> None:
        resp = json.dumps({
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }).encode()
        usage = extract_usage(resp)
        assert usage is not None
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20

    def test_openai_usage(self) -> None:
        resp = json.dumps({
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        }).encode()
        usage = extract_usage(resp)
        assert usage is not None
        assert usage["input_tokens"] == 15
        assert usage["output_tokens"] == 25

    def test_no_usage(self) -> None:
        resp = json.dumps({"content": [{"type": "text", "text": "hi"}]}).encode()
        assert extract_usage(resp) is None

    def test_empty_bytes(self) -> None:
        assert extract_usage(b"") is None


class TestNormalizeResponse:
    def test_full_normalization(self) -> None:
        resp = json.dumps({
            "content": [{"type": "text", "text": "Normalized"}],
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }).encode()
        result = normalize_response(resp, provider_id="claude")
        assert result["text"] == "Normalized"
        assert result["usage"]["input_tokens"] == 5
        assert result["provider_id"] == "claude"
        assert result["raw_json"] is not None

    def test_raw_text_fallback(self) -> None:
        result = normalize_response(b"plain text", provider_id="openai")
        assert result["text"] == "plain text"
        assert result["usage"] is None
        assert result["raw_json"] is None
