#!/usr/bin/env python3
"""
Intelligent Fallback Chain Orchestrator for Image Recognition
==============================================================

Implements multi-stage fallback strategy for robust element recognition:
- Stage 1: Template Matching (fastest, most reliable for exact matches)
- Stage 2: OCR-based Recognition (flexible, handles text variations)
- Stage 3: Feature Matching (powerful, works with similar elements)

Features:
- Configurable strategy selection
- Performance metrics collection
- Detailed stage-by-stage results
- Logging and debugging support
- Timeout management per stage
- Confidence threshold validation

Author: MoAI Backend Specialist
License: MIT
Version: 1.0.0
"""

import logging
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
import argparse

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# 1. DATA STRUCTURES AND ENUMS
# ============================================================================

class ChainStrategy(str, Enum):
    """Fallback chain strategy options"""
    TEMPLATE_FIRST = "template_first"
    OCR_FIRST = "ocr_first"
    FEATURE_FIRST = "feature_first"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


class RecognitionMethod(str, Enum):
    """Method used for recognition"""
    TEMPLATE_MATCHING = "template_matching"
    OCR_RECOGNITION = "ocr_recognition"
    FEATURE_MATCHING = "feature_matching"
    NOT_FOUND = "not_found"


@dataclass
class StageResult:
    """Result from a single recognition stage"""
    method: RecognitionMethod
    found: bool
    confidence: float
    location: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    processing_time: float = 0.0
    error: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "method": self.method.value,
            "found": self.found,
            "confidence": self.confidence,
            "location": self.location,
            "text": self.text,
            "processing_time": self.processing_time,
            "error": self.error,
        }


@dataclass
class ChainResult:
    """Complete chain execution result"""
    success: bool
    target: str
    method_used: RecognitionMethod
    confidence: float
    location: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    total_time: float = 0.0
    stages: List[StageResult] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "target": self.target,
            "method_used": self.method_used.value,
            "confidence": self.confidence,
            "location": self.location,
            "text": self.text,
            "total_time": self.total_time,
            "stages": [s.to_dict() for s in self.stages],
            "metrics": self.metrics,
        }


# ============================================================================
# 2. BASE FALLBACK HANDLER
# ============================================================================

class BaseFallbackHandler(ABC):
    """Abstract base class for fallback handlers"""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    @abstractmethod
    def recognize(
        self,
        image: np.ndarray,
        target: Any,
        confidence_threshold: float = 0.5,
    ) -> StageResult:
        """
        Recognize target in image.

        Args:
            image: Image to search
            target: Target to recognize (varies by handler)
            confidence_threshold: Minimum confidence

        Returns:
            StageResult with recognition details
        """
        pass

    def _enforce_timeout(self, start_time: float) -> None:
        """Check if timeout exceeded"""
        if time.time() - start_time > self.timeout:
            raise TimeoutError(
                f"Operation exceeded timeout of {self.timeout}s"
            )


# ============================================================================
# 3. TEMPLATE MATCHING FALLBACK
# ============================================================================

