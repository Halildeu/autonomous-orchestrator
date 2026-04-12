"""Contract tests for llm_transport — HTTP execution, TLS, error classification."""

from __future__ import annotations

from src.prj_kernel_api.llm_transport import (
    bucket_elapsed_ms,
    redact_secrets,
    sha256_hex,
)


class TestBucketElapsedMs:
    def test_rounds_to_10(self) -> None:
        assert bucket_elapsed_ms(14.0) == 10
        assert bucket_elapsed_ms(15.0) == 20
        assert bucket_elapsed_ms(0.0) == 0

    def test_large_values(self) -> None:
        assert bucket_elapsed_ms(1234.5) == 1230


class TestSha256Hex:
    def test_empty(self) -> None:
        result = sha256_hex(b"")
        assert len(result) == 64
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_deterministic(self) -> None:
        assert sha256_hex(b"hello") == sha256_hex(b"hello")

    def test_different_inputs(self) -> None:
        assert sha256_hex(b"a") != sha256_hex(b"b")


class TestRedactSecrets:
    def test_no_env(self) -> None:
        result = redact_secrets("some error text")
        assert result == "some error text"

    def test_empty_string(self) -> None:
        assert redact_secrets("") == ""
