"""
Comprehensive test suite for exponential backoff retry logic.

Test coverage includes:
- Exponential backoff calculation and validation
- Jitter application and bounds checking
- Circuit breaker state machine
- Retry executor with configurable strategies
- Error recovery and metrics tracking
- Configuration loading from TOML
- Edge cases and error conditions

Target coverage: ≥85%
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "advanced"))

from adb_retry_configurable import (
    BackoffConfig,
    ActionRetryStrategy,
    RetryMetrics,
    CircuitBreakerState,
    ExponentialBackoffEngine,
    CircuitBreaker,
    RetryExecutor,
    ConfigLoader,
    OutputFormatter,
)


# ============================================================================
# SECTION 1: EXPONENTIAL BACKOFF TESTS
# ============================================================================

class TestExponentialBackoffCalculation:
    """Test exponential backoff delay calculations."""

    def test_first_attempt_is_immediate(self):
        """First attempt should have zero delay."""
        config = BackoffConfig(jitter_enabled=False)
        engine = ExponentialBackoffEngine(config)

        delay = engine.calculate_delay(0)
        assert delay == 0, "First attempt should be immediate"

    def test_exponential_growth(self):
        """Verify exponential growth pattern: 1s, 2s, 4s, 8s, 16s, 20s."""
        config = BackoffConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=20.0,
            backoff_multiplier=2.0,
            jitter_enabled=False
        )
        engine = ExponentialBackoffEngine(config)

        expected = [0, 1.0, 2.0, 4.0, 8.0, 16.0, 20.0]
        for attempt, expected_delay in enumerate(expected):
            delay = engine.calculate_delay(attempt)
            assert delay == expected_delay, f"Attempt {attempt} should be {expected_delay}s, got {delay}s"

    def test_max_delay_capping(self):
        """Verify max_delay ceiling is enforced."""
        config = BackoffConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=10.0,
            backoff_multiplier=2.0,
            jitter_enabled=False
        )
        engine = ExponentialBackoffEngine(config)

        # Attempt 5 would be 32s without cap
        delay = engine.calculate_delay(5)
        assert delay <= 10.0, f"Delay {delay}s exceeds max {config.max_delay_seconds}s"
        assert delay == 10.0, "Should be capped at max_delay"

    def test_custom_base_delay(self):
        """Verify custom base delay is applied correctly."""
        config = BackoffConfig(
            base_delay_seconds=0.5,
            max_delay_seconds=20.0,
            backoff_multiplier=2.0,
            jitter_enabled=False
        )
        engine = ExponentialBackoffEngine(config)

        delays = [engine.calculate_delay(i) for i in range(5)]
        expected = [0, 0.5, 1.0, 2.0, 4.0]
        assert delays == expected, f"Expected {expected}, got {delays}"

    def test_custom_multiplier(self):
        """Verify custom backoff multiplier is applied."""
        config = BackoffConfig(
            base_delay_seconds=1.0,
            backoff_multiplier=3.0,
            jitter_enabled=False
        )
        engine = ExponentialBackoffEngine(config)

        delays = [engine.calculate_delay(i) for i in range(4)]
        # 0, 1*3^1=3, 1*3^2=9, 1*3^3=27 (but capped at 20)
        expected = [0, 3.0, 9.0, 20.0]
        assert delays == expected, f"Expected {expected}, got {delays}"


# ============================================================================
# SECTION 2: JITTER TESTS
# ============================================================================

class TestJitterApplication:
    """Test jitter randomization for preventing thundering herd."""

    def test_jitter_disabled_is_deterministic(self):
        """Without jitter, same input should give same output."""
        config = BackoffConfig(jitter_enabled=False)
        engine = ExponentialBackoffEngine(config)

        delays = [engine.calculate_delay(3) for _ in range(10)]
        assert all(d == delays[0] for d in delays), "Without jitter, delays should be identical"

    def test_jitter_enabled_adds_randomness(self):
        """With jitter enabled, outputs should vary."""
        config = BackoffConfig(jitter_enabled=True, jitter_factor=0.1)
        engine = ExponentialBackoffEngine(config)

        delays = [engine.calculate_delay(3) for _ in range(100)]
        # Should have some variance
        assert len(set(delays)) > 1, "Jitter should produce different values"

    def test_jitter_bounds(self):
        """Jitter should stay within expected bounds."""
        config = BackoffConfig(
            base_delay_seconds=1.0,
            jitter_enabled=True,
            jitter_factor=0.1
        )
        engine = ExponentialBackoffEngine(config)

        # Attempt 3 has base delay of 8s
        base_delay = 8.0
        min_expected = base_delay * (1 - 0.1)  # 7.2s
        max_expected = base_delay * (1 + 0.1)  # 8.8s

        for _ in range(100):
            delay = engine.calculate_delay(3)
            assert min_expected <= delay <= max_expected, \
                f"Delay {delay}s outside bounds [{min_expected}, {max_expected}]"

    def test_jitter_factor_effect(self):
        """Larger jitter factor should produce larger variance."""
        config_small = BackoffConfig(jitter_enabled=True, jitter_factor=0.05)
        config_large = BackoffConfig(jitter_enabled=True, jitter_factor=0.2)

        engine_small = ExponentialBackoffEngine(config_small)
        engine_large = ExponentialBackoffEngine(config_large)

        # Get ranges
        small_delays = [engine_small.calculate_delay(3) for _ in range(100)]
        large_delays = [engine_large.calculate_delay(3) for _ in range(100)]

        small_range = max(small_delays) - min(small_delays)
        large_range = max(large_delays) - min(large_delays)

        assert large_range > small_range, "Larger jitter factor should produce larger range"


# ============================================================================
# SECTION 3: BACKOFF SEQUENCE TESTS
# ============================================================================

class TestBackoffSequence:
    """Test complete backoff sequences."""

    def test_sequence_generation(self):
        """Test generating complete backoff sequence."""
        config = BackoffConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=20.0,
            jitter_enabled=False
        )
        engine = ExponentialBackoffEngine(config)

        sequence = engine.get_backoff_sequence(7)
        expected = [0, 1.0, 2.0, 4.0, 8.0, 16.0, 20.0]
        assert sequence == expected, f"Expected {expected}, got {sequence}"

    def test_sequence_length(self):
        """Verify sequence has correct length."""
        config = BackoffConfig()
        engine = ExponentialBackoffEngine(config)

        for length in [1, 3, 5, 10]:
            sequence = engine.get_backoff_sequence(length)
            assert len(sequence) == length, f"Expected length {length}, got {len(sequence)}"

    def test_sequence_cumulative_time(self):
        """Test total time for complete retry sequence."""
        config = BackoffConfig(jitter_enabled=False)
        engine = ExponentialBackoffEngine(config)

        sequence = engine.get_backoff_sequence(7)
        total_time = sum(sequence)

        # 0+1+2+4+8+16+20 = 51 seconds
        assert total_time == 51.0, f"Expected 51s total, got {total_time}s"


# ============================================================================
# SECTION 4: CIRCUIT BREAKER TESTS
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    def test_initial_state_closed(self):
        """Circuit should start in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.state.state == "CLOSED"
        assert breaker.state.is_healthy is True

    def test_transitions_to_open_on_failures(self):
        """Circuit should open after failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        for i in range(3):
            breaker.record_failure()

        assert breaker.state.state == "OPEN", "Should be OPEN after 3 failures"
        assert breaker.state.is_healthy is False

    def test_resets_on_success(self):
        """Success should reset failure count in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()

        assert breaker.state.failure_count == 0, "Failure count should reset on success"
        assert breaker.state.state == "CLOSED", "Should remain CLOSED"

    def test_half_open_recovery(self):
        """Circuit should transition through HALF_OPEN during recovery."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for testing
            success_threshold=2
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state.state == "OPEN"

        # Wait for recovery timeout
        time.sleep(0.15)

        # Check state (should transition to HALF_OPEN)
        state = breaker.check_state()
        assert state.state == "HALF_OPEN", "Should transition to HALF_OPEN"

        # Record successes
        breaker.record_success()
        breaker.record_success()
        assert breaker.state.state == "CLOSED", "Should close after successes in HALF_OPEN"
        assert breaker.state.is_healthy is True

    def test_failure_in_half_open_reopens(self):
        """Failure in HALF_OPEN should reopen circuit."""
        breaker = CircuitBreaker(failure_threshold=1)

        breaker.record_failure()
        breaker.state.state = "HALF_OPEN"

        breaker.record_failure()
        assert breaker.state.state == "OPEN", "Should reopen on failure in HALF_OPEN"

    def test_health_check_convenience_method(self):
        """is_healthy should reflect circuit state."""
        breaker = CircuitBreaker(failure_threshold=2)

        assert breaker.is_healthy is True, "Should be healthy initially"

        breaker.record_failure()
        breaker.record_failure()

        assert breaker.is_healthy is False, "Should be unhealthy when open"


# ============================================================================
# SECTION 5: RETRY EXECUTOR TESTS
# ============================================================================

class TestRetryExecutor:
    """Test retry executor with operations."""

    def test_successful_operation_first_attempt(self):
        """Operation succeeding on first attempt."""
        config = BackoffConfig()
        executor = RetryExecutor(config)

        operation = Mock(return_value=True)
        success, metrics = executor.execute_with_retry("test_action", operation)

        assert success is True
        assert metrics.attempts == 1
        assert metrics.total_delay_seconds == 0

    def test_operation_succeeds_after_retries(self):
        """Operation succeeding after multiple attempts."""
        config = BackoffConfig(jitter_enabled=False)
        executor = RetryExecutor(config)

        operation = Mock(side_effect=[False, False, True])
        success, metrics = executor.execute_with_retry("test_action", operation, max_attempts=5)

        assert success is True
        assert metrics.attempts == 3
        assert operation.call_count == 3

    def test_max_retries_exceeded(self):
        """Operation failing after max retries."""
        config = BackoffConfig(max_attempts=3)
        executor = RetryExecutor(config)

        operation = Mock(return_value=False)
        success, metrics = executor.execute_with_retry("test_action", operation)

        assert success is False
        assert metrics.attempts == 3
        assert metrics.success is False

    def test_exception_handling_and_retry(self):
        """Exceptions should trigger retry."""
        config = BackoffConfig(jitter_enabled=False)
        executor = RetryExecutor(config)

        operation = Mock(side_effect=[
            Exception("Network error"),
            Exception("Timeout"),
            True
        ])

        success, metrics = executor.execute_with_retry("test_action", operation)

        assert success is True
        assert metrics.attempts == 3
        assert len(metrics.errors) == 2

    def test_metrics_tracking(self):
        """Verify metrics are tracked correctly."""
        config = BackoffConfig(jitter_enabled=False)
        executor = RetryExecutor(config)

        operation = Mock(side_effect=[False, False, True])
        success, metrics = executor.execute_with_retry("test_action", operation)

        assert metrics.action == "test_action"
        assert metrics.success is True
        assert metrics.attempts == 3
        # Total delay = 0 + 1.0 = 1.0 (first retry waits 1s)
        assert metrics.total_delay_seconds > 0

    def test_circuit_breaker_integration(self):
        """Executor should respect circuit breaker state."""
        config = BackoffConfig()
        breaker = CircuitBreaker(failure_threshold=1)
        executor = RetryExecutor(config, breaker)

        # Open the circuit
        breaker.record_failure()

        operation = Mock(return_value=True)
        success, metrics = executor.execute_with_retry("test_action", operation)

        assert success is False
        assert "Circuit breaker is OPEN" in metrics.errors
        assert operation.call_count == 0  # Never attempted


# ============================================================================
# SECTION 6: CONFIGURATION TESTS
# ============================================================================

class TestConfigLoader:
    """Test configuration loading from TOML."""

    def test_create_backoff_config_defaults(self):
        """Test creating config with defaults."""
        config = ConfigLoader.create_backoff_config()

        assert config.enabled is True
        assert config.max_attempts == 5
        assert config.base_delay_seconds == 1.0
        assert config.jitter_enabled is True

    def test_create_backoff_config_custom(self):
        """Test creating config with custom values."""
        config = ConfigLoader.create_backoff_config(
            max_attempts=7,
            base_delay=0.5,
            max_delay=30.0,
            jitter=False
        )

        assert config.max_attempts == 7
        assert config.base_delay_seconds == 0.5
        assert config.max_delay_seconds == 30.0
        assert config.jitter_enabled is False

    @pytest.fixture
    def sample_toml_file(self, tmp_path):
        """Create a sample TOML config file."""
        config_content = """
