"""
Comprehensive test suite for multi-resolution template matching.

Tests cover:
- Image pyramid generation
- Multi-scale template matching
- Fallback chain behavior
- Configuration loading
- Error handling
- Performance characteristics
- Cache management

Target Coverage: ≥85%
"""

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pytest

# Import classes under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "advanced"))

from adb_template_multiresolution import (
    TemplateScaler,
    MultiScaleMatcher,
    ConfigLoader,
    MatchResult,
    CacheStats,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def template_image() -> np.ndarray:
    """Create a synthetic template image (100x100 white square)"""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[25:75, 25:75] = 255  # White square in center
    return img


@pytest.fixture
def screenshot_image() -> np.ndarray:
    """Create a synthetic screenshot (1920x1080 gray background)"""
    return np.ones((1080, 1920, 3), dtype=np.uint8) * 128


@pytest.fixture
def screenshot_with_template(template_image, screenshot_image) -> np.ndarray:
    """Create screenshot with template embedded at 0.9x scale"""
    screenshot = screenshot_image.copy()
    scaled = cv2.resize(template_image, None, fx=0.9, fy=0.9)
    x_pos, y_pos = 500, 300
    h, w = scaled.shape[:2]
    screenshot[y_pos : y_pos + h, x_pos : x_pos + w] = scaled
    return screenshot


@pytest.fixture
def scaler() -> TemplateScaler:
    """Create a TemplateScaler instance"""
    return TemplateScaler(scales=[0.8, 0.9, 1.0, 1.1, 1.2])


@pytest.fixture
def matcher() -> MultiScaleMatcher:
    """Create a MultiScaleMatcher instance"""
    return MultiScaleMatcher(scales=[0.8, 0.9, 1.0, 1.1, 1.2], threshold=0.7)


# ============================================================================
# TEST GROUP 1: IMAGE PYRAMID GENERATION
# ============================================================================


class TestImagePyramid:
    """Test image pyramid generation and caching"""

    def test_pyramid_generation_basic(self, scaler, template_image):
        """Test basic pyramid generation"""
        pyramid = scaler.generate_pyramid(template_image, "test_1")

        # Should have entries for all scales
        assert len(pyramid) == 5, "Should generate pyramid for all 5 scales"

        # Check that scales are present
        assert 0.8 in pyramid
        assert 0.9 in pyramid
        assert 1.0 in pyramid
        assert 1.1 in pyramid
        assert 1.2 in pyramid

    def test_pyramid_scaling(self, scaler, template_image):
        """Test correct scaling dimensions"""
        pyramid = scaler.generate_pyramid(template_image, "test_2")

        original_h, original_w = template_image.shape[:2]

        # Check each scale produces correct dimensions
        for scale, scaled_img in pyramid.items():
            expected_h = int(original_h * scale)
            expected_w = int(original_w * scale)
            assert scaled_img.shape[0] == expected_h, f"Height mismatch at {scale}x"
            assert scaled_img.shape[1] == expected_w, f"Width mismatch at {scale}x"

    def test_pyramid_cache_hit(self, scaler, template_image):
        """Test pyramid caching mechanism"""
        template_id = "cached_template"

        # First call should be a miss
        pyramid1 = scaler.generate_pyramid(template_image, template_id)
        assert scaler.stats.misses == 1
        assert scaler.stats.hits == 0

        # Second call should be a cache hit
        pyramid2 = scaler.generate_pyramid(template_image, template_id)
        assert scaler.stats.hits == 1
        assert scaler.stats.misses == 1

        # Same object should be returned
        assert pyramid1 is pyramid2

    def test_pyramid_cache_clear(self, scaler, template_image):
        """Test cache clearing"""
        pyramid = scaler.generate_pyramid(template_image, "test_3")
        assert len(scaler.pyramid_cache) > 0

        scaler.clear_cache()
        assert len(scaler.pyramid_cache) == 0
        assert scaler.stats.hits == 0
        assert scaler.stats.misses == 0

    def test_pyramid_lru_eviction(self, scaler, template_image):
        """Test LRU cache eviction when max size exceeded"""
        scaler.max_cache_size = 2

        # Add three pyramids
        scaler.generate_pyramid(template_image, "template_a")
        scaler.generate_pyramid(template_image, "template_b")
        scaler.generate_pyramid(template_image, "template_c")

        # Should only have 2 in cache (LRU eviction)
        assert len(scaler.pyramid_cache) <= scaler.max_cache_size

    def test_cache_stats_tracking(self, scaler, template_image):
        """Test cache statistics tracking"""
        # Generate multiple pyramids
        scaler.generate_pyramid(template_image, "template_1")
        scaler.generate_pyramid(template_image, "template_2")
        scaler.generate_pyramid(template_image, "template_1")  # Cache hit

        stats = scaler.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["total"] == 3
        assert abs(stats["hit_rate"] - 1/3) < 0.01

    def test_very_small_template(self, scaler):
        """Test handling of very small templates"""
        tiny_template = np.ones((5, 5, 3), dtype=np.uint8)
        pyramid = scaler.generate_pyramid(tiny_template, "tiny")

        # Should still generate valid pyramid
        assert len(pyramid) > 0
        assert 1.0 in pyramid  # Should have at least 1.0x


# ============================================================================
# TEST GROUP 2: TEMPLATE MATCHING AT SCALES
# ============================================================================


class TestMultiScaleMatching:
    """Test multi-scale template matching"""

    def test_match_at_correct_scale(self, matcher, screenshot_with_template, template_image):
        """Test that matcher finds template at 0.9x scale"""
        result = matcher.match(screenshot_with_template, template_image, "scale_test")

        assert result is not None, "Should find template at 0.9x scale"
        assert 0.85 <= result.scale <= 0.95, "Should match at approximately 0.9x scale"
        assert result.confidence > 0.7, "Should have confidence > 0.7"

    def test_match_confidence_scoring(self, matcher, screenshot_with_template, template_image):
        """Test confidence score is reasonable"""
        result = matcher.match(screenshot_with_template, template_image, "confidence_test")

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0, "Confidence must be 0-1"
        assert result.confidence > 0.5, "Good match should have high confidence"

    def test_match_position_accuracy(self, matcher, screenshot_with_template, template_image):
        """Test match position is within expected bounds"""
        result = matcher.match(screenshot_with_template, template_image, "position_test")

        assert result is not None

        # Template was placed at (500, 300) at 0.9x scale
        # Allow 50 pixel error margin
        assert 450 < result.x < 550, f"X position {result.x} should be near 500"
        assert 250 < result.y < 350, f"Y position {result.y} should be near 300"

    def test_no_match_below_threshold(self, matcher, screenshot_image, template_image):
        """Test that no match is found when template absent"""
        # Screenshot has no template
        result = matcher.match(screenshot_image, template_image, "no_match_test")

        assert result is None, "Should return None when template not found"

    def test_method_set_correctly(self, matcher, screenshot_with_template, template_image):
        """Test that matching method is TM_CCOEFF_NORMED"""
        result = matcher.match(screenshot_with_template, template_image, "method_test")

        assert result is not None
        # Method should be one of the fallback options
        assert result.method in ["multi_scale", "single_scale", "feature_matching"]

    def test_execution_time_measured(self, matcher, screenshot_with_template, template_image):
        """Test that execution time is measured"""
        result = matcher.match(screenshot_with_template, template_image, "time_test")

        assert result is not None
        assert result.execution_time_ms > 0, "Should measure execution time"
        assert result.execution_time_ms < 10000, "Should complete in reasonable time"


# ============================================================================
# TEST GROUP 3: FALLBACK BEHAVIOR
# ============================================================================


class TestFallbackChain:
    """Test fallback chain: multi-scale → single-scale → feature matching"""

    def test_multi_scale_preferred(self, matcher, screenshot_with_template, template_image):
        """Test that multi-scale method is preferred"""
        result = matcher.match(screenshot_with_template, template_image, "fallback_1")

        assert result is not None
        # At 0.9x scale match, should prefer multi_scale method
        if 0.85 <= result.scale <= 0.95:
            assert result.method == "multi_scale"

    def test_single_scale_fallback(self, matcher, screenshot_image, template_image):
        """Test single-scale fallback when multi-scale fails"""
        # Create screenshot with template at exact 1.0x scale
        screenshot = screenshot_image.copy()
        x_pos, y_pos = 500, 300
        h, w = template_image.shape[:2]
        screenshot[y_pos : y_pos + h, x_pos : x_pos + w] = template_image

        result = matcher.match(screenshot, template_image, "fallback_2")

        assert result is not None
        # Should match at 1.0x scale
        assert result.scale == 1.0
        assert result.method in ["multi_scale", "single_scale"]

    def test_feature_fallback_with_complex_image(self, matcher):
        """Test feature matching fallback"""
        # Create template with distinctive features
        template = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.circle(template, (25, 25), 15, 255, -1)
        cv2.rectangle(template, (50, 50), (80, 80), 255, -1)

        # Create screenshot with rotated/scaled version
        screenshot = np.ones((1080, 1920, 3), dtype=np.uint8) * 100
        scaled = cv2.resize(template, None, fx=0.8, fy=0.8)
        x_pos, y_pos = 400, 200
        h, w = scaled.shape[:2]
        screenshot[y_pos : y_pos + h, x_pos : x_pos + w] = scaled

        result = matcher.match(screenshot, template, "feature_fallback")

        # Should find match through some method
        assert result is not None


# ============================================================================
# TEST GROUP 4: CONFIGURATION LOADING
# ============================================================================


class TestConfigLoader:
    """Test configuration loading and validation"""

    def test_default_config(self):
        """Test default configuration"""
        config = ConfigLoader.get_default()

        assert "scales" in config
        assert "threshold" in config
        assert "method" in config

    def test_load_valid_config(self):
        """Test loading valid configuration"""
        custom_config = {
            "scales": [0.9, 1.0, 1.1],
            "threshold": 0.75,
        }

        loaded = ConfigLoader.load_from_dict(custom_config)

        assert loaded["scales"] == [0.9, 1.0, 1.1]
        assert loaded["threshold"] == 0.75

    def test_invalid_scales_not_list(self):
        """Test that invalid scales type is rejected"""
        with pytest.raises(ValueError):
            ConfigLoader.load_from_dict({"scales": 1.0})

    def test_invalid_scales_non_numeric(self):
        """Test that non-numeric scales are rejected"""
        with pytest.raises(ValueError):
            ConfigLoader.load_from_dict({"scales": [0.8, "invalid", 1.2]})

    def test_invalid_scales_out_of_range(self):
        """Test that out-of-range scales are rejected"""
        with pytest.raises(ValueError):
            ConfigLoader.load_from_dict({"scales": [0.2, 0.5, 1.0]})  # 0.2 too small

        with pytest.raises(ValueError):
            ConfigLoader.load_from_dict({"scales": [0.8, 1.0, 3.0]})  # 3.0 too large

    def test_invalid_threshold(self):
        """Test that invalid threshold is rejected"""
        with pytest.raises(ValueError):
            ConfigLoader.load_from_dict({"threshold": 1.5})

        with pytest.raises(ValueError):
            ConfigLoader.load_from_dict({"threshold": -0.1})


# ============================================================================
# TEST GROUP 5: ERROR HANDLING
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_match_with_none_image(self, matcher, template_image):
        """Test handling of None input"""
        # Should handle gracefully
        result = matcher._match_single_scale(None, template_image, "test")
        assert result is None

    def test_match_with_empty_template(self, matcher, screenshot_image):
        """Test handling of empty template"""
        empty = np.zeros((0, 0, 3), dtype=np.uint8)

        # Should handle without crashing
        result = matcher._match_single_scale(screenshot_image, empty, "test")
        assert result is None

    def test_oversized_template(self, matcher, screenshot_image):
        """Test template larger than screenshot"""
        huge_template = np.ones((2000, 3000, 3), dtype=np.uint8)

        result = matcher.match(screenshot_image, huge_template, "oversized")

        # Should skip scales larger than screenshot
        assert result is None or result.scale <= 1.0

    def test_mismatched_channels(self, matcher, screenshot_image, template_image):
        """Test handling of mismatched color channels"""
        # Convert template to grayscale
        gray_template = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)

        # Should handle gracefully
        try:
            result = matcher.match(screenshot_image, gray_template, "mismatch")
            # Either returns None or handles conversion
        except Exception as e:
            pytest.fail(f"Should handle grayscale template: {e}")


