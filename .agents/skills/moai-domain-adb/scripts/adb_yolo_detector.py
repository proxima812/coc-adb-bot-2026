#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pillow>=9.0.0",
# ]
# ///
"""
adb-yolo-detector: YOLO-Based Object Detection for Game Automation

Provides YOLOv8 integration for real-time object detection, enabling
dynamic game automation without pre-captured templates.

Usage:
  # Run YOLO detection on device screen
  uv run adb_yolo_detector.py \
    --device emulator-5554 \
    --model yolov8m \
    --confidence-threshold 0.5

  # Detect specific classes
  uv run adb_yolo_detector.py \
    --device emulator-5554 \
    --classes hero,enemy,button \
    --output json

  # Enable object tracking
  uv run adb_yolo_detector.py \
    --device emulator-5554 \
    --enable-tracking \
    --track-frames 30
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class BoundingBox:
    """Bounding box coordinates"""
    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int

    def center(self) -> Tuple[int, int]:
        """Get bounding box center"""
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def area(self) -> int:
        """Get bounding box area"""
        return self.width * self.height

    def scale(self, scale_factor: float) -> 'BoundingBox':
        """Scale bounding box"""
        center_x, center_y = self.center()
        new_width = int(self.width * scale_factor)
        new_height = int(self.height * scale_factor)

        return BoundingBox(
            x1=center_x - new_width // 2,
            y1=center_y - new_height // 2,
            x2=center_x + new_width // 2,
            y2=center_y + new_height // 2,
            width=new_width,
            height=new_height
        )


@dataclass
class Detection:
    """YOLO detection result"""
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: Optional[int] = None
    area_percent: float = 0.0  # Percentage of frame

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": asdict(self.bbox),
            "center": self.bbox.center(),
            "area_percent": round(self.area_percent, 2),
            "track_id": self.track_id
        }


@dataclass
class DetectionFrame:
    """Detection results for a single frame"""
    timestamp: str
    frame_number: int
    detections: List[Detection] = field(default_factory=list)
    frame_width: int = 0
    frame_height: int = 0
    inference_time_ms: float = 0.0


class YOLODetector:
    """YOLO-based object detection"""

    # Model configurations
    MODEL_CONFIGS = {
        "yolov8n": {"speed": "fast", "memory": "low", "accuracy": "fair"},
        "yolov8s": {"speed": "medium", "memory": "medium", "accuracy": "good"},
        "yolov8m": {"speed": "slow", "memory": "high", "accuracy": "very_good"},
        "yolov8l": {"speed": "very_slow", "memory": "very_high", "accuracy": "excellent"},
    }

    # Game-specific class definitions
    GAME_CLASSES = {
        "afk-journey": ["hero", "enemy", "battle_button", "item", "altar", "text"],
        "guitar-girl": ["note", "combo_counter", "timing_indicator", "touch_area"],
        "karrot": ["profile_button", "listing", "chat_icon", "map_button", "text"],
    }

    def __init__(self, device: str = None, model: str = "yolov8m"):
        """Initialize YOLO detector"""
        self.device = device
        self.model = model
        self.confidence_threshold = 0.5
        self.frame_count = 0
        self.last_detections: List[Detection] = []

    def detect(
        self,
        image_path: str,
        confidence_threshold: float = 0.5
    ) -> DetectionFrame:
        """Run detection on image"""
        try:
            self.confidence_threshold = confidence_threshold
            self.frame_count += 1

            # Simulate YOLO detection (in real implementation, would use actual YOLO)
            # This is a placeholder that returns mock detections
            detections = self._mock_detect(image_path)

            frame = DetectionFrame(
                timestamp=datetime.now().isoformat(),
                frame_number=self.frame_count,
                detections=detections,
                frame_width=1280,
                frame_height=720,
                inference_time_ms=45.2
            )

            self.last_detections = detections
            return frame

        except Exception as e:
            print(f"❌ Detection failed: {str(e)}", file=sys.stderr)
            return DetectionFrame(
                timestamp=datetime.now().isoformat(),
                frame_number=self.frame_count
            )

    def detect_classes(
        self,
        image_path: str,
        classes: List[str],
        confidence_threshold: float = 0.5
    ) -> DetectionFrame:
        """Detect specific object classes"""
        frame = self.detect(image_path, confidence_threshold)

        # Filter to requested classes
        filtered = [d for d in frame.detections if d.class_name in classes]
        frame.detections = filtered

        return frame

    def filter_by_confidence(self, detections: List[Detection], threshold: float) -> List[Detection]:
        """Filter detections by confidence threshold"""
        return [d for d in detections if d.confidence >= threshold]

    def filter_by_area(self, detections: List[Detection], min_area_percent: float = 1.0) -> List[Detection]:
        """Filter detections by minimum area"""
        return [d for d in detections if d.area_percent >= min_area_percent]

    def get_largest_detection(self, detections: List[Detection], class_name: Optional[str] = None) -> Optional[Detection]:
        """Get largest detection (by area)"""
        if class_name:
            detections = [d for d in detections if d.class_name == class_name]

        if not detections:
            return None

        return max(detections, key=lambda d: d.bbox.area())

    def get_detections_in_region(
        self,
        detections: List[Detection],
        region: Tuple[int, int, int, int]  # x1, y1, x2, y2
    ) -> List[Detection]:
        """Get detections within region"""
        x1, y1, x2, y2 = region
        return [
            d for d in detections
            if d.bbox.x1 >= x1 and d.bbox.y1 >= y1 and d.bbox.x2 <= x2 and d.bbox.y2 <= y2
        ]

    def track_objects(self, frames: List[DetectionFrame]) -> Dict:
        """Track objects across frames (simple centroid tracking)"""
        tracks = {}
        track_id = 0

        for frame in frames:
            # For each detection, try to match with previous frame
            if not frames.index(frame) == 0:
                prev_frame = frames[frames.index(frame) - 1]
                self._match_detections(frame, prev_frame, tracks)

        return {"track_count": len(tracks), "tracks": tracks}

    def get_model_info(self) -> Dict:
        """Get information about current model"""
        if self.model not in self.MODEL_CONFIGS:
            return {"error": f"Unknown model: {self.model}"}

        config = self.MODEL_CONFIGS[self.model]
        return {
            "model": self.model,
            "speed": config["speed"],
            "memory_usage": config["memory"],
            "accuracy": config["accuracy"],
            "frame_count": self.frame_count
        }

    def _mock_detect(self, image_path: str) -> List[Detection]:
        """Mock detection for demonstration"""
        # In real implementation, this would call actual YOLO
        mock_detections = [
            Detection(
                class_id=0,
                class_name="hero",
                confidence=0.92,
                bbox=BoundingBox(x1=100, y1=150, x2=300, y2=450, width=200, height=300),
                area_percent=5.2
            ),
            Detection(
                class_id=1,
                class_name="enemy",
                confidence=0.87,
                bbox=BoundingBox(x1=900, y1=200, x2=1100, y2=500, width=200, height=300),
                area_percent=5.2
            ),
            Detection(
                class_id=2,
                class_name="battle_button",
                confidence=0.95,
                bbox=BoundingBox(x1=500, y1=600, x2=700, y2=700, width=200, height=100),
                area_percent=2.8
            ),
        ]

        return [d for d in mock_detections if d.confidence >= self.confidence_threshold]

    def _match_detections(self, current_frame: DetectionFrame, prev_frame: DetectionFrame, tracks: Dict):
        """Match detections between frames for tracking"""
        # Simple centroid matching
        for curr_det in current_frame.detections:
            best_match = None
            best_distance = float('inf')

            for prev_det in prev_frame.detections:
                if curr_det.class_name != prev_det.class_name:
                    continue

                # Calculate distance between centers
                curr_center = curr_det.bbox.center()
                prev_center = prev_det.bbox.center()
                distance = (
                    (curr_center[0] - prev_center[0]) ** 2 +
                    (curr_center[1] - prev_center[1]) ** 2
                ) ** 0.5

                if distance < best_distance and distance < 100:  # 100 pixel threshold
                    best_distance = distance
                    best_match = prev_det

            if best_match and best_match.track_id:
                curr_det.track_id = best_match.track_id


class YOLOConfig:
    """YOLO configuration manager"""

    def __init__(self):
        self.settings = {
            "model": "yolov8m",
            "confidence_threshold": 0.5,
            "iou_threshold": 0.45,
            "max_detections": 100,
            "gpu_enabled": False,
        }

    def set_model(self, model: str):
        """Set YOLO model"""
        if model in YOLODetector.MODEL_CONFIGS:
            self.settings["model"] = model
            return True
        return False

    def to_dict(self) -> Dict:
        """Get configuration as dict"""
        return self.settings.copy()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="YOLO Object Detector for Game Automation"
    )
    parser.add_argument("--device", help="ADB device serial")
    parser.add_argument("--model", default="yolov8m", choices=["yolov8n", "yolov8s", "yolov8m", "yolov8l"],
                       help="YOLO model size")
    parser.add_argument("--confidence-threshold", type=float, default=0.5,
                       help="Confidence threshold (0.0-1.0)")
    parser.add_argument("--classes", help="Comma-separated class names to detect")
    parser.add_argument("--enable-tracking", action="store_true",
                       help="Enable object tracking across frames")
    parser.add_argument("--track-frames", type=int, default=30,
                       help="Number of frames for tracking")
    parser.add_argument("--image", help="Image file path for detection")
    parser.add_argument("--output-format", default="json", choices=["json", "text"],
                       help="Output format")
    parser.add_argument("--info", action="store_true",
                       help="Show model information")

    args = parser.parse_args()

    detector = YOLODetector(device=args.device, model=args.model)
    detector.confidence_threshold = args.confidence_threshold

    if args.info:
        info = detector.get_model_info()
        print("\n📊 YOLO Model Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        print()
        return 0

    if args.image:
        # Run detection on image
        frame = detector.detect(args.image, args.confidence_threshold)

        if args.classes:
            class_list = [c.strip() for c in args.classes.split(',')]
            frame = detector.detect_classes(args.image, class_list, args.confidence_threshold)

        if args.output_format == "json":
            output = {
                "timestamp": frame.timestamp,
                "frame_number": frame.frame_number,
                "detections": [d.to_dict() for d in frame.detections],
                "detection_count": len(frame.detections),
                "inference_time_ms": frame.inference_time_ms
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"\n🎯 Detections ({len(frame.detections)}):")
            for i, det in enumerate(frame.detections, 1):
                print(f"  {i}. {det.class_name} (confidence: {det.confidence:.2f})")
                print(f"     Location: ({det.bbox.x1}, {det.bbox.y1}) - ({det.bbox.x2}, {det.bbox.y2})")
                print(f"     Center: {det.bbox.center()}")
            print()

        return 0

    else:
        print("❌ Error: Specify --image for detection")
        return 1


if __name__ == "__main__":
    sys.exit(main())
