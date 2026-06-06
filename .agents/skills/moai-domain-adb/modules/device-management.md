# Module 2: Device Management

**Level**: Intermediate
**Prerequisites**: Module 1 (adb-fundamentals)
**Estimated Learning Time**: 45-60 minutes
**Hands-On Practice**: 20-30 minutes

---

## 1️⃣ Multi-Device Architecture

When automating 5+ Android devices, managing them individually becomes unwieldy. This module covers orchestration patterns.

### Device Pool Concept

```
Device Pool Manager
    ├─ Device #1 (emulator-5554)      State: idle
    ├─ Device #2 (emulator-5556)      State: executing
    ├─ Device #3 (192.168.1.100:5555) State: idle
    ├─ Device #4 (Pixel2 USB)         State: error (offline)
    └─ Device #5 (Galaxy S20 USB)     State: executing
```

**Key Responsibilities**:
- Maintain device list with current states
- Assign tasks to least-loaded device
- Handle device disconnections gracefully
- Monitor device health
- Implement retry on other devices

---

## 2️⃣ Device State Tracking

### Device States

```
┌─────────────────────────────────────────┐
│         DEVICE STATE MACHINE            │
├─────────────────────────────────────────┤
│                                         │
│  [UNKNOWN] → [CONNECTING] → [ONLINE]   │
│                                   ↓     │
│                           [EXECUTING]   │
│                                   ↓     │
│                             [IDLE]      │
│                                   ↓     │
│            [ERROR] ← ← ← ← ← ← ←|      │
│              ↓                          │
│         [OFFLINE]                       │
│                                         │
└─────────────────────────────────────────┘
```

### Tracking Data Structure

```python
class DeviceState:
    serial_number: str           # Device identifier
    connection_type: str         # "usb" or "network"
    state: str                   # "online", "offline", "executing"
    api_level: int              # Android API
    resolution: str             # "1080x1920"
    free_memory: int            # MB
    last_heartbeat: float       # Timestamp
    current_task_id: str        # Executing task ID
    error_count: int            # Consecutive errors

    def is_healthy(self) -> bool:
        return self.state == "online" and self.error_count < 3

    def is_available(self) -> bool:
        return self.state in ["idle", "online"]
```

### State Persistence

```python
# Save device state to JSON
device_state = {
    "devices": {
        "emulator-5554": {
            "state": "idle",
            "api_level": 31,
            "last_seen": 1701470400,
        }
    },
    "last_sync": 1701470400
}

# Store in .moai/cache/device-state.json for cross-session reference
```

---

## 3️⃣ Connection Pooling

### Single Pool Instance

```python
class ADBConnectionPool:
    def __init__(self, max_connections=5):
        self.pool = {}              # device_id -> Connection
        self.max_connections = max_connections
        self.lock = threading.Lock()

    def get_connection(self, device_id: str) -> Connection:
        with self.lock:
            if device_id not in self.pool:
                # Verify device is online before creating
                if not self.verify_device(device_id):
                    raise DeviceOfflineError(device_id)
                self.pool[device_id] = self._create_connection(device_id)
            return self.pool[device_id]

    def close_connection(self, device_id: str):
        with self.lock:
            if device_id in self.pool:
                self.pool[device_id].close()
                del self.pool[device_id]

    def health_check(self):
        """Verify all connections are still alive"""
        for device_id, conn in list(self.pool.items()):
            if not conn.is_alive():
                self.close_connection(device_id)
```

### Lazy Initialization

```python
# Connection created on first use
pool = ADBConnectionPool()

# First access: creates connection
conn1 = pool.get_connection("emulator-5554")

# Second access: reuses connection
conn2 = pool.get_connection("emulator-5554")
assert conn1 is conn2  # Same connection object
```

---

## 4️⃣ Task Distribution

### Task Queue Pattern

```
[Task Queue]
    ├─ Task A (Priority: HIGH)
    ├─ Task B (Priority: MEDIUM)
    ├─ Task C (Priority: MEDIUM)
    └─ Task D (Priority: LOW)
         ↓
    [Device Selector]
         ↓
    [Assign to best device]
         ↓
    [Device executes task]
```

### Selection Algorithm