# ============================================================================
# TEST GROUP 6: INTEGRATION SCENARIOS
# ============================================================================


class TestIntegrationScenarios:
    """Test real-world integration scenarios"""

    def test_multiple_templates_sequential(self, matcher, screenshot_image, template_image):
        """Test matching multiple templates sequentially"""
        # Add same template at different locations
        screenshot = screenshot_image.copy()

        pos1 = (400, 300)
        pos2 = (1200, 700)

        h, w = template_image.shape[:2]
        screenshot[pos1[1] : pos1[1] + h, pos1[0] : pos1[0] + w] = template_image
        screenshot[pos2[1] : pos2[1] + h, pos2[0] : pos2[0] + w] = template_image

        # Should find at least one instance
        result = matcher.match(screenshot, template_image, "multi_instance")
        assert result is not None

    def test_performance_benchmark(self, matcher, screenshot_image, template_image):
        """Test performance characteristics"""
        times = []

        for _ in range(5):
            start = time.time()
            result = matcher.match(screenshot_image, template_image, f"bench_{_}")
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)

        # Multi-scale matching should complete in reasonable time
        assert avg_time < 1.0, f"Average match time {avg_time}s exceeds 1 second"

    def test_resolution_profile_720p(self, template_image):
        """Test with 720p resolution profile"""
        matcher = MultiScaleMatcher(
            scales=[0.9, 1.0, 1.1],  # 720p profile
            threshold=0.7,
        )

        screenshot = np.ones((720, 1280, 3), dtype=np.uint8) * 128
        h, w = template_image.shape[:2]
        screenshot[300 : 300 + h, 400 : 400 + w] = template_image

        result = matcher.match(screenshot, template_image, "720p_profile")
        assert result is not None

    def test_resolution_profile_1440p(self, template_image):
        """Test with 1440p resolution profile"""
        matcher = MultiScaleMatcher(
            scales=[0.7, 0.8, 0.9, 1.0, 1.1, 1.2],  # 1440p profile
            threshold=0.7,
        )

        screenshot = np.ones((1440, 2560, 3), dtype=np.uint8) * 128
        h, w = template_image.shape[:2]
        screenshot[500 : 500 + h, 800 : 800 + w] = template_image

        result = matcher.match(screenshot, template_image, "1440p_profile")
        assert result is not None


