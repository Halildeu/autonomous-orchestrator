"""Contract tests for circuit_breaker — state transitions + thread safety."""

from __future__ import annotations

import threading
import time

from src.prj_kernel_api.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitState,
    ProviderCircuitBreaker,
    get_circuit_breaker,
    reset_all,
)


class TestCircuitBreakerStates:
    def setup_method(self) -> None:
        reset_all()

    def test_initial_state_closed(self) -> None:
        cb = ProviderCircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_closed_allows_request(self) -> None:
        cb = ProviderCircuitBreaker("test")
        allowed, reason = cb.allow_request()
        assert allowed is True
        assert reason == "circuit_closed"

    def test_open_after_threshold(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout_seconds=60.0)
        cb = ProviderCircuitBreaker("test", config)
        for _ in range(3):
            cb.record_failure(Exception("test"))
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_request(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        cb.record_failure(Exception("2"))
        allowed, reason = cb.allow_request()
        assert allowed is False
        assert reason == "circuit_open"

    def test_half_open_after_recovery_timeout(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.1)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_one_test_call(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.1, half_open_max_calls=1)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        time.sleep(0.15)
        allowed1, reason1 = cb.allow_request()
        assert allowed1 is True
        assert reason1 == "circuit_half_open_test"
        allowed2, reason2 = cb.allow_request()
        assert allowed2 is False
        assert reason2 == "circuit_half_open_limit"

    def test_half_open_success_closes(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.1)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        time.sleep(0.15)
        cb.allow_request()  # half_open test call
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.1)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        time.sleep(0.15)
        cb.allow_request()  # half_open
        cb.record_failure(Exception("2"))
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        cb.record_failure(Exception("2"))
        cb.record_success()
        cb.record_failure(Exception("3"))
        assert cb.state == CircuitState.CLOSED  # Reset by success

    def test_status_dict(self) -> None:
        cb = ProviderCircuitBreaker("test")
        status = cb.status_dict()
        assert status["provider_id"] == "test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    def test_reset(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = ProviderCircuitBreaker("test", config)
        cb.record_failure(Exception("1"))
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    def setup_method(self) -> None:
        reset_all()

    def test_get_creates_new(self) -> None:
        cb = get_circuit_breaker("provider_a")
        assert cb.provider_id == "provider_a"

    def test_get_returns_same(self) -> None:
        cb1 = get_circuit_breaker("provider_b")
        cb2 = get_circuit_breaker("provider_b")
        assert cb1 is cb2

    def test_isolation_between_providers(self) -> None:
        cb_a = get_circuit_breaker("a", CircuitBreakerConfig(failure_threshold=1))
        cb_b = get_circuit_breaker("b", CircuitBreakerConfig(failure_threshold=1))
        cb_a.record_failure(Exception("1"))
        assert cb_a.state == CircuitState.OPEN
        assert cb_b.state == CircuitState.CLOSED


class TestCircuitBreakerThreadSafety:
    def test_concurrent_failures(self) -> None:
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = ProviderCircuitBreaker("concurrent", config)
        errors = []

        def fail_n_times(n: int) -> None:
            try:
                for _ in range(n):
                    cb.record_failure(Exception("concurrent"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail_n_times, args=(5,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        status = cb.status_dict()
        assert status["failure_count"] == 20  # 4 threads × 5 failures
        assert status["state"] == "open"  # 20 >= threshold 10
