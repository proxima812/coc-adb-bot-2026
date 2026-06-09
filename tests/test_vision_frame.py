from __future__ import annotations

import unittest

import numpy as np

from coc_bot.vision import VisionModule


class CountingVision(VisionModule):
    """Минимальный double для замера screenshot-вызовов."""

    def __init__(self) -> None:
        self._frame_cache = None
        self._frame_depth = 0
        self.capture_calls = 0

    def _capture_fresh_screenshot(self) -> np.ndarray:
        self.capture_calls += 1
        return np.full((10, 10, 3), 1, dtype=np.uint8)


class VisionFrameCacheTest(unittest.TestCase):
    def test_screenshot_array_uses_cached_frame_inside_with_block(self) -> None:
        vision = CountingVision()
        with vision.frame():
            vision.screenshot_array()
            vision.screenshot_array()
            vision.screenshot_array()
        self.assertEqual(vision.capture_calls, 1)

    def test_screenshot_array_captures_fresh_outside_with_block(self) -> None:
        vision = CountingVision()
        vision.screenshot_array()
        vision.screenshot_array()
        self.assertEqual(vision.capture_calls, 2)

    def test_nested_frame_blocks_share_one_capture(self) -> None:
        vision = CountingVision()
        with vision.frame():
            with vision.frame():
                vision.screenshot_array()
            vision.screenshot_array()
        self.assertEqual(vision.capture_calls, 1)

    def test_cache_invalidated_after_with_block_exits(self) -> None:
        vision = CountingVision()
        with vision.frame():
            vision.screenshot_array()
        vision.screenshot_array()
        self.assertEqual(vision.capture_calls, 2)

    def test_invalidate_frame_refreshes_cache_inside_block(self) -> None:
        vision = CountingVision()
        with vision.frame():
            vision.screenshot_array()
            vision.invalidate_frame()
            vision.screenshot_array()
        self.assertEqual(vision.capture_calls, 2)


if __name__ == "__main__":
    unittest.main()
