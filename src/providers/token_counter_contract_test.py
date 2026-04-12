"""Contract tests for token_counter — multi-provider counting + budget tracking."""

from __future__ import annotations

from src.providers.token_counter import (
    UsageRecord,
    UsageTracker,
    count_tokens,
    count_tokens_heuristic,
    count_tokens_tiktoken,
)

SAMPLE_MESSAGES = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello, how are you?"},
]


class TestCountTokensHeuristic:
    def test_basic_estimate(self) -> None:
        result = count_tokens_heuristic(SAMPLE_MESSAGES)
        assert result > 0
        assert isinstance(result, int)

    def test_empty_messages(self) -> None:
        result = count_tokens_heuristic([])
        assert result >= 1  # min 1

    def test_long_message(self) -> None:
        msgs = [{"role": "user", "content": "a" * 4000}]
        result = count_tokens_heuristic(msgs)
        assert result >= 1000  # ~4000/4 + overhead

    def test_list_content(self) -> None:
        msgs = [{"role": "user", "content": [{"type": "text", "text": "hello world"}]}]
        result = count_tokens_heuristic(msgs)
        assert result > 0


class TestCountTokensTiktoken:
    def test_gpt4o_count(self) -> None:
        result = count_tokens_tiktoken(SAMPLE_MESSAGES, "gpt-4o")
        if result is not None:  # tiktoken may not be installed
            assert result > 0
            assert isinstance(result, int)

    def test_unknown_model_fallback(self) -> None:
        result = count_tokens_tiktoken(SAMPLE_MESSAGES, "unknown-model-xyz")
        if result is not None:
            assert result > 0  # falls back to cl100k_base

    def test_empty_messages(self) -> None:
        result = count_tokens_tiktoken([], "gpt-4o")
        if result is not None:
            assert result >= 2  # reply priming tokens


class TestCountTokens:
    def test_openai_uses_tiktoken(self) -> None:
        result = count_tokens(SAMPLE_MESSAGES, provider_id="openai", model="gpt-4o")
        assert result["estimated_tokens"] > 0
        # If tiktoken installed: method=tiktoken, is_exact=True
        # If not: method=heuristic, is_exact=False
        assert result["method"] in ("tiktoken", "heuristic")

    def test_claude_uses_heuristic(self) -> None:
        result = count_tokens(SAMPLE_MESSAGES, provider_id="claude", model="claude-sonnet-4")
        assert result["method"] == "heuristic"
        assert result["is_exact"] is False

    def test_deepseek_uses_heuristic(self) -> None:
        result = count_tokens(SAMPLE_MESSAGES, provider_id="deepseek", model="deepseek-chat")
        assert result["method"] == "heuristic"

    def test_result_shape(self) -> None:
        result = count_tokens(SAMPLE_MESSAGES, provider_id="openai", model="gpt-4o")
        assert "estimated_tokens" in result
        assert "method" in result
        assert "model" in result
        assert "is_exact" in result


class TestUsageRecord:
    def test_creation(self) -> None:
        rec = UsageRecord("claude", "claude-sonnet-4", 100, 50, 0.001)
        assert rec.provider_id == "claude"
        assert rec.input_tokens == 100
        assert rec.timestamp  # auto-filled

    def test_to_dict(self) -> None:
        rec = UsageRecord("openai", "gpt-4o", 200, 100, 0.005)
        d = rec.to_dict()
        assert d["provider_id"] == "openai"
        assert d["input_tokens"] == 200
        assert d["output_tokens"] == 100


class TestUsageTracker:
    def test_unlimited_budget(self) -> None:
        tracker = UsageTracker(max_tokens_per_run=0)
        ok, remaining = tracker.check_budget(10000)
        assert ok is True
        assert remaining == -1

    def test_budget_check_pass(self) -> None:
        tracker = UsageTracker(max_tokens_per_run=1000)
        ok, remaining = tracker.check_budget(500)
        assert ok is True
        assert remaining == 1000

    def test_budget_check_fail(self) -> None:
        tracker = UsageTracker(max_tokens_per_run=100)
        ok, remaining = tracker.check_budget(200)
        assert ok is False
        assert remaining == 100

    def test_budget_after_usage(self) -> None:
        tracker = UsageTracker(max_tokens_per_run=1000)
        tracker.record(UsageRecord("openai", "gpt-4o", 400, 100))
        ok, remaining = tracker.check_budget(600)
        assert ok is False  # 500 used, 500 remaining < 600
        assert remaining == 500

    def test_record_multiple(self) -> None:
        tracker = UsageTracker()
        tracker.record(UsageRecord("claude", "sonnet", 100, 50, 0.001))
        tracker.record(UsageRecord("openai", "gpt-4o", 200, 100, 0.005))
        summary = tracker.summary()
        assert summary["actual_total_tokens"] == 450
        assert summary["call_count"] == 2
        assert summary["estimated_cost_usd"] == 0.006

    def test_summary_shape(self) -> None:
        tracker = UsageTracker(max_tokens_per_run=5000)
        summary = tracker.summary()
        assert "estimated_total_tokens" in summary
        assert "actual_total_tokens" in summary
        assert "estimated_cost_usd" in summary
        assert "call_count" in summary
        assert "max_tokens_per_run" in summary
        assert "budget_remaining" in summary

    def test_estimate_tracking(self) -> None:
        tracker = UsageTracker()
        tracker.record_estimate(500)
        tracker.record_estimate(300)
        summary = tracker.summary()
        assert summary["estimated_total_tokens"] == 800
