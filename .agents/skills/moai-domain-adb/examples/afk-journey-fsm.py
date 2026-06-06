#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example: AFK Journey Daily Quest Bot with Explicit FSM

This example implements a complete daily quest bot using the FSM pattern
from game-automation.md Module 4.

Features:
  - State machine with 8 game states
  - Per-state timeout protection
  - Automatic error recovery
  - Per-quest timeout tracking
  - Comprehensive state transition logging
  - Support for 5 daily quests

Usage:
  fsm = AFKJourneyDailyQuestFSM(device, detector)
  while True:
      fsm.update()
      time.sleep(0.1)
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, List
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# State Definitions
# ============================================================================

class DailyQuestState(Enum):
    """AFK Journey Daily Quest FSM States"""
    IDLE = "idle"                        # Waiting to start
    MENU_OPEN = "menu_open"              # Menu is open
    QUEST_SELECTED = "quest_selected"    # Quest selected
    BATTLE_LOADING = "battle_loading"    # Battle loading
    BATTLE_RUNNING = "battle_running"    # Battle in progress
    BATTLE_RESULT = "battle_result"      # Result screen showing
    REWARD_CLAIMED = "reward_claimed"    # Reward taken
    ERROR = "error"                      # Error state


@dataclass
class StateTransition:
    """State transition definition"""
    from_state: DailyQuestState
    to_state: DailyQuestState
    guard: Optional[Callable[[], bool]] = None
    action: Optional[Callable[[], None]] = None
    timeout_sec: int = 30


# ============================================================================
# AFK Journey FSM Implementation
# ============================================================================

