"""Contract tests for PR4b — capability-aware request building + multi-modal normalization."""

from __future__ import annotations

import json

from src.prj_kernel_api.llm_request_builder import (
    build_embeddings_request,
    build_moderation_request,
    check_capabilities_before_request,
)
from src.prj_kernel_api.llm_response_normalizer import (
    extract_embeddings,
    extract_moderation,
    normalize_response,
)


class TestCapabilityCheck:
    def test_chat_only_passes(self) -> None:
        ok, pid, missing = check_capabilities_before_request(
            provider_id="claude", model="claude-sonnet-4-20250514",
        )
        assert ok is True
        assert missing == []

    def test_tools_check_for_unsupported(self) -> None:
        # Claude registry shows tool_use=unsupported
        ok, pid, missing = check_capabilities_before_request(
            provider_id="claude", model="claude-sonnet-4-20250514", has_tools=True,
        )
        assert ok is False
        assert "tool_use" in missing

    def test_openai_batch_supported(self) -> None:
        ok, pid, missing = check_capabilities_before_request(
            provider_id="openai", model="gpt-4o",
        )
        assert ok is True

    def test_unknown_provider_fails(self) -> None:
        ok, pid, missing = check_capabilities_before_request(
            provider_id="unknown", model="model-x",
        )
        assert ok is False
        assert "chat" in missing


class TestBuildEmbeddingsRequest:
    def test_google_embeddings(self) -> None:
        req = build_embeddings_request(
            provider_id="google",
            model="text-embedding-004",
            input_text="hello world",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key="test-key",
        )
        assert "embedContent" in req["url"]
        assert req["headers"]["x-goog-api-key"] == "test-key"
        body = json.loads(req["body_bytes"])
        assert body["taskType"] == "SEMANTIC_SIMILARITY"

    def test_openai_embeddings(self) -> None:
        req = build_embeddings_request(
            provider_id="openai",
            model="text-embedding-3-small",
            input_text="hello world",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
        )
        assert req["url"].endswith("/embeddings")
        body = json.loads(req["body_bytes"])
        assert body["model"] == "text-embedding-3-small"
        assert body["input"] == "hello world"


class TestBuildModerationRequest:
    def test_moderation_request(self) -> None:
        req = build_moderation_request(
            provider_id="openai",
            input_text="test content",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
        )
        assert req["url"].endswith("/moderations")
        body = json.loads(req["body_bytes"])
        assert body["input"] == "test content"


class TestExtractEmbeddings:
    def test_google_embedding(self) -> None:
        resp = json.dumps({
            "embedding": {"values": [0.1, 0.2, 0.3]},
        }).encode()
        result = extract_embeddings(resp, provider_id="google")
        assert result == [0.1, 0.2, 0.3]

    def test_openai_embedding(self) -> None:
        resp = json.dumps({
            "data": [{"embedding": [0.4, 0.5, 0.6], "index": 0}],
        }).encode()
        result = extract_embeddings(resp, provider_id="openai")
        assert result == [0.4, 0.5, 0.6]

    def test_no_embedding(self) -> None:
        resp = json.dumps({"content": "no embedding"}).encode()
        assert extract_embeddings(resp, provider_id="openai") is None

    def test_empty_bytes(self) -> None:
        assert extract_embeddings(b"", provider_id="google") is None


class TestExtractModeration:
    def test_flagged(self) -> None:
        resp = json.dumps({
            "results": [{"flagged": True, "categories": {"hate": True}, "category_scores": {"hate": 0.9}}],
        }).encode()
        result = extract_moderation(resp)
        assert result is not None
        assert result["flagged"] is True
        assert result["categories"]["hate"] is True

    def test_not_flagged(self) -> None:
        resp = json.dumps({
            "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
        }).encode()
        result = extract_moderation(resp)
        assert result is not None
        assert result["flagged"] is False

    def test_no_results(self) -> None:
        assert extract_moderation(json.dumps({}).encode()) is None


class TestNormalizeResponseWithToolCalls:
    def test_claude_with_tool_calls(self) -> None:
        resp = json.dumps({
            "content": [
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "t1", "name": "system-status", "input": {}},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }).encode()
        result = normalize_response(resp, provider_id="claude")
        assert result["text"] == "Let me check."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "system-status"
        assert result["usage"]["input_tokens"] == 10

    def test_no_tool_calls(self) -> None:
        resp = json.dumps({
            "content": [{"type": "text", "text": "Just text."}],
        }).encode()
        result = normalize_response(resp, provider_id="claude")
        assert result["tool_calls"] == []