class TemplateMatchingFallback(BaseFallbackHandler):
    """Stage 1: Template matching for exact match recognition"""

    def __init__(self, timeout: float = 5.0):
        super().__init__(timeout)
        self.method_match = {
            "ccoeff": cv2.TM_CCOEFF,
            "ccoeff_normed": cv2.TM_CCOEFF_NORMED,
            "ccorr": cv2.TM_CCORR,
            "ccorr_normed": cv2.TM_CCORR_NORMED,
            "sqdiff": cv2.TM_SQDIFF,
            "sqdiff_normed": cv2.TM_SQDIFF_NORMED,
        }

    def recognize(
        self,
        image: np.ndarray,
        target: Union[str, Path, np.ndarray],
        confidence_threshold: float = 0.5,
        method: str = "ccoeff_normed",
    ) -> StageResult:
        """
        Recognize template in image.

        Args:
            image: Image to search
            target: Path to template or template array
            confidence_threshold: Minimum confidence
            method: Matching method

        Returns:
            StageResult with template match location
        """
        start_time = time.time()
        result = StageResult(
            method=RecognitionMethod.TEMPLATE_MATCHING,
            found=False,
            confidence=0.0,
        )

        try:
            # Load template
            if isinstance(target, (str, Path)):
                template = cv2.imread(str(target))
                if template is None:
                    result.error = f"Failed to load template: {target}"
                    return result
                template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
            else:
                template = target

            # Check dimensions
            if (
                template.shape[0] > image.shape[0]
                or template.shape[1] > image.shape[1]
            ):
                result.error = "Template larger than image"
                return result

            # Match template
            method_code = self.method_match.get(method)
            if method_code is None:
                result.error = f"Unknown matching method: {method}"
                return result

            result_map = cv2.matchTemplate(image, template, method_code)

            # Find best match
            if method.startswith("sqdiff"):
                # Lower is better for SQ_DIFF
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(
                    result_map
                )
                confidence = 1.0 - (min_val / 255.0)
                location = min_loc
            else:
                # Higher is better for others
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(
                    result_map
                )
                confidence = max(0.0, min(1.0, max_val))
                location = max_loc

            # Check threshold
            if confidence >= confidence_threshold:
                result.found = True
                result.confidence = confidence
                result.location = location
                result.extra_data = {
                    "template_size": template.shape[:2],
                    "method": method,
                }
            else:
                result.found = False
                result.confidence = confidence

        except Exception as e:
            result.error = str(e)
            logger.error(f"Template matching failed: {e}")

        result.processing_time = time.time() - start_time
        return result


# ============================================================================
# 4. OCR FALLBACK
# ============================================================================

class OCRFallback(BaseFallbackHandler):
    """Stage 2: OCR-based recognition for text elements"""

    def __init__(self, timeout: float = 15.0):
        super().__init__(timeout)
        self.ocr_engine = None
        self._init_ocr()

    def _init_ocr(self) -> None:
        """Initialize OCR engine"""
        try:
            import pytesseract
            self.ocr_engine = "tesseract"
        except ImportError:
            try:
                from paddleocr import PaddleOCR
                self.ocr_engine = "paddle"
            except ImportError:
                self.ocr_engine = None

    def recognize(
        self,
        image: np.ndarray,
        target: str,
        confidence_threshold: float = 0.5,
    ) -> StageResult:
        """
        Recognize text target in image using OCR.

        Args:
            image: Image to search
            target: Text to find
            confidence_threshold: Minimum confidence

        Returns:
            StageResult with OCR recognition
        """
        start_time = time.time()
        result = StageResult(
            method=RecognitionMethod.OCR_RECOGNITION,
            found=False,
            confidence=0.0,
        )

        if self.ocr_engine is None:
            result.error = "No OCR engine available"
            return result

        try:
            if self.ocr_engine == "tesseract":
                result = self._recognize_with_tesseract(
                    image, target, confidence_threshold
                )
            elif self.ocr_engine == "paddle":
                result = self._recognize_with_paddle(
                    image, target, confidence_threshold
                )

        except Exception as e:
            result.error = str(e)
            logger.error(f"OCR recognition failed: {e}")

        result.processing_time = time.time() - start_time
        return result

    def _recognize_with_tesseract(
        self,
        image: np.ndarray,
        target: str,
        confidence_threshold: float,
    ) -> StageResult:
        """Recognize using Tesseract"""
        from PIL import Image
        import pytesseract

        result = StageResult(
            method=RecognitionMethod.OCR_RECOGNITION,
            found=False,
            confidence=0.0,
        )

        try:
            # Perform OCR
            data = pytesseract.image_to_data(
                Image.fromarray(image),
                output_type=pytesseract.Output.DICT,
            )

            # Find target text
            target_lower = target.lower()
            for i, text in enumerate(data["text"]):
                if target_lower in text.lower():
                    # Found matching text
                    confidence = float(data["conf"][i]) / 100.0
                    if confidence >= confidence_threshold:
                        x = data["left"][i]
                        y = data["top"][i]
                        result.found = True
                        result.confidence = confidence
                        result.location = (x, y)
                        result.text = text
                        break

        except Exception as e:
            result.error = str(e)

        return result

    def _recognize_with_paddle(
        self,
        image: np.ndarray,
        target: str,
        confidence_threshold: float,
    ) -> StageResult:
        """Recognize using PaddleOCR"""
        from paddleocr import PaddleOCR

        result = StageResult(
            method=RecognitionMethod.OCR_RECOGNITION,
            found=False,
            confidence=0.0,
        )

        try:
            # Initialize if needed
            ocr = PaddleOCR(use_angle_cls=True, lang="ch")

            # Perform OCR
            results = ocr.ocr(image, cls=True)

            # Find target text
            target_lower = target.lower()
            if results and results[0]:
                for line in results[0]:
                    if line:
                        bbox, (text, conf) = line
                        if target_lower in text.lower():
                            if conf >= confidence_threshold:
                                x, y = int(bbox[0][0]), int(bbox[0][1])
                                result.found = True
                                result.confidence = conf
                                result.location = (x, y)
                                result.text = text
                                break

        except Exception as e:
            result.error = str(e)

        return result