```python
class DeviceSelector:
    def select_best_device(self, available_devices: List[Device]) -> Device:
        """Select device using weighted scoring"""

        scores = {}
        for device in available_devices:
            # Lower score = better candidate
            score = 0

            # Prefer higher API level (game compatibility)
            score -= device.api_level / 100

            # Prefer more free memory
            score -= device.free_memory / 1000

            # Penalize devices with recent errors
            score += device.error_count * 10

            # Penalize devices with high latency
            score += device.avg_latency_ms / 100

            scores[device] = score

        return min(scores, key=scores.get)
```

### Batch Task Execution

```python
# Execute same task on 3 devices
devices = pool.get_devices(count=3, healthy_only=True)
futures = []

with ThreadPoolExecutor(max_workers=3) as executor:
    for device in devices:
        future = executor.submit(
            self.execute_task,
            device=device,
            task_id="click_button"
        )
        futures.append(future)

# Wait for all to complete
results = [f.result(timeout=30) for f in futures]
```

---

## 5️⃣ Failover Strategies

### Retry with Fallback

```python
def execute_with_retry(task_id: str, max_devices: int = 3) -> bool:
    """Try task on up to 3 devices"""

    devices = pool.get_healthy_devices(count=max_devices)

    for attempt, device in enumerate(devices):
        try:
            result = device.execute(task_id)
            if result.success:
                return True
            device.increment_error_count()

        except DeviceOfflineError:
            pool.mark_offline(device.serial)
        except Exception as e:
            logger.warning(f"Task failed on {device.serial}: {e}")

    return False  # All devices failed
```

### Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout_sec=60):
        self.failures = 0
        self.failure_threshold = failure_threshold
        self.timeout_sec = timeout_sec
        self.last_failure_time = None

    def record_success(self):
        self.failures = 0

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()

    def is_open(self) -> bool:
        """Circuit is open = don't use device"""
        if self.failures < self.failure_threshold:
            return False

        # Allow retry after timeout
        elapsed = time.time() - self.last_failure_time
        return elapsed < self.timeout_sec

    def can_attempt(self) -> bool:
        return not self.is_open()
```

---

## 6️⃣ Monitoring & Health Checks

### Heartbeat Mechanism

```python
def health_monitor():
    """Run in background thread, ping all devices every 5s"""
    while True:
        for device in pool.get_all_devices():
            try:
                # Quick connectivity check
                result = device.execute("adb shell echo ok", timeout=2)

                if result.success:
                    device.update_heartbeat()
                    device.reset_error_count()
                else:
                    device.increment_error_count()

            except TimeoutError:
                device.mark_offline()

        time.sleep(5)  # Check every 5 seconds
```

### Metrics Collection

```python
class DeviceMetrics:
    """Collect per-device statistics"""

    def record_execution(self, device_id: str, duration_ms: int, success: bool):
        self.total_executions += 1
        self.successful_executions += success
        self.avg_duration = (
            (self.avg_duration * (self.total_executions - 1) + duration_ms) /
            self.total_executions
        )

    def get_reliability(self) -> float:
        """Return success rate (0.0 to 1.0)"""
        return self.successful_executions / self.total_executions
```

---

## 7️⃣ Lifecycle Management

### Device Initialization

```python
def initialize_device(device_id: str):
    """Prepare device for bot execution"""

    device = pool.get_connection(device_id)

    # Step 1: Verify online
    assert device.is_online(), f"Device {device_id} offline"

    # Step 2: Enable necessary permissions
    device.execute("adb shell pm grant app.permission.CAMERA")
    device.execute("adb shell pm grant app.permission.WRITE_EXTERNAL_STORAGE")

    # Step 3: Clear app data
    device.execute("adb shell pm clear com.example.game")

    # Step 4: Set screen on
    device.execute("adb shell input keyevent 224")  # WAKE

    # Step 5: Disable screen timeout
    device.execute("adb shell settings put system screen_off_timeout 0")

    logger.info(f"Device {device_id} initialized")