[retry]
enabled = true
max_attempts = 5
base_delay_seconds = 1.0
max_delay_seconds = 20.0
jitter_enabled = true

[retry.strategies]
click = { max_attempts = 3, base_delay = 0.5 }
screenshot = { max_attempts = 2, base_delay = 0.2 }
wait_element = { max_attempts = 7, base_delay = 1.0, max_delay = 30.0 }
"""
        config_file = tmp_path / "test_config.toml"
        config_file.write_text(config_content)
        return config_file

    def test_load_from_toml(self, sample_toml_file):
        """Test loading configuration from TOML file."""
        config = ConfigLoader.load_from_toml(sample_toml_file)

        assert config["retry"]["enabled"] is True
        assert config["retry"]["max_attempts"] == 5
        assert "click" in config["retry"]["strategies"]

    def test_get_action_strategy(self, sample_toml_file):
        """Test extracting action-specific retry strategy."""
        config = ConfigLoader.load_from_toml(sample_toml_file)

        click_strategy = ConfigLoader.get_action_strategy(config, "click")
        assert click_strategy is not None
        assert click_strategy.action_type == "click"
        assert click_strategy.max_attempts == 3
        assert click_strategy.base_delay == 0.5

    def test_missing_config_file(self):
        """Test handling missing config file."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load_from_toml(Path("/nonexistent/config.toml"))

    def test_nonexistent_action_strategy(self, sample_toml_file):
        """Test requesting strategy for action not in config."""
        config = ConfigLoader.load_from_toml(sample_toml_file)

        strategy = ConfigLoader.get_action_strategy(config, "nonexistent")
        assert strategy is None


