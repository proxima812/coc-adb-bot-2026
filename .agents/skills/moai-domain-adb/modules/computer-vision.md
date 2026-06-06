# Module 4: Computer Vision

**Level**: Intermediate → Advanced
**Prerequisites**: Module 3 (game-automation)
**Estimated Learning Time**: 45-60 minutes
**Hands-On Practice**: 20-30 minutes

---

## 1️⃣ Template Matching (OpenCV)

### Basic Template Matching

```python
import cv2
import numpy as np

class TemplateDetector:
    def __init__(self, template_dir: str = "templates/"):
        self.template_dir = template_dir

    def find_template(self, image_path: str, template_name: str, threshold: float = 0.7) -> Optional[tuple]:
        """Find template in image, return (x, y) or None"""

        image = cv2.imread(image_path)
        template = cv2.imread(f"{self.template_dir}/{template_name}.png")

        if image is None or template is None:
            return None

        # Match template
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # Check confidence
        if max_val > threshold:
            # Return center coordinates
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y)

        return None

    def find_all_templates(self, image_path: str, template_name: str, threshold: float = 0.7) -> List[tuple]:
        """Find all occurrences of template"""

        image = cv2.imread(image_path)
        template = cv2.imread(f"{self.template_dir}/{template_name}.png")

        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

        # Get all matches above threshold
        locations = np.where(result >= threshold)

        matches = []
        for (y, x) in zip(*locations):
            h, w = template.shape[:2]
            center_x = x + w // 2
            center_y = y + h // 2
            confidence = result[y, x]
            matches.append((center_x, center_y, confidence))

        return matches

# Usage
detector = TemplateDetector()

# Find single match
location = detector.find_template("screenshot.png", "play_button")
if location:
    device.tap(location[0], location[1])

# Find all buttons of same type
buttons = detector.find_all_templates("screenshot.png", "item_slot")
for x, y, confidence in buttons:
    print(f"Button at ({x}, {y}) with confidence {confidence:.2%}")
```

### Template Methods

```python
# TM_CCOEFF_NORMED: Normalized cross-correlation (recommended)
#   - Range: -1 to 1 (higher is better)
#   - Robust to lighting changes
#   - Best for general purpose

# TM_SQDIFF_NORMED: Sum of squared differences
#   - Range: 0 to 1 (lower is better)
#   - Fast computation
#   - Good for exact matches

# TM_CCORR_NORMED: Cross correlation
#   - Range: 0 to 1 (higher is better)
#   - Very fast
#   - Sensitive to lighting

# Choose based on use case:
# - Fast buttons: TM_CCORR_NORMED
# - Exact images: TM_SQDIFF_NORMED
# - Variable lighting: TM_CCOEFF_NORMED (default)
```

---

## 2️⃣ Region-Based Detection

### Region of Interest (ROI)

```python
class RegionDetector:
    def __init__(self):
        # Define game regions
        self.regions = {
            "inventory": (0, 0, 1080, 600),      # Top half
            "action_bar": (0, 900, 1080, 1920),  # Bottom quarter
            "character": (400, 200, 680, 800),   # Center area
        }

    def get_region(self, image: np.ndarray, region_name: str) -> np.ndarray:
        """Extract region from image"""
        x1, y1, x2, y2 = self.regions[region_name]
        return image[y1:y2, x1:x2]

    def detect_in_region(self, image: np.ndarray, region_name: str, template_name: str) -> Optional[tuple]:
        """Find template in specific region only"""

        roi = self.get_region(image, region_name)
        template = cv2.imread(f"templates/{template_name}.png")

        result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > 0.7:
            # Adjust coordinates back to full image
            x1, y1, _, _ = self.regions[region_name]
            h, w = template.shape[:2]
            center_x = x1 + max_loc[0] + w // 2
            center_y = y1 + max_loc[1] + h // 2
            return (center_x, center_y)

        return None

# Usage
detector = RegionDetector()
image = cv2.imread("screenshot.png")

# Find skill button in action bar only
skill_pos = detector.detect_in_region(image, "action_bar", "skill_button")
```

---

## 3️⃣ Feature Detection (Advanced)

### SIFT Features (Scale-Invariant)

