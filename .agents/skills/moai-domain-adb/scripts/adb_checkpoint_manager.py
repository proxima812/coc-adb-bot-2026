#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
adb-checkpoint-manager: State Checkpointing & Recovery System

Enables long-running automation to save and resume from checkpoints,
reducing restart time and improving reliability for game automation.

Usage:
  # Save current state as checkpoint
  uv run adb_checkpoint_manager.py \
    --device emulator-5554 \
    --game afk-journey \
    --save-checkpoint

  # List available checkpoints
  uv run adb_checkpoint_manager.py \
    --list-checkpoints \
    --game afk-journey

  # Load from checkpoint
  uv run adb_checkpoint_manager.py \
    --load-checkpoint ckpt_afk_20251202_150000_abc123
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib


class CheckpointType(Enum):
    """Checkpoint types"""
    MANUAL = "manual"
    AUTO = "auto"
    MILESTONE = "milestone"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class FSMStateData:
    """FSM state data for checkpointing"""
    current_state: str
    state_entry_time: str
    timeout_remaining: int
    iteration: int
    progress: Dict = field(default_factory=dict)


@dataclass
class DeviceStateData:
    """Device state data"""
    serial: str
    battery_percent: int
    memory_percent: int
    temperature_celsius: Optional[int] = None


@dataclass
class AutomationContextData:
    """Automation context data"""
    current_target: str
    detection_scale: float
    last_action_time: str
    action_queue: List[Dict] = field(default_factory=list)


@dataclass
class RecoveryStateData:
    """Recovery state data"""
    failed_attempts: int
    last_error: Optional[str] = None
    recovery_strategy: str = "none"


@dataclass
class Checkpoint:
    """Complete checkpoint data"""
    checkpoint_id: str
    game: str
    created_at: str
    resumed_at: Optional[str] = None
    duration_seconds: float = 0.0
    checkpoint_type: str = "manual"
    fsm_state: Optional[FSMStateData] = None
    device_state: Optional[DeviceStateData] = None
    automation_context: Optional[AutomationContextData] = None
    recovery_state: Optional[RecoveryStateData] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        # Keep nested dataclasses as dicts (from asdict)
        return data

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)


