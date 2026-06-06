# Module 3: Game Automation

**Level**: Intermediate → Advanced
**Prerequisites**: Module 1 (adb-fundamentals), Module 2 (device-management)
**Estimated Learning Time**: 60-90 minutes
**Hands-On Practice**: 30-45 minutes

---

## 1️⃣ Bot Architecture Patterns

### Simple Sequence Bot

```
┌─────────────────┐
│   Game State    │ ← Monitor game screen
└────────┬────────┘
         │
    ┌────▼────┐
    │ Tap 1   │ ← Click button
    └────┬────┘
         │
    ┌────▼────┐
    │ Wait 2s │ ← Wait for animation
    └────┬────┘
         │
    ┌────▼────┐
    │ Tap 2   │ ← Click confirm
    └────┬────┘
         │
    ┌────▼────────┐
    │ Check result│ ← Verify success
    └─────────────┘
```

### State Machine Bot

```python
class BotState:
    def __init__(self):
        self.current_state = "MENU"
        self.frame_count = 0

    def update(self, screenshot_path: str) -> str:
        """Analyze screenshot and transition state"""

        image = cv2.imread(screenshot_path)
        detections = self.detector.detect(image)

        if "play_button" in detections:
            if self.current_state == "MENU":
                adb.tap(detections["play_button"].center)
                self.current_state = "LOADING"
                return "tap_play"

        elif "battle_ready" in detections:
            if self.current_state == "LOADING":
                self.current_state = "BATTLING"
                return "battle_started"

        else:
            return "waiting"

        self.frame_count += 1
        return self.current_state
```

---

## 2️⃣ Action Templates

### Click Sequences

```python
class ClickAction:
    def __init__(self, x: int, y: int, delay_ms: int = 500):
        self.x = x
        self.y = y
        self.delay_ms = delay_ms

    def execute(self, device):
        device.execute(f"adb shell input tap {self.x} {self.y}")
        time.sleep(self.delay_ms / 1000)

# Usage
actions = [
    ClickAction(x=540, y=960),           # Tap button 1
    ClickAction(x=540, y=1000),          # Tap button 2
    ClickAction(x=540, y=1100, 2000),    # Tap button 3, wait 2s
]

for action in actions:
    action.execute(device)
```

### Swipe Gestures

```python
class SwipeAction:
    def __init__(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.duration_ms = duration_ms

    def execute(self, device):
        cmd = f"adb shell input swipe {self.x1} {self.y1} {self.x2} {self.y2} {self.duration_ms}"
        device.execute(cmd)

# Usage: Swipe to open menu
swipe_open = SwipeAction(x1=0, y1=540, x2=200, y2=540, duration_ms=600)
swipe_open.execute(device)
```

### Text Input

```python
class TextAction:
    def __init__(self, text: str):
        self.text = text

    def execute(self, device):
        # Clear existing text
        device.execute("adb shell input keyevent 6 6 6")  # DEL key 3x
        # Type new text
        device.execute(f"adb shell input text '{self.text}'")

# Usage: Type username
text_action = TextAction("MyUsername123")
text_action.execute(device)
```

### Wait Actions

```python
class WaitAction:
    def __init__(self, duration_ms: int, until_condition=None):
        self.duration_ms = duration_ms
        self.until_condition = until_condition

    def execute(self, device):
        if self.until_condition:
            # Wait until condition met (max timeout)
            elapsed = 0
            while elapsed < self.duration_ms:
                if self.until_condition():
                    break
                time.sleep(0.1)
                elapsed += 100
        else:
            # Fixed wait
            time.sleep(self.duration_ms / 1000)

# Usage: Wait until specific button appears
wait = WaitAction(
    duration_ms=5000,
    until_condition=lambda: detector.detect_button("confirm_button")
)
wait.execute(device)
```

---

## 3️⃣ Timing Control

### Frame-Based Timing

```python
class BotTiming:
    def __init__(self, fps: int = 10):
        self.fps = fps
        self.frame_duration_ms = 1000 / fps  # 100ms per frame at 10 FPS

    def wait_next_frame(self):
        """Ensure minimum frame duration"""
        elapsed = (time.time() - self.last_frame_time) * 1000
        remaining = self.frame_duration_ms - elapsed

        if remaining > 0:
            time.sleep(remaining / 1000)

        self.last_frame_time = time.time()

# Usage: Maintain 10 FPS execution
timing = BotTiming(fps=10)

while running:
    # Execute action (may take 50-100ms)
    action.execute(device)

    # Wait to maintain frame rate
    timing.wait_next_frame()
```