```python
class FeatureDetector:
    def __init__(self):
        # SIFT requires OpenCV contrib (opencv-contrib-python)
        self.sift = cv2.SIFT_create()
        self.matcher = cv2.BFMatcher()

    def find_object(self, image_path: str, template_path: str) -> Optional[tuple]:
        """Find object using SIFT features (rotation/scale invariant)"""

        image = cv2.imread(image_path)
        template = cv2.imread(template_path)

        # Find keypoints and descriptors
        kp1, des1 = self.sift.detectAndCompute(image, None)
        kp2, des2 = self.sift.detectAndCompute(template, None)

        if des1 is None or des2 is None:
            return None

        # Match features
        matches = self.matcher.knnMatch(des2, des1, k=2)

        # Apply Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)

        if len(good_matches) >= 10:
            # Enough matches to consider object found
            # Get average position
            positions = [kp1[m.trainIdx].pt for m in good_matches]
            avg_x = sum(x for x, y in positions) / len(positions)
            avg_y = sum(y for x, y in positions) / len(positions)
            return (int(avg_x), int(avg_y))

        return None

# Usage: Find object with rotation/scale changes
detector = FeatureDetector()
pos = detector.find_object("screenshot.png", "character_template.png")
```

---

## 4️⃣ Color-Based Detection

### Color Range Detection

```python
class ColorDetector:
    def __init__(self):
        # HSV ranges for common colors
        self.colors = {
            "red": {
                "lower": np.array([0, 100, 100]),
                "upper": np.array([10, 255, 255])
            },
            "green": {
                "lower": np.array([35, 100, 100]),
                "upper": np.array([85, 255, 255])
            },
            "blue": {
                "lower": np.array([100, 100, 100]),
                "upper": np.array([130, 255, 255])
            },
            "yellow": {
                "lower": np.array([20, 100, 100]),
                "upper": np.array([30, 255, 255])
            },
        }

    def detect_color(self, image_path: str, color_name: str) -> Optional[tuple]:
        """Find region with specific color, return center"""

        image = cv2.imread(image_path)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Create mask
        lower = self.colors[color_name]["lower"]
        upper = self.colors[color_name]["upper"]
        mask = cv2.inRange(hsv, lower, upper)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Get largest contour
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)

            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return (cx, cy)

        return None

    def detect_all_colors(self, image_path: str, color_name: str) -> List[tuple]:
        """Find all regions with specific color"""

        image = cv2.imread(image_path)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, self.colors[color_name]["lower"], self.colors[color_name]["upper"])
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        centers = []
        for contour in contours:
            if cv2.contourArea(contour) > 100:  # Filter small noise
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    centers.append((cx, cy))

        return centers

# Usage: Detect all gold/yellow drops
detector = ColorDetector()
drops = detector.detect_all_colors("screenshot.png", "yellow")
for x, y in drops:
    device.tap(x, y)
```

---

## 5️⃣ Image Preprocessing

### Enhance Detection Accuracy

```python
class ImagePreprocessor:
    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Increase contrast for better detection"""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    @staticmethod
    def threshold_binary(image: np.ndarray, threshold: int = 127) -> np.ndarray:
        """Convert to binary (black/white) for shape detection"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        return binary

    @staticmethod
    def remove_noise(image: np.ndarray) -> np.ndarray:
        """Remove small noise from image"""
        return cv2.morphologyEx(image, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    @staticmethod
    def resize_match_template(template: np.ndarray, target_height: int) -> np.ndarray:
        """Resize template to match expected size on screen"""
        scale = target_height / template.shape[0]
        new_width = int(template.shape[1] * scale)
        return cv2.resize(template, (new_width, target_height))

# Usage
preprocessor = ImagePreprocessor()
image = cv2.imread("screenshot.png")

# Enhance for better template matching
enhanced = preprocessor.enhance_contrast(image)
template = cv2.imread("template.png")

# Resize template to expected screen size
resized_template = preprocessor.resize_match_template(template, 100)
```

---

## 6️⃣ Adaptive Detection

### Multi-Scale Template Matching