class AFKJourneyDailyQuestFSM:
    """Finite State Machine for AFK Journey daily quests"""

    def __init__(self, device, detector):
        """Initialize FSM"""
        self.device = device
        self.detector = detector
        self.current_state = DailyQuestState.IDLE
        self.state_entered_at = time.time()
        self.quest_count = 0
        self.max_quests = 5
        self.transitions = self._build_transitions()
        self.state_timestamps = []
        logger.info("AFKJourneyDailyQuestFSM initialized")

    def _build_transitions(self) -> dict:
        """Define all valid state transitions"""
        return {
            DailyQuestState.IDLE: [
                StateTransition(
                    from_state=DailyQuestState.IDLE,
                    to_state=DailyQuestState.MENU_OPEN,
                    guard=self._can_start_quests,
                    action=self._open_menu,
                    timeout_sec=10
                ),
            ],
            DailyQuestState.MENU_OPEN: [
                StateTransition(
                    from_state=DailyQuestState.MENU_OPEN,
                    to_state=DailyQuestState.QUEST_SELECTED,
                    guard=self._detect_quest_button,
                    action=self._select_quest,
                    timeout_sec=10
                ),
                StateTransition(
                    from_state=DailyQuestState.MENU_OPEN,
                    to_state=DailyQuestState.IDLE,
                    guard=self._all_quests_complete,
                    action=self._close_menu,
                    timeout_sec=5
                ),
            ],
            DailyQuestState.QUEST_SELECTED: [
                StateTransition(
                    from_state=DailyQuestState.QUEST_SELECTED,
                    to_state=DailyQuestState.BATTLE_LOADING,
                    guard=self._detect_start_button,
                    action=self._start_battle,
                    timeout_sec=5
                ),
            ],
            DailyQuestState.BATTLE_LOADING: [
                StateTransition(
                    from_state=DailyQuestState.BATTLE_LOADING,
                    to_state=DailyQuestState.BATTLE_RUNNING,
                    guard=self._battle_started,
                    action=None,  # No action needed
                    timeout_sec=20
                ),
            ],
            DailyQuestState.BATTLE_RUNNING: [
                StateTransition(
                    from_state=DailyQuestState.BATTLE_RUNNING,
                    to_state=DailyQuestState.BATTLE_RESULT,
                    guard=self._battle_complete,
                    action=None,  # Battle completes automatically
                    timeout_sec=120
                ),
            ],
            DailyQuestState.BATTLE_RESULT: [
                StateTransition(
                    from_state=DailyQuestState.BATTLE_RESULT,
                    to_state=DailyQuestState.REWARD_CLAIMED,
                    guard=self._detect_reward_button,
                    action=self._claim_reward,
                    timeout_sec=10
                ),
            ],
            DailyQuestState.REWARD_CLAIMED: [
                StateTransition(
                    from_state=DailyQuestState.REWARD_CLAIMED,
                    to_state=DailyQuestState.MENU_OPEN,
                    guard=self._returned_to_menu,
                    action=None,
                    timeout_sec=10
                ),
            ],
            DailyQuestState.ERROR: [
                StateTransition(
                    from_state=DailyQuestState.ERROR,
                    to_state=DailyQuestState.IDLE,
                    guard=lambda: True,
                    action=self._reset_to_idle,
                    timeout_sec=5
                ),
            ],
        }

    def update(self) -> DailyQuestState:
        """
        Main FSM update loop.
        Call this every 100ms for smooth operation.
        """
        # Check for state timeout
        if self._check_state_timeout():
            self._log_timeout()
            self.current_state = DailyQuestState.ERROR
            self.state_entered_at = time.time()
            return self.current_state

        # Try transitions from current state
        if self.current_state in self.transitions:
            for transition in self.transitions[self.current_state]:
                if transition.guard and transition.guard():
                    # Execute transition
                    if transition.action:
                        transition.action()

                    # Update state
                    old_state = self.current_state
                    self.current_state = transition.to_state
                    self.state_entered_at = time.time()

                    # Log transition
                    self._log_transition(old_state, self.current_state)
                    return self.current_state

        return self.current_state

    def is_complete(self) -> bool:
        """Check if all quests completed"""
        return (self.current_state == DailyQuestState.IDLE and
                self.quest_count >= self.max_quests)

    # ========================================================================
    # Guard Functions (Precondition Checks)
    # ========================================================================

    def _can_start_quests(self) -> bool:
        """Can start new quest batch"""
        return self.quest_count < self.max_quests

    def _all_quests_complete(self) -> bool:
        """All 5 quests completed"""
        return self.quest_count >= self.max_quests

    def _detect_quest_button(self) -> bool:
        """Quest button visible"""
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "quest_button")

    def _detect_start_button(self) -> bool:
        """Start battle button visible"""
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "start_button")

    def _battle_started(self) -> bool:
        """Battle animation started"""
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "battle_animation")

    def _battle_complete(self) -> bool:
        """Battle finished (victory or defeat)"""
        state = self.detector.capture_and_analyze(self.device)
        return (self.detector.detect_element(state["image"], "victory_screen") or
                self.detector.detect_element(state["image"], "defeat_screen"))

    def _detect_reward_button(self) -> bool:
        """Reward claim button visible"""
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "reward_button")

    def _returned_to_menu(self) -> bool:
        """Returned to quest menu"""
        state = self.detector.capture_and_analyze(self.device)
        return self.detector.detect_element(state["image"], "quest_menu")

    # ========================================================================
    # Action Functions (Side Effects)
    # ========================================================================

    def _open_menu(self):
        """Open quest menu"""
        logger.info(f"Opening menu (Quest {self.quest_count + 1}/5)")
        # Navigate to menu if needed
        state = self.detector.capture_and_analyze(self.device)
        if not self.detector.detect_element(state["image"], "quest_menu"):
            self.device.tap(540, 100)  # Menu button
            time.sleep(1)

    def _select_quest(self):
        """Select next quest"""
        logger.info(f"Selecting quest {self.quest_count + 1}/5")
        state = self.detector.capture_and_analyze(self.device)
        region = self.detector.get_element_region(state["image"], "quest_button")
        if region:
            cx = (region[0] + region[2]) // 2
            cy = (region[1] + region[3]) // 2
            self.device.tap(cx, cy)
            time.sleep(2)  # Wait for quest detail to load

    def _start_battle(self):
        """Start the battle"""
        logger.info("Starting battle")
        self.device.tap(540, 960)  # Start button
        time.sleep(2)

    def _claim_reward(self):
        """Claim quest reward"""
        logger.info(f"Claiming reward for quest {self.quest_count + 1}/5")
        self.device.tap(540, 1000)  # Reward button
        self.quest_count += 1
        logger.info(f"Quests completed: {self.quest_count}/{self.max_quests}")
        time.sleep(1)

    def _close_menu(self):
        """Close quest menu"""
        logger.info("All quests completed, closing menu")
        self.device.tap(100, 100)  # Back button
        time.sleep(1)

    def _reset_to_idle(self):
        """Reset FSM to idle after error"""
        logger.warning("Error occurred, resetting to idle")
        self.device.tap(100, 100)  # Home button
        time.sleep(2)

    # ========================================================================
    # Timeout & Logging
    # ========================================================================

    def _check_state_timeout(self) -> bool:
        """Check if state exceeded timeout"""
        elapsed = time.time() - self.state_entered_at
        timeout = self._get_state_timeout()
        return elapsed > timeout

    def _get_state_timeout(self) -> int:
        """Get timeout for current state"""
        state_timeouts = {
            DailyQuestState.MENU_OPEN: 30,
            DailyQuestState.BATTLE_LOADING: 30,
            DailyQuestState.BATTLE_RUNNING: 180,
            DailyQuestState.BATTLE_RESULT: 30,
        }
        return state_timeouts.get(self.current_state, 60)

    def _log_transition(self, from_state: DailyQuestState, to_state: DailyQuestState):
        """Log state transition"""
        elapsed = time.time() - self.state_entered_at
        logger.info(f"FSM: {from_state.value} → {to_state.value} "
                   f"(spent {elapsed:.1f}s in {from_state.value})")
        self.state_timestamps.append({
            'from': from_state.value,
            'to': to_state.value,
            'time': datetime.now().isoformat()
        })

    def _log_timeout(self):
        """Log timeout event"""
        elapsed = time.time() - self.state_entered_at
        timeout = self._get_state_timeout()
        logger.error(f"Timeout in {self.current_state.value}: "
                    f"spent {elapsed:.1f}s > {timeout}s")

    def get_state_summary(self) -> dict:
        """Get current execution summary"""
        return {
            'state': self.current_state.value,
            'quests_completed': self.quest_count,
            'is_complete': self.is_complete(),
            'transitions': len(self.state_timestamps),
            'timestamp': datetime.now().isoformat()
        }