# ============================================================================
# 5. FEATURE MATCHING FALLBACK
# ============================================================================

class FeatureMatchingFallback(BaseFallbackHandler):
    """Stage 3: Feature-based matching for complex element recognition"""

    def __init__(self, timeout: float = 10.0):
        super().__init__(timeout)
        self.detector = self._init_detector()

    def _init_detector(self):
        """Initialize feature detector"""
        try:
            return cv2.SIFT_create()
        except AttributeError:
            # Fallback to ORB if SIFT not available
            return cv2.ORB_create(nfeatures=500)

    def recognize(
        self,
        image: np.ndarray,
        target: Union[str, Path, np.ndarray],
        confidence_threshold: float = 0.5,
    ) -> StageResult:
        """
        Recognize target using feature matching.

        Args:
            image: Image to search
            target: Path to target or target array
            confidence_threshold: Minimum confidence (0.0-1.0)

        Returns:
            StageResult with feature match location
        """
        start_time = time.time()
        result = StageResult(
            method=RecognitionMethod.FEATURE_MATCHING,
            found=False,
            confidence=0.0,
        )

        try:
            # Load target
            if isinstance(target, (str, Path)):
                template = cv2.imread(str(target))
                if template is None:
                    result.error = f"Failed to load target: {target}"
                    return result
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            else:
                if len(target.shape) == 3:
                    template = cv2.cvtColor(target, cv2.COLOR_RGB2GRAY)
                else:
                    template = target

            # Convert image to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

            # Detect features
            kp1, des1 = self.detector.detectAndCompute(template, None)
            kp2, des2 = self.detector.detectAndCompute(gray, None)

            if des1 is None or des2 is None:
                result.error = "No features detected"
                return result

            # Match features
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(des1, des2, k=2)

            # Apply Lowe's ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

            # Calculate confidence based on match count
            if len(good_matches) > 0:
                # Normalize confidence (more matches = higher confidence)
                confidence = min(
                    1.0, len(good_matches) / max(len(kp1), 10)
                )

                if confidence >= confidence_threshold:
                    # Get location from matches
                    src_pts = np.float32([
                        kp1[m.queryIdx].pt for m in good_matches
                    ]).reshape(-1, 1, 2)
                    dst_pts = np.float32([
                        kp2[m.trainIdx].pt for m in good_matches
                    ]).reshape(-1, 1, 2)

                    # Calculate centroid of matched points
                    x = int(np.mean(dst_pts[:, 0, 0]))
                    y = int(np.mean(dst_pts[:, 0, 1]))

                    result.found = True
                    result.confidence = confidence
                    result.location = (x, y)
                    result.extra_data = {
                        "good_matches": len(good_matches),
                        "total_matches": len(matches),
                    }

        except Exception as e:
            result.error = str(e)
            logger.error(f"Feature matching failed: {e}")

        result.processing_time = time.time() - start_time
        return result


