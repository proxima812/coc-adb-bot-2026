# Module 5: Tauri Integration

**Level**: Advanced
**Prerequisites**: All previous modules
**Estimated Learning Time**: 60-90 minutes
**Hands-On Practice**: 30-45 minutes

---

## 1️⃣ Tauri-Python IPC Architecture

### Real-Time Communication

```
┌─────────────────────────────────────────┐
│         Tauri UI (Svelte/React)         │
│  (User interactions, Bot status)        │
└────────────┬────────────────────────────┘
             │ invoke() / listen()
             │ (WebSocket via invoke)
┌────────────▼────────────────────────────┐
│      Tauri Backend (Rust Layer)         │
│  (Command router, security boundary)    │
└────────────┬────────────────────────────┘
             │ Python subprocess
┌────────────▼────────────────────────────┐
│       Python Bot Process                │
│  (ADB control, game automation)         │
└─────────────────────────────────────────┘
```

### Command Invocation Flow

```python
# Frontend (TypeScript/Svelte)
const result = await invoke('run_bot', {
    bot_id: 'daily_quest',
    device_id: 'emulator-5554'
});

# Backend (Rust - main.rs)
#[tauri::command]
async fn run_bot(bot_id: String, device_id: String) -> Result<String, String> {
    // Call Python via child process
    let output = Command::new("python")
        .args(&["-m", "adb_auto_player.cli", "run", &bot_id])
        .output()?;
    Ok(String::from_utf8(output.stdout)?)
}

# Python (receives via CLI args)
@click.command()
@click.option('--bot-id', required=True)
def run_bot(bot_id: str):
    bot = load_bot(bot_id)
    bot.execute()
```

---

## 2️⃣ Event System (Status Updates)

### Real-Time Bot Status

```python
class BotEventBus:
    """Publish bot events to Tauri frontend"""

    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_type: str, callback):
        """Register event listener"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def emit(self, event_type: str, data: dict):
        """Broadcast event to all listeners"""
        if event_type in self.listeners:
            for callback in self.listeners[event_type]:
                callback(data)

# Usage
bus = BotEventBus()

# Register frontend listeners
bus.subscribe("bot_started", lambda data: print(f"Bot {data['bot_id']} started"))
bus.subscribe("action_executed", lambda data: print(f"Action: {data['action']}"))
bus.subscribe("bot_error", lambda data: print(f"Error: {data['error']}"))

# Emit events during execution
bus.emit("bot_started", {"bot_id": "daily_quest", "device": "emulator-5554"})
bus.emit("action_executed", {"action": "click_button", "x": 540, "y": 960})
```

### Event Types

```python
class BotEvents:
    # Bot lifecycle
    BOT_STARTED = "bot_started"           # Bot execution started
    BOT_COMPLETED = "bot_completed"       # Bot finished successfully
    BOT_STOPPED = "bot_stopped"           # Bot stopped by user
    BOT_ERROR = "bot_error"               # Bot encountered error

    # Action events
    ACTION_STARTED = "action_started"     # Action began
    ACTION_COMPLETED = "action_completed" # Action finished
    ACTION_FAILED = "action_failed"       # Action failed, retrying

    # Device events
    DEVICE_CONNECTED = "device_connected" # Device came online
    DEVICE_DISCONNECTED = "device_disconnected" # Device went offline
    DEVICE_ERROR = "device_error"         # Device error

    # Status events
    STATUS_UPDATE = "status_update"       # General status
    SCREENSHOT_CAPTURED = "screenshot_captured" # New screenshot available
    LOG_MESSAGE = "log_message"           # Log output
```

---

## 3️⃣ Command Queue Pattern

### Async Task Queue

```python
import asyncio
from typing import Callable

class CommandQueue:
    """Queue bot commands from UI, execute sequentially"""

    def __init__(self):
        self.queue = asyncio.Queue()
        self.running = False

    async def enqueue(self, command: str, params: dict):
        """Add command to queue"""
        await self.queue.put({
            "command": command,
            "params": params,
            "timestamp": time.time()
        })

    async def worker(self):
        """Process queue items"""
        self.running = True

        while self.running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                # Execute command
                result = await self._execute_command(
                    item["command"],
                    item["params"]
                )

                # Emit result event
                self.event_bus.emit("command_executed", {
                    "command": item["command"],
                    "result": result
                })

            except asyncio.TimeoutError:
                continue

    async def _execute_command(self, command: str, params: dict) -> dict:
        """Execute individual command"""
        if command == "run_bot":
            return {"status": "success", "bot_id": params["bot_id"]}
        elif command == "stop_bot":
            return {"status": "stopped"}
        # ... handle other commands
```