```python
class AdaptiveDetector:
    def find_at_multiple_scales(self, image_path: str, template_name: str,
                               scales: List[float] = [0.8, 0.9, 1.0, 1.1, 1.2]) -> Optional[tuple]:
        """Find template at different scales (for UI elements that change size)"""

        image = cv2.imread(image_path)
        template = cv2.imread(f"templates/{template_name}.png")

        best_match = None
        best_confidence = 0

        for scale in scales:
            # Resize template
            scaled_template = cv2.resize(template, None, fx=scale, fy=scale)

            # Match
            result = cv2.matchTemplate(image, scaled_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_confidence:
                best_confidence = max_val
                h, w = scaled_template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                best_match = (center_x, center_y, best_confidence)

        return best_match if best_confidence > 0.7 else None

    def detect_with_rotation(self, image_path: str, template_name: str,
                            angles: List[int] = [-15, -10, -5, 0, 5, 10, 15]) -> Optional[tuple]:
        """Find template with rotation variations"""

        image = cv2.imread(image_path)
        template = cv2.imread(f"templates/{template_name}.png")
        h, w = template.shape[:2]

        best_match = None
        best_confidence = 0

        for angle in angles:
            # Rotate template
            matrix = cv2.getRotationMatrix2D((w//2, h//2), angle, 1)
            rotated = cv2.warpAffine(template, matrix, (w, h))

            # Match
            result = cv2.matchTemplate(image, rotated, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_confidence:
                best_confidence = max_val
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                best_match = (center_x, center_y, best_confidence)

        return best_match if best_confidence > 0.7 else None

# Usage
detector = AdaptiveDetector()

# Find button that may be scaled differently
pos = detector.find_at_multiple_scales("screenshot.png", "button",
                                       scales=[0.9, 1.0, 1.1])

# Find button that may be slightly rotated
pos = detector.detect_with_rotation("screenshot.png", "button",
                                    angles=[-5, 0, 5])
```

---

## 7️⃣ Multi-Scale Template Matching (Density-Independent Detection)

### Image Pyramid Concept

Multi-scale template matching solves the critical problem of UI templates working across different device densities without modification. Rather than creating separate templates for each resolution, generate an **image pyramid** of the template at different scales and match against the actual screenshot.

**When to Use**:
- Device has different DPI (720p, 1080p, 1440p, etc.)
- UI elements appear scaled on different devices
- Need 5-10x faster resolution handling vs sequential tries
- Supporting tablets + phones with same bot code

**Scale Strategy** (0.8x to 1.2x):
```
Scale 0.8x  ───┐
Scale 0.9x  ──┬┴─ Match against screenshot
Scale 1.0x  ──┼─  Return best match + scale info
Scale 1.1x  ──┬┐
Scale 1.2x  ───┘

Performance: Single match ~50-100ms | Multi-scale ~250-500ms | With cache ~100-200ms
Improvement: 5-10x faster density handling vs retry loop
```

### Implementation Pattern