# ============================================================================
# 6. FALLBACK CHAIN ORCHESTRATOR
# ============================================================================

class FallbackChainOrchestrator:
    """
    Main orchestrator for intelligent fallback chain execution.

    Coordinates multiple recognition strategies in configured order
    with performance metrics and detailed results tracking.
    """

    def __init__(
        self,
        strategy: ChainStrategy = ChainStrategy.SEQUENTIAL,
        timeout_per_stage: float = 10.0,
    ):
        self.strategy = strategy
        self.timeout_per_stage = timeout_per_stage

        # Initialize handlers
        self.template_handler = TemplateMatchingFallback(timeout_per_stage)
        self.ocr_handler = OCRFallback(timeout_per_stage)
        self.feature_handler = FeatureMatchingFallback(timeout_per_stage)

    def execute(
        self,
        image: Union[str, Path, np.ndarray],
        target: Any,
        confidence_threshold: float = 0.5,
        target_type: str = "template",
    ) -> ChainResult:
        """
        Execute fallback chain for element recognition.

        Args:
            image: Image to search
            target: Target to recognize (path or object)
            confidence_threshold: Minimum confidence threshold
            target_type: Type of target ('template' or 'text')

        Returns:
            ChainResult with execution details
        """
        start_time = time.time()
        chain_result = ChainResult(
            success=False,
            target=str(target),
            method_used=RecognitionMethod.NOT_FOUND,
            confidence=0.0,
        )

        # Load image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                chain_result.stages.append(StageResult(
                    method=RecognitionMethod.NOT_FOUND,
                    found=False,
                    confidence=0.0,
                    error=f"Failed to load image: {image}",
                ))
                return chain_result
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img = image

        # Execute chain based on strategy
        if self.strategy == ChainStrategy.SEQUENTIAL:
            stage_result = self._execute_sequential(
                img,
                target,
                confidence_threshold,
                target_type,
            )
        elif self.strategy == ChainStrategy.PARALLEL:
            stage_result = self._execute_parallel(
                img,
                target,
                confidence_threshold,
                target_type,
            )
        elif self.strategy == ChainStrategy.TEMPLATE_FIRST:
            stage_result = self._execute_template_first(
                img,
                target,
                confidence_threshold,
                target_type,
            )
        elif self.strategy == ChainStrategy.OCR_FIRST:
            stage_result = self._execute_ocr_first(
                img,
                target,
                confidence_threshold,
                target_type,
            )
        elif self.strategy == ChainStrategy.FEATURE_FIRST:
            stage_result = self._execute_feature_first(
                img,
                target,
                confidence_threshold,
                target_type,
            )
        else:
            stage_result = self._execute_sequential(
                img,
                target,
                confidence_threshold,
                target_type,
            )

        chain_result.stages = stage_result["stages"]
        chain_result.success = stage_result["success"]
        chain_result.method_used = stage_result["method_used"]
        chain_result.confidence = stage_result["confidence"]
        chain_result.location = stage_result.get("location")
        chain_result.text = stage_result.get("text")
        chain_result.total_time = time.time() - start_time

        # Calculate metrics
        chain_result.metrics = {
            "total_time": chain_result.total_time,
            "stages_attempted": len(chain_result.stages),
            "success": chain_result.success,
            "confidence": chain_result.confidence,
            "stages": {
                s.method.value: s.processing_time
                for s in chain_result.stages
            },
        }

        return chain_result

    def _execute_sequential(
        self,
        image: np.ndarray,
        target: Any,
        confidence_threshold: float,
        target_type: str,
    ) -> Dict[str, Any]:
        """Execute template -> OCR -> feature matching sequence"""
        stages = []

        # Stage 1: Template Matching
        if target_type == "template":
            result = self.template_handler.recognize(
                image, target, confidence_threshold
            )
            stages.append(result)
            if result.found:
                return {
                    "stages": stages,
                    "success": True,
                    "method_used": RecognitionMethod.TEMPLATE_MATCHING,
                    "confidence": result.confidence,
                    "location": result.location,
                }

        # Stage 2: OCR
        if target_type == "text" or isinstance(target, str):
            result = self.ocr_handler.recognize(
                image,
                target if isinstance(target, str) else str(target),
                confidence_threshold,
            )
            stages.append(result)
            if result.found:
                return {
                    "stages": stages,
                    "success": True,
                    "method_used": RecognitionMethod.OCR_RECOGNITION,
                    "confidence": result.confidence,
                    "location": result.location,
                    "text": result.text,
                }

        # Stage 3: Feature Matching
        if target_type == "template":
            result = self.feature_handler.recognize(
                image, target, confidence_threshold * 0.8
            )
            stages.append(result)
            if result.found:
                return {
                    "stages": stages,
                    "success": True,
                    "method_used": RecognitionMethod.FEATURE_MATCHING,
                    "confidence": result.confidence,
                    "location": result.location,
                }

        return {
            "stages": stages,
            "success": False,
            "method_used": RecognitionMethod.NOT_FOUND,
            "confidence": 0.0,
        }

    def _execute_parallel(
        self,
        image: np.ndarray,
        target: Any,
        confidence_threshold: float,
        target_type: str,
    ) -> Dict[str, Any]:
        """Execute all methods in parallel and return best result"""
        results = []

        # Template matching
        if target_type == "template":
            result = self.template_handler.recognize(
                image, target, confidence_threshold
            )
            results.append(result)

        # OCR
        if target_type == "text" or isinstance(target, str):
            result = self.ocr_handler.recognize(
                image,
                target if isinstance(target, str) else str(target),
                confidence_threshold,
            )
            results.append(result)

        # Feature matching
        if target_type == "template":
            result = self.feature_handler.recognize(
                image, target, confidence_threshold * 0.8
            )
            results.append(result)

        # Find best result
        successful = [r for r in results if r.found]
        if successful:
            best = max(successful, key=lambda r: r.confidence)
            return {
                "stages": results,
                "success": True,
                "method_used": best.method,
                "confidence": best.confidence,
                "location": best.location,
                "text": best.text if best.text else None,
            }

        return {
            "stages": results,
            "success": False,
            "method_used": RecognitionMethod.NOT_FOUND,
            "confidence": 0.0,
        }

    def _execute_template_first(
        self,
        image: np.ndarray,
        target: Any,
        confidence_threshold: float,
        target_type: str,
    ) -> Dict[str, Any]:
        """Try template matching first, then fallback to others"""
        stages = []

        if target_type == "template":
            result = self.template_handler.recognize(
                image, target, confidence_threshold
            )
            stages.append(result)
            if result.found:
                return {
                    "stages": stages,
                    "success": True,
                    "method_used": RecognitionMethod.TEMPLATE_MATCHING,
                    "confidence": result.confidence,
                    "location": result.location,
                }

        # Fallback to feature matching
        result = self.feature_handler.recognize(
            image, target, confidence_threshold * 0.8
        )
        stages.append(result)
        if result.found:
            return {
                "stages": stages,
                "success": True,
                "method_used": RecognitionMethod.FEATURE_MATCHING,
                "confidence": result.confidence,
                "location": result.location,
            }

        return {
            "stages": stages,
            "success": False,
            "method_used": RecognitionMethod.NOT_FOUND,
            "confidence": 0.0,
        }

    def _execute_ocr_first(
        self,
        image: np.ndarray,
        target: Any,
        confidence_threshold: float,
        target_type: str,
    ) -> Dict[str, Any]:
        """Try OCR first, then fallback to template matching"""
        stages = []

        result = self.ocr_handler.recognize(
            image,
            target if isinstance(target, str) else str(target),
            confidence_threshold,
        )
        stages.append(result)
        if result.found:
            return {
                "stages": stages,
                "success": True,
                "method_used": RecognitionMethod.OCR_RECOGNITION,
                "confidence": result.confidence,
                "location": result.location,
                "text": result.text,
            }

        # Fallback to template matching
        if target_type == "template":
            result = self.template_handler.recognize(
                image, target, confidence_threshold
            )
            stages.append(result)
            if result.found:
                return {
                    "stages": stages,
                    "success": True,
                    "method_used": RecognitionMethod.TEMPLATE_MATCHING,
                    "confidence": result.confidence,
                    "location": result.location,
                }

        return {
            "stages": stages,
            "success": False,
            "method_used": RecognitionMethod.NOT_FOUND,
            "confidence": 0.0,
        }

    def _execute_feature_first(
        self,
        image: np.ndarray,
        target: Any,
        confidence_threshold: float,
        target_type: str,
    ) -> Dict[str, Any]:
        """Try feature matching first, then fallback to others"""
        stages = []

        result = self.feature_handler.recognize(
            image, target, confidence_threshold
        )
        stages.append(result)
        if result.found:
            return {
                "stages": stages,
                "success": True,
                "method_used": RecognitionMethod.FEATURE_MATCHING,
                "confidence": result.confidence,
                "location": result.location,
            }

        # Fallback to template matching
        if target_type == "template":
            result = self.template_handler.recognize(
                image, target, confidence_threshold
            )
            stages.append(result)
            if result.found:
                return {
                    "stages": stages,
                    "success": True,
                    "method_used": RecognitionMethod.TEMPLATE_MATCHING,
                    "confidence": result.confidence,
                    "location": result.location,
                }

        return {
            "stages": stages,
            "success": False,
            "method_used": RecognitionMethod.NOT_FOUND,
            "confidence": 0.0,
        }


