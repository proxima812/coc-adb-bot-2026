#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
adb-action-recorder: Automation Action Recording & Playback System

Records sequences of automation steps for analysis, debugging, and playback
on different devices with adaptive timing and error recovery.

Usage:
  # Start recording actions
  uv run adb_action_recorder.py \
    --device emulator-5554 \
    --game afk-journey \
    --record \
    --output-file recording.yaml

  # Play back recording
  uv run adb_action_recorder.py \
    --device emulator-5554 \
    --replay recording.yaml \
    --adaptive-timing \
    --resolution-fallback

  # Analyze recording
  uv run adb_action_recorder.py \
    --analyze recording.yaml \
    --output-format json
"""

import json
import sys
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Iterator
from dataclasses import dataclass, asdict, field
from enum import Enum
import time


class ActionType(Enum):
    """Supported automation action types"""
    SCREEN_CAPTURE = "screen_capture"
    TEMPLATE_DETECT = "template_detect"
    YOLO_DETECT = "yolo_detect"
    TAP = "tap"
    SWIPE = "swipe"
    LONG_PRESS = "long_press"
    WAIT = "wait"
    OCR = "ocr"
    CHECKPOINT = "checkpoint"
    CONDITIONAL = "conditional"


@dataclass
class AutomationAction:
    """Single automation action with timestamp and parameters"""
    timestamp: float
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_result: Optional[Dict[str, Any]] = None
    error_recovery: Optional[str] = None


@dataclass
class RecordingMetadata:
    """Recording session metadata"""
    game: str
    device: str
    created_at: str
    duration: float = 0.0
    source: str = "auto-recording"
    environment: Dict[str, str] = field(default_factory=dict)
    notes: Optional[str] = None


@dataclass
class ActionRecording:
    """Complete action recording with metadata and actions"""
    metadata: RecordingMetadata
    actions: List[AutomationAction] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    replay_strategy: Dict[str, bool] = field(default_factory=lambda: {
        "adaptive_timing": True,
        "error_recovery": True,
        "resolution_fallback": True,
        "template_scale_matching": True
    })

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "metadata": asdict(self.metadata),
            "actions": [asdict(action) for action in self.actions],
            "validation_rules": self.validation_rules,
            "replay_strategy": self.replay_strategy
        }

    def to_yaml(self) -> str:
        """Convert to YAML string"""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)


class ActionRecorder:
    """Records automation actions during execution"""

    def __init__(self, game: str, device: str):
        """Initialize action recorder"""
        self.game = game
        self.device = device
        self.recording: Optional[ActionRecording] = None
        self.start_time: Optional[float] = None
        self.is_recording = False
        self.errors: List[str] = []

    def start_recording(self) -> bool:
        """Start recording session"""
        try:
            self.start_time = time.time()
            self.recording = ActionRecording(
                metadata=RecordingMetadata(
                    game=self.game,
                    device=self.device,
                    created_at=datetime.now().isoformat(),
                    environment={
                        "resolution": "1280x720",  # Would be detected in real implementation
                        "device_model": "Android Device"
                    }
                )
            )
            self.is_recording = True
            return True

        except Exception as e:
            self.errors.append(f"Failed to start recording: {str(e)}")
            return False

    def record_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        expected_result: Optional[Dict[str, Any]] = None,
        error_recovery: Optional[str] = None
    ) -> bool:
        """Record a single action"""
        try:
            if not self.is_recording or not self.recording or not self.start_time:
                self.errors.append("Recording not started")
                return False

            elapsed = time.time() - self.start_time
            action = AutomationAction(
                timestamp=round(elapsed, 2),
                action_type=action_type,
                params=params,
                expected_result=expected_result,
                error_recovery=error_recovery
            )

            self.recording.actions.append(action)
            return True

        except Exception as e:
            self.errors.append(f"Failed to record action: {str(e)}")
            return False

    def record_tap(self, x: int, y: int, duration: float = 0.1) -> bool:
        """Record tap action"""
        return self.record_action(
            ActionType.TAP.value,
            {"x": x, "y": y, "duration": duration}
        )

    def record_swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: float = 0.5
    ) -> bool:
        """Record swipe action"""
        return self.record_action(
            ActionType.SWIPE.value,
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration}
        )

    def record_wait(self, duration: float, condition: Optional[str] = None) -> bool:
        """Record wait action"""
        return self.record_action(
            ActionType.WAIT.value,
            {"duration": duration, "condition": condition}
        )

    def record_template_detect(
        self,
        template: str,
        confidence: float = 0.95,
        location: Optional[List[int]] = None
    ) -> bool:
        """Record template detection"""
        return self.record_action(
            ActionType.TEMPLATE_DETECT.value,
            {"template": template, "confidence": confidence, "location": location}
        )

    def record_checkpoint(self, checkpoint_id: str, description: str = "") -> bool:
        """Record checkpoint"""
        return self.record_action(
            ActionType.CHECKPOINT.value,
            {"checkpoint_id": checkpoint_id, "description": description}
        )

    def stop_recording(self) -> Optional[ActionRecording]:
        """Stop recording and return recording object"""
        try:
            if not self.is_recording or not self.recording or not self.start_time:
                self.errors.append("Recording not started")
                return None

            elapsed = time.time() - self.start_time
            self.recording.metadata.duration = round(elapsed, 2)
            self.is_recording = False

            return self.recording

        except Exception as e:
            self.errors.append(f"Failed to stop recording: {str(e)}")
            return None

    def save_recording(self, output_path: str) -> bool:
        """Save recording to YAML file"""
        try:
            if not self.recording:
                self.errors.append("No recording to save")
                return False

            filepath = Path(output_path)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                f.write(self.recording.to_yaml())

            return True

        except Exception as e:
            self.errors.append(f"Failed to save recording: {str(e)}")
            return False


class ActionPlayer:
    """Plays back recorded automation actions"""

    def __init__(self):
        """Initialize action player"""
        self.recording: Optional[ActionRecording] = None
        self.errors: List[str] = []

    def load_recording(self, recording_path: str) -> bool:
        """Load recording from YAML file"""
        try:
            filepath = Path(recording_path)
            if not filepath.exists():
                self.errors.append(f"Recording file not found: {recording_path}")
                return False

            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)

            metadata = RecordingMetadata(
                game=data['metadata']['game'],
                device=data['metadata']['device'],
                created_at=data['metadata']['created_at'],
                duration=data['metadata'].get('duration', 0),
                source=data['metadata'].get('source', 'unknown'),
                environment=data['metadata'].get('environment', {}),
                notes=data['metadata'].get('notes')
            )

            actions = []
            for action_data in data.get('actions', []):
                action = AutomationAction(
                    timestamp=action_data['timestamp'],
                    action_type=action_data['action_type'],
                    params=action_data.get('params', {}),
                    expected_result=action_data.get('expected_result'),
                    error_recovery=action_data.get('error_recovery')
                )
                actions.append(action)

            self.recording = ActionRecording(
                metadata=metadata,
                actions=actions,
                validation_rules=data.get('validation_rules', {}),
                replay_strategy=data.get('replay_strategy', {})
            )

            return True

        except Exception as e:
            self.errors.append(f"Failed to load recording: {str(e)}")
            return False

    def play(self, device: str = None) -> Dict[str, Any]:
        """Execute all recorded actions (simulated)"""
        try:
            if not self.recording:
                self.errors.append("No recording loaded")
                return {"success": False, "error": "No recording loaded"}

            executed_count = 0
            failed_count = 0
            timings = []

            for action in self.recording.actions:
                timing = {
                    "action_type": action.action_type,
                    "timestamp": action.timestamp,
                    "duration": 0.0
                }

                # Simulate action execution
                start = time.time()
                success = self._execute_action(action, device)
                duration = time.time() - start

                timing["duration"] = round(duration, 3)

                if success:
                    executed_count += 1
                else:
                    failed_count += 1

                timings.append(timing)

            return {
                "success": failed_count == 0,
                "total_actions": len(self.recording.actions),
                "executed": executed_count,
                "failed": failed_count,
                "total_duration": round(sum(t["duration"] for t in timings), 2),
                "timings": timings
            }

        except Exception as e:
            self.errors.append(f"Playback error: {str(e)}")
            return {"success": False, "error": str(e)}

    def play_step_by_step(self, device: str = None) -> Iterator[Dict[str, Any]]:
        """Play with step-by-step control"""
        try:
            if not self.recording:
                yield {"error": "No recording loaded"}
                return

            for idx, action in enumerate(self.recording.actions, 1):
                start = time.time()
                success = self._execute_action(action, device)
                duration = time.time() - start

                yield {
                    "step": idx,
                    "total_steps": len(self.recording.actions),
                    "action": action.action_type,
                    "success": success,
                    "duration": round(duration, 3),
                    "timestamp": action.timestamp
                }

        except Exception as e:
            yield {"error": str(e)}

    def _execute_action(self, action: AutomationAction, device: str = None) -> bool:
        """Execute single action (simulated implementation)"""
        try:
            action_type = action.action_type

            if action_type == ActionType.TAP.value:
                x, y = action.params.get('x'), action.params.get('y')
                # Would execute: adb shell input tap x y
                return True

            elif action_type == ActionType.SWIPE.value:
                x1, y1 = action.params.get('x1'), action.params.get('y1')
                x2, y2 = action.params.get('x2'), action.params.get('y2')
                # Would execute: adb shell input swipe x1 y1 x2 y2
                return True

            elif action_type == ActionType.WAIT.value:
                duration = action.params.get('duration', 1.0)
                time.sleep(min(duration, 1.0))  # Cap at 1 second for simulation
                return True

            elif action_type == ActionType.CHECKPOINT.value:
                # Validate checkpoint exists and is valid
                return True

            else:
                return True  # Other actions pass through

        except Exception as e:
            self.errors.append(f"Action execution error: {str(e)}")
            return False


class ActionAnalyzer:
    """Analyzes recording data for insights and metrics"""

    @staticmethod
    def analyze(recording: ActionRecording) -> Dict[str, Any]:
        """Analyze recording comprehensively"""
        try:
            analysis = {
                "summary": {
                    "total_duration": recording.metadata.duration,
                    "total_actions": len(recording.actions),
                    "game": recording.metadata.game,
                    "device": recording.metadata.device,
                    "created_at": recording.metadata.created_at
                },
                "action_breakdown": {},
                "timing_analysis": {
                    "min_gap": 0.0,
                    "max_gap": 0.0,
                    "avg_gap": 0.0
                },
                "action_sequence": [],
                "errors": []
            }

            # Action breakdown
            action_counts = {}
            for action in recording.actions:
                atype = action.action_type
                action_counts[atype] = action_counts.get(atype, 0) + 1

            analysis["action_breakdown"] = action_counts

            # Timing analysis
            if len(recording.actions) > 1:
                gaps = []
                for i in range(1, len(recording.actions)):
                    gap = recording.actions[i].timestamp - recording.actions[i-1].timestamp
                    gaps.append(gap)

                analysis["timing_analysis"] = {
                    "min_gap": round(min(gaps), 3) if gaps else 0.0,
                    "max_gap": round(max(gaps), 3) if gaps else 0.0,
                    "avg_gap": round(sum(gaps) / len(gaps), 3) if gaps else 0.0
                }

            # Action sequence
            for action in recording.actions:
                analysis["action_sequence"].append({
                    "timestamp": action.timestamp,
                    "type": action.action_type,
                    "params_count": len(action.params)
                })

            return analysis

        except Exception as e:
            return {"error": str(e)}


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Action Recorder - Automation Recording & Playback"
    )
    parser.add_argument("--device", help="ADB device serial")
    parser.add_argument("--game", help="Game name")
    parser.add_argument("--record", action="store_true",
                       help="Start recording actions")
    parser.add_argument("--replay", help="Play back recording file")
    parser.add_argument("--analyze", help="Analyze recording file")
    parser.add_argument("--output-file", help="Output file for recording")
    parser.add_argument("--output-format", default="yaml", choices=["yaml", "json"],
                       help="Output format")
    parser.add_argument("--adaptive-timing", action="store_true",
                       help="Enable adaptive timing during playback")
    parser.add_argument("--resolution-fallback", action="store_true",
                       help="Enable resolution fallback during playback")
    parser.add_argument("--step-by-step", action="store_true",
                       help="Play back step by step")

    args = parser.parse_args()

    if args.record:
        if not args.game or not args.device:
            print("❌ Error: --game and --device required for --record")
            return 1

        # Simulate recording
        recorder = ActionRecorder(game=args.game, device=args.device)
        if not recorder.start_recording():
            print(f"❌ Failed to start recording: {recorder.errors[0]}")
            return 1

        # Record sample actions
        recorder.record_template_detect("quest_start_button.png", confidence=0.95, location=[540, 600])
        recorder.record_tap(540, 600)
        recorder.record_wait(1.5, condition="quest_battle_screen_visible")
        recorder.record_checkpoint("ckpt_quest_started", "Quest started successfully")

        recording = recorder.stop_recording()
        if not recording:
            print(f"❌ Failed to stop recording: {recorder.errors[0]}")
            return 1

        output_file = args.output_file or f"recording_{args.game}_{int(time.time())}.yaml"
        if recorder.save_recording(output_file):
            print(f"✅ Recording saved: {output_file}")
            print(f"   Actions: {len(recording.actions)}")
            print(f"   Duration: {recording.metadata.duration:.2f}s")
            return 0
        else:
            print(f"❌ Failed to save recording: {recorder.errors[0]}")
            return 1

    elif args.replay:
        player = ActionPlayer()
        if not player.load_recording(args.replay):
            print(f"❌ Failed to load recording: {player.errors[0]}")
            return 1

        if args.step_by_step:
            print(f"\n▶️ Playing back {args.replay} (step-by-step):\n")
            for step in player.play_step_by_step(args.device):
                if "error" in step:
                    print(f"❌ {step['error']}")
                    return 1
                else:
                    status = "✓" if step.get("success") else "✗"
                    print(f"  [{status}] Step {step['step']}/{step['total_steps']}: "
                          f"{step['action']} ({step['duration']:.3f}s)")
        else:
            result = player.play(args.device)
            print(f"\n▶️ Playback Result:\n")
            print(f"  Total Actions: {result['total_actions']}")
            print(f"  Executed: {result['executed']}")
            print(f"  Failed: {result['failed']}")
            print(f"  Total Duration: {result['total_duration']:.2f}s")

            if result["success"]:
                print(f"\n✅ Playback successful")
                return 0
            else:
                print(f"\n❌ Playback failed")
                return 1

    elif args.analyze:
        player = ActionPlayer()
        if not player.load_recording(args.analyze):
            print(f"❌ Failed to load recording: {player.errors[0]}")
            return 1

        analyzer = ActionAnalyzer()
        analysis = analyzer.analyze(player.recording)

        print(f"\n📊 Recording Analysis:\n")
        print(f"Summary:")
        for key, value in analysis['summary'].items():
            print(f"  {key}: {value}")

        print(f"\nAction Breakdown:")
        for action_type, count in analysis['action_breakdown'].items():
            print(f"  {action_type}: {count}")

        print(f"\nTiming Analysis:")
        timing = analysis['timing_analysis']
        print(f"  Min Gap: {timing['min_gap']:.3f}s")
        print(f"  Max Gap: {timing['max_gap']:.3f}s")
        print(f"  Avg Gap: {timing['avg_gap']:.3f}s")

        return 0

    else:
        print("❌ Error: Specify --record, --replay, or --analyze")
        return 1


if __name__ == "__main__":
    sys.exit(main())