### Adaptive Timing

```python
class AdaptiveTimer:
    def __init__(self):
        self.action_times = []  # Recent action durations

    def calculate_delay(self, action: Action) -> int:
        """Adjust delay based on action complexity"""

        base_delay = action.recommended_delay_ms

        # If device is slow, increase delay
        avg_time = sum(self.action_times[-10:]) / 10
        if avg_time > 200:  # Device slow
            return int(base_delay * 1.5)

        return base_delay

    def record_execution(self, action: Action, duration_ms: int):
        self.action_times.append(duration_ms)
```

---

## 4️⃣ Finite State Machines (FSM) - Advanced State Management

**Key Concept**: Explicit FSM design for predictable, recoverable bot behavior across all game states.

### FSM Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Game State Machine (AFK Journey Example)                │
├─────────────────────────────────────────────────────────┤
│                                                           │
│   ┌──────────┐                                            │
│   │  IDLE    │◄──────────────┐                            │
│   └────┬─────┘               │                            │
│        │                     │                            │
│        │ start_quest         │ quest_done               │
│        ▼                     │                            │
│   ┌──────────┐               │                            │
│   │ LOADING  │───────┐       │                            │
│   └────┬─────┘       │       │                            │
│        │             │       │                            │
│        │game_loaded  │timeout│                            │
│        ▼             ▼       │                            │
│   ┌──────────┐  ┌────────────┤                            │
│   │ BATTLING │──►│   ERROR    │                            │
│   └────┬─────┘  └──────┬─────┤                            │
│        │                │     │                            │
│        │battle_done     │retry│                            │
│        ▼                ▼     │                            │
│   ┌──────────┐  ┌──────────┐ │                            │
│   │  VICTORY │──►│ RECOVERY │─┘                            │
│   └────┬─────┘  └──────────┘                              │
│        │                                                   │
│        └──────────────────────────────────────────────────┘
│
```

### State Definition

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable

class BotState(Enum):
    """Enumeration of all possible bot states"""
    IDLE = "idle"                    # Waiting for action
    LOADING = "loading"              # Game/quest loading
    BATTLING = "battling"            # Battle in progress
    VICTORY = "victory"              # Battle won
    DEFEAT = "defeat"                # Battle lost
    ERROR = "error"                  # Unexpected state
    RECOVERY = "recovery"            # Attempting recovery
    PAUSED = "paused"                # User paused bot

@dataclass
class StateTransition:
    """Represents a state transition with guards and actions"""
    from_state: BotState
    to_state: BotState
    guard: Optional[Callable[[], bool]] = None    # Condition for transition
    action: Optional[Callable[[], None]] = None   # Action on transition
    timeout_sec: int = 30                          # Transition timeout
```

### Explicit FSM Implementation