# ============================================================================
# SECTION 7: RETRY METRICS TESTS
# ============================================================================

class TestRetryMetrics:
    """Test metrics tracking and reporting."""

    def test_metrics_initialization(self):
        """Test creating metrics instance."""
        metrics = RetryMetrics(
            action="click",
            success=True,
            attempts=3,
            total_delay_seconds=1.5
        )

        assert metrics.action == "click"
        assert metrics.success is True
        assert metrics.attempts == 3
        assert len(metrics.errors) == 0

    def test_metrics_with_errors(self):
        """Test metrics with error tracking."""
        metrics = RetryMetrics(
            action="tap",
            success=False,
            attempts=3,
            total_delay_seconds=2.0,
            errors=["Timeout", "Device offline"]
        )

        assert len(metrics.errors) == 2
        assert metrics.errors[0] == "Timeout"

    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = RetryMetrics(
            action="screenshot",
            success=True,
            attempts=1,
            total_delay_seconds=0.0
        )

        metrics_dict = metrics.to_dict()
        assert isinstance(metrics_dict, dict)
        assert metrics_dict["action"] == "screenshot"
        assert metrics_dict["success"] is True

    def test_engine_statistics(self):
        """Test retry engine statistics collection."""
        config = BackoffConfig()
        engine = ExponentialBackoffEngine(config)

        # Record some operations
        engine.record_retry(RetryMetrics("action1", success=True, attempts=1, total_delay_seconds=0))
        engine.record_retry(RetryMetrics("action2", success=False, attempts=3, total_delay_seconds=3.0))
        engine.record_retry(RetryMetrics("action3", success=True, attempts=2, total_delay_seconds=1.0))

        stats = engine.get_statistics()
        assert stats["total_operations"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=0.01)

    def test_empty_statistics(self):
        """Test statistics with no recorded operations."""
        config = BackoffConfig()
        engine = ExponentialBackoffEngine(config)

        stats = engine.get_statistics()
        assert stats["total_operations"] == 0
        assert stats["success_rate"] == 0.0


