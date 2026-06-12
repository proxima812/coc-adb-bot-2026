from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
from loguru import logger
from PIL import Image

# easyocr тянет torch (~2 ГБ) — импортируем лениво, чтобы дешёвые операции
# (template-matching, screenshots) работали даже без OCR-движка и чтобы
# импорт модуля не падал в среде без него.

from .adb_device import AdbDevice
from .config import BotConfig, RelativeArea, RelativePoint


@dataclass(frozen=True)
class Loot:
    gold: int
    elixir: int
    dark_elixir: int = 0


@dataclass(frozen=True)
class TemplateMatch:
    x: int
    y: int
    score: float


@dataclass(frozen=True)
class BoundaryCandidate:
    x: int
    y: int
    score: float


class GameState:
    VILLAGE = "village"
    BATTLE = "battle"
    UNKNOWN = "unknown"


class BuilderSlotState:
    NOT_DEPLOYED = "not_deployed"
    DEPLOYED = "deployed"
    ABILITY_READY = "ability_ready"
    UNKNOWN = "unknown"


class VisionModule:
    def __init__(self, device: AdbDevice, config: BotConfig) -> None:
        self.device = device
        self.config = config
        self._reader = None  # type: ignore[var-annotated]  # easyocr.Reader, lazy
        self._template_cache: dict[str, np.ndarray | None] = {}
        self._template_gray_cache: dict[str, np.ndarray | None] = {}
        self._stable_state = GameState.UNKNOWN
        self._candidate_state = GameState.UNKNOWN
        self._candidate_count = 0
        # Кэш кадра для batch-детекции: внутри `with vision.frame():`
        # все вызовы screenshot_array() возвращают один и тот же RGB-массив.
        self._frame_cache: np.ndarray | None = None
        self._frame_depth = 0

    @property
    def reader(self):  # type: ignore[no-untyped-def]
        if self._reader is None:
            import easyocr  # ленивый импорт: тянет torch на сотни МБ

            self._reader = easyocr.Reader(["en"], gpu=False)
        return self._reader

    def screenshot_image(self) -> Image.Image:
        return Image.fromarray(self.screenshot_array())

    def screenshot_array(self) -> np.ndarray:
        # Внутри активного `with self.frame()` отдаём кэшированный кадр и
        # экономим круг ADB→PNG→decode на каждом has_*-вызове.
        if self._frame_cache is not None:
            return self._frame_cache
        return self._capture_fresh_screenshot()

    def _capture_fresh_screenshot(self) -> np.ndarray:
        raw = self.device.screenshot()
        data = np.frombuffer(raw, dtype=np.uint8)
        if data.size == 0:
            raise RuntimeError("Android screenshot is empty")
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("Unable to decode Android screenshot")
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    @contextmanager
    def frame(self) -> Iterator[np.ndarray]:
        """Шаг детекции с единым screenshot для всех has_*/find_*/OCR проверок.

        Использование:

            with vision.frame():
                if vision.has_okay_button():
                    ...
                if vision.has_configured_popup():
                    ...

        Поддерживает вложенные вызовы — внутренний блок переиспользует кадр
        внешнего. Кадр инвалидируется автоматически при выходе из самого
        внешнего блока. Тяжёлые операции (тап/swipe/sleep) принципиально не
        выполняются внутри блока — кадр не отражает изменения экрана.
        """
        outer = self._frame_depth == 0
        if outer:
            self._frame_cache = self._capture_fresh_screenshot()
        self._frame_depth += 1
        try:
            assert self._frame_cache is not None
            yield self._frame_cache
        finally:
            self._frame_depth -= 1
            if self._frame_depth == 0:
                self._frame_cache = None

    def invalidate_frame(self) -> None:
        """Принудительно сбросить кэшированный кадр (например, после tap)."""
        if self._frame_depth > 0:
            self._frame_cache = self._capture_fresh_screenshot()

    def save_debug_screenshot(self, reason: str, image: np.ndarray | None = None) -> Path | None:
        if not self.config.debug_screenshots_enabled:
            return None
        safe_reason = re.sub(r"[^a-zA-Z0-9_.-]+", "_", reason).strip("_") or "debug"
        output_dir = Path(self.config.debug_screenshot_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{safe_reason}.png"
        if image is None:
            image = self.screenshot_array()
        Image.fromarray(image).save(path)
        return path

    def detect_state(self) -> str:
        raw_state = self._detect_state_once()
        return self._confirm_state(raw_state)

    def _detect_state_once(self) -> str:
        started_at = time.perf_counter()
        screenshot = self.screenshot_array()
        screenshot_at = time.perf_counter()
        if self._has_battle_button(screenshot):
            logger.debug("State detected by battle template in {:.1f}ms", (time.perf_counter() - started_at) * 1000)
            return GameState.BATTLE
        if self._has_next_button(screenshot):
            logger.debug("State detected by next template in {:.1f}ms", (time.perf_counter() - started_at) * 1000)
            return GameState.BATTLE
        if self._has_attack_button(screenshot):
            logger.debug("State detected by attack template in {:.1f}ms", (time.perf_counter() - started_at) * 1000)
            return GameState.VILLAGE
        if self._has_star_bonus_counter(screenshot):
            logger.debug(
                "State detected by star bonus template in {:.1f}ms",
                (time.perf_counter() - started_at) * 1000,
            )
            return GameState.VILLAGE

        template_at = time.perf_counter()
        battle_text = self._read_screen_text_from_image(screenshot, self.config.state_ocr_battle_area).lower()
        if any(marker in battle_text for marker in ("next", "end battle", "surrender")):
            logger.debug(
                "State detected by battle OCR in {:.1f}ms; screenshot={:.1f}ms template={:.1f}ms",
                (time.perf_counter() - started_at) * 1000,
                (screenshot_at - started_at) * 1000,
                (template_at - screenshot_at) * 1000,
            )
            return GameState.BATTLE

        village_text = self._read_screen_text_from_image(screenshot, self.config.state_ocr_village_area).lower()
        if any(marker in village_text for marker in ("attack", "shop", "clan", "builder")):
            logger.debug(
                "State detected by village OCR in {:.1f}ms; screenshot={:.1f}ms template={:.1f}ms",
                (time.perf_counter() - started_at) * 1000,
                (screenshot_at - started_at) * 1000,
                (template_at - screenshot_at) * 1000,
            )
            return GameState.VILLAGE

        top_left_text = self._read_screen_text_from_image(screenshot, self.config.state_ocr_top_left_area).lower()
        if "available loot" in top_left_text:
            logger.debug(
                "State detected by top-left OCR in {:.1f}ms; screenshot={:.1f}ms template={:.1f}ms",
                (time.perf_counter() - started_at) * 1000,
                (screenshot_at - started_at) * 1000,
                (template_at - screenshot_at) * 1000,
            )
            return GameState.BATTLE
        saved = self.save_debug_screenshot("unknown-state", screenshot)
        if saved is not None:
            logger.warning("Game state unknown; saved debug screenshot: {}", saved)
        logger.debug(
            "State detection failed in {:.1f}ms; screenshot={:.1f}ms template={:.1f}ms",
            (time.perf_counter() - started_at) * 1000,
            (screenshot_at - started_at) * 1000,
            (template_at - screenshot_at) * 1000,
        )
        return GameState.UNKNOWN

    def _confirm_state(self, raw_state: str) -> str:
        if raw_state == GameState.UNKNOWN:
            if self._stable_state != GameState.UNKNOWN:
                logger.debug("Ignoring raw unknown state; keeping stable state {}", self._stable_state)
                return self._stable_state
            return GameState.UNKNOWN

        if raw_state == self._stable_state:
            self._candidate_state = GameState.UNKNOWN
            self._candidate_count = 0
            return self._stable_state

        if raw_state == self._candidate_state:
            self._candidate_count += 1
        else:
            self._candidate_state = raw_state
            self._candidate_count = 1

        required = self.config.state_confirmations_required
        if self._candidate_count >= required:
            logger.info(
                "State transition confirmed: {} -> {} after {} detections",
                self._stable_state,
                raw_state,
                self._candidate_count,
            )
            self._stable_state = raw_state
            self._candidate_state = GameState.UNKNOWN
            self._candidate_count = 0
            return self._stable_state

        logger.debug(
            "State transition pending: {} -> {} ({}/{})",
            self._stable_state,
            raw_state,
            self._candidate_count,
            required,
        )
        return self._stable_state

    def is_attack_ready(self) -> bool:
        text = self._read_screen_text(self.config.state_ocr_bottom_area).lower()
        normalized = re.sub(r"\s+", " ", text)
        if "attack available in" in normalized:
            return False
        return (
            "find a match" in normalized
            or ("find" in normalized and "match" in normalized)
            or "battle" in normalized
        )

    def has_battle_button(self) -> bool:
        match = self.find_template(
            self.config.battle_template_path,
            self.config.battle_template_threshold,
            self.config.battle_template_area,
        )
        return match is not None

    def _has_battle_button(self, screenshot: np.ndarray) -> bool:
        match = self._find_template_in_image(
            screenshot,
            self.config.battle_template_path,
            self.config.battle_template_threshold,
            self.config.battle_template_area,
        )
        return match is not None

    def has_next_button(self) -> bool:
        paths = [self.config.next_template_path, *self.config.next_template_paths]
        return self._find_any_template(paths, self.config.next_template_threshold, self.config.next_template_area)

    def _has_next_button(self, screenshot: np.ndarray) -> bool:
        paths = [self.config.next_template_path, *self.config.next_template_paths]
        return self._find_any_template_in_image(
            screenshot,
            paths,
            self.config.next_template_threshold,
            self.config.next_template_area,
        )

    def has_attack_button(self) -> bool:
        paths = [self.config.attack_template_path, *self.config.attack_template_paths]
        return self._find_any_template(paths, self.config.attack_template_threshold, self.config.attack_template_area)

    def _has_attack_button(self, screenshot: np.ndarray) -> bool:
        paths = [self.config.attack_template_path, *self.config.attack_template_paths]
        return self._find_any_template_in_image(
            screenshot,
            paths,
            self.config.attack_template_threshold,
            self.config.attack_template_area,
        )

    def _has_star_bonus_counter(self, screenshot: np.ndarray) -> bool:
        return self._find_any_template_in_image(
            screenshot,
            self.config.star_bonus_template_paths,
            self.config.star_bonus_template_threshold,
            self.config.star_bonus_template_area,
        )

    def has_star_bonus_counter(self) -> bool:
        return self._find_any_template(
            self.config.star_bonus_template_paths,
            self.config.star_bonus_template_threshold,
            self.config.star_bonus_template_area,
        )

    def has_troops_deployed_marker(self) -> bool:
        if not self.config.troops_deployed_template_path:
            return False
        match = self.find_template(
            self.config.troops_deployed_template_path,
            self.config.troops_deployed_template_threshold,
            self.config.troops_deployed_detection_area,
        )
        if match is None:
            return False
        logger.info("Troops deployed marker detected at {},{} score={:.3f}", match.x, match.y, match.score)
        return True

    def has_free_button(self) -> bool:
        if not self.config.free_button_template_path:
            return False
        match = self.find_template(
            self.config.free_button_template_path,
            self.config.free_button_template_threshold,
            self.config.free_button_template_area,
        )
        if match is None:
            return False
        logger.info("Free button detected at {},{} score={:.3f}", match.x, match.y, match.score)
        return True

    def has_builder_attack_button(self) -> bool:
        return self._find_any_template(
            self.config.builder_attack_template_paths,
            self.config.builder_attack_template_threshold,
            self.config.builder_attack_template_area,
        )

    def find_builder_find_match_button(self) -> TemplateMatch | None:
        for template_path in self.config.builder_find_match_template_paths:
            match = self.find_template(
                template_path,
                self.config.builder_find_match_template_threshold,
                self.config.builder_find_match_template_area,
            )
            if match is not None:
                return match
        return None

    def has_builder_battle_marker(self) -> bool:
        return self._find_any_template(
            self.config.builder_battle_template_paths,
            self.config.builder_battle_template_threshold,
            self.config.builder_battle_template_area,
        )

    def has_builder_hero(self) -> bool:
        return self._find_any_template(
            self.config.builder_hero_present_template_paths,
            self.config.builder_hero_present_template_threshold,
            self.config.builder_hero_present_template_area,
        )

    def detect_builder_slot_state(self, slot: RelativePoint, screenshot: np.ndarray | None = None) -> str:
        if screenshot is None:
            screenshot = self.screenshot_array()
        area = self._builder_slot_state_area(slot)
        if self._find_any_template_in_image(
            screenshot,
            self.config.builder_slot_ability_ready_template_paths,
            self.config.builder_slot_state_template_threshold,
            area,
        ):
            return BuilderSlotState.ABILITY_READY
        if self._find_any_template_in_image(
            screenshot,
            self.config.builder_slot_not_deployed_template_paths,
            self.config.builder_slot_state_template_threshold,
            area,
        ):
            return BuilderSlotState.NOT_DEPLOYED
        if self._find_any_template_in_image(
            screenshot,
            self.config.builder_slot_deployed_template_paths,
            self.config.builder_slot_state_template_threshold,
            area,
        ):
            return BuilderSlotState.DEPLOYED
        return BuilderSlotState.UNKNOWN

    def _builder_slot_state_area(self, slot: RelativePoint) -> RelativeArea:
        return RelativeArea(
            x_min=max(0.0, slot.x - self.config.builder_slot_state_area_radius_x),
            x_max=min(100.0, slot.x + self.config.builder_slot_state_area_radius_x),
            y_min=max(0.0, slot.y + self.config.builder_slot_state_area_y_min_offset),
            y_max=min(100.0, slot.y + self.config.builder_slot_state_area_y_max_offset),
        )

    def has_builder_return_home_button(self) -> bool:
        return self._find_any_template(
            self.config.builder_return_home_template_paths,
            self.config.builder_return_home_template_threshold,
            self.config.builder_return_home_template_area,
        )

    def has_okay_button(self) -> bool:
        if not self.config.okay_button_enabled:
            return False
        for popup in self.config.popup_templates:
            if "okay" not in popup.name.lower():
                continue
            if self.find_template(popup.template_path, self.config.popup_template_threshold) is not None:
                return True
        text = self._read_screen_text(self.config.okay_button_detection_area).lower()
        normalized = re.sub(r"[^a-z]+", "", text)
        return "okay" in normalized or "ok" == normalized

    def has_configured_popup(self) -> bool:
        for popup in self.config.popup_templates:
            match = self.find_template(popup.template_path, self.config.popup_template_threshold)
            if match is None:
                continue
            logger.info("Popup template detected: {} score={:.3f}", popup.name, match.score)
            return True
        return False

    def detect_deploy_boundary_points(self) -> list[RelativePoint]:
        if not self.config.auto_deploy_boundaries_enabled:
            return []

        screenshot = self.screenshot_array()
        candidates = self._detect_boundary_candidates(screenshot, self.config.auto_deploy_boundary_area)
        if len(candidates) < self.config.auto_deploy_boundary_min_points:
            logger.warning(
                "Auto deploy boundary detection found only {} points; using configured fallback points",
                len(candidates),
            )
            return []

        selected = self._spread_boundary_candidates(candidates, self.config.auto_deploy_boundary_points)
        height, width = screenshot.shape[:2]
        points = [
            RelativePoint(
                x=max(0.0, min(100.0, candidate.x * 100 / width)),
                y=max(0.0, min(100.0, candidate.y * 100 / height)),
            )
            for candidate in selected
        ]
        logger.info("Auto deploy boundary points detected: {}", len(points))
        return points

    def _detect_boundary_candidates(self, screenshot: np.ndarray, area: RelativeArea) -> list[BoundaryCandidate]:
        height, width = screenshot.shape[:2]
        x_min = round(width * area.x_min / 100)
        x_max = round(width * area.x_max / 100)
        y_min = round(height * area.y_min / 100)
        y_max = round(height * area.y_max / 100)
        crop = screenshot[y_min:y_max, x_min:x_max]
        if crop.size == 0:
            return []

        hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        red_mask = cv2.inRange(hsv, np.array([0, 35, 45]), np.array([18, 255, 255]))
        red_mask |= cv2.inRange(hsv, np.array([158, 35, 45]), np.array([180, 255, 255]))
        red_mask |= cv2.inRange(hsv, np.array([0, 20, 80]), np.array([12, 180, 235]))
        white_mask = cv2.inRange(hsv, np.array([0, 0, 170]), np.array([180, 90, 255]))
        mask = cv2.bitwise_or(red_mask, white_mask)
        mask = cv2.medianBlur(mask, 5)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[BoundaryCandidate] = []
        for contour in contours:
            area_px = cv2.contourArea(contour)
            if area_px < 12:
                continue
            perimeter = cv2.arcLength(contour, closed=False)
            if perimeter < 16:
                continue
            for point in contour[:: max(1, len(contour) // 16)]:
                x, y = point[0]
                candidates.append(BoundaryCandidate(x=x_min + int(x), y=y_min + int(y), score=float(area_px)))

        if len(candidates) >= self.config.auto_deploy_boundary_min_points:
            return candidates
        return self._detect_boundary_candidates_by_lines(mask, crop, x_min, y_min)

    def _detect_boundary_candidates_by_lines(
        self,
        mask: np.ndarray,
        crop: np.ndarray,
        offset_x: int,
        offset_y: int,
    ) -> list[BoundaryCandidate]:
        red_edges = cv2.Canny(mask, 40, 120)
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        gray_edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 90, 190)
        edges = cv2.bitwise_or(red_edges, gray_edges)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=40, maxLineGap=12)
        if lines is None:
            return []

        candidates: list[BoundaryCandidate] = []
        for line in lines[:, 0]:
            x1, y1, x2, y2 = [int(value) for value in line]
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0:
                continue
            slope = abs(dy / dx)
            length = (dx * dx + dy * dy) ** 0.5
            if length < 40 or slope < 0.18 or slope > 4.5:
                continue
            line_mask = np.zeros(mask.shape, dtype=np.uint8)
            cv2.line(line_mask, (x1, y1), (x2, y2), 255, 3)
            red_support = cv2.countNonZero(cv2.bitwise_and(mask, line_mask))
            if red_support < max(4, length * 0.08):
                continue
            steps = max(2, min(8, round(length / 45)))
            for index in range(steps + 1):
                ratio = index / steps
                x = round(x1 + dx * ratio)
                y = round(y1 + dy * ratio)
                candidates.append(BoundaryCandidate(x=offset_x + x, y=offset_y + y, score=length))
        return candidates

    @staticmethod
    def _spread_boundary_candidates(candidates: list[BoundaryCandidate], target_count: int) -> list[BoundaryCandidate]:
        if len(candidates) <= target_count:
            return sorted(candidates, key=lambda item: (item.y, item.x))

        ordered = sorted(candidates, key=lambda item: (item.y, item.x))
        selected: list[BoundaryCandidate] = []
        for index in np.linspace(0, len(ordered) - 1, target_count):
            selected.append(ordered[round(float(index))])
        return selected

    def _find_any_template(
        self,
        template_paths: list[str],
        threshold: float,
        search_area: RelativeArea | None = None,
    ) -> bool:
        if not any(template_paths):
            return False
        screenshot = self.screenshot_array()
        return self._find_any_template_in_image(screenshot, template_paths, threshold, search_area)

    def _find_any_template_in_image(
        self,
        screenshot: np.ndarray,
        template_paths: list[str],
        threshold: float,
        search_area: RelativeArea | None = None,
    ) -> bool:
        for template_path in template_paths:
            if not template_path:
                continue
            if self._find_template_in_image(screenshot, template_path, threshold, search_area) is not None:
                return True
        return False

    def find_template(
        self,
        template_path_value: str,
        threshold: float,
        search_area: RelativeArea | None = None,
    ) -> TemplateMatch | None:
        screenshot = self.screenshot_array()
        return self._find_template_in_image(screenshot, template_path_value, threshold, search_area)

    def _find_template_in_image(
        self,
        screenshot_rgb: np.ndarray,
        template_path_value: str,
        threshold: float,
        search_area: RelativeArea | None = None,
    ) -> TemplateMatch | None:
        gray_template = self._load_gray_template(template_path_value)
        if gray_template is None:
            return None

        screenshot = cv2.cvtColor(screenshot_rgb, cv2.COLOR_RGB2BGR)
        offset_x = 0
        offset_y = 0
        if search_area is not None:
            height, width = screenshot.shape[:2]
            offset_x = round(width * search_area.x_min / 100)
            offset_y = round(height * search_area.y_min / 100)
            x_max = round(width * search_area.x_max / 100)
            y_max = round(height * search_area.y_max / 100)
            screenshot = screenshot[offset_y:y_max, offset_x:x_max]

        match = self._best_template_match(screenshot, gray_template)
        if match.score < threshold:
            return None
        return TemplateMatch(x=match.x + offset_x, y=match.y + offset_y, score=match.score)

    def _load_template(self, template_path_value: str) -> np.ndarray | None:
        if template_path_value in self._template_cache:
            return self._template_cache[template_path_value]

        template_path = Path(template_path_value)
        if not template_path.exists():
            self._template_cache[template_path_value] = None
            return None
        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        self._template_cache[template_path_value] = template
        return template

    def _load_gray_template(self, template_path_value: str) -> np.ndarray | None:
        if template_path_value in self._template_gray_cache:
            return self._template_gray_cache[template_path_value]

        template = self._load_template(template_path_value)
        if template is None:
            self._template_gray_cache[template_path_value] = None
            return None
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        self._template_gray_cache[template_path_value] = gray_template
        return gray_template

    @staticmethod
    def _best_template_match(screenshot: np.ndarray, gray_template: np.ndarray) -> TemplateMatch:
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        if gray_template.shape[0] > gray_screen.shape[0] or gray_template.shape[1] > gray_screen.shape[1]:
            return TemplateMatch(x=0, y=0, score=0.0)

        result = cv2.matchTemplate(gray_screen, gray_template, cv2.TM_CCOEFF_NORMED)
        _, max_value, _, max_location = cv2.minMaxLoc(result)
        center_x = max_location[0] + gray_template.shape[1] // 2
        center_y = max_location[1] + gray_template.shape[0] // 2
        return TemplateMatch(x=center_x, y=center_y, score=float(max_value))

    def read_battle_loot(self) -> Loot:
        image = np.array(self.screenshot_image())
        h, w = image.shape[:2]
        loot_region = image[0 : int(h * 0.42), 0 : int(w * 0.34)]
        enlarged = cv2.resize(loot_region, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        result = self.reader.readtext(enlarged, detail=0, paragraph=False, allowlist="0123456789 ")
        text = "\n".join(str(item) for item in result)
        numbers = [self._parse_number(value) for value in re.findall(r"\d[\d\s,.]*", text)]
        numbers = [value for value in numbers if value > 100]
        if len(numbers) < 2:
            return Loot(gold=0, elixir=0, dark_elixir=0)
        dark_elixir = numbers[2] if len(numbers) > 2 else 0
        return Loot(gold=numbers[0], elixir=numbers[1], dark_elixir=dark_elixir)

    def _read_screen_text(self, area: RelativeArea | None = None) -> str:
        image = self.screenshot_array()
        return self._read_screen_text_from_image(image, area)

    def _read_screen_text_from_image(self, image: np.ndarray, area: RelativeArea | None = None) -> str:
        if area is not None:
            h, w = image.shape[:2]
            x_min = round(w * area.x_min / 100)
            x_max = round(w * area.x_max / 100)
            y_min = round(h * area.y_min / 100)
            y_max = round(h * area.y_max / 100)
            image = image[y_min:y_max, x_min:x_max]
        result = self.reader.readtext(image, detail=0, paragraph=True)
        return "\n".join(str(item) for item in result)

    @staticmethod
    def _parse_number(value: str) -> int:
        digits = re.sub(r"\D", "", value)
        return int(digits) if digits else 0