```python
class GameBotFSM:
    """Finite State Machine for game automation"""

    def __init__(self, device, detector):
        self.device = device
        self.detector = detector
        self.current_state = BotState.IDLE
        self.state_entered_at = time.time()
        self.transitions = self._build_transitions()

    def _build_transitions(self) -> dict:
        """Define all valid state transitions"""
        return {
            BotState.IDLE: [
                StateTransition(
                    from_state=BotState.IDLE,
                    to_state=BotState.LOADING,
                    guard=self._detect_quest_button,
                    action=self._click_quest_button,
                    timeout_sec=5
                ),
            ],
            BotState.LOADING: [
                StateTransition(
                    from_state=BotState.LOADING,
                    to_state=BotState.BATTLING,
                    guard=self._detect_battle_ready,
                    action=self._start_battle,
                    timeout_sec=15
                ),
                StateTransition(
                    from_state=BotState.LOADING,
                    to_state=BotState.ERROR,
                    guard=lambda: self._check_timeout(15),
                    action=self._log_timeout,
                    timeout_sec=2
                ),
            ],
            BotState.BATTLING: [
                StateTransition(
                    from_state=BotState.BATTLING,
                    to_state=BotState.VICTORY,
                    guard=self._detect_victory,
                    action=self._claim_reward,
                    timeout_sec=60
                ),
                StateTransition(
                    from_state=BotState.BATTLING,
                    to_state=BotState.DEFEAT,
                    guard=self._detect_defeat,
                    action=self._handle_defeat,
                    timeout_sec=60
                ),
            ],
            BotState.VICTORY: [
                StateTransition(
                    from_state=BotState.VICTORY,
                    to_state=BotState.IDLE,
                    guard=self._detect_return_to_menu,
                    action=self._return_to_menu,
                    timeout_sec=10
                ),
            ],
            BotState.ERROR: [
                StateTransition(
                    from_state=BotState.ERROR,
                    to_state=BotState.RECOVERY,
                    guard=lambda: True,  # Always attempt recovery
                    action=self._initiate_recovery,
                    timeout_sec=5
                ),
            ],
            BotState.RECOVERY: [
                StateTransition(
                    from_state=BotState.RECOVERY,
                    to_state=BotState.IDLE,
                    guard=self._recovery_successful,
                    action=self._complete_recovery,
                    timeout_sec=10
                ),
            ],
        }

    def update(self) -> BotState:
        """Main FSM update loop - call each frame"""

        # Check for state-specific timeout
        if self._check_state_timeout():
            self._handle_state_timeout()
            return self.current_state

        # Try each valid transition from current state
        if self.current_state in self.transitions:
            for transition in self.transitions[self.current_state]:
                # Check if transition guard is met
                if transition.guard and transition.guard():
                    # Execute transition action
                    if transition.action:
                        transition.action()

                    # Update state
                    old_state = self.current_state
                    self.current_state = transition.to_state
                    self.state_entered_at = time.time()

                    logger.info(f"FSM: {old_state.value} → {self.current_state.value}")
                    return self.current_state

        # No transition triggered, stay in current state
        return self.current_state

    def _check_state_timeout(self) -> bool:
        """Check if current state has exceeded timeout"""
        elapsed = time.time() - self.state_entered_at
        timeout = self._get_state_timeout()
        return elapsed > timeout

    def _get_state_timeout(self) -> int:
        """Get timeout for current state"""
        state_timeouts = {
            BotState.LOADING: 20,
            BotState.BATTLING: 120,
            BotState.RECOVERY: 30,
        }
        return state_timeouts.get(self.current_state, 60)

    def _handle_state_timeout(self):
        """Handle timeout by transitioning to ERROR"""
        logger.warning(f"State timeout in {self.current_state.value}")
        self.current_state = BotState.ERROR
        self.state_entered_at = time.time()

    # Guard functions (check conditions)
    def _detect_quest_button(self) -> bool:
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "quest_button")

    def _detect_battle_ready(self) -> bool:
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "start_button")

    def _detect_victory(self) -> bool:
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "victory_screen")

    def _detect_defeat(self) -> bool:
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "defeat_screen")

    def _detect_return_to_menu(self) -> bool:
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "main_menu")

    def _recovery_successful(self) -> bool:
        state = self.detector.capture_and_analyze(self.device)
        # Consider recovery successful if we're back to a known state
        return (self.detector.detect_element(state["image"], "main_menu") or
                self.detector.detect_element(state["image"], "quest_list"))

    def _check_timeout(self, sec: int) -> bool:
        """Generic timeout check"""
        return (time.time() - self.state_entered_at) > sec

    # Action functions (perform side effects)
    def _click_quest_button(self):
        state = self.detector.capture_and_analyze(self.device)
        region = self.detector.get_element_region(state["image"], "quest_button")
        if region:
            cx = (region[0] + region[2]) // 2
            cy = (region[1] + region[3]) // 2
            self.device.tap(cx, cy)

    def _start_battle(self):
        self.device.tap(540, 960)  # "Start" button position

    def _claim_reward(self):
        self.device.tap(540, 1000)  # "Claim" button

    def _handle_defeat(self):
        logger.warning("Battle defeated, returning to menu")
        self.device.tap(100, 100)  # Back button

    def _return_to_menu(self):
        self.device.tap(100, 100)  # Back button

    def _initiate_recovery(self):
        """Reset to known state"""
        self.device.tap(100, 100)  # Home button
        time.sleep(2)

    def _complete_recovery(self):
        logger.info("Recovery complete")

    def _log_timeout(self):
        logger.error(f"Timeout in state {self.current_state.value}")

# Usage
fsm = GameBotFSM(device, detector)
while running:
    fsm.update()
    time.sleep(0.1)  # 10 FPS update rate
```

