#!/usr/bin/env python3
"""
Unified OCR with Multi-Engine Support and Fallback Strategy
============================================================

Provides intelligent OCR integration combining Tesseract and PaddleOCR with:
- Automatic language detection
- Confidence scoring and aggregation
- Chinese character optimization (CJK support)
- Optional image preprocessing
- LRU caching with TTL
- Performance optimization
- GPU acceleration when available

Author: MoAI Backend Specialist
License: MIT
Version: 1.0.0
"""

import logging
import hashlib
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any, Union
import argparse
import json

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ============================================================================
# 1. DATA STRUCTURES AND ENUMS
# ============================================================================

class Language(str, Enum):
    """Supported languages for OCR"""
    ENGLISH = "eng"
    CHINESE_SIMPLIFIED = "chi_sim"
    CHINESE_TRADITIONAL = "chi_tra"
    JAPANESE = "jpn"
    KOREAN = "kor"


class OCREngine(str, Enum):
    """Available OCR engines"""
    TESSERACT = "tesseract"
    PADDLE = "paddle"
    AUTO = "auto"


class PSMMode(int, Enum):
    """Tesseract Page Segmentation Modes"""
    OSD_ONLY = 0
    AUTO_OSD = 1
    AUTO_ONLY = 2
    AUTO = 3
    SINGLE_COLUMN = 4
    SINGLE_PARAGRAPH = 5
    SINGLE_LINE = 6
    SINGLE_WORD = 7
    SPARSE_TEXT = 8
    RAW_LINE = 13


@dataclass
class OCRResult:
    """Result from OCR operation"""
    text: str
    confidence: float
    engine: str
    language: Language
    processing_time: float
    raw_data: Optional[Dict[str, Any]] = None
    preprocessing_applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "engine": self.engine,
            "language": self.language.value,
            "processing_time": self.processing_time,
            "preprocessing_applied": self.preprocessing_applied,
        }


@dataclass
class LanguageDetectionResult:
    """Language detection result"""
    detected_language: Language
    confidence: float
    script_type: str
    is_cjk: bool


@dataclass
class ConfidenceAggregation:
    """Aggregated confidence from multiple engines"""
    average_confidence: float
    max_confidence: float
    min_confidence: float
    engine_results: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "average": self.average_confidence,
            "max": self.max_confidence,
            "min": self.min_confidence,
            "by_engine": self.engine_results,
        }


# ============================================================================
# 2. BASE OCR ENGINE INTERFACE
# ============================================================================

