# Module: Resilience Patterns for ADB Automation

**Level**: Advanced
**Prerequisites**: Module 1 (adb-fundamentals), Module 3 (game-automation)
**Estimated Learning Time**: 45-60 minutes
**Hands-On Practice**: 20-30 minutes

---

## Overview

Resilience patterns provide robust error recovery, retry strategies, and failure isolation for ADB automation. This module covers exponential backoff, circuit breaker patterns, health checks, and state management recovery.

---

## 1️⃣ Exponential Backoff Pattern

Exponential backoff prevents retry storms and gives devices time to recover from transient failures.

### Standard Pattern

```
Attempt 1: immediate (0s)
Attempt 2: 1s
Attempt 3: 2s
Attempt 4: 4s
Attempt 5: 8s
Attempt 6: 16s
Attempt 7: 20s (capped at 20s)
```

### Calculation

```python
def calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 20.0) -> float:
    """Calculate exponential backoff with ceiling."""
    if attempt == 0:
        return 0  # First attempt is immediate

    # Exponential: 2^(attempt-1) * base_delay
    delay = (2 ** (attempt - 1)) * base_delay

    # Cap at maximum
    return min(delay, max_delay)

# Example
for attempt in range(7):
    delay = calculate_backoff(attempt, base_delay=1.0, max_delay=20.0)
    print(f"Attempt {attempt}: delay={delay}s")
```

### With Jitter (Prevent Thundering Herd)

Jitter randomizes retry timing to prevent all clients retrying simultaneously after service recovery.

```python
import random
import math

def calculate_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    jitter_factor: float = 0.1
) -> float:
    """Calculate exponential backoff with jitter."""
    if attempt == 0:
        return 0

    # Base exponential delay
    delay = (2 ** (attempt - 1)) * base_delay
    delay = min(delay, max_delay)

    # Add jitter: +/- jitter_factor * delay
    jitter = random.uniform(-jitter_factor * delay, jitter_factor * delay)

    return max(0, delay + jitter)

# Example usage
print("Exponential backoff with jitter (10 trials, attempt 3):")
for trial in range(10):
    delay = calculate_backoff_with_jitter(attempt=3, jitter_factor=0.1)
    print(f"  Trial {trial}: {delay:.2f}s")
```

### Using Tenacity Library

Tenacity provides production-ready retry decorators:

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception_type(IOError),
)
def tap_with_retry(device, x: int, y: int) -> bool:
    """Tap screen with automatic retry on IOError."""
    try:
        device.tap(x, y)
        return True
    except IOError as e:
        print(f"Tap failed: {e}, will retry...")
        raise  # Tenacity catches and retries

# Usage
try:
    tap_with_retry(device, 540, 960)
except RetryError as e:
    print(f"Tap failed after retries: {e.last_attempt}")
```

### TOML Configuration

```toml
[retry]
# Enable/disable retry logic
enabled = true

# Maximum number of retry attempts (including initial)
max_attempts = 5

# Exponential backoff settings
base_delay_seconds = 1.0      # Initial delay (2^0 * base_delay)
max_delay_seconds = 20.0      # Cap exponential growth
backoff_multiplier = 2.0      # Exponential base

# Jitter to prevent thundering herd
jitter_enabled = true
jitter_factor = 0.1           # +/- 10% randomness

# Retry strategies by action type
[retry.strategies]
click = { max_attempts = 3, base_delay = 0.5 }
screenshot = { max_attempts = 2, base_delay = 0.2 }
swipe = { max_attempts = 3, base_delay = 1.0 }
wait_element = { max_attempts = 7, base_delay = 1.0, max_delay = 30.0 }
```

### Error Types to Retry

```python
class RetryableError(Exception):
    """Base class for retryable errors."""
    pass

class DeviceTimeoutError(RetryableError):
    """Device not responding - worth retrying."""
    pass

class ScreenshotFailed(RetryableError):
    """Screenshot capture failed - likely transient."""
    pass

class TapFailed(RetryableError):
    """Tap input failed - worth retrying."""
    pass

# Non-retryable errors (fail immediately)
class GameStateInvalidError(Exception):
    """Game state corrupted - retry won't help."""
    pass