### FSM Benefits Over Sequence-Based Bots

| Aspect | Sequence Bot | FSM Bot |
|--------|--------------|---------|
| State Awareness | Linear flow, no true state | Explicit states with context |
| Error Recovery | Restart entire sequence | Recover from specific state |
| Timeout Handling | Generic wait, can hang | Per-state timeout protection |
| Debugging | Hard to trace execution | Clear state transitions logged |
| Maintainability | Add new steps = full rewrite | New state + transitions = modular |
| Performance | Fixed delays everywhere | Adaptive based on state |

### FSM Best Practices for Game Bots

✅ **DO**:
- Define all states upfront
- Make state transitions explicit and testable
- Use guards to check preconditions
- Log all state transitions
- Implement per-state timeouts
- Handle errors as dedicated states
- Keep state logic pure (no side effects in guards)

❌ **DON'T**:
- Perform heavy operations in guard functions (breaks responsiveness)
- Create circular state dependencies
- Skip error states ("it won't happen")
- Mix UI logic with state logic
- Hardcode timeouts (make configurable)

---

## 5️⃣ OCR Integration

### Text Detection

```python
import pytesseract

class OCRDetector:
    def detect_text(self, image_path: str) -> List[str]:
        """Extract all text from screenshot"""
        image = cv2.imread(image_path)
        text = pytesseract.image_to_string(image)
        return text.split('\n')

    def find_text(self, image_path: str, search_text: str) -> bool:
        """Check if specific text appears in screenshot"""
        text = pytesseract.image_to_string(cv2.imread(image_path))
        return search_text.lower() in text.lower()

    def get_text_location(self, image_path: str, search_text: str) -> Optional[tuple]:
        """Get (x, y) coordinates of text"""
        image = cv2.imread(image_path)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        for i, text in enumerate(data['text']):
            if search_text in text:
                x = data['left'][i] + data['width'][i] // 2
                y = data['top'][i] + data['height'][i] // 2
                return (x, y)

        return None

# Usage
ocr = OCRDetector()

# Check if battle is running
if ocr.find_text("screenshot.png", "Battling"):
    print("Battle in progress")

# Find and click on "Continue" button
location = ocr.get_text_location("screenshot.png", "Continue")
if location:
    device.tap(location[0], location[1])
```

### Language Support

```python
def detect_text_with_lang(image_path: str, lang: str = "eng") -> str:
    """Detect text with specific language"""
    image = cv2.imread(image_path)
    # Supported: "eng", "chi_sim", "kor", "jpn", etc.
    text = pytesseract.image_to_string(image, lang=lang)
    return text
```

---

## 5️⃣ State Detection

### Screenshot Analysis

```python
class StateDetector:
    def capture_and_analyze(self, device) -> dict:
        """Capture screenshot and analyze game state"""

        # Capture screenshot
        device.execute("adb shell screencap -p /sdcard/screen.png")
        device.pull("/sdcard/screen.png", "current.png")

        # Load and preprocess
        image = cv2.imread("current.png")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        return {
            "image": image,
            "gray": gray,
            "timestamp": time.time(),
            "text": pytesseract.image_to_string(image),
        }

    def detect_element(self, image, element_name: str) -> bool:
        """Check if UI element is visible"""
        # Load template
        template = cv2.imread(f"templates/{element_name}.png")

        # Match template in image
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Threshold for match confidence
        return max_val > 0.8

    def get_element_region(self, image, element_name: str) -> Optional[tuple]:
        """Get bounding box of UI element"""
        template = cv2.imread(f"templates/{element_name}.png")
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > 0.8:
            h, w = template.shape[:2]
            return (max_loc[0], max_loc[1], max_loc[0] + w, max_loc[1] + h)

        return None

# Usage
detector = StateDetector()
state = detector.capture_and_analyze(device)

if detector.detect_element(state["image"], "play_button"):
    print("Ready to start!")
```

---

## 6️⃣ Bot Routine Templates

### Daily Quest Bot

