# Multi-Scale Template Matching - Quick Reference

**Last Updated**: December 2, 2025
**Status**: Production Ready
**Version**: 1.0.0

---

## 5-Minute Quick Start

### Installation
```bash
# No installation needed - UV script runs directly
python adb_template_multiresolution.py --help
```

### Basic Usage
```bash
# Find template in screenshot
python adb_template_multiresolution.py \
    --template button.png \
    --screenshot current.png
```

### Output
```
MATCH 520,315 0.92 0.9x multi_scale
```
Meaning: Match found at (520,315) with 92% confidence at 0.9x scale using multi-scale method

---

## Common Scenarios

### Scenario 1: Mobile Bot (1080p)
```bash
python adb_template_multiresolution.py \
    --template templates/play_button.png \
    --screenshot screenshots/current.png \
    --scales 0.8 0.9 1.0 1.1 \
    --threshold 0.72
```

### Scenario 2: Tablet Support (2560p)
```bash
python adb_template_multiresolution.py \
    --template templates/play_button.png \
    --screenshot screenshots/current.png \
    --scales 0.6 0.7 0.8 0.9 1.0 1.1 1.2 1.3 \
    --threshold 0.70
```

### Scenario 3: JSON Integration
```bash
python adb_template_multiresolution.py \
    --template button.png \
    --screenshot current.png \
    --json | python process_result.py
```

### Scenario 4: Debug Visualization
```bash
python adb_template_multiresolution.py \
    --template button.png \
    --screenshot current.png \
    --save-debug debug_output.png \
    --verbose
```

---

## Python API Usage

### Basic Matching
```python
import cv2
from adb_template_multiresolution import MultiScaleMatcher

# Load images
screenshot = cv2.imread("screenshot.png")
template = cv2.imread("template.png")

# Create matcher
matcher = MultiScaleMatcher(
    scales=[0.8, 0.9, 1.0, 1.1, 1.2],
    threshold=0.7
)

# Find match
result = matcher.match(screenshot, template, "button_id")

if result:
    print(f"Found at ({result.x}, {result.y})")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Scale: {result.scale}x")
    print(f"Time: {result.execution_time_ms:.1f}ms")
```

### With Configuration File
```python
import tomllib
from adb_template_multiresolution import MultiScaleMatcher

# Load config
with open("multi-scale-config.toml", "rb") as f:
    config = tomllib.load(f)

# Get mobile 1080p profile
profile = config["resolution_profiles"]["mobile_1080p"]

# Create matcher
matcher = MultiScaleMatcher(
    scales=profile["scales"],
    threshold=profile["threshold"]
)

result = matcher.match(screenshot, template, "button")
```

### Cache Statistics
```python
# Get cache performance stats
stats = matcher.get_scaler_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache hit rate: {stats['hit_rate']:.1%}")
```

---

## Configuration Profiles