class BaseOCREngine(ABC):
    """Abstract base class for OCR engines"""

    def __init__(self, language: Language = Language.ENGLISH):
        self.language = language
        self.available = self._check_availability()

    @abstractmethod
    def _check_availability(self) -> bool:
        """Check if engine is available"""
        pass

    @abstractmethod
    def recognize(
        self,
        image: Union[str, Path, np.ndarray],
        confidence_threshold: float = 0.5,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> OCRResult:
        """
        Recognize text in image.

        Args:
            image: Path to image or numpy array
            confidence_threshold: Minimum confidence to accept
            roi: Region of interest (x1, y1, x2, y2)

        Returns:
            OCRResult with recognized text and metadata
        """
        pass

    def _load_image(
        self, image: Union[str, Path, np.ndarray]
    ) -> np.ndarray:
        """Load image from various formats"""
        if isinstance(image, np.ndarray):
            return image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"Failed to load image: {image}")
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        raise TypeError(f"Unsupported image type: {type(image)}")

    def _apply_roi(
        self, image: np.ndarray, roi: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """Apply region of interest to image"""
        x1, y1, x2, y2 = roi
        return image[y1:y2, x1:x2]


# ============================================================================
# 3. TESSERACT OCR ENGINE
# ============================================================================

class TesseractOCREngine(BaseOCREngine):
    """Tesseract OCR engine implementation"""

    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)
        self.pil_lang_map = {
            Language.ENGLISH: "eng",
            Language.CHINESE_SIMPLIFIED: "chi_sim",
            Language.CHINESE_TRADITIONAL: "chi_tra",
            Language.JAPANESE: "jpn",
            Language.KOREAN: "kor",
        }

    def _check_availability(self) -> bool:
        """Check if Tesseract is available"""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")
            return False

    def recognize(
        self,
        image: Union[str, Path, np.ndarray],
        confidence_threshold: float = 0.5,
        roi: Optional[Tuple[int, int, int, int]] = None,
        psm_mode: PSMMode = PSMMode.AUTO,
    ) -> OCRResult:
        """
        Recognize text using Tesseract.

        Args:
            image: Image source
            confidence_threshold: Minimum confidence
            roi: Region of interest
            psm_mode: Tesseract page segmentation mode

        Returns:
            OCRResult with Tesseract recognition
        """
        if not self.available:
            raise RuntimeError("Tesseract is not available")

        import pytesseract

        start_time = time.time()
        img = self._load_image(image)

        if roi:
            img = self._apply_roi(img, roi)

        # Configure Tesseract
        config = f"--psm {psm_mode.value}"
        lang = self.pil_lang_map.get(self.language, "eng")

        try:
            # Get detailed output
            data = pytesseract.image_to_data(
                Image.fromarray(img),
                lang=lang,
                config=config,
                output_type=pytesseract.Output.DICT,
            )

            # Calculate average confidence
            confidences = [
                float(conf) / 100
                for conf in data["conf"]
                if float(conf) > 0
            ]
            avg_confidence = (
                sum(confidences) / len(confidences)
                if confidences
                else 0.0
            )

            # Get text
            text = pytesseract.image_to_string(
                Image.fromarray(img), lang=lang, config=config
            ).strip()

            processing_time = time.time() - start_time

            return OCRResult(
                text=text,
                confidence=min(1.0, avg_confidence),
                engine="tesseract",
                language=self.language,
                processing_time=processing_time,
                raw_data={"data": data},
            )

        except Exception as e:
            logger.error(f"Tesseract recognition failed: {e}")
            raise


# ============================================================================
# 4. PADDLE OCR ENGINE
# ============================================================================