```python
class DailyQuestBot:
    def run(self, device):
        """Execute daily quests"""

        for quest_num in range(5):
            # Capture state
            state = self.detector.capture_and_analyze(device)

            # Find and click quest
            quest_btn = self.detector.get_element_region(state["image"], "quest_button")
            if quest_btn:
                center_x = (quest_btn[0] + quest_btn[2]) // 2
                center_y = (quest_btn[1] + quest_btn[3]) // 2
                device.tap(center_x, center_y)

            # Wait for quest load
            time.sleep(2)

            # Start battle
            device.tap(540, 960)  # "Start" button

            # Wait for battle complete
            self.wait_until(device, "battle_complete", timeout_sec=30)

            # Claim reward
            device.tap(540, 1000)

            # Return to menu
            device.tap(100, 100)  # Back button

            time.sleep(1)

    def wait_until(self, device, element: str, timeout_sec: int):
        """Wait for element to appear"""
        start = time.time()

        while time.time() - start < timeout_sec:
            state = self.detector.capture_and_analyze(device)
            if self.detector.detect_element(state["image"], element):
                return True
            time.sleep(0.5)

        raise TimeoutError(f"Element {element} not found after {timeout_sec}s")
```

### Arena Battle Bot

```python
class ArenaBattleBot:
    def run_battles(self, device, count: int = 5):
        """Run arena battles and claim rewards"""

        for _ in range(count):
            # Check opponent
            self.check_opponent(device)

            # Start battle
            device.tap(540, 960)

            # Wait battle to complete
            self.wait_battle_done(device)

            # Auto-battle if available
            if self.has_auto_battle(device):
                device.tap(100, 100)  # Auto button

            # Collect reward
            device.tap(540, 1000)

    def has_auto_battle(self, device) -> bool:
        """Check if auto-battle button available"""
        state = self.detector.capture_and_analyze(device)
        return self.detector.detect_element(state["image"], "auto_button")

    def wait_battle_done(self, device):
        """Wait for battle to finish"""
        self.wait_until(device, "victory_screen", timeout_sec=60)
```

---

## 7️⃣ Error Recovery

### Retry with Screenshot Comparison

```python
def execute_action_with_recovery(action: Action, device, max_retries: int = 3):
    """Execute action with error recovery"""

    for attempt in range(max_retries):
        try:
            # Capture before
            before_state = detector.capture_and_analyze(device)

            # Execute action
            action.execute(device)
            time.sleep(action.expected_delay_ms / 1000)

            # Capture after
            after_state = detector.capture_and_analyze(device)

            # Verify change
            if not are_similar(before_state["image"], after_state["image"]):
                return True  # State changed, action succeeded

            # State didn't change, retry
            logger.warning(f"Action {action} didn't change state, retrying...")

        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")

            if attempt < max_retries - 1:
                # Recovery: tap back or home to reset
                device.tap(100, 100)
                time.sleep(1)

    return False  # All retries failed

def are_similar(img1, img2, threshold=0.85) -> bool:
    """Compare two images for similarity"""
    # Use structural similarity (SSIM)
    from skimage.metrics import structural_similarity as ssim
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    return ssim(gray1, gray2) > threshold
```

---

## 8️⃣ Performance Optimization

### Batch Screenshot Processing

```python
def process_screenshots_batch(device, action_count: int):
    """Process multiple screenshots efficiently"""

    # Capture all screenshots at once
    for i in range(action_count):
        device.execute(f"adb shell screencap -p /sdcard/screen_{i}.png")

    # Pull all to local
    device.execute("adb pull /sdcard/screen_*.png ./")

    # Process locally (faster than per-screenshot captures)
    for i in range(action_count):
        image = cv2.imread(f"screen_{i}.png")
        # Analyze...
```

### Template Caching

```python
class TemplateCache:
    def __init__(self):
        self.templates = {}

    def get_template(self, name: str):
        if name not in self.templates:
            self.templates[name] = cv2.imread(f"templates/{name}.png")
        return self.templates[name]

    def clear(self):
        self.templates.clear()
```

---

## 5️⃣ Retry Logic & Error Recovery

### Exponential Backoff Configuration

```toml
[retry]
enabled = true
max_attempts = 5
base_delay_seconds = 1.0
max_delay_seconds = 20.0
backoff_multiplier = 2.0
jitter_enabled = true
jitter_factor = 0.1

# Per-action retry configuration
[retry.strategies]
click = { max_attempts = 3, base_delay = 0.5 }
screenshot = { max_attempts = 2, base_delay = 0.2 }
swipe = { max_attempts = 3, base_delay = 1.0 }
wait_element = { max_attempts = 7, base_delay = 1.0, max_delay = 30.0 }
```