class PermissionDeniedError(Exception):
    """Device permission issue - fix config, don't retry."""
    pass
```

---

## 2️⃣ Circuit Breaker Pattern

Circuit breaker prevents cascading failures by stopping requests to failing services.

### State Machine

```
CLOSED (normal)
  ↓ (consecutive failures >= threshold)
OPEN (failing, reject requests)
  ↓ (after timeout, try recovery)
HALF_OPEN (testing recovery)
  ↓ (success)
CLOSED (recovered)
  ↓ (failure)
OPEN (failing again)
```

### Implementation

```python
from enum import Enum
from time import time
from dataclasses import dataclass

class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5        # Failures before open
    recovery_timeout: float = 30.0    # Seconds before attempting recovery
    success_threshold: int = 2        # Successes in half-open to close

class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if time() - self.last_failure_time > self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit open, recovery in {self.config.recovery_timeout}s"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                print("Circuit recovered, back to CLOSED state")

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"Circuit breaker OPEN after {self.failure_count} failures")

    @property
    def is_healthy(self) -> bool:
        """Check if service is considered healthy."""
        return self.state == CircuitState.CLOSED

# Usage
breaker = CircuitBreaker(
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        success_threshold=2
    )
)

def screenshot_action(device):
    """Action protected by circuit breaker."""
    try:
        return breaker.call(device.screenshot)
    except CircuitBreakerOpenError:
        print("Screenshot service unhealthy, skipping")
        return None
```

### TOML Configuration

```toml
[circuit_breaker]
enabled = true

# Failure threshold before opening circuit
failure_threshold = 5

# Time to wait before attempting recovery (seconds)
recovery_timeout = 30.0

# Success threshold during half-open to return to closed
success_threshold = 2

# Per-service configuration
[circuit_breaker.services]
screenshot = { failure_threshold = 3, recovery_timeout = 20.0 }
input = { failure_threshold = 5, recovery_timeout = 30.0 }
network = { failure_threshold = 2, recovery_timeout = 60.0 }
```

---

## 3️⃣ Health Check Strategies

Health checks monitor system state and initiate recovery when needed.

### Device Health Check

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeviceHealth:
    is_online: bool
    battery_percent: int
    memory_available_mb: int
    screen_responsive: bool
    app_running: bool
    last_check_time: float

class HealthChecker:
    def check_device_health(self, device) -> DeviceHealth:
        """Comprehensive device health check."""

        try:
            # Check online status
            is_online = device.is_online()

            # Get battery level
            battery = self._get_battery_level(device)

            # Check available memory
            memory = self._get_available_memory(device)

            # Test screen responsiveness
            screen_ok = self._test_screen_response(device)

            # Check app running
            app_ok = self._check_app_running(device)

            return DeviceHealth(
                is_online=is_online,
                battery_percent=battery,
                memory_available_mb=memory,
                screen_responsive=screen_ok,
                app_running=app_ok,
                last_check_time=time()
            )
        except Exception as e:
            print(f"Health check failed: {e}")
            return DeviceHealth(
                is_online=False,
                battery_percent=0,
                memory_available_mb=0,
                screen_responsive=False,
                app_running=False,
                last_check_time=time()
            )

    def _get_battery_level(self, device) -> int:
        """Extract battery percentage."""
        try:
            output = device.shell("dumpsys battery")
            for line in output.split('\n'):
                if "level:" in line:
                    return int(line.split("level:")[-1].strip())
        except Exception:
            return 0
        return 50

    def _get_available_memory(self, device) -> int:
        """Get available RAM in MB."""
        try:
            output = device.shell("free -m")
            lines = output.split('\n')
            # Parse memory info
            return int(lines[1].split()[-1])  # Available column
        except Exception:
            return 0

    def _test_screen_response(self, device) -> bool:
        """Test if screen responds to input."""
        try:
            device.tap(540, 960)  # Safe tap
            return True
        except Exception:
            return False

    def _check_app_running(self, device) -> bool:
        """Check if target app is running."""
        try:
            output = device.shell("dumpsys activity | grep afk")
            return len(output) > 0
        except Exception:
            return False

    def is_healthy(self, health: DeviceHealth) -> bool:
        """Determine if device is healthy enough to continue."""
        return (
            health.is_online and
            health.battery_percent > 5 and
            health.memory_available_mb > 100 and
            health.screen_responsive
        )

    def get_recovery_actions(self, health: DeviceHealth) -> list:
        """Suggest recovery actions based on health state."""
        actions = []

        if not health.is_online:
            actions.append("reconnect_device")
        if health.battery_percent < 10:
            actions.append("stop_automation")
        if health.memory_available_mb < 100:
            actions.append("restart_app")
        if not health.screen_responsive:
            actions.append("restart_device")

        return actions
```