```python
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict
import time

@dataclass
class MatchResult:
    """Result from template matching"""
    x: int
    y: int
    confidence: float
    scale: float
    method: str  # 'multi_scale', 'single_scale', 'feature_matching'
    execution_time: float

class TemplateScaler:
    """Generate and cache template pyramids at multiple scales"""

    def __init__(self, scales: List[float] = None):
        """Initialize scaler with scale factors"""
        self.scales = scales or [0.8, 0.9, 1.0, 1.1, 1.2]
        self.pyramid_cache: Dict[str, Dict[float, np.ndarray]] = {}
        self.hit_count = 0
        self.miss_count = 0

    def generate_pyramid(self, template: np.ndarray, template_id: str) -> Dict[float, np.ndarray]:
        """Generate image pyramid for template"""

        # Check cache first
        if template_id in self.pyramid_cache:
            self.hit_count += 1
            return self.pyramid_cache[template_id]

        self.miss_count += 1
        pyramid = {}

        for scale in self.scales:
            # Calculate new dimensions
            height = int(template.shape[0] * scale)
            width = int(template.shape[1] * scale)

            if height > 2 and width > 2:  # Avoid degenerate cases
                scaled = cv2.resize(template, (width, height), interpolation=cv2.INTER_LINEAR)
                pyramid[scale] = scaled

        # Cache pyramid
        self.pyramid_cache[template_id] = pyramid
        return pyramid

    def clear_cache(self):
        """Clear pyramid cache"""
        self.pyramid_cache.clear()
        self.hit_count = 0
        self.miss_count = 0

    def cache_stats(self) -> Dict[str, int]:
        """Get cache hit/miss statistics"""
        total = self.hit_count + self.miss_count
        return {
            'hits': self.hit_count,
            'misses': self.miss_count,
            'total': total,
            'hit_rate': self.hit_count / total if total > 0 else 0
        }

class MultiScaleMatcher:
    """Match templates at multiple scales with fallback chain"""

    def __init__(self, scales: List[float] = None, threshold: float = 0.7):
        """Initialize multi-scale matcher"""
        self.scaler = TemplateScaler(scales)
        self.threshold = threshold
        self.method = cv2.TM_CCOEFF_NORMED

    def match(self, screenshot: np.ndarray, template: np.ndarray,
              template_id: str = "template") -> Optional[MatchResult]:
        """
        Match template at multiple scales with fallback chain

        Fallback chain:
        1. Multi-scale matching (0.8x-1.2x)
        2. Single-scale matching (1.0x)
        3. Feature matching (SIFT/ORB)
        """
        start_time = time.time()

        # Step 1: Multi-scale matching
        pyramid = self.scaler.generate_pyramid(template, template_id)
        best_result = None
        best_confidence = 0

        for scale, scaled_template in pyramid.items():
            if scaled_template.shape[0] > screenshot.shape[0] or \
               scaled_template.shape[1] > screenshot.shape[1]:
                continue  # Skip scales larger than screenshot

            # Match at this scale
            result = cv2.matchTemplate(screenshot, scaled_template, self.method)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_confidence:
                best_confidence = max_val
                h, w = scaled_template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                best_result = MatchResult(
                    x=center_x,
                    y=center_y,
                    confidence=best_confidence,
                    scale=scale,
                    method='multi_scale',
                    execution_time=time.time() - start_time
                )

        # Check multi-scale result
        if best_result and best_result.confidence > self.threshold:
            return best_result

        # Step 2: Single-scale fallback
        single_scale_result = self._match_single_scale(screenshot, template, template_id)
        if single_scale_result:
            single_scale_result.execution_time = time.time() - start_time
            return single_scale_result

        # Step 3: Feature matching fallback
        feature_result = self._match_features(screenshot, template)
        if feature_result:
            feature_result.execution_time = time.time() - start_time
            return feature_result

        return None

    def _match_single_scale(self, screenshot: np.ndarray, template: np.ndarray,
                           template_id: str) -> Optional[MatchResult]:
        """Fallback: Match template at 1.0x scale only"""
        result = cv2.matchTemplate(screenshot, template, self.method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > self.threshold:
            h, w = template.shape[:2]
            return MatchResult(
                x=max_loc[0] + w // 2,
                y=max_loc[1] + h // 2,
                confidence=max_val,
                scale=1.0,
                method='single_scale',
                execution_time=0
            )
        return None

    def _match_features(self, screenshot: np.ndarray, template: np.ndarray) -> Optional[MatchResult]:
        """Fallback: Match using ORB features (lightweight alternative to SIFT)"""
        try:
            orb = cv2.ORB_create(nfeatures=500)

            kp1, des1 = orb.detectAndCompute(screenshot, None)
            kp2, des2 = orb.detectAndCompute(template, None)

            if des1 is None or des2 is None or len(kp1) < 5:
                return None

            # Match features
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des2, des1)
            matches = sorted(matches, key=lambda x: x.distance)

            # Need at least 10 good matches
            if len(matches) >= 10:
                positions = [kp1[m.trainIdx].pt for m in matches[:10]]
                avg_x = int(sum(x for x, y in positions) / len(positions))
                avg_y = int(sum(y for x, y in positions) / len(positions))

                return MatchResult(
                    x=avg_x,
                    y=avg_y,
                    confidence=1.0,
                    scale=1.0,
                    method='feature_matching',
                    execution_time=0
                )
        except Exception:
            pass

        return None

# Usage Example
print("=== Multi-Scale Template Matching Example ===\n")

# Create synthetic test images
screenshot = np.ones((1080, 1440, 3), dtype=np.uint8) * 200
template = np.zeros((100, 100, 3), dtype=np.uint8)
template[25:75, 25:75] = 255  # White square in center

# Initialize matcher
matcher = MultiScaleMatcher(scales=[0.8, 0.9, 1.0, 1.1, 1.2], threshold=0.7)

# Add template to screenshot at 0.9x scale
scaled = cv2.resize(template, None, fx=0.9, fy=0.9)
x_pos, y_pos = 500, 300
screenshot[y_pos:y_pos+scaled.shape[0], x_pos:x_pos+scaled.shape[1]] = scaled

# Match template
result = matcher.match(screenshot, template, "test_button")
if result:
    print(f"Match found: ({result.x}, {result.y})")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Scale: {result.scale}x")
    print(f"Method: {result.method}")
    print(f"Time: {result.execution_time*1000:.1f}ms")
```