### Implementation with Tenacity

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import time

class RetryableClickAction:
    def __init__(self, x: int, y: int, delay_ms: int = 500, max_retries: int = 3):
        self.x = x
        self.y = y
        self.delay_ms = delay_ms
        self.max_retries = max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        retry=retry_if_exception_type((IOError, TimeoutError))
    )
    def execute(self, device) -> bool:
        """Execute tap with exponential backoff retry."""
        try:
            # Capture state before
            before_state = device.screenshot()

            # Execute tap
            device.tap(self.x, self.y)
            time.sleep(self.delay_ms / 1000)

            # Verify state changed
            after_state = device.screenshot()

            if not self._are_similar(before_state, after_state):
                return True  # Success

            # State unchanged, retry
            raise IOError("Tap did not change state")

        except (IOError, TimeoutError) as e:
            print(f"Click failed: {e}, will retry...")
            raise

    def _are_similar(self, img1, img2, threshold=0.85) -> bool:
        """Compare screenshots for similarity."""
        # Simplified comparison (use SSIM in production)
        return True  # Implementation depends on CV library

# Usage
action = RetryableClickAction(x=540, y=960)
try:
    action.execute(device)
except Exception as e:
    print(f"Click failed after retries: {e}")
```

### Per-Action Retry Configuration

```python
class ClickAction:
    def __init__(self, x: int, y: int, delay_ms: int = 500):
        self.x = x
        self.y = y
        self.delay_ms = delay_ms
        self.action_type = "click"

    def execute_with_config_retry(self, device, retry_config: dict) -> bool:
        """Execute with retry config from TOML."""

        strategy = retry_config.get("strategies", {}).get(self.action_type, {})
        max_attempts = strategy.get("max_attempts", retry_config.get("max_attempts", 3))
        base_delay = strategy.get("base_delay", retry_config.get("base_delay_seconds", 1.0))

        for attempt in range(max_attempts):
            try:
                device.tap(self.x, self.y)
                time.sleep(self.delay_ms / 1000)
                return True

            except Exception as e:
                if attempt < max_attempts - 1:
                    # Calculate backoff
                    delay = self._calculate_backoff(attempt, base_delay, strategy.get("max_delay", 20.0))
                    print(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    print(f"Click failed after {max_attempts} attempts: {e}")
                    raise

        return False

    def _calculate_backoff(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate exponential backoff with jitter."""
        import random

        if attempt == 0:
            return 0

        delay = (2 ** attempt) * base_delay
        delay = min(delay, max_delay)

        # Add 10% jitter
        jitter = random.uniform(-0.1 * delay, 0.1 * delay)
        return max(0, delay + jitter)

# Usage
import toml

config = toml.load("game_config.toml")
action = ClickAction(540, 960)
action.execute_with_config_retry(device, config["retry"])
```

### Error Recovery Patterns

```python
class ErrorRecoveryHandler:
    """Handle common game errors with recovery strategies."""

    def handle_tap_failure(self, device, x: int, y: int):
        """Recover from failed tap."""
        # Tap back button to reset state
        device.tap(100, 100)
        time.sleep(0.5)

        # Retry original action
        device.tap(x, y)

    def handle_screenshot_failure(self, device):
        """Recover from screenshot capture failure."""
        # Restart ADB connection
        device.restart()
        time.sleep(2)

        # Retry screenshot
        return device.screenshot()

    def handle_timeout(self, device, element: str, timeout_sec: int = 30):
        """Recover from element not appearing."""
        # Close any dialogs
        device.tap(100, 100)
        time.sleep(1)

        # Reopen game location
        device.tap(540, 540)  # Center tap
        time.sleep(2)

        # Check element again
        return self._check_element_visible(device, element)

    def _check_element_visible(self, device, element: str) -> bool:
        """Verify element is visible."""
        screenshot = device.screenshot()
        # Template matching logic
        return True  # Simplified
```

---

## 6️⃣ State Machine with Recovery

### FSM State Transitions

```
┌─────────────┐
│    MENU     │
│ (start)     │
└─────┬───────┘
      │ (tap_play)
      ↓ [retry_on_fail]
┌─────────────┐
│  LOADING    │
│ (buffering) │
└─────┬───────┘
      │ (loaded)
      ↓ [retry_on_fail]
┌─────────────┐
│  BATTLE     │ ←─────────┐
│ (fighting)  │           │
└─────┬───────┘           │
      │ (battle_won/lost)  │
      ↓ [retry_on_fail]    │
┌─────────────┐            │
│   REWARDS   │            │
│  (claiming) │            │
└─────┬───────┘            │
      │ (claimed)          │
      ↓ [retry_on_fail]    │
┌─────────────┐            │
│    MENU     │            │
│ (completed) │────────────┘
└─────────────┘   (restart_loop)
```

### FSM with Recovery Paths

```python
from enum import Enum
from typing import Callable, Optional

class GameState(Enum):
    MENU = "menu"
    LOADING = "loading"
    BATTLE = "battle"
    REWARDS = "rewards"

class GameFSM:
    def __init__(self, device, state_detector):
        self.device = device
        self.detector = state_detector
        self.state = GameState.MENU
        self.retry_count = 0
        self.max_retries = 3

    def transition(self, action: Callable, next_state: GameState) -> bool:
        """Transition to next state with retry."""

        for attempt in range(self.max_retries):
            try:
                # Execute action
                action()

                # Verify state transition
                time.sleep(1)
                current = self._detect_state()

                if current == next_state:
                    self.state = next_state
                    self.retry_count = 0
                    print(f"Transitioned to {next_state.value}")
                    return True

                # State didn't change, retry
                print(f"State didn't change, retrying (attempt {attempt + 1})...")

            except Exception as e:
                print(f"Action failed: {e}, attempting recovery...")
                self._recover_from_error()

        # Recovery failed
        print(f"Failed to transition to {next_state.value} after {self.max_retries} attempts")
        return False

    def _detect_state(self) -> GameState:
        """Detect current game state from screenshot."""
        screenshot = self.device.screenshot()

        if self.detector.has_element(screenshot, "play_button"):
            return GameState.MENU
        elif self.detector.has_element(screenshot, "loading_spinner"):
            return GameState.LOADING
        elif self.detector.has_element(screenshot, "battle_ui"):
            return GameState.BATTLE
        elif self.detector.has_element(screenshot, "rewards"):
            return GameState.REWARDS

        return self.state  # Unknown, assume no change

    def _recover_from_error(self):
        """Recover from error state."""
        # Close dialogs
        self.device.tap(100, 100)  # Back button
        time.sleep(1)

        # Verify we're in a known state
        self.state = self._detect_state()
        print(f"Recovered to state: {self.state.value}")

    def run_battle_loop(self):
        """Run a complete battle loop with recovery."""

        # MENU → LOADING
        if not self.transition(
            action=lambda: self.device.tap(540, 960),
            next_state=GameState.LOADING
        ):
            return False

        # LOADING → BATTLE
        if not self.transition(
            action=lambda: time.sleep(2),  # Wait for load
            next_state=GameState.BATTLE
        ):
            return False

        # BATTLE → REWARDS
        if not self.transition(
            action=lambda: time.sleep(10),  # Battle duration
            next_state=GameState.REWARDS
        ):
            return False

        # REWARDS → MENU
        if not self.transition(
            action=lambda: self.device.tap(540, 1000),  # Claim button
            next_state=GameState.MENU
        ):
            return False

        return True
```

---

## 9️⃣ Best Practices

✅ **DO**:
- Capture screenshot before critical decision
- Implement timeout on all wait operations
- Use state machine for complex flows
- Cache templates to avoid disk I/O
- Log action sequences for debugging
- Validate bot changes on test device first
- Implement exponential backoff for retries
- Use circuit breaker for external services
- Monitor device health continuously
- Save checkpoints before risky operations

❌ **DON'T**:
- Assume timing without testing on actual device
- Tap random coordinates without verification
- Ignore OCR errors (fallback to template matching)
- Run bot 24/7 without monitoring (risk ban)
- Use hard-coded delays (use state detection)
- Modify game assets while bot running
- Retry infinite times without bounds
- Assume device health remains stable
- Skip error recovery mechanisms
- Ignore checkpoint corruption

---

**Status**: ✅ Game Automation Patterns Covered
**Next Module**: [computer-vision](./computer-vision.md)
**Related Patterns**: [resilience-patterns](./resilience-patterns.md)
