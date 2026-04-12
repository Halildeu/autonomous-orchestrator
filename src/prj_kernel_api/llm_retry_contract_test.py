"""Contract tests for llm_retry — exponential backoff + retryability."""

from __future__ import annotations

import pytest

from src.prj_kernel_api.llm_retry import (
    RETRYABLE_STATUS_CODES,
    NON_RETRYABLE_STATUS_CODES,
    LLMHTTPError,
    execute_with_retry,
)


class TestLLMHTTPError:
    def test_retryable_429(self) -> None:
        err = LLMHTTPError(429, b"rate limited", "openai")
        assert err.is_retryable is True

    def test_retryable_500(self) -> None:
        err = LLMHTTPError(500, b"server error", "claude")
        assert err.is_retryable is True

    def test_retryable_502(self) -> None:
        assert LLMHTTPError(502, b"", "google").is_retryable is True

    def test_retryable_503(self) -> None:
        assert LLMHTTPError(503, b"", "deepseek").is_retryable is True

    def test_non_retryable_400(self) -> None:
        assert LLMHTTPError(400, b"bad request", "openai").is_retryable is False

    def test_non_retryable_401(self) -> None:
        assert LLMHTTPError(401, b"unauthorized", "claude").is_retryable is False

    def test_non_retryable_403(self) -> None:
        assert LLMHTTPError(403, b"forbidden", "google").is_retryable is False

    def test_non_retryable_404(self) -> None:
        assert LLMHTTPError(404, b"not found", "xai").is_retryable is False


class TestExecuteWithRetry:
    def test_no_retry_success(self) -> None:
        """max_retries=0 should call fn once and return."""
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return {"status": "OK", "http_status": 200}
        result = execute_with_retry(fn, max_retries=0, provider_id="test", request_id="r1")
        assert result["status"] == "OK"
        assert call_count == 1

    def test_success_no_retry_needed(self) -> None:
        """Successful call should not trigger retries."""
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return {"status": "OK", "http_status": 200}
        result = execute_with_retry(fn, max_retries=3, provider_id="test", request_id="r2")
        assert result["status"] == "OK"
        assert call_count == 1

    def test_retry_then_success(self) -> None:
        """Retryable error followed by success."""
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"status": "FAIL", "http_status": 429, "resp_bytes": b"rate limited"}
            return {"status": "OK", "http_status": 200, "resp_bytes": b"ok"}
        result = execute_with_retry(fn, max_retries=3, provider_id="test", request_id="r3")
        assert result["status"] == "OK"
        assert call_count == 3  # 2 fails + 1 success

    def test_non_retryable_immediate_fail(self) -> None:
        """Non-retryable status (400) should fail immediately."""
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return {"status": "FAIL", "http_status": 400, "resp_bytes": b"bad request"}
        result = execute_with_retry(fn, max_retries=3, provider_id="test", request_id="r4")
        assert result["status"] == "FAIL"
        assert call_count == 1  # No retries for 400

    def test_retries_exhausted(self) -> None:
        """All retries fail."""
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return {"status": "FAIL", "http_status": 500, "resp_bytes": b"server error"}
        result = execute_with_retry(fn, max_retries=2, provider_id="test", request_id="r5")
        assert result["status"] == "FAIL"
        assert call_count == 3  # 1 initial + 2 retries

    def test_on_retry_callback(self) -> None:
        """on_retry callback should be called for each retry."""
        call_count = 0
        retry_log: list[int] = []
        def fn():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return {"status": "FAIL", "http_status": 429, "resp_bytes": b""}
            return {"status": "OK", "http_status": 200}
        def on_retry(attempt, wait, exc):
            retry_log.append(attempt)
        result = execute_with_retry(
            fn, max_retries=2, provider_id="test", request_id="r6",
            on_retry=on_retry,
        )
        assert result["status"] == "OK"
        assert len(retry_log) == 1

    def test_ok_200_no_retry(self) -> None:
        """HTTP 200 with status OK should never retry."""
        def fn():
            return {"status": "OK", "http_status": 200}
        result = execute_with_retry(fn, max_retries=3, provider_id="test", request_id="r7")
        assert result["status"] == "OK"