# ============================================================================
# SECTION 8: INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_retry_flow_success(self):
        """Complete flow: operation, retry, success."""
        # Setup
        config = BackoffConfig(
            max_attempts=5,
            base_delay_seconds=0.01,  # Short for testing
            jitter_enabled=False
        )
        executor = RetryExecutor(config)

        # Simulate operation that fails twice then succeeds
        operation = Mock(side_effect=[False, False, True])

        # Execute
        success, metrics = executor.execute_with_retry("test_op", operation)

        # Verify
        assert success is True
        assert metrics.attempts == 3
        assert metrics.total_delay_seconds > 0

    def test_full_retry_flow_failure(self):
        """Complete flow: operation, all retries fail."""
        # Setup
        config = BackoffConfig(
            max_attempts=3,
            base_delay_seconds=0.01,
            jitter_enabled=False
        )
        executor = RetryExecutor(config)

        # Simulate always-failing operation
        operation = Mock(return_value=False)

        # Execute
        success, metrics = executor.execute_with_retry("test_op", operation)

        # Verify
        assert success is False
        assert metrics.attempts == 3

    def test_realistic_adb_scenario(self):
        """Realistic ADB scenario: occasional timeouts with recovery."""
        config = BackoffConfig(
            max_attempts=5,
            base_delay_seconds=0.01,
            jitter_enabled=False
        )
        breaker = CircuitBreaker(failure_threshold=5)
        executor = RetryExecutor(config, breaker)

        # Simulate ADB operation with occasional timeouts
        operation = Mock(side_effect=[
            Exception("Connection timeout"),
            Exception("Device busy"),
            True  # Success after retries
        ])

        success, metrics = executor.execute_with_retry(
            "adb_screenshot",
            operation,
            max_attempts=5
        )

        assert success is True
        assert metrics.attempts == 3
        assert len(metrics.errors) == 2

    def test_backoff_prevents_overwhelming_device(self):
        """Verify backoff provides sufficient delays between attempts."""
        config = BackoffConfig(
            base_delay_seconds=0.1,
            jitter_enabled=False
        )
        executor = RetryExecutor(config)

        operation = Mock(side_effect=[False, False, True])

        start_time = time.time()
        success, metrics = executor.execute_with_retry("test_op", operation)
        total_time = time.time() - start_time

        # Should have delays: 0 + 0.1 + 0.2 = 0.3 seconds
        assert total_time >= 0.3