### Parallel Execution with Limits

```python
class ParallelExecutor:
    """Run multiple bots in parallel with resource limits"""

    def __init__(self, max_parallel: int = 3):
        self.max_parallel = max_parallel
        self.running_tasks = []

    async def run_multiple_bots(self, bot_ids: List[str]):
        """Execute multiple bots with concurrency limit"""

        semaphore = asyncio.Semaphore(self.max_parallel)

        async def run_with_limit(bot_id: str):
            async with semaphore:
                return await self.run_bot(bot_id)

        tasks = [run_with_limit(bot_id) for bot_id in bot_ids]
        results = await asyncio.gather(*tasks)
        return results

    async def run_bot(self, bot_id: str) -> dict:
        """Run single bot"""
        # Implementation
        pass
```

---

## 4️⃣ State Persistence

### Save/Restore Bot State

```python
import json
from pathlib import Path

class BotStateManager:
    def __init__(self, state_dir: str = ".moai/cache/bot-state/"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, bot_id: str, state: dict):
        """Persist bot state"""
        state_file = self.state_dir / f"{bot_id}.json"
        state["last_updated"] = time.time()
        state_file.write_text(json.dumps(state, indent=2))

    def load_state(self, bot_id: str) -> Optional[dict]:
        """Load saved bot state"""
        state_file = self.state_dir / f"{bot_id}.json"
        if state_file.exists():
            return json.loads(state_file.read_text())
        return None

    def clear_state(self, bot_id: str):
        """Clear saved state"""
        state_file = self.state_dir / f"{bot_id}.json"
        state_file.unlink(missing_ok=True)

# Usage
state_mgr = BotStateManager()

# Save bot progress
state_mgr.save_state("daily_quest", {
    "completed_quests": 3,
    "next_quest_index": 4,
    "total_reward": 5000
})

# Resume from saved state
saved_state = state_mgr.load_state("daily_quest")
if saved_state:
    bot.resume_from_state(saved_state)
```

---

## 5️⃣ Resource Management

### Memory Monitoring

```python
import psutil

class ResourceMonitor:
    def __init__(self, max_memory_percent: float = 80.0):
        self.max_memory_percent = max_memory_percent
        self.process = psutil.Process()

    def get_memory_usage(self) -> dict:
        """Get current memory usage"""
        mem_info = self.process.memory_info()
        mem_percent = self.process.memory_percent()

        return {
            "rss_mb": mem_info.rss / 1024 / 1024,     # Physical memory
            "vms_mb": mem_info.vms / 1024 / 1024,     # Virtual memory
            "percent": mem_percent,
            "available_mb": psutil.virtual_memory().available / 1024 / 1024
        }

    def check_memory_limit(self) -> bool:
        """Check if memory usage is safe"""
        mem = self.get_memory_usage()
        return mem["percent"] < self.max_memory_percent

    def should_cleanup(self) -> bool:
        """Determine if garbage collection needed"""
        mem = self.get_memory_usage()
        return mem["percent"] > self.max_memory_percent * 0.9

# Usage
monitor = ResourceMonitor()

if not monitor.check_memory_limit():
    logger.warning("Memory usage critical!")
    # Clear caches, stop bots, etc.
```

### Performance Profiling

```python
import cProfile
import pstats

class BotProfiler:
    def profile_bot_execution(self, bot: Bot, duration_seconds: int = 60):
        """Profile bot to identify bottlenecks"""

        profiler = cProfile.Profile()
        profiler.enable()

        # Run bot
        start = time.time()
        while time.time() - start < duration_seconds:
            bot.step()

        profiler.disable()

        # Generate report
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions

# Usage
profiler = BotProfiler()
profiler.profile_bot_execution(bot, duration_seconds=60)
```

---

## 6️⃣ Frontend Integration

### Bot Control Panel (Svelte Example)