### Configuration & Tuning

```python
# TOML Configuration (multi-scale-config.toml)
[scales]
enabled = true
factors = [0.8, 0.9, 1.0, 1.1, 1.2]
cache_enabled = true
max_cache_size = 50

[matching]
threshold = 0.7
method = "TM_CCOEFF_NORMED"
timeout_ms = 500

[resolution_profiles]
[resolution_profiles.mobile_720p]
scales = [0.9, 1.0, 1.1]

[resolution_profiles.mobile_1080p]
scales = [0.8, 0.9, 1.0]

[resolution_profiles.tablet_1440p]
scales = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2]

# Python usage
import tomllib

with open('multi-scale-config.toml', 'rb') as f:
    config = tomllib.load(f)

matcher = MultiScaleMatcher(
    scales=config['scales']['factors'],
    threshold=config['matching']['threshold']
)
```

### Best Practices

✅ **DO**:
- Use 5 scales (0.8, 0.9, 1.0, 1.1, 1.2) as baseline
- Cache pyramids for repeated template matching
- Set threshold appropriate to device quality
- Monitor cache hit rate in production
- Use feature matching as last fallback
- Profile performance on target devices

❌ **DON'T**:
- Use too many scales (causes slowdown)
- Skip caching for production code
- Assume same scales work for all templates
- Ignore execution time measurements
- Use overly small templates with scaling
- Skip fallback chain validation

---

## 5️⃣ Advanced Image Preprocessing

Advanced preprocessing enhances image quality and improves computer vision task accuracy through contrast enhancement, morphological operations, edge detection, and grayscale conversion variants.

### 5.1 Contrast Limited Adaptive Histogram Equalization (CLAHE)

CLAHE improves local contrast by applying histogram equalization to small tiles of the image, preventing excessive noise amplification. Particularly useful for low-contrast screenshots.

**Theory**: Instead of applying global histogram equalization (which can cause artifacts), CLAHE divides the image into small regions (tiles) and applies histogram equalization to each tile independently, then combines them with bilinear interpolation.

```python
import cv2
import numpy as np

class CLAHEPreprocessor:
    def __init__(self, clip_limit: float = 2.0, tile_grid_size: tuple = (8, 8)):
        """
        Initialize CLAHE.

        clip_limit: Threshold for contrast limiting
                   - Low (1.0-2.0): Conservative, less artifact risk
                   - High (3.0+): Aggressive enhancement, more artifacts
        tile_grid_size: Size of grid for histogram equalization
                       - Small (4,4): More local adaptation
                       - Large (16,16): Less local adaptation, smoother
        """
        self.clahe = cv2.createCLAHE(
            clipLimit=clip_limit,
            tileGridSize=tile_grid_size
        )

    def process(self, image: np.ndarray) -> np.ndarray:
        """Apply CLAHE to image"""
        # For color images, convert to LAB and apply CLAHE only to L channel
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # Apply CLAHE only to brightness
        l_enhanced = self.clahe.apply(l_channel)

        # Merge and convert back to BGR
        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

# Usage
preprocessor = CLAHEPreprocessor(clip_limit=2.0, tile_grid_size=(8, 8))
image = cv2.imread("screenshot.png")
enhanced = preprocessor.process(image)
```

