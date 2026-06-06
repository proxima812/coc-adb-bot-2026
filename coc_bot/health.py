from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from .adb_device import AdbDevice
from .config import BotConfig
from .vision import GameState, VisionModule


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    state: str
    screen_size: tuple[int, int]


class HealthChecker:
    def __init__(self, device: AdbDevice, vision: VisionModule, config: BotConfig) -> None:
        self.device = device
        self.vision = vision
        self.config = config

    def check_before_cycle(self) -> HealthReport:
        self.device.check()
        screen_size = self.device.screen_size()
        self._check_screen_size(screen_size)
        image = self.vision.screenshot_image()
        if image.width <= 0 or image.height <= 0:
            raise RuntimeError("Health check failed: empty screenshot image")

        state = self.vision.detect_state()
        if state == GameState.UNKNOWN:
            saved = self.vision.save_debug_screenshot("health-unknown-state")
            raise RuntimeError(f"Health check failed: game state is unknown; screenshot={saved}")

        logger.info("Health check passed: state={}, screen={}x{}", state, screen_size[0], screen_size[1])
        return HealthReport(ok=True, state=state, screen_size=screen_size)

    def _check_screen_size(self, screen_size: tuple[int, int]) -> None:
        expected_width = self.config.expected_screen_width
        expected_height = self.config.expected_screen_height
        if expected_width <= 0 or expected_height <= 0:
            return
        if screen_size != (expected_width, expected_height):
            raise RuntimeError(
                "Health check failed: screen size changed "
                f"from expected {expected_width}x{expected_height} to {screen_size[0]}x{screen_size[1]}"
            )