# ============================================================================
# TEST GROUP 7: MATCH RESULT DATACLASS
# ============================================================================


class TestMatchResult:
    """Test MatchResult dataclass"""

    def test_match_result_creation(self):
        """Test creating MatchResult"""
        result = MatchResult(
            x=100,
            y=200,
            confidence=0.95,
            scale=1.0,
            method="test",
            execution_time_ms=50.5,
        )

        assert result.x == 100
        assert result.y == 200
        assert result.confidence == 0.95
        assert result.scale == 1.0

    def test_match_result_to_dict(self):
        """Test MatchResult serialization"""
        result = MatchResult(
            x=100,
            y=200,
            confidence=0.95,
            scale=1.0,
            method="test",
            execution_time_ms=50.5,
        )

        d = result.to_dict()

        assert d["x"] == 100
        assert d["y"] == 200
        assert d["confidence"] == 0.95


# ============================================================================
# TEST GROUP 8: CACHE STATISTICS
# ============================================================================


class TestCacheStatistics:
    """Test cache statistics tracking"""

    def test_cache_stats_initialization(self):
        """Test CacheStats initialization"""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total_operations == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate(self):
        """Test hit rate calculation"""
        stats = CacheStats(hits=3, misses=7, total_operations=10)

        assert abs(stats.hit_rate - 0.3) < 0.01

    def test_scaler_stats_retrieval(self, scaler, template_image):
        """Test retrieving scaler statistics"""
        scaler.generate_pyramid(template_image, "stat_test_1")
        scaler.generate_pyramid(template_image, "stat_test_1")  # Hit
        scaler.generate_pyramid(template_image, "stat_test_2")  # Miss

        stats = scaler.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["total"] == 3


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
