"""Contract tests for llm_post_processors — evidence writing, output save, payload."""

from __future__ import annotations

from src.prj_kernel_api.llm_post_processors import (
    _sanitize_name,
    build_live_response_payload,
    truncate_output,
)


class TestSanitizeName:
    def test_basic(self) -> None:
        assert _sanitize_name("hello world") == "hello_world"

    def test_special_chars(self) -> None:
        result = _sanitize_name("req/123@test!")
        assert "/" not in result
        assert "@" not in result

    def test_empty(self) -> None:
        assert _sanitize_name("") == "item"

    def test_max_length(self) -> None:
        assert len(_sanitize_name("a" * 200)) <= 120


class TestTruncateOutput:
    def test_within_limit(self) -> None:
        preview, truncated = truncate_output("hello", max_chars=10)
        assert preview == "hello"
        assert truncated is False

    def test_over_limit(self) -> None:
        preview, truncated = truncate_output("hello world", max_chars=5)
        assert preview == "hello"
        assert truncated is True

    def test_zero_max_chars_with_text(self) -> None:
        preview, truncated = truncate_output("some text", max_chars=0)
        assert preview == ""
        assert truncated is True

    def test_zero_max_chars_empty(self) -> None:
        preview, truncated = truncate_output("", max_chars=0)
        assert preview == ""
        assert truncated is False


class TestBuildLiveResponsePayload:
    def test_basic_payload(self) -> None:
        payload = build_live_response_payload(
            provider_id="claude",
            model="claude-3-haiku",
            timeout_seconds=5.0,
            tls_cafile="/etc/ssl/cert.pem",
            http_status=200,
            elapsed_ms=150,
            error_type=None,
            error_detail=None,
            output_sha256="abc123",
            output_preview="Hello",
            output_truncated=False,
            output_full_path="/tmp/output.txt",
        )
        assert payload["provider_id"] == "claude"
        assert payload["model"] == "claude-3-haiku"
        assert payload["dry_run"] is False
        assert payload["api_key_present"] is True
        assert payload["http_status"] == 200
        assert payload["elapsed_ms"] == 150
        assert payload["nondeterministic"] is True
        assert payload["error_type"] is None

    def test_error_payload(self) -> None:
        payload = build_live_response_payload(
            provider_id="openai",
            model="gpt-4o",
            timeout_seconds=10.0,
            tls_cafile=None,
            http_status=429,
            elapsed_ms=50,
            error_type="HTTPError",
            error_detail="Rate limited",
            output_sha256="def456",
            output_preview="",
            output_truncated=False,
            output_full_path=None,
        )
        assert payload["http_status"] == 429
        assert payload["error_type"] == "HTTPError"
        assert payload["error_detail"] == "Rate limited"