class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR engine with CJK optimization"""

    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)
        self.paddle_ocr = None
        self.lang_map = {
            Language.ENGLISH: "en",
            Language.CHINESE_SIMPLIFIED: "ch",
            Language.CHINESE_TRADITIONAL: "ch",
            Language.JAPANESE: "japan",
            Language.KOREAN: "korean",
        }

    def _check_availability(self) -> bool:
        """Check if PaddleOCR is available"""
        try:
            from paddleocr import PaddleOCR
            lang = self.lang_map.get(self.language, "en")
            self.paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                use_gpu=self._has_gpu(),
            )
            return True
        except ImportError:
            logger.warning("PaddleOCR not installed")
            return False
        except Exception as e:
            logger.warning(f"PaddleOCR initialization failed: {e}")
            return False

    @staticmethod
    def _has_gpu() -> bool:
        """Check if GPU is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def recognize(
        self,
        image: Union[str, Path, np.ndarray],
        confidence_threshold: float = 0.5,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> OCRResult:
        """
        Recognize text using PaddleOCR.

        Args:
            image: Image source
            confidence_threshold: Minimum confidence
            roi: Region of interest

        Returns:
            OCRResult with PaddleOCR recognition
        """
        if not self.available:
            raise RuntimeError("PaddleOCR is not available")

        start_time = time.time()
        img = self._load_image(image)

        if roi:
            img = self._apply_roi(img, roi)

        try:
            # PaddleOCR expects BGR format for file paths
            if isinstance(image, (str, Path)):
                results = self.paddle_ocr.ocr(str(image), cls=True)
            else:
                results = self.paddle_ocr.ocr(img, cls=True)

            # Process results
            texts = []
            confidences = []

            if results and results[0]:
                for line in results[0]:
                    if line:
                        bbox, (text, conf) = line
                        if conf >= confidence_threshold:
                            texts.append(text)
                            confidences.append(conf)

            text = " ".join(texts)
            avg_confidence = (
                sum(confidences) / len(confidences)
                if confidences
                else 0.0
            )

            processing_time = time.time() - start_time

            return OCRResult(
                text=text,
                confidence=min(1.0, avg_confidence),
                engine="paddle",
                language=self.language,
                processing_time=processing_time,
                raw_data={"results": results},
            )

        except Exception as e:
            logger.error(f"PaddleOCR recognition failed: {e}")
            raise


# ============================================================================
# 5. LANGUAGE DETECTION
# ============================================================================

class LanguageDetector:
    """Automatic language detection based on script analysis"""

    # Unicode ranges for script detection
    CJK_RANGES = [
        (0x4E00, 0x9FFF),    # CJK Unified Ideographs
        (0x3400, 0x4DBF),    # CJK Extension A
        (0x20000, 0x2A6DF),  # CJK Extension B
        (0x3040, 0x309F),    # Hiragana
        (0x30A0, 0x30FF),    # Katakana
        (0xAC00, 0xD7AF),    # Hangul Syllables
    ]

    LATIN_RANGES = [
        (0x0041, 0x005A),    # A-Z
        (0x0061, 0x007A),    # a-z
        (0x00C0, 0x00FF),    # Latin Extended
    ]

    @classmethod
    def detect(cls, text: str) -> LanguageDetectionResult:
        """
        Detect language from text.

        Args:
            text: Text to analyze

        Returns:
            LanguageDetectionResult with detected language
        """
        if not text:
            return LanguageDetectionResult(
                detected_language=Language.ENGLISH,
                confidence=0.0,
                script_type="unknown",
                is_cjk=False,
            )

        # Character analysis
        cjk_count = 0
        hiragana_count = 0
        katakana_count = 0
        hangul_count = 0
        latin_count = 0

        for char in text:
            code = ord(char)

            # Check CJK
            for start, end in cls.CJK_RANGES[:2]:
                if start <= code <= end:
                    cjk_count += 1
                    break

            # Check Hiragana
            if 0x3040 <= code <= 0x309F:
                hiragana_count += 1

            # Check Katakana
            if 0x30A0 <= code <= 0x30FF:
                katakana_count += 1

            # Check Hangul
            if 0xAC00 <= code <= 0xD7AF:
                hangul_count += 1

            # Check Latin
            for start, end in cls.LATIN_RANGES:
                if start <= code <= end:
                    latin_count += 1
                    break

        total = len(text)
        cjk_ratio = cjk_count / total if total > 0 else 0
        hiragana_ratio = hiragana_count / total if total > 0 else 0
        katakana_ratio = katakana_count / total if total > 0 else 0
        hangul_ratio = hangul_count / total if total > 0 else 0
        latin_ratio = latin_count / total if total > 0 else 0

        # Determine language
        if cjk_ratio > 0.3:
            if hangul_ratio > 0.2:
                return LanguageDetectionResult(
                    detected_language=Language.KOREAN,
                    confidence=hangul_ratio,
                    script_type="cjk+hangul",
                    is_cjk=True,
                )
            if hiragana_ratio > 0.1 or katakana_ratio > 0.1:
                return LanguageDetectionResult(
                    detected_language=Language.JAPANESE,
                    confidence=max(hiragana_ratio, katakana_ratio),
                    script_type="cjk+kana",
                    is_cjk=True,
                )
            return LanguageDetectionResult(
                detected_language=Language.CHINESE_SIMPLIFIED,
                confidence=cjk_ratio,
                script_type="cjk",
                is_cjk=True,
            )

        if hangul_ratio > 0.3:
            return LanguageDetectionResult(
                detected_language=Language.KOREAN,
                confidence=hangul_ratio,
                script_type="hangul",
                is_cjk=True,
            )

        return LanguageDetectionResult(
            detected_language=Language.ENGLISH,
            confidence=latin_ratio,
            script_type="latin",
            is_cjk=False,
        )


# ============================================================================
# 6. CONFIDENCE SCORING
# ============================================================================

class ConfidenceScorer:
    """Aggregate confidence scores from multiple engines"""

    @staticmethod
    def aggregate(results: List[OCRResult]) -> ConfidenceAggregation:
        """
        Aggregate confidence from multiple OCR results.

        Args:
            results: List of OCRResult objects

        Returns:
            ConfidenceAggregation with statistics
        """
        if not results:
            return ConfidenceAggregation(
                average_confidence=0.0,
                max_confidence=0.0,
                min_confidence=0.0,
            )

        confidences = [r.confidence for r in results]
        engine_results = {r.engine: r.confidence for r in results}

        return ConfidenceAggregation(
            average_confidence=sum(confidences) / len(confidences),
            max_confidence=max(confidences),
            min_confidence=min(confidences),
            engine_results=engine_results,
        )


# ============================================================================
# 7. IMAGE PREPROCESSING (Optional)
# ============================================================================

class ImagePreprocessor:
    """Optional image preprocessing for OCR optimization"""

    @staticmethod
    def apply_clahe(
        image: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8
    ) -> np.ndarray:
        """
        Apply Contrast Limited Adaptive Histogram Equalization.

        Args:
            image: Input image
            clip_limit: Threshold for contrast limiting
            tile_size: Size of grid for histogram equalization

        Returns:
            CLAHE-enhanced image
        """
        # Convert to LAB
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(
            clipLimit=clip_limit, tileGridSize=(tile_size, tile_size)
        )
        l_clahe = clahe.apply(l)

        # Merge and convert back
        lab_clahe = cv2.merge([l_clahe, a, b])
        return cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2RGB)

    @staticmethod
    def apply_morphological(
        image: np.ndarray, kernel_size: int = 3, operation: str = "close"
    ) -> np.ndarray:
        """
        Apply morphological operations.

        Args:
            image: Input image
            kernel_size: Size of morphological kernel
            operation: 'close', 'open', 'erode', 'dilate'

        Returns:
            Processed image
        """
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size)
        )

        if operation == "close":
            return cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
        elif operation == "open":
            return cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)
        elif operation == "erode":
            return cv2.erode(image, kernel)
        elif operation == "dilate":
            return cv2.dilate(image, kernel)
        else:
            return image

    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """
        Correct image skew.

        Args:
            image: Input image

        Returns:
            Deskewed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Find contours
        coords = np.column_stack(np.where(gray > 0))
        if len(coords) < 4:
            return image

        # Calculate angle
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle

        # Rotate
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image, matrix, (w, h), flags=cv2.INTER_CUBIC
        )


# ============================================================================
# 8. CACHING MECHANISM
# ============================================================================

class OCRCache:
    """LRU cache for OCR results with TTL"""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[OCRResult, float]] = {}

    def _get_image_hash(self, image: Union[str, Path, np.ndarray]) -> str:
        """Get hash of image for caching"""
        if isinstance(image, (str, Path)):
            return hashlib.sha256(str(image).encode()).hexdigest()
        elif isinstance(image, np.ndarray):
            return hashlib.sha256(image.tobytes()).hexdigest()
        return ""

    def get(self, image: Union[str, Path, np.ndarray]) -> Optional[OCRResult]:
        """Get cached result if available and not expired"""
        key = self._get_image_hash(image)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return result
            else:
                del self.cache[key]
        return None

    def set(
        self,
        image: Union[str, Path, np.ndarray],
        result: OCRResult,
    ) -> None:
        """Store result in cache"""
        key = self._get_image_hash(image)
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k][1],
            )
            del self.cache[oldest_key]
        self.cache[key] = (result, time.time())

    def clear(self) -> None:
        """Clear cache"""
        self.cache.clear()


# ============================================================================
# 9. UNIFIED OCR ORCHESTRATOR
# ============================================================================

class UnifiedOCROrchestrator:
    """
    Main OCR orchestrator with intelligent engine selection and fallback.

    Features:
    - Automatic language detection
    - Multi-engine recognition with fallback
    - Confidence aggregation
    - Optional preprocessing
    - Result caching
    """

    def __init__(
        self,
        default_language: Language = Language.ENGLISH,
        enable_preprocessing: bool = True,
        enable_caching: bool = True,
        cache_size: int = 100,
        cache_ttl: int = 3600,
    ):
        self.default_language = default_language
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = ImagePreprocessor() if enable_preprocessing else None
        self.cache = (
            OCRCache(cache_size, cache_ttl) if enable_caching else None
        )

        # Initialize engines
        self.tesseract = TesseractOCREngine(default_language)
        self.paddle = PaddleOCREngine(default_language)

    def detect_language(self, image_text: str) -> Language:
        """Detect language from image text"""
        result = LanguageDetector.detect(image_text)
        return result.detected_language

    def recognize(
        self,
        image: Union[str, Path, np.ndarray],
        language: Optional[Language] = None,
        confidence_threshold: float = 0.5,
        roi: Optional[Tuple[int, int, int, int]] = None,
        engine: OCREngine = OCREngine.AUTO,
        apply_preprocessing: bool = True,
    ) -> OCRResult:
        """
        Recognize text with intelligent engine selection.

        Args:
            image: Image source
            language: Language to use (auto-detect if None)
            confidence_threshold: Minimum confidence
            roi: Region of interest
            engine: Preferred engine (auto for intelligent selection)
            apply_preprocessing: Apply preprocessing if enabled

        Returns:
            Best OCRResult from available engines
        """
        # Check cache
        if self.cache:
            cached = self.cache.get(image)
            if cached:
                return cached

        # Load image
        img = cv2.imread(str(image)) if isinstance(image, (str, Path)) else image
        if img is None and isinstance(image, (str, Path)):
            raise ValueError(f"Failed to load image: {image}")
        if isinstance(img, np.ndarray):
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Apply preprocessing
        if apply_preprocessing and self.enable_preprocessing:
            img = self.preprocessor.apply_clahe(img)

        # Detect language if not provided
        if language is None:
            # Quick OCR to detect language
            try:
                quick_result = self.tesseract.recognize(
                    img, confidence_threshold=0.0
                )
                language = self.detect_language(quick_result.text)
            except Exception:
                language = self.default_language
        else:
            # Update engine language
            self.tesseract.language = language
            self.paddle.language = language

        # Select engine and recognize
        results = []

        if engine in [OCREngine.AUTO, OCREngine.TESSERACT]:
            if self.tesseract.available:
                try:
                    result = self.tesseract.recognize(
                        img,
                        confidence_threshold=confidence_threshold,
                        roi=roi,
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Tesseract failed: {e}")

        if engine in [OCREngine.AUTO, OCREngine.PADDLE]:
            if self.paddle.available:
                try:
                    result = self.paddle.recognize(
                        img,
                        confidence_threshold=confidence_threshold,
                        roi=roi,
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(f"PaddleOCR failed: {e}")

        # Return best result
        if results:
            best = max(results, key=lambda r: r.confidence)
            if self.cache:
                self.cache.set(image, best)
            return best

        raise RuntimeError("No OCR engines available")

    def recognize_with_fallback(
        self,
        image: Union[str, Path, np.ndarray],
        languages: Optional[List[Language]] = None,
        confidence_threshold: float = 0.5,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> OCRResult:
        """
        Recognize text with fallback through multiple languages.

        Args:
            image: Image source
            languages: List of languages to try (in order)
            confidence_threshold: Minimum confidence
            roi: Region of interest

        Returns:
            Best OCRResult from language fallback chain
        """
        if languages is None:
            languages = [self.default_language]

        results = []
        for lang in languages:
            try:
                result = self.recognize(
                    image,
                    language=lang,
                    confidence_threshold=confidence_threshold,
                    roi=roi,
                )
                if result.text:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Recognition failed for {lang}: {e}")

        if results:
            return max(results, key=lambda r: r.confidence)

        raise RuntimeError("Recognition failed for all languages")

    def benchmark_engines(
        self, image: Union[str, Path, np.ndarray]
    ) -> Dict[str, float]:
        """
        Benchmark OCR engines on image.

        Args:
            image: Image to test

        Returns:
            Dict with engine names and processing times
        """
        benchmarks = {}

        if self.tesseract.available:
            start = time.time()
            try:
                self.tesseract.recognize(image)
                benchmarks["tesseract"] = time.time() - start
            except Exception:
                benchmarks["tesseract"] = -1.0

        if self.paddle.available:
            start = time.time()
            try:
                self.paddle.recognize(image)
                benchmarks["paddle"] = time.time() - start
            except Exception:
                benchmarks["paddle"] = -1.0

        return benchmarks


# ============================================================================
# 10. CLI INTERFACE
# ============================================================================

def main():
    """CLI interface for OCR operations"""
    parser = argparse.ArgumentParser(
        description="Unified OCR with Multi-Engine Support"
    )

    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device: cpu or gpu",
    )
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to image file",
    )
    parser.add_argument(
        "--languages",
        type=str,
        default="eng",
        help="Comma-separated languages (eng,chi_sim,jpn,kor)",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["tesseract", "paddle", "auto"],
        default="auto",
        help="OCR engine to use",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum confidence threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--fallback-enabled",
        action="store_true",
        help="Enable language fallback chain",
    )
    parser.add_argument(
        "--roi",
        type=str,
        help="Region of interest (x1,y1,x2,y2)",
    )
    parser.add_argument(
        "--preprocessing",
        action="store_true",
        help="Apply preprocessing before OCR",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Benchmark engines",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse parameters
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}", flush=True)
        return 1

    # Parse languages
    language_strs = args.languages.split(",")
    languages = []
    for lang_str in language_strs:
        try:
            languages.append(Language(lang_str.strip()))
        except ValueError:
            print(f"Warning: Unknown language: {lang_str}", flush=True)

    if not languages:
        languages = [Language.ENGLISH]

    # Parse ROI
    roi = None
    if args.roi:
        try:
            roi = tuple(map(int, args.roi.split(",")))
        except ValueError:
            print("Error: Invalid ROI format. Use x1,y1,x2,y2", flush=True)
            return 1

    # Create orchestrator
    orchestrator = UnifiedOCROrchestrator(
        default_language=languages[0],
        enable_preprocessing=True,
        enable_caching=True,
    )

    # Benchmark if requested
    if args.benchmark:
        benchmarks = orchestrator.benchmark_engines(image_path)
        print("Engine Benchmarks:", flush=True)
        for engine, time_taken in benchmarks.items():
            if time_taken >= 0:
                print(f"  {engine}: {time_taken:.3f}s", flush=True)
            else:
                print(f"  {engine}: FAILED", flush=True)
        return 0

    # Perform recognition
    try:
        if args.fallback_enabled:
            result = orchestrator.recognize_with_fallback(
                image_path,
                languages=languages,
                confidence_threshold=args.confidence_threshold,
                roi=roi,
            )
        else:
            result = orchestrator.recognize(
                image_path,
                language=languages[0],
                confidence_threshold=args.confidence_threshold,
                roi=roi,
                engine=OCREngine(args.engine),
                apply_preprocessing=args.preprocessing,
            )

        # Output result
        if args.output_format == "json":
            output = {
                "text": result.text,
                "confidence": result.confidence,
                "engine": result.engine,
                "language": result.language.value,
                "processing_time": result.processing_time,
            }
            print(json.dumps(output, indent=2), flush=True)
        else:
            print(f"Text: {result.text}", flush=True)
            print(
                f"Confidence: {result.confidence:.3f} ({result.engine})",
                flush=True,
            )
            print(f"Time: {result.processing_time:.3f}s", flush=True)

        return 0

    except Exception as e:
        print(f"Error: {e}", flush=True)
        logger.exception("Recognition failed")
        return 1


if __name__ == "__main__":
    exit(main())