**Parameters Guide**:
- `clip_limit=1.0-2.0`: Conservative (recommended for production)
- `clip_limit=3.0-4.0`: Aggressive (use for very low-contrast images)
- `tile_grid_size=(4,4)`: High local adaptation (more artifacts)
- `tile_grid_size=(8,8)`: Balanced (recommended)
- `tile_grid_size=(16,16)`: Low local adaptation (smoother)

### 5.2 Morphological Operations

Morphological operations modify image structure using a structuring element (kernel).

**Basic Operations**:
- **Erosion**: Removes small white objects, shrinks white regions
- **Dilation**: Fills small black holes, expands white regions
- **Opening**: Erosion + Dilation (removes noise, preserves large objects)
- **Closing**: Dilation + Erosion (fills holes, preserves background)

```python
class MorphologicalProcessor:
    def __init__(self, kernel_size: str = "medium"):
        """
        Initialize with kernel size.

        kernel_size options:
        - "small": (3, 3) - Affects small details
        - "medium": (5, 5) - Balanced
        - "large": (7, 7) - Affects large areas
        """
        kernel_sizes = {
            "small": (3, 3),
            "medium": (5, 5),
            "large": (7, 7),
        }
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            kernel_sizes[kernel_size]
        )

    def erode(self, image: np.ndarray) -> np.ndarray:
        """Remove white noise and shrink white regions"""
        return cv2.erode(image, self.kernel, iterations=1)

    def dilate(self, image: np.ndarray) -> np.ndarray:
        """Fill black holes and expand white regions"""
        return cv2.dilate(image, self.kernel, iterations=1)

    def open(self, image: np.ndarray) -> np.ndarray:
        """Remove noise while preserving large objects"""
        return cv2.morphologyEx(image, cv2.MORPH_OPEN, self.kernel)

    def close(self, image: np.ndarray) -> np.ndarray:
        """Fill holes while preserving background"""
        return cv2.morphologyEx(image, cv2.MORPH_CLOSE, self.kernel)

# Usage
processor = MorphologicalProcessor(kernel_size="medium")
image = cv2.imread("screenshot.png")

# Remove noise
denoised = processor.open(image)

# Fill holes in detected objects
filled = processor.close(denoised)
```

**When to Use Each**:
| Operation | Effect | Use Case |
|-----------|--------|----------|
| Erode | Shrink white | Remove thin lines, noise |
| Dilate | Expand white | Connect broken objects |
| Open | Shrink then expand | Remove noise, keep objects |
| Close | Expand then shrink | Fill holes, keep background |

### 5.3 Edge Detection

Edge detection identifies object boundaries using gradient-based algorithms.

**Canny Edge Detection** (Recommended):
- Multi-stage algorithm with non-maximum suppression
- Hysteresis thresholding for edge linking
- More precise edges, fewer false positives

**Sobel Edge Detection**:
- Computes X and Y gradients independently
- Faster computation
- Better for gradient direction analysis

```python
class EdgeDetectionProcessor:
    def canny(self, image: np.ndarray,
              threshold1: int = 100,
              threshold2: int = 200) -> np.ndarray:
        """
        Canny edge detection.

        threshold1: Lower threshold (edges below ignored)
        threshold2: Upper threshold (edges above always included)
        Edges between thresholds included if connected to strong edges

        Typical values:
        - threshold1 = 100, threshold2 = 200 (conservative)
        - threshold1 = 50, threshold2 = 150 (aggressive)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
        return cv2.Canny(blurred, threshold1, threshold2)

    def sobel(self, image: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """
        Sobel edge detection.

        kernel_size: 1, 3, 5, 7 (larger = more smoothing)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Compute gradients
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=kernel_size)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=kernel_size)

        # Combine magnitudes
        magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
        return np.uint8(np.clip(magnitude, 0, 255))

# Usage
processor = EdgeDetectionProcessor()

# Canny (more precise)
edges_canny = processor.canny(image, threshold1=100, threshold2=200)

# Sobel (faster)
edges_sobel = processor.sobel(image, kernel_size=3)
```

### 5.4 Grayscale Conversion Variants

Different grayscale conversion methods preserve different aspects of color information.