class CheckpointManager:
    """Manages automation state checkpointing and recovery"""

    def __init__(self, storage_dir: str = ".moai/checkpoints"):
        """Initialize checkpoint manager"""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints: Dict[str, Checkpoint] = {}
        self._load_existing_checkpoints()

    def save_checkpoint(
        self,
        game: str,
        device_serial: str,
        fsm_state: Optional[Dict] = None,
        device_state: Optional[Dict] = None,
        automation_context: Optional[Dict] = None,
        checkpoint_type: str = "manual",
        metadata: Optional[Dict] = None
    ) -> str:
        """Save current automation state as checkpoint"""
        try:
            # Generate checkpoint ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            hash_suffix = hashlib.md5(f"{timestamp}{game}".encode()).hexdigest()[:6]
            checkpoint_id = f"ckpt_{game}_{timestamp}_{hash_suffix}"

            # Create checkpoint object
            checkpoint = Checkpoint(
                checkpoint_id=checkpoint_id,
                game=game,
                created_at=datetime.now().isoformat(),
                checkpoint_type=checkpoint_type,
                fsm_state=FSMStateData(**fsm_state) if fsm_state else None,
                device_state=DeviceStateData(**device_state) if device_state else None,
                automation_context=AutomationContextData(**automation_context) if automation_context else None,
                recovery_state=RecoveryStateData(failed_attempts=0),
                metadata=metadata or {}
            )

            # Save to file
            filepath = self.storage_dir / f"{checkpoint_id}.json"
            with open(filepath, 'w') as f:
                f.write(checkpoint.to_json())

            self.checkpoints[checkpoint_id] = checkpoint
            return checkpoint_id

        except Exception as e:
            print(f"❌ Failed to save checkpoint: {str(e)}", file=sys.stderr)
            return ""

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load checkpoint from storage"""
        try:
            if checkpoint_id in self.checkpoints:
                checkpoint = self.checkpoints[checkpoint_id]
                checkpoint.resumed_at = datetime.now().isoformat()
                return checkpoint

            # Try to load from file
            filepath = self.storage_dir / f"{checkpoint_id}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)

                # Reconstruct checkpoint
                checkpoint = Checkpoint(
                    checkpoint_id=data['checkpoint_id'],
                    game=data['game'],
                    created_at=data['created_at'],
                    resumed_at=datetime.now().isoformat(),
                    duration_seconds=data.get('duration_seconds', 0),
                    checkpoint_type=data.get('checkpoint_type', 'manual'),
                    fsm_state=FSMStateData(**data['fsm_state']) if data.get('fsm_state') else None,
                    device_state=DeviceStateData(**data['device_state']) if data.get('device_state') else None,
                    automation_context=AutomationContextData(**data['automation_context']) if data.get('automation_context') else None,
                    recovery_state=RecoveryStateData(**data['recovery_state']) if data.get('recovery_state') else None,
                    metadata=data.get('metadata', {})
                )

                self.checkpoints[checkpoint_id] = checkpoint
                return checkpoint

            return None

        except Exception as e:
            print(f"❌ Failed to load checkpoint: {str(e)}", file=sys.stderr)
            return None

    def list_checkpoints(self, game: Optional[str] = None, limit: int = 20) -> List[Checkpoint]:
        """List available checkpoints"""
        checkpoints = list(self.checkpoints.values())

        if game:
            checkpoints = [c for c in checkpoints if c.game == game]

        # Sort by creation time, newest first
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints[:limit]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete checkpoint"""
        try:
            filepath = self.storage_dir / f"{checkpoint_id}.json"
            if filepath.exists():
                filepath.unlink()

            if checkpoint_id in self.checkpoints:
                del self.checkpoints[checkpoint_id]

            return True

        except Exception as e:
            print(f"❌ Failed to delete checkpoint: {str(e)}", file=sys.stderr)
            return False

    def cleanup_old_checkpoints(self, game: str, keep_count: int = 5) -> int:
        """Delete old checkpoints, keeping only recent ones"""
        try:
            game_checkpoints = self.list_checkpoints(game=game, limit=1000)

            deleted_count = 0
            for checkpoint in game_checkpoints[keep_count:]:
                if self.delete_checkpoint(checkpoint.checkpoint_id):
                    deleted_count += 1

            return deleted_count

        except Exception as e:
            print(f"❌ Failed to cleanup checkpoints: {str(e)}", file=sys.stderr)
            return 0

    def get_checkpoint_info(self, checkpoint_id: str) -> Optional[Dict]:
        """Get detailed checkpoint information"""
        checkpoint = self.load_checkpoint(checkpoint_id)
        if not checkpoint:
            return None

        return {
            "id": checkpoint.checkpoint_id,
            "game": checkpoint.game,
            "created_at": checkpoint.created_at,
            "resumed_at": checkpoint.resumed_at,
            "duration": checkpoint.duration_seconds,
            "type": checkpoint.checkpoint_type,
            "fsm_state": checkpoint.fsm_state.current_state if checkpoint.fsm_state else "N/A",
            "device": checkpoint.device_state.serial if checkpoint.device_state else "N/A",
            "battery": f"{checkpoint.device_state.battery_percent}%" if checkpoint.device_state else "N/A",
            "memory": f"{checkpoint.device_state.memory_percent}%" if checkpoint.device_state else "N/A",
        }

    def validate_checkpoint(self, checkpoint_id: str) -> bool:
        """Validate checkpoint integrity"""
        checkpoint = self.load_checkpoint(checkpoint_id)
        if not checkpoint:
            return False

        # Basic validation
        required_fields = ['checkpoint_id', 'game', 'created_at']
        for field in required_fields:
            if not getattr(checkpoint, field, None):
                return False

        return True

    def _load_existing_checkpoints(self):
        """Load all existing checkpoints from storage"""
        try:
            for filepath in self.storage_dir.glob("ckpt_*.json"):
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)

                    checkpoint_id = data['checkpoint_id']
                    self.checkpoints[checkpoint_id] = Checkpoint(
                        checkpoint_id=checkpoint_id,
                        game=data['game'],
                        created_at=data['created_at'],
                        duration_seconds=data.get('duration_seconds', 0),
                        checkpoint_type=data.get('checkpoint_type', 'manual'),
                    )
                except:
                    pass

        except Exception as e:
            print(f"⚠️ Warning: Failed to load existing checkpoints: {str(e)}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Checkpoint Manager - State Checkpointing & Recovery"
    )
    parser.add_argument("--device", help="ADB device serial")
    parser.add_argument("--game", help="Game name")
    parser.add_argument("--save-checkpoint", action="store_true",
                       help="Save current state as checkpoint")
    parser.add_argument("--load-checkpoint", help="Load checkpoint by ID")
    parser.add_argument("--list-checkpoints", action="store_true",
                       help="List available checkpoints")
    parser.add_argument("--delete-checkpoint", help="Delete checkpoint by ID")
    parser.add_argument("--cleanup", action="store_true",
                       help="Cleanup old checkpoints")
    parser.add_argument("--keep-count", type=int, default=5,
                       help="Number of recent checkpoints to keep")
    parser.add_argument("--storage-dir", default=".moai/checkpoints",
                       help="Checkpoint storage directory")
    parser.add_argument("--info", help="Get checkpoint info")

    args = parser.parse_args()

    manager = CheckpointManager(storage_dir=args.storage_dir)

    if args.save_checkpoint:
        if not args.game or not args.device:
            print("❌ Error: --game and --device required for --save-checkpoint")
            return 1

        checkpoint_id = manager.save_checkpoint(
            game=args.game,
            device_serial=args.device,
            fsm_state={
                "current_state": "EXECUTING",
                "state_entry_time": datetime.now().isoformat(),
                "timeout_remaining": 0,
                "iteration": 0,
            },
            device_state={
                "serial": args.device,
                "battery_percent": 80,
                "memory_percent": 50,
            }
        )

        if checkpoint_id:
            print(f"✅ Checkpoint saved: {checkpoint_id}")
            return 0
        else:
            return 1

    elif args.load_checkpoint:
        checkpoint = manager.load_checkpoint(args.load_checkpoint)
        if checkpoint:
            print(f"✅ Checkpoint loaded: {checkpoint.checkpoint_id}")
            print(f"  Game: {checkpoint.game}")
            print(f"  Created: {checkpoint.created_at}")
            print(f"  State: {checkpoint.fsm_state.current_state if checkpoint.fsm_state else 'N/A'}")
            return 0
        else:
            print(f"❌ Checkpoint not found: {args.load_checkpoint}")
            return 1

    elif args.list_checkpoints:
        game = args.game
        checkpoints = manager.list_checkpoints(game=game)

        print(f"\n📋 Checkpoints{f' for {game}' if game else ''} ({len(checkpoints)}):\n")
        for cp in checkpoints:
            info = manager.get_checkpoint_info(cp.checkpoint_id)
            if info:
                print(f"  {info['id']}")
                print(f"    Game: {info['game']}")
                print(f"    Created: {info['created_at']}")
                print(f"    State: {info['fsm_state']}")
                print()

        return 0

    elif args.delete_checkpoint:
        if manager.delete_checkpoint(args.delete_checkpoint):
            print(f"✅ Checkpoint deleted: {args.delete_checkpoint}")
            return 0
        else:
            print(f"❌ Failed to delete checkpoint")
            return 1

    elif args.cleanup:
        if not args.game:
            print("❌ Error: --game required for --cleanup")
            return 1

        deleted = manager.cleanup_old_checkpoints(args.game, keep_count=args.keep_count)
        print(f"✅ Cleaned up {deleted} old checkpoints for {args.game}")
        return 0

    elif args.info:
        info = manager.get_checkpoint_info(args.info)
        if info:
            print(f"\n📋 Checkpoint Information:\n")
            for key, value in info.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
            print()
            return 0
        else:
            print(f"❌ Checkpoint not found: {args.info}")
            return 1

    else:
        print("❌ Error: Specify --save-checkpoint, --load-checkpoint, --list-checkpoints, or --delete-checkpoint")
        return 1


if __name__ == "__main__":
    sys.exit(main())