# ============================================================================
# SECTION 9: EDGE CASES AND ERROR CONDITIONS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_base_delay(self):
        """Test behavior with zero base delay."""
        config = BackoffConfig(base_delay_seconds=0.0, jitter_enabled=False)
        engine = ExponentialBackoffEngine(config)

        delays = [engine.calculate_delay(i) for i in range(5)]
        assert all(d == 0 for d in delays), "Zero base delay should produce all zeros"

    def test_very_large_max_delay(self):
        """Test with very large max_delay cap."""
        config = BackoffConfig(max_delay_seconds=3600.0, jitter_enabled=False)
        engine = ExponentialBackoffEngine(config)

        delay = engine.calculate_delay(20)
        assert delay <= 3600.0, "Should not exceed max_delay"

    def test_single_attempt_max(self):
        """Test with max_attempts=1."""
        config = BackoffConfig(max_attempts=1)
        executor = RetryExecutor(config)

        operation = Mock(return_value=False)
        success, metrics = executor.execute_with_retry("test", operation)

        assert metrics.attempts == 1
        assert metrics.total_delay_seconds == 0

    def test_operation_raising_different_exceptions(self):
        """Test handling different exception types."""
        config = BackoffConfig(max_attempts=5, jitter_enabled=False)
        executor = RetryExecutor(config)

        operation = Mock(side_effect=[
            TimeoutError("Request timeout"),
            IOError("Device error"),
            RuntimeError("Unexpected error"),
            True
        ])

        success, metrics = executor.execute_with_retry("test", operation)

        assert success is True
        assert len(metrics.errors) == 3
        assert "TimeoutError" in str(metrics.errors[0]) or "Request timeout" in str(metrics.errors[0])

    def test_jitter_never_creates_negative_delay(self):
        """Verify jitter doesn't create negative delays."""
        config = BackoffConfig(
            base_delay_seconds=0.5,
            jitter_enabled=True,
            jitter_factor=0.5  # Large jitter
        )
        engine = ExponentialBackoffEngine(config)

        for _ in range(100):
            delay = engine.calculate_delay(1)
            assert delay >= 0, "Jitter should never create negative delays"


# ============================================================================
# SECTION 10: COVERAGE VERIFICATION
# ============================================================================

class TestCoverageRequirements:
    """Verify test coverage requirements are met."""

    def test_all_backoff_config_fields(self):
        """Ensure BackoffConfig is fully tested."""
        config = BackoffConfig(
            enabled=False,
            max_attempts=10,
            base_delay_seconds=2.0,
            max_delay_seconds=40.0,
            backoff_multiplier=3.0,
            jitter_enabled=False,
            jitter_factor=0.2
        )

        assert config.enabled is False
        assert config.max_attempts == 10

    def test_action_retry_strategy_creation(self):
        """Test ActionRetryStrategy instantiation."""
        strategy = ActionRetryStrategy(
            action_type="tap",
            max_attempts=5,
            base_delay=1.0,
            max_delay=20.0
        )

        assert strategy.action_type == "tap"
        assert strategy.max_attempts == 5

    def test_circuit_breaker_state_dict(self):
        """Test CircuitBreakerState conversion."""
        from dataclasses import asdict

        state = CircuitBreakerState(
            state="CLOSED",
            failure_count=0,
            is_healthy=True
        )

        state_dict = asdict(state)
        assert state_dict["state"] == "CLOSED"
        assert state_dict["failure_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