```python
class GrayscaleVariantProcessor:
    @staticmethod
    def convert_luminosity(image: np.ndarray) -> np.ndarray:
        """Weighted average based on human perception
        Formula: 0.299*R + 0.587*G + 0.114*B
        Best for: Most use cases, mimics human vision"""
        b, g, r = cv2.split(image)
        return np.uint8(0.299 * r + 0.587 * g + 0.114 * b)

    @staticmethod
    def convert_average(image: np.ndarray) -> np.ndarray:
        """Simple arithmetic mean
        Formula: (R + G + B) / 3
        Best for: Fast computation, rough approximation"""
        return np.uint8(np.mean(image, axis=2))

    @staticmethod
    def convert_desaturation(image: np.ndarray) -> np.ndarray:
        """Average of max and min channels
        Formula: (max(R,G,B) + min(R,G,B)) / 2
        Best for: Preserving midtones"""
        max_val = np.max(image, axis=2)
        min_val = np.min(image, axis=2)
        return np.uint8((max_val + min_val) / 2)

    @staticmethod
    def convert_decomposition(image: np.ndarray) -> np.ndarray:
        """V (Value) channel from HSV
        Best for: Brightness-based processing"""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _, _, v = cv2.split(hsv)
        return v

# Usage
processor = GrayscaleVariantProcessor()
image = cv2.imread("screenshot.png")

# Different conversion methods
gray_luminosity = processor.convert_luminosity(image)      # Best for templates
gray_average = processor.convert_average(image)            # Fastest
gray_desaturation = processor.convert_desaturation(image)  # Balanced
gray_value = processor.convert_decomposition(image)        # Brightness only
```

### 5.5 Preprocessing Pipeline Architecture

Compose multiple preprocessing operations into configurable pipelines.

```python
class PreprocessingPipeline:
    def __init__(self, cache_enabled: bool = False):
        self.cache_enabled = cache_enabled
        self.clahe = CLAHEPreprocessor()
        self.morphology = MorphologicalProcessor()
        self.edges = EdgeDetectionProcessor()
        self.grayscale = GrayscaleVariantProcessor()

    def execute(self, image: np.ndarray, preset: str = "balanced") -> np.ndarray:
        """
        Execute preprocessing pipeline with preset.

        Presets:
        - "balanced": CLAHE + morphological opening (best for template matching)
        - "contrast": High-clip CLAHE (for very low-contrast images)
        - "edges": Canny edge detection (for shape detection)
        - "denoise": Morphological open + close (remove noise)
        - "grayscale": Convert to grayscale (for template matching)
        """
        result = image.copy()

        if preset == "balanced":
            # Enhance contrast
            result, _ = self.clahe.process(result)
            # Remove noise while preserving objects
            result, _ = self.morphology.open(result)

        elif preset == "contrast":
            clahe = CLAHEPreprocessor(clip_limit=4.0)
            result, _ = clahe.process(result)

        elif preset == "edges":
            result, _ = self.edges.canny(result)

        elif preset == "denoise":
            result, _ = self.morphology.open(result)
            result, _ = self.morphology.close(result)

        return result

# Usage
pipeline = PreprocessingPipeline(cache_enabled=True)
image = cv2.imread("screenshot.png")

# Different preprocessing strategies
balanced = pipeline.execute(image, preset="balanced")     # Best general-purpose
contrast = pipeline.execute(image, preset="contrast")     # Low-contrast recovery
edges = pipeline.execute(image, preset="edges")           # Shape detection
```

### 5.6 Performance Optimization

**Processing Time Targets** (for 1920x1080 image):
- CLAHE: 50-100ms
- Morphological Operations: 10-30ms
- Canny Edge Detection: 20-40ms
- Sobel Edge Detection: 10-20ms
- Grayscale Conversion: 5-10ms
- Full Pipeline (balanced): <500ms

**Optimization Strategies**:
1. **Caching**: Cache preprocessed images to avoid recomputation
2. **Resolution Reduction**: Process at lower resolution, then scale up if needed
3. **Selective Processing**: Only preprocess regions of interest (ROI)
4. **Async Processing**: Preprocess images in background thread