```

### Device Cleanup

```python
def cleanup_device(device_id: str):
    """Clean up after bot execution"""

    device = pool.get_connection(device_id)

    # Stop running apps
    device.execute("adb shell am force-stop com.example.game")

    # Clear cache (optional)
    device.execute("adb shell rm -rf /sdcard/bot_temp/")

    # Reset screen timeout
    device.execute("adb shell settings put system screen_off_timeout 30000")

    # Close connection if needed
    if device.connection_type == "network":
        pool.close_connection(device_id)

    logger.info(f"Device {device_id} cleaned up")
```

---

## 8️⃣ Configuration & Scaling

### Device Profile

```yaml
# device-config.yaml
devices:
  emulator-5554:
    type: "emulator"
    api_level: 31
    resolution: "1080x1920"
    cpu_threads: 4
    memory_mb: 4096
    priority: 10

  emulator-5556:
    type: "emulator"
    api_level: 29
    resolution: "720x1280"
    cpu_threads: 2
    memory_mb: 2048
    priority: 5

  real-device-usb:
    type: "physical"
    api_level: 30
    resolution: "1440x3200"
    connection: "usb"
    priority: 15

max_concurrent_tasks: 3
health_check_interval_sec: 5
connection_timeout_sec: 10
```

### Scaling Considerations

- **Small Setup** (1-2 devices): Direct execution, no pooling needed
- **Medium Setup** (3-5 devices): Connection pooling, simple round-robin
- **Large Setup** (10+ devices): Advanced pooling, load balancing, metrics

---

## 9️⃣ Debugging Multi-Device Issues

### Common Problems

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Device keeps going offline | Check WiFi signal, USB cable | Move device closer, use better cable |
| Uneven task distribution | Check device capabilities | Adjust device weights in selector |
| Memory leaks in daemon | Monitor: `adb shell dumpsys meminfo adbd` | Restart ADB: `adb kill-server` |
| Connection pool exhausted | Check: `netstat -an \| grep 5555` | Increase pool size or add connection limits |

### Monitoring Commands

```bash
# Monitor all device states
watch -n 1 'adb devices -l'

# Watch connection pool usage
lsof -i :5555

# Monitor Python thread count (bot process)
ps aux | grep python | wc -l

# Profile device memory
adb shell dumpsys meminfo | tail -20
```

---

## 🔟 Best Practices

✅ **DO**:
- Initialize devices before heavy use
- Implement timeouts for all device operations
- Use connection pooling for 3+ devices
- Monitor device health continuously
- Implement exponential backoff on retries
- Log device state changes for debugging

❌ **DON'T**:
- Assume device will stay connected (always check state)
- Keep connections open forever (use timeouts)
- Send commands to 10+ devices sequentially
- Ignore device error counts (track and fallback)
- Mix connection types in same pool without care
- Leave app data in device cache (clean up properly)

---

## 🔟 Device Health & Auto-Recovery

When running automation 24/7 across multiple devices, failures are inevitable. This section
covers continuous health monitoring and automated recovery strategies.

### Health Monitoring Architecture

```
┌──────────────────────────────────────────────────────────┐
│         Device Health Monitor (Background Thread)        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ For Each Device (Every 5-10 seconds):           │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ 1. ConnectionHealthCheck                        │    │
│  │    ├─ Ping device (latency measurement)         │    │
│  │    ├─ Check stability (coefficient of variation)│    │
│  │    └─ Track consecutive failures                │    │
│  │                                                 │    │
│  │ 2. PerformanceMetricsCollector                  │    │
│  │    ├─ CPU usage %                               │    │
│  │    ├─ Memory usage %                            │    │
│  │    └─ Thermal temperature (°C)                  │    │
│  │                                                 │    │
│  │ 3. HealthStatusEvaluator                        │    │
│  │    ├─ HEALTHY: All metrics normal               │    │
│  │    ├─ DEGRADED: Some metrics warning level      │    │
│  │    ├─ CRITICAL: Multiple metrics critical       │    │
│  │    └─ OFFLINE: Cannot connect                   │    │
│  └─────────────────────────────────────────────────┘    │
│                       ↓                                  │
│       RecoveryStatesMachine (State Machine)             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Recovery State Machine