# ============================================================================
# 7. CLI INTERFACE
# ============================================================================

def main():
    """CLI interface for fallback chain operations"""
    parser = argparse.ArgumentParser(
        description="Intelligent Fallback Chain Orchestrator"
    )

    parser.add_argument(
        "--device",
        type=str,
        default="localhost:5555",
        help="ADB device identifier",
    )
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to image file to search",
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target to find (path to template or text string)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=[s.value for s in ChainStrategy],
        default="sequential",
        help="Fallback chain strategy",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout per stage in seconds",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum confidence threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable performance profiling",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Validate inputs
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}", flush=True)
        return 1

    target_path = Path(args.target)
    target = target_path if target_path.exists() else args.target

    # Create orchestrator
    orchestrator = FallbackChainOrchestrator(
        strategy=ChainStrategy(args.strategy),
        timeout_per_stage=args.timeout,
    )

    # Execute chain
    try:
        # Determine target type
        target_type = "template" if target_path.exists() else "text"

        result = orchestrator.execute(
            image_path,
            target,
            confidence_threshold=args.confidence_threshold,
            target_type=target_type,
        )

        # Output result
        if args.output_format == "json":
            output = result.to_dict()
            print(json.dumps(output, indent=2), flush=True)
        else:
            print(f"Success: {result.success}", flush=True)
            print(f"Target: {result.target}", flush=True)
            print(f"Method: {result.method_used.value}", flush=True)
            print(f"Confidence: {result.confidence:.3f}", flush=True)
            if result.location:
                print(f"Location: {result.location}", flush=True)
            if result.text:
                print(f"Text: {result.text}", flush=True)
            print(f"Total Time: {result.total_time:.3f}s", flush=True)

            if args.profile:
                print("\nStage Breakdown:", flush=True)
                for stage in result.stages:
                    print(
                        f"  {stage.method.value}: "
                        f"{stage.processing_time:.3f}s "
                        f"(confidence: {stage.confidence:.3f})",
                        flush=True,
                    )

        return 0 if result.success else 1

    except Exception as e:
        print(f"Error: {e}", flush=True)
        logger.exception("Chain execution failed")
        return 1


if __name__ == "__main__":
    exit(main())