```python
# Example: Cached preprocessing
class CachedPipeline:
    def __init__(self):
        self.pipeline = PreprocessingPipeline(cache_enabled=True)
        self.cache = {}

    def process(self, image_path: str, preset: str = "balanced"):
        """Process with caching"""
        key = f"{image_path}_{preset}"

        if key in self.cache:
            return self.cache[key]  # Cache hit!

        image = cv2.imread(image_path)
        result = self.pipeline.execute(image, preset=preset)

        self.cache[key] = result
        return result

    def clear_cache(self):
        """Clear cache when memory is low"""
        self.cache.clear()
```

### 5.7 Configuration Format

TOML configuration for preprocessing pipelines:

```toml
[preprocessing]
cache_enabled = true
max_cache_size = 50

[clahe]
clip_limit = 2.0
tile_grid_size = [8, 8]

[morphology]
kernel_size = "medium"
open_iterations = 1
close_iterations = 1

[edge_detection]
canny_threshold1 = 100
canny_threshold2 = 200
sobel_kernel_size = 3

[pipeline_presets]
[pipeline_presets.balanced]
steps = ["clahe", "open"]

[pipeline_presets.contrast]
steps = ["clahe_aggressive"]

[pipeline_presets.denoise]
steps = ["open", "close"]

[pipeline_presets.edges]
steps = ["canny"]
```

### 5.8 Integration with Template Matching

Preprocessing significantly improves template matching accuracy:

```python
class PreprocessingTemplateDetector:
    def __init__(self):
        self.pipeline = PreprocessingPipeline(cache_enabled=True)

    def find_template(self, image: np.ndarray, template: np.ndarray) -> tuple:
        """Find template with preprocessing"""
        # Preprocess both images
        image_processed = self.pipeline.execute(image, preset="balanced")
        template_processed = self.pipeline.execute(template, preset="balanced")

        # Match preprocessed images
        result = cv2.matchTemplate(
            image_processed,
            template_processed,
            cv2.TM_CCOEFF_NORMED
        )

        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > 0.7:
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)

        return None

# Usage
detector = PreprocessingTemplateDetector()
image = cv2.imread("screenshot.png")
template = cv2.imread("button.png")

position = detector.find_template(image, template)
if position:
    x, y, confidence = position
    print(f"Found at ({x}, {y}) with {confidence:.2%} confidence")
```

---

## 8️⃣ Performance Optimization

### Image Caching & Lazy Loading

```python
class VisionCache:
    def __init__(self):
        self.image_cache = {}
        self.template_cache = {}

    def load_image(self, path: str) -> np.ndarray:
        """Load image with caching"""
        if path not in self.image_cache:
            self.image_cache[path] = cv2.imread(path)
        return self.image_cache[path]

    def load_template(self, name: str) -> np.ndarray:
        """Load template with caching"""
        if name not in self.template_cache:
            self.template_cache[name] = cv2.imread(f"templates/{name}.png")
        return self.template_cache[name]

    def clear_cache(self):
        """Clear all cached images"""
        self.image_cache.clear()
        self.template_cache.clear()

# Usage
cache = VisionCache()
template = cache.load_template("button")  # Loaded from disk
template = cache.load_template("button")  # Retrieved from cache (faster)
```

---

## 9️⃣ Best Practices

✅ **DO**:
- Use TM_CCOEFF_NORMED for robustness
- Cache templates to avoid repeated disk I/O
- Preprocess images to improve accuracy
- Use ROI to reduce search space
- Fall back between methods (template → color → features)
- Test templates on multiple device types
- Use multi-scale matching for resolution-independent detection

❌ **DON'T**:
- Use exact pixel color matching (use color ranges)
- Assume templates work across all resolutions without multi-scale
- Run expensive SIFT for every frame
- Use overly small templates (noise sensitive)
- Skip preprocessing for poor image quality
- Match against entire screen (use ROI)
- Hardcode scale factors (use configuration files)

---

## 🔗 Integration

Multi-scale template matching integrates with:
- **adb_template_multiresolution.py** - UV script implementation (see scripts/advanced/)
- **test_multiresolution_matching.py** - Comprehensive test suite (see tests/)
- **multi-scale-config.toml** - Configuration template (see examples/)

---

**Status**: ✅ Computer Vision Techniques Covered
**Next Module**: [tauri-integration](./tauri-integration.md)