```svelte
<script>
    import { invoke } from '@tauri-apps/api/tauri';

    let bots = [];
    let selectedBot = null;
    let status = "idle";

    async function startBot(botId) {
        try {
            const result = await invoke('run_bot', { bot_id: botId });
            status = "running";
            selectedBot = botId;
        } catch (err) {
            console.error("Bot error:", err);
            status = "error";
        }
    }

    async function stopBot() {
        const result = await invoke('stop_bot', {});
        status = "stopped";
    }

    function setupListeners() {
        listen('bot_status', (event) => {
            // Update UI with bot status
            status = event.payload.status;
        });

        listen('action_executed', (event) => {
            // Log action
            console.log(`Action: ${event.payload.action}`);
        });
    }
</script>

<div class="bot-panel">
    <h2>Bot Control</h2>
    <button on:click={() => startBot('daily_quest')}>
        Start Daily Quest
    </button>
    <button on:click={stopBot} disabled={status !== 'running'}>
        Stop Bot
    </button>
    <p>Status: {status}</p>
</div>
```

---

## 7️⃣ Deployment Strategies

### Single Device Deployment

```python
class SingleDeviceDeployer:
    def deploy(self, bot_config: dict, device_id: str):
        """Deploy bot to single device"""

        # 1. Validate device
        if not self.device_pool.get_device(device_id).is_healthy():
            raise DeviceOfflineError(device_id)

        # 2. Install app if needed
        if not self.app_manager.is_installed(device_id):
            self.app_manager.install(device_id)

        # 3. Start bot
        self.event_bus.emit("deployment_started", {
            "device_id": device_id,
            "bot_id": bot_config["id"]
        })

        # 4. Run bot with error handling
        try:
            self.run_bot(bot_config, device_id)
        except Exception as e:
            self.event_bus.emit("deployment_failed", {"error": str(e)})
```

### Multi-Device Deployment

```python
class MultiDeviceDeployer:
    async def deploy_to_multiple(self, bot_config: dict, device_ids: List[str]):
        """Deploy bot to multiple devices in parallel"""

        tasks = [
            self.deploy_single(bot_config, device_id)
            for device_id in device_ids
        ]

        results = await asyncio.gather(*tasks)
        return results

    async def deploy_single(self, bot_config: dict, device_id: str):
        """Deploy to single device (async)"""
        # Deployment logic
        pass
```

---

## 8️⃣ Error Handling & Recovery

### Graceful Shutdown

```python
class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = asyncio.Event()

    def signal_shutdown(self):
        """Request graceful shutdown"""
        self.shutdown_event.set()

    async def wait_shutdown(self):
        """Wait for shutdown signal"""
        await self.shutdown_event.wait()

    async def cleanup(self):
        """Cleanup resources on shutdown"""
        # Save state
        for bot in self.running_bots:
            bot.save_state()

        # Close connections
        for device in self.device_pool.devices:
            device.disconnect()

        # Stop event listeners
        self.event_bus.shutdown()

# Usage
shutdown_handler = GracefulShutdown()

try:
    await main_loop()
except KeyboardInterrupt:
    await shutdown_handler.cleanup()
```

### Crash Recovery

```python
class CrashRecovery:
    def recover_bot(self, bot_id: str):
        """Recover bot from crash"""

        # Load last known state
        state = self.state_manager.load_state(bot_id)

        if state:
            logger.info(f"Recovering bot {bot_id} from state")
            # Resume from checkpoint
            bot = self.load_bot(bot_id)
            bot.resume_from_state(state)
            return bot
        else:
            logger.warning(f"No saved state for {bot_id}, starting fresh")
            return self.load_bot(bot_id)
```

---

## 9️⃣ Best Practices

✅ **DO**:
- Persist bot state periodically
- Monitor resource usage continuously
- Use event bus for all UI updates
- Implement timeout on all operations
- Log all bot actions for debugging
- Gracefully handle app shutdown

❌ **DON'T**:
- Block UI thread with long operations (use async)
- Create new process for every command (use queue)
- Assume device stays connected (check state)
- Ignore resource limits (monitor memory)
- Store sensitive data in unencrypted state files
- Leave zombie processes on crash

---

**Status**: ✅ Tauri Integration Complete
**Next Phase**: Create 7 UV Scripts + 5 Agents + 4 Commands