```
┌──────────────┐
│    IDLE      │ ← Starting state
└──────┬───────┘
       │
       ├─→ CHECKING (1-5 seconds)
       │       ↓
       │   Measure health metrics
       │   Evaluate status
       │       ↓
       │   ┌─→ HEALTHY? → IDLE (Loop)
       │   │
       │   └─→ UNHEALTHY? → RECOVERING
       │
       └─→ RECOVERING (up to 180 seconds max)
               ├─ Strategy 1: Reconnect (adb disconnect/connect)
               ├─ Strategy 2: Restart (adb reboot + wait online)
               ├─ Strategy 3: Fallback (switch to other device)
               │
               ├─→ Success → RECOVERED
               │                ↓
               │         Reset attempts
               │                ↓
               │            → IDLE
               │
               └─→ Max attempts exceeded → FAILED
                        ↓
                    → IDLE (circuit open)
```

**State Timeout Protection**: Each state has 180-second max (configurable).
If state enters timeout, transition to FAILED.

### Health Metrics Thresholds

```python
# Default thresholds
CPU_THRESHOLD = 80%          # Warn if CPU > 80%
MEMORY_THRESHOLD = 85%        # Warn if memory > 85%
THERMAL_THRESHOLD = 45°C      # Warn if temp > 45°C

# Stability calculation
stability = 100 - (std_dev/mean * 50)  # 0-100%

# Connection latency
avg_latency_ms = sum(samples) / count
max_healthy_latency = 100ms
max_degraded_latency = 500ms
```

### Recovery Strategies

#### Strategy 1: Reconnect (Fast Recovery)

```python
# Execution time: 2-3 seconds
def reconnect_strategy():
    # 1. Disconnect from device
    adb disconnect <device_id>
    time.sleep(1)

    # 2. Reconnect
    adb connect <device_id>

    # 3. Verify connection
    adb shell echo ok  # Check if responsive
```

**Best for**: Temporary network glitches, ADB daemon hiccup
**Success rate**: 70-85%

#### Strategy 2: Restart (Full Recovery)

```python
# Execution time: 30-60 seconds
def restart_strategy():
    # 1. Issue reboot command
    adb -s <device_id> reboot

    # 2. Wait for device to go offline
    poll until offline (max 10s)

    # 3. Wait for device to come back online
    poll until online (max 50s)

    # 4. Verify responsive
    adb shell echo ok
```

**Best for**: Device stuck, app crashed, memory exhausted
**Success rate**: 85-95%

#### Strategy 3: Fallback (Automatic Substitution)

```python
# For batch execution
def fallback_strategy():
    # 1. Device A is unhealthy
    # 2. Move pending tasks to Device B
    # 3. Mark Device A for recovery later
    # 4. Continue with Device B
```

**Best for**: Critical tasks, batch execution
**Success rate**: 95%+ (if backup device available)

### Multi-Device Health Aggregation

```python
class FleetHealthAggregator:
    """Aggregate health status across multiple devices."""

    def get_fleet_health_status(self) -> Dict[str, Any]:
        """Compute overall fleet health."""

        # Count devices by status
        healthy = sum(1 for d in devices if d.status == HEALTHY)
        degraded = sum(1 for d in devices if d.status == DEGRADED)
        critical = sum(1 for d in devices if d.status == CRITICAL)
        offline = sum(1 for d in devices if d.status == OFFLINE)

        total = len(devices)

        # Compute fleet health percentage
        health_score = (healthy / total) * 100

        return {
            "fleet_health": health_score,
            "healthy": healthy,
            "degraded": degraded,
            "critical": critical,
            "offline": offline,
            "total": total,
        }
```

### Implementation Example

```python
from adb_device_health_check import (
    DeviceHealthMonitor,
    RecoveryConfig,
)

# Create monitor
monitor = DeviceHealthMonitor(check_interval=10)

# Configure recovery
config = RecoveryConfig(
    enabled=True,
    max_attempts=3,
    cpu_threshold=80,
    memory_threshold=85,
    thermal_threshold=45,
)

# Add devices
monitor.add_device("emulator-5554", config)
monitor.add_device("emulator-5556", config)
monitor.add_device("192.168.1.100:5555", config)

# Start monitoring
monitor.start_monitoring()

# Check specific device health
report = monitor.check_device("emulator-5554")
print(f"Status: {report.health_status}")
print(f"CPU: {report.metrics['cpu_usage']}%")
print(f"Memory: {report.metrics['memory_usage']}%")

# Auto-recover if needed
if report.health_status != "healthy":
    success = monitor.auto_recover_device("emulator-5554")
    print(f"Recovery: {'SUCCESS' if success else 'FAILED'}")

# Get all device reports
reports = monitor.check_all_devices()
for device_id, report in reports.items():
    print(f"{device_id}: {report.health_status}")

# Stop monitoring
monitor.stop_monitoring()
```