### Game State Validation

```python
def validate_game_state(device) -> bool:
    """Validate game is in expected state."""
    try:
        # Take screenshot
        screenshot = device.screenshot()

        # Check for error dialogs
        if has_error_dialog(screenshot):
            return False

        # Check for ANR (Application Not Responding)
        if has_anr_dialog(screenshot):
            return False

        # Check game UI elements visible
        if not has_game_ui_elements(screenshot):
            return False

        return True
    except Exception:
        return False

def recover_from_error(device) -> bool:
    """Attempt to recover from game error state."""
    try:
        # Close dialogs
        device.tap(100, 100)  # Back button
        time.sleep(1)

        # Verify recovery
        return validate_game_state(device)
    except Exception:
        return False
```

---

## 4️⃣ State Checkpointing (Foundation for Phase 10)

State checkpointing enables resuming interrupted game sessions.

### Checkpoint Data Structure

```python
from dataclasses import dataclass, asdict
from typing import Dict, Any
import json
from datetime import datetime

@dataclass
class GameCheckpoint:
    """Game state checkpoint for recovery."""

    # Session info
    session_id: str
    timestamp: str

    # Game state
    current_location: str           # "menu", "battle", "inventory", etc.
    game_screen: bytes              # Screenshot bytes

    # Progress tracking
    actions_completed: int
    current_action_index: int

    # Metadata
    device_info: Dict[str, Any]
    bot_version: str
    notes: str = ""

class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "./.checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

    def save_checkpoint(self, checkpoint: GameCheckpoint) -> Path:
        """Save checkpoint to disk."""
        filename = f"checkpoint_{checkpoint.session_id}_{int(time.time())}.json"
        filepath = self.checkpoint_dir / filename

        # Convert to JSON-serializable format
        data = asdict(checkpoint)
        data['game_screen'] = checkpoint.game_screen.hex()  # Bytes to hex string

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Checkpoint saved: {filepath}")
        return filepath

    def load_checkpoint(self, checkpoint_path: Path) -> Optional[GameCheckpoint]:
        """Load checkpoint from disk."""
        try:
            with open(checkpoint_path, 'r') as f:
                data = json.load(f)

            # Restore screenshot bytes
            data['game_screen'] = bytes.fromhex(data['game_screen'])

            return GameCheckpoint(**data)
        except Exception as e:
            print(f"Failed to load checkpoint: {e}")
            return None

    def list_checkpoints(self, session_id: str) -> list:
        """List all checkpoints for a session."""
        pattern = f"checkpoint_{session_id}_*.json"
        return sorted(self.checkpoint_dir.glob(pattern))

    def cleanup_old_checkpoints(self, max_age_hours: int = 24):
        """Remove checkpoints older than max_age_hours."""
        cutoff_time = time.time() - (max_age_hours * 3600)

        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
            if checkpoint_file.stat().st_mtime < cutoff_time:
                checkpoint_file.unlink()
                print(f"Removed old checkpoint: {checkpoint_file.name}")

# Usage
checkpoint_mgr = CheckpointManager()

# Save checkpoint
checkpoint = GameCheckpoint(
    session_id="session_123",
    timestamp=datetime.now().isoformat(),
    current_location="battle",
    game_screen=screenshot_bytes,
    actions_completed=5,
    current_action_index=5,
    device_info={"model": "Pixel 5", "api_level": 31},
    bot_version="1.0.0",
    notes="Paused before arena battle"
)
checkpoint_mgr.save_checkpoint(checkpoint)

# Later: recover from checkpoint
checkpoints = checkpoint_mgr.list_checkpoints("session_123")
if checkpoints:
    latest = checkpoints[-1]
    recovered = checkpoint_mgr.load_checkpoint(latest)
    print(f"Resumed from: {recovered.current_location}")
```

