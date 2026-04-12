"""Contract tests for rate_limiter — token bucket rate limiting."""

from __future__ import annotations

import time

from src.prj_kernel_api.rate_limiter import (
    TokenBucketRateLimiter,
    get_rate_limiter,
    reset_all,
)


class TestTokenBucketRateLimiter:
    def test_first_acquire_succeeds(self) -> None:
        rl = TokenBucketRateLimiter(rps=10.0)
        assert rl.acquire(timeout_s=0.1) is True

    def test_try_acquire_succeeds(self) -> None:
        rl = TokenBucketRateLimiter(rps=10.0)
        assert rl.try_acquire() is True

    def test_exhaust_then_fail(self) -> None:
        rl = TokenBucketRateLimiter(rps=1.0)
        # First should succeed (1 initial token)
        assert rl.try_acquire() is True
        # Second should fail (no tokens left)
        assert rl.try_acquire() is False

    def test_refill_after_wait(self) -> None:
        rl = TokenBucketRateLimiter(rps=10.0)
        # Drain tokens
        while rl.try_acquire():
            pass
        # Wait for refill
        time.sleep(0.15)
        assert rl.try_acquire() is True

    def test_acquire_with_timeout(self) -> None:
        rl = TokenBucketRateLimiter(rps=1.0)
        rl.try_acquire()  # drain
        # Should eventually succeed within 2 seconds
        assert rl.acquire(timeout_s=2.0) is True

    def test_acquire_timeout_exceeded(self) -> None:
        rl = TokenBucketRateLimiter(rps=0.5)
        rl.try_acquire()  # drain
        rl.try_acquire()  # extra drain
        # Very short timeout — should fail
        assert rl.acquire(timeout_s=0.05) is False


class TestRateLimiterRegistry:
    def setup_method(self) -> None:
        reset_all()

    def test_get_creates_new(self) -> None:
        rl = get_rate_limiter("provider_a", 5.0)
        assert rl is not None

    def test_get_returns_same(self) -> None:
        rl1 = get_rate_limiter("provider_b", 5.0)
        rl2 = get_rate_limiter("provider_b", 5.0)
        assert rl1 is rl2

    def test_isolation(self) -> None:
        rl_a = get_rate_limiter("a", 1.0)
        rl_b = get_rate_limiter("b", 1.0)
        rl_a.try_acquire()
        assert rl_b.try_acquire() is True  # b not affected by a