# ============================================================================
# Example Usage
# ============================================================================

def main():
    """Example: Run daily quest bot with FSM"""
    from unittest.mock import Mock

    # Create mock device and detector
    device = Mock()
    detector = Mock()

    # Setup detector mocks
    detector.capture_and_analyze = Mock(return_value={'image': Mock()})
    detector.detect_element = Mock(return_value=False)
    detector.get_element_region = Mock(return_value=(0, 0, 100, 100))

    # Create FSM
    fsm = AFKJourneyDailyQuestFSM(device, detector)

    # Simulate quest execution
    logger.info("Starting daily quest automation")

    for i in range(100):  # 100 updates (10 seconds at 10 FPS)
        # Simulate quest progression
        if i == 2:
            detector.detect_element.side_effect = lambda img, elem: elem == "quest_button"
        elif i == 5:
            detector.detect_element.side_effect = lambda img, elem: elem == "start_button"
        elif i == 10:
            detector.detect_element.side_effect = lambda img, elem: elem == "battle_animation"
        elif i == 50:
            detector.detect_element.side_effect = lambda img, elem: elem == "victory_screen"
        elif i == 60:
            detector.detect_element.side_effect = lambda img, elem: elem == "reward_button"
        elif i == 70:
            detector.detect_element.side_effect = lambda img, elem: elem == "quest_menu"
            fsm.quest_count = 1  # Simulate quest completion
        else:
            detector.detect_element.side_effect = lambda img, elem: False

        # Update FSM
        fsm.update()

        # Check completion
        if fsm.is_complete():
            logger.info("All quests completed!")
            break

        time.sleep(0.1)

    # Print summary
    print("\nFSM Execution Summary:")
    print(f"  Final State: {fsm.current_state.value}")
    print(f"  Quests Completed: {fsm.quest_count}")
    print(f"  Total Transitions: {len(fsm.state_timestamps)}")
    print(f"  Is Complete: {fsm.is_complete()}")


if __name__ == "__main__":
    main()