### Recovery Workflow

```
1. Bot crash or interrupt
    ↓
2. CheckpointManager loads latest checkpoint
    ↓
3. Verify device state matches checkpoint
    ↓
4. Take fresh screenshot, compare with saved
    ↓
5. If match: resume from checkpoint
   If mismatch: full recovery sequence
    ↓
6. Resume action from current_action_index
```

---

## 5️⃣ Best Practices

### Retry Configuration

✅ **DO**:
- Set reasonable max_attempts (typically 3-7)
- Use exponential backoff with jitter
- Configure different retry strategies per action type
- Log all retry attempts for debugging
- Test retry behavior on slow devices
- Use circuit breaker for external services

❌ **DON'T**:
- Retry infinite times (risk hanging)
- Use fixed delays (inefficient recovery)
- Retry non-idempotent operations carelessly
- Ignore circuit breaker state
- Retry immediately without delay
- Log sensitive data in retry logs

### Health Monitoring

✅ **DO**:
- Check device health before action sequences
- Monitor battery level during long sessions
- Track memory usage for memory leaks
- Log health issues for analysis
- Implement automatic recovery triggers
- Validate game state after critical actions

❌ **DON'T**:
- Assume device health remains stable
- Ignore out-of-memory conditions
- Continue with low battery
- Skip game state validation
- Log health checks too frequently (performance)
- Ignore recovery failures

### Error Recovery

✅ **DO**:
- Implement graceful degradation
- Save checkpoints before risky operations
- Test recovery paths thoroughly
- Document recovery procedures
- Monitor recovery success rate
- Clean up stale checkpoints

❌ **DON'T**:
- Assume recovery always succeeds
- Ignore checkpoint corruption
- Skip error state validation
- Mix recovery logic with normal flow
- Retain infinite checkpoints
- Resume without state verification

---

## 6️⃣ Integration Example

Complete resilience pattern integration:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientGameBot:
    def __init__(self, device, config_file: str):
        self.device = device
        self.config = self._load_config(config_file)

        self.health_checker = HealthChecker()
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=self.config.circuit_breaker.failure_threshold,
                recovery_timeout=self.config.circuit_breaker.recovery_timeout
            )
        )
        self.checkpoint_mgr = CheckpointManager()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute_action_with_resilience(self, action):
        """Execute action with full resilience support."""

        # 1. Health check
        health = self.health_checker.check_device_health(self.device)
        if not self.health_checker.is_healthy(health):
            recovery_actions = self.health_checker.get_recovery_actions(health)
            print(f"Unhealthy device, recovery actions: {recovery_actions}")
            raise DeviceUnhealthyError(health)

        # 2. Circuit breaker check
        if not self.circuit_breaker.is_healthy:
            raise CircuitBreakerOpenError("Service is unhealthy")

        # 3. Save checkpoint before risky action
        self.checkpoint_mgr.save_checkpoint(
            GameCheckpoint(
                session_id=self.session_id,
                timestamp=datetime.now().isoformat(),
                current_location=self._get_current_location(),
                game_screen=self.device.screenshot(),
                actions_completed=self.action_count,
                current_action_index=self.action_count,
                device_info=self._get_device_info(),
                bot_version="1.0.0"
            )
        )

        # 4. Execute action
        try:
            result = self.circuit_breaker.call(action.execute, self.device)
            self.action_count += 1
            return result
        except Exception as e:
            print(f"Action failed: {e}, will retry...")
            raise

    def _load_config(self, config_file: str):
        """Load resilience configuration."""
        # Implementation
        pass
```

---

## 7️⃣ Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| **Retry storm** | Many retries in short time | Increase backoff delays, add jitter |
| **Circuit always open** | Service continuously failing | Check device health, investigate root cause |
| **Checkpoint corruption** | Recovered state invalid | Validate checkpoint data, add checksums |
| **Memory leak** | Available memory decreases | Check for unclosed resources in recovery |
| **Infinite retry loop** | Bot never progresses | Set finite max_attempts, implement max time limit |

---

**Status**: ✅ Resilience Patterns Complete
**Next Module**: [tauri-integration](./tauri-integration.md)