### Mobile Phones
- **720p** (5.0-5.5"): `scales=[0.9, 1.0, 1.1]`
- **1080p** (5.5-6.2"): `scales=[0.8, 0.9, 1.0, 1.1]`
- **1440p** (5.8-6.5"): `scales=[0.75, 0.85, 0.95, 1.05, 1.15]`

### Tablets
- **1440p** (10"): `scales=[0.7, 0.8, 0.9, 1.0, 1.1, 1.2]`
- **2560p** (12.9"): `scales=[0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]`

### Custom
```python
matcher = MultiScaleMatcher(
    scales=[0.85, 0.95, 1.05],  # Custom range
    threshold=0.75              # Adjust strictness
)
```

---

## Threshold Tuning

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| 0.50 | Very lenient | Noisy captures |
| 0.65 | Lenient | Mixed quality |
| 0.70 | **Recommended** | Most scenarios |
| 0.80 | Strict | High quality only |
| 0.90 | Very strict | Perfect matches only |

---

## Performance Tips

### 1. Enable Caching
```python
# Cache is automatic, but you can monitor it
stats = matcher.get_scaler_stats()
if stats['hit_rate'] < 0.5:
    # Consider different template IDs
    pass
```

### 2. Adjust Scale Range
```python
# Fewer scales = faster
matcher = MultiScaleMatcher(
    scales=[0.9, 1.0, 1.1],  # Only 3 scales
    threshold=0.75
)
```

### 3. Preload Configuration
```python
# Load config once, reuse
with open("multi-scale-config.toml", "rb") as f:
    config = tomllib.load(f)

# Reuse for all matches
for template_id in ["button", "icon", "text"]:
    # Use same config
    pass
```

### 4. Monitor Execution Time
```python
if result.execution_time_ms > 500:
    # Consider adjusting scales or threshold
    logger.warning(f"Slow match: {result.execution_time_ms}ms")
```

---

## Troubleshooting

### No Match Found
```
# Try steps in order:
1. Lower threshold: --threshold 0.65
2. Add more scales: --scales 0.7 0.8 0.9 1.0 1.1 1.2
3. Check template quality
4. Verify screenshot includes template area
```

### Low Confidence Match
```
# Options:
1. Increase threshold for next match
2. Use feature matching fallback: --enable-features
3. Preprocess screenshot (enhance contrast)
4. Verify template matches screenshot style
```

### Slow Performance
```
# Optimization:
1. Reduce scales: [0.9, 1.0, 1.1] instead of full range
2. Increase threshold: 0.75 instead of 0.70
3. Limit cache size: max_cache_size=10
4. Use single-scale matching for specific templates
```

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Match found | Use result |
| 1 | No match found | Try different scales/threshold |
| 2 | Invalid file path | Check template/screenshot paths |
| 3 | Config error | Validate TOML file |
| 4 | Processing error | Check image format/size |

---

## Test Your Setup

```bash
# Create simple test
python -c "
import cv2
import numpy as np
from adb_template_multiresolution import MultiScaleMatcher

# Create synthetic images
screenshot = np.ones((1080, 1440, 3), dtype=np.uint8) * 200
template = np.zeros((100, 100, 3), dtype=np.uint8)
template[25:75, 25:75] = 255

# Add template to screenshot
scaled = cv2.resize(template, None, fx=0.9, fy=0.9)
screenshot[300:300+scaled.shape[0], 500:500+scaled.shape[1]] = scaled

# Test matching
matcher = MultiScaleMatcher()
result = matcher.match(screenshot, template, 'test')

print(f'✓ Success: Found at ({result.x}, {result.y})')
"
```

---

## Integration Examples

### Game Automation Bot
```python
class GameBot:
    def __init__(self):
        from adb_template_multiresolution import MultiScaleMatcher
        self.matcher = MultiScaleMatcher(
            scales=[0.8, 0.9, 1.0, 1.1, 1.2],
            threshold=0.72
        )

    def find_and_tap(self, template_name):
        screenshot = self.device.screenshot()
        template = cv2.imread(f"templates/{template_name}.png")

        result = self.matcher.match(screenshot, template, template_name)
        if result:
            self.device.tap(result.x, result.y)
            return True
        return False
```

### CI/CD Pipeline
```bash
#!/bin/bash
for device in 720p 1080p 1440p; do
    python adb_template_multiresolution.py \
        --template templates/button.png \
        --screenshot tests/$device/screenshot.png \
        --json > tests/$device/result.json

    if [ $? -ne 0 ]; then
        echo "Failed on $device"
        exit 1
    fi
done
```

### Data Pipeline
```python
import json
import subprocess

result = subprocess.run([
    'python', 'adb_template_multiresolution.py',
    '--template', 'button.png',
    '--screenshot', 'screenshot.png',
    '--json'
], capture_output=True, text=True)

match_data = json.loads(result.stdout)
if match_data['status'] == 'match_found':
    x = match_data['result']['x']
    y = match_data['result']['y']
    # Process coordinates
```

---

## Files Overview

| File | Purpose | Size |
|------|---------|------|
| `computer-vision.md` | Documentation (section 7️⃣) | ~150 lines |
| `adb_template_multiresolution.py` | Main implementation | ~280 lines |
| `test_multiresolution_matching.py` | Test suite | ~200 lines |
| `multi-scale-config.toml` | Configuration template | ~180 lines |

---

## Key Features Checklist

- ✅ Multi-scale template matching (0.8x-1.2x)
- ✅ Pyramid caching for performance
- ✅ Fallback chain (multi-scale → single-scale → features)
- ✅ CLI with 7 options
- ✅ JSON/YAML output formats
- ✅ Configuration file support
- ✅ Device-specific profiles (720p-2560p)
- ✅ Performance benchmarking
- ✅ Debug visualization
- ✅ 34 comprehensive tests (≥85% coverage)

---

## Support & Contribution

**Issue**: Template not matching?
→ See "Troubleshooting" section above

**Performance too slow?**
→ Try reducing scales: `[0.9, 1.0, 1.1]`

**Need custom profile?**
→ Add to `multi-scale-config.toml` `[resolution_profiles]`

**Want to contribute?**
→ Add tests to `test_multiresolution_matching.py`

---

**Version**: 1.0.0 | **Status**: Production Ready | **Date**: December 2, 2025