### Error Handling & Logging

**Connection Errors**:
- Timeout (adb shell hangs) → Reconnect strategy
- Device offline → Restart strategy
- Repeated failures → Fallback strategy

**Performance Errors**:
- CPU spike → Usually recovers naturally (monitor 5 min)
- Memory exhaustion → Restart app or device
- Thermal throttling → Cool down (reduce load/frequency)

**Logging Best Practices**:

```python
# Log health check start
logger.info(f"{device_id}: Starting health check")

# Log metrics
logger.debug(f"{device_id}: CPU={cpu}%, Memory={mem}%, Temp={temp}°C")

# Log status changes
logger.warning(f"{device_id}: Status HEALTHY → DEGRADED")

# Log recovery attempts
logger.info(f"{device_id}: Executing reconnect strategy (attempt 1/3)")

# Log final result
logger.info(f"{device_id}: Recovery SUCCESS")  # or FAILED
```

### Integration with Phase 9a (FSM & Exponential Backoff)

The device health recovery state machine integrates with Phase 9a patterns:

**Phase 9a FSM Pattern**:
- RecoveryStatesMachine uses Phase 9a state transition patterns
- Timeout protection prevents stuck states (180s max per state)

**Phase 9a Exponential Backoff**:
- Recovery strategies use exponential backoff via tenacity
- Base delay: 1 second
- Max delay: 20 seconds
- Jitter: ±10% to prevent thundering herd
- Max attempts: 3 (configurable)

```python
# Example: Reconnect with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=20),
)
def reconnect_with_backoff(device_id):
    return reconnect_strategy(device_id)
```

### Production Deployment Guidelines

**Monitoring Intervals**:
- Light load: 30-60 seconds (slow failure detection)
- Normal load: 10-15 seconds (balanced)
- Heavy load: 5-10 seconds (responsive)
- Critical: 2-5 seconds (real-time)

**Resource Usage**:
- Memory per device: ~5-10 MB
- CPU overhead: <1% per device (monitoring)
- Network overhead: ~100 bytes/check
- Total bandwidth for 10 devices: ~10 KB/min

**Thresholds by Scenario**:

| Scenario | CPU | Memory | Thermal | Latency |
|----------|-----|--------|---------|---------|
| Light app | 70% | 80% | 50°C | 100ms |
| Game bot | 80% | 85% | 45°C | 50ms |
| Heavy ML | 85% | 90% | 40°C | 200ms |
| Server-side | 95% | 95% | 60°C | 500ms |

**Recovery Timeout Strategy**:

```python
# Sequential timeout handling
CHECKING_TIMEOUT = 5 seconds      # Quick health check
RECONNECT_TIMEOUT = 3 seconds     # Fast local operation
RESTART_TIMEOUT = 60 seconds      # Wait for reboot
MAX_STATE_TIME = 180 seconds      # Global safety limit
```

### Best Practices

✅ **DO**:
- Monitor continuously in background thread (non-blocking)
- Use exponential backoff for recovery attempts
- Log state transitions for debugging
- Implement timeout on every state
- Fallback to other devices if available
- Reset attempts on successful recovery
- Track recovery metrics (success/failure rate)
- Aggregate fleet health across all devices

❌ **DON'T**:
- Block main thread during monitoring
- Assume recovery always succeeds
- Ignore consecutive failures
- Skip timeout protection
- Retry indefinitely without backoff
- Log too verbosely (impacts performance)
- Ignore thermal warnings
- Execute recovery on devices simultaneously (stagger attempts)

---

**Status**: ✅ Device Health & Auto-Recovery Covered
**Integration**: Phase 9a FSM & Exponential Backoff Patterns
**Next Module**: [game-automation](./game-automation.md)
