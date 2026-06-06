#!/usr/bin/env -S uv run --quiet --script
# /// script
# dependencies = [
#   "click>=8.1.0",
#   "pyyaml>=6.0",
#   "jsonschema>=4.0",
# ]
# ///
"""
ADB Configuration Validator

Validates bot and device configuration files (YAML/JSON) for ADB Auto Player.
Checks schema compliance, required fields, coordinate ranges, and file references.

Usage:
    python adb_config_validator.py --config-file bot_config.yaml
    python adb_config_validator.py --config-file device.json --schema device
    python adb_config_validator.py --config-file config.yaml --strict --fix
    python adb_config_validator.py --config-file config.json --json

Author: MoAI-ADK
Date: 2025-12-01
Version: 1.0.0
"""

# ============================================================================
# SECTION 1: IMPORTS AND DEPENDENCIES
# ============================================================================

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import yaml
from jsonschema import Draft7Validator, ValidationError, validators


# ============================================================================
# SECTION 2: CONSTANTS AND CONFIGURATION
# ============================================================================

# Schema definitions for bot and device configurations
BOT_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "version", "actions"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "description": {"type": "string"},
        "actions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "target"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["tap", "swipe", "wait", "template_match", "ocr"]
                    },
                    "target": {
                        "oneOf": [
                            {
                                "type": "object",
                                "required": ["x", "y"],
                                "properties": {
                                    "x": {"type": "integer", "minimum": 0},
                                    "y": {"type": "integer", "minimum": 0}
                                }
                            },
                            {"type": "string"}
                        ]
                    },
                    "duration": {"type": "integer", "minimum": 0},
                    "threshold": {"type": "number", "minimum": 0, "maximum": 1},
                    "template": {"type": "string"}
                }
            }
        },
        "settings": {
            "type": "object",
            "properties": {
                "max_retries": {"type": "integer", "minimum": 0},
                "timeout": {"type": "integer", "minimum": 0},
                "screenshot_delay": {"type": "integer", "minimum": 0}
            }
        }
    }
}

DEVICE_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["device_id", "resolution"],
    "properties": {
        "device_id": {"type": "string", "minLength": 1},
        "resolution": {
            "type": "object",
            "required": ["width", "height"],
            "properties": {
                "width": {"type": "integer", "minimum": 1, "maximum": 4096},
                "height": {"type": "integer", "minimum": 1, "maximum": 4096}
            }
        },
        "orientation": {
            "type": "string",
            "enum": ["portrait", "landscape"]
        },
        "adb_path": {"type": "string"},
        "screenshot_method": {
            "type": "string",
            "enum": ["screencap", "minicap", "scrcpy"]
        },
        "input_method": {
            "type": "string",
            "enum": ["adb", "minitouch", "scrcpy"]
        }
    }
}

# Coordinate validation limits
MAX_COORDINATE_VALUE = 4096
MIN_COORDINATE_VALUE = 0


# ============================================================================
# SECTION 3: CUSTOM EXCEPTIONS
# ============================================================================

class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class SchemaNotFoundError(Exception):
    """Raised when requested schema is not found."""
    pass


# ============================================================================
# SECTION 4: CORE DATA STRUCTURES
# ============================================================================

class ValidationResult:
    """Container for validation results."""

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.fixes: List[Dict[str, Any]] = []
        self.is_valid: bool = True

    def add_error(self, path: str, message: str, value: Any = None):
        """Add validation error."""
        self.errors.append({
            "path": path,
            "message": message,
            "value": value,
            "severity": "error"
        })
        self.is_valid = False

    def add_warning(self, path: str, message: str, value: Any = None):
        """Add validation warning."""
        self.warnings.append({
            "path": path,
            "message": message,
            "value": value,
            "severity": "warning"
        })

    def add_fix(self, path: str, current: Any, suggested: Any, reason: str):
        """Add suggested fix."""
        self.fixes.append({
            "path": path,
            "current": current,
            "suggested": suggested,
            "reason": reason
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "fixes": self.fixes,
            "summary": {
                "total_errors": len(self.errors),
                "total_warnings": len(self.warnings),
                "total_fixes": len(self.fixes)
            }
        }


# ============================================================================
# SECTION 5: HELPER FUNCTIONS
# ============================================================================

def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from YAML or JSON file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary

    Raises:
        ConfigValidationError: If file cannot be loaded
    """
    if not config_path.exists():
        raise ConfigValidationError(f"Config file not found: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif config_path.suffix == '.json':
                return json.load(f)
            else:
                raise ConfigValidationError(
                    f"Unsupported file format: {config_path.suffix}"
                )
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"YAML parsing error: {e}")
    except json.JSONDecodeError as e:
        raise ConfigValidationError(f"JSON parsing error: {e}")


def get_schema(schema_name: str) -> Dict[str, Any]:
    """
    Get validation schema by name.

    Args:
        schema_name: Name of schema ('bot' or 'device')

    Returns:
        Schema dictionary

    Raises:
        SchemaNotFoundError: If schema not found
    """
    schemas = {
        'bot': BOT_CONFIG_SCHEMA,
        'device': DEVICE_CONFIG_SCHEMA
    }

    if schema_name not in schemas:
        raise SchemaNotFoundError(
            f"Schema '{schema_name}' not found. Available: {list(schemas.keys())}"
        )

    return schemas[schema_name]


def validate_coordinates(
    config: Dict[str, Any],
    result: ValidationResult,
    path_prefix: str = ""
) -> None:
    """
    Recursively validate coordinate values in configuration.

    Args:
        config: Configuration dictionary
        result: ValidationResult to update
        path_prefix: Current path in configuration
    """
    if isinstance(config, dict):
        # Check for coordinate fields
        if 'x' in config and isinstance(config['x'], int):
            if not (MIN_COORDINATE_VALUE <= config['x'] <= MAX_COORDINATE_VALUE):
                result.add_error(
                    f"{path_prefix}.x",
                    f"X coordinate out of range [{MIN_COORDINATE_VALUE}, {MAX_COORDINATE_VALUE}]",
                    config['x']
                )

        if 'y' in config and isinstance(config['y'], int):
            if not (MIN_COORDINATE_VALUE <= config['y'] <= MAX_COORDINATE_VALUE):
                result.add_error(
                    f"{path_prefix}.y",
                    f"Y coordinate out of range [{MIN_COORDINATE_VALUE}, {MAX_COORDINATE_VALUE}]",
                    config['y']
                )

        # Recurse into nested structures
        for key, value in config.items():
            new_prefix = f"{path_prefix}.{key}" if path_prefix else key
            validate_coordinates(value, result, new_prefix)

    elif isinstance(config, list):
        for i, item in enumerate(config):
            validate_coordinates(item, result, f"{path_prefix}[{i}]")


def validate_file_references(
    config: Dict[str, Any],
    config_dir: Path,
    result: ValidationResult,
    path_prefix: str = ""
) -> None:
    """
    Validate file path references in configuration.

    Args:
        config: Configuration dictionary
        config_dir: Directory containing config file
        result: ValidationResult to update
        path_prefix: Current path in configuration
    """
    if isinstance(config, dict):
        # Check template field
        if 'template' in config and isinstance(config['template'], str):
            template_path = config_dir / config['template']
            if not template_path.exists():
                result.add_warning(
                    f"{path_prefix}.template",
                    f"Template file not found: {config['template']}",
                    config['template']
                )

        # Check adb_path field
        if 'adb_path' in config and isinstance(config['adb_path'], str):
            adb_path = Path(config['adb_path'])
            if not adb_path.exists():
                result.add_warning(
                    f"{path_prefix}.adb_path",
                    f"ADB executable not found: {config['adb_path']}",
                    config['adb_path']
                )

        # Recurse
        for key, value in config.items():
            new_prefix = f"{path_prefix}.{key}" if path_prefix else key
            validate_file_references(value, config_dir, result, new_prefix)

    elif isinstance(config, list):
        for i, item in enumerate(config):
            validate_file_references(item, config_dir, result, f"{path_prefix}[{i}]")


# ============================================================================
# SECTION 6: CORE VALIDATION LOGIC
# ============================================================================

def validate_schema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """
    Validate configuration against JSON schema.

    Args:
        config: Configuration to validate
        schema: JSON schema

    Returns:
        List of validation error messages
    """
    validator = Draft7Validator(schema)
    errors = []

    for error in validator.iter_errors(config):
        path = '.'.join(str(p) for p in error.path) if error.path else 'root'
        errors.append(f"{path}: {error.message}")

    return errors


def generate_fixes(
    config: Dict[str, Any],
    result: ValidationResult
) -> Dict[str, Any]:
    """
    Generate automatic fixes for common issues.

    Args:
        config: Original configuration
        result: ValidationResult with identified issues

    Returns:
        Fixed configuration dictionary
    """
    fixed_config = json.loads(json.dumps(config))  # Deep copy

    # Fix coordinate ranges
    def fix_coords(obj, path=""):
        if isinstance(obj, dict):
            if 'x' in obj and isinstance(obj['x'], int):
                if obj['x'] < MIN_COORDINATE_VALUE:
                    result.add_fix(f"{path}.x", obj['x'], MIN_COORDINATE_VALUE, "Below minimum")
                    obj['x'] = MIN_COORDINATE_VALUE
                elif obj['x'] > MAX_COORDINATE_VALUE:
                    result.add_fix(f"{path}.x", obj['x'], MAX_COORDINATE_VALUE, "Above maximum")
                    obj['x'] = MAX_COORDINATE_VALUE

            if 'y' in obj and isinstance(obj['y'], int):
                if obj['y'] < MIN_COORDINATE_VALUE:
                    result.add_fix(f"{path}.y", obj['y'], MIN_COORDINATE_VALUE, "Below minimum")
                    obj['y'] = MIN_COORDINATE_VALUE
                elif obj['y'] > MAX_COORDINATE_VALUE:
                    result.add_fix(f"{path}.y", obj['y'], MAX_COORDINATE_VALUE, "Above maximum")
                    obj['y'] = MAX_COORDINATE_VALUE

            for key, value in obj.items():
                fix_coords(value, f"{path}.{key}" if path else key)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                fix_coords(item, f"{path}[{i}]")

    fix_coords(fixed_config)
    return fixed_config


def validate_config_file(
    config_path: Path,
    schema_name: str,
    strict_mode: bool = False
) -> ValidationResult:
    """
    Validate configuration file completely.

    Args:
        config_path: Path to config file
        schema_name: Schema to validate against
        strict_mode: Treat warnings as errors

    Returns:
        ValidationResult object
    """
    result = ValidationResult()

    try:
        # Load configuration
        config = load_config(config_path)

        # Get schema
        schema = get_schema(schema_name)

        # Schema validation
        schema_errors = validate_schema(config, schema)
        for error in schema_errors:
            result.add_error("schema", error)

        # Coordinate validation
        validate_coordinates(config, result)

        # File reference validation
        config_dir = config_path.parent
        validate_file_references(config, config_dir, result)

        # Strict mode: warnings become errors
        if strict_mode and result.warnings:
            result.is_valid = False

    except (ConfigValidationError, SchemaNotFoundError) as e:
        result.add_error("file", str(e))

    return result


# ============================================================================
# SECTION 7: CLI INTERFACE
# ============================================================================

@click.command()
@click.option(
    '--config-file',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to configuration file (YAML/JSON)'
)
@click.option(
    '--schema',
    type=click.Choice(['bot', 'device'], case_sensitive=False),
    default='bot',
    help='Schema type to validate against'
)
@click.option(
    '--strict',
    is_flag=True,
    help='Treat warnings as errors'
)
@click.option(
    '--json',
    'json_output',
    is_flag=True,
    help='Output results as JSON'
)
@click.option(
    '--fix',
    is_flag=True,
    help='Generate and apply automatic fixes'
)
def main(
    config_file: Path,
    schema: str,
    strict: bool,
    json_output: bool,
    fix: bool
):
    """
    Validate ADB bot/device configuration files.

    Checks schema compliance, coordinate ranges, and file references.
    """
    try:
        # Validate configuration
        result = validate_config_file(config_file, schema, strict)

        # Generate fixes if requested
        if fix and not result.is_valid:
            config = load_config(config_file)
            fixed_config = generate_fixes(config, result)

            # Save fixed configuration
            fixed_path = config_file.with_stem(f"{config_file.stem}_fixed")
            with open(fixed_path, 'w', encoding='utf-8') as f:
                if config_file.suffix in ['.yaml', '.yml']:
                    yaml.safe_dump(fixed_config, f, default_flow_style=False)
                else:
                    json.dump(fixed_config, f, indent=2)

            result.add_warning("fix", f"Fixed configuration saved to: {fixed_path}")

        # Output results
        if json_output:
            click.echo(json.dumps(result.to_dict(), indent=2))
        else:
            # Human-readable output
            click.echo(f"\n{'='*60}")
            click.echo(f"Configuration Validation: {config_file.name}")
            click.echo(f"{'='*60}\n")

            click.echo(f"Status: {'✅ VALID' if result.is_valid else '❌ INVALID'}")
            click.echo(f"Schema: {schema}")
            click.echo(f"Strict Mode: {'Yes' if strict else 'No'}\n")

            if result.errors:
                click.echo(f"Errors ({len(result.errors)}):")
                for error in result.errors:
                    click.echo(f"  ❌ [{error['path']}] {error['message']}")
                    if error.get('value') is not None:
                        click.echo(f"     Value: {error['value']}")
                click.echo()

            if result.warnings:
                click.echo(f"Warnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    click.echo(f"  ⚠️  [{warning['path']}] {warning['message']}")
                    if warning.get('value') is not None:
                        click.echo(f"     Value: {warning['value']}")
                click.echo()

            if result.fixes:
                click.echo(f"Suggested Fixes ({len(result.fixes)}):")
                for fix_item in result.fixes:
                    click.echo(f"  🔧 [{fix_item['path']}]")
                    click.echo(f"     Current: {fix_item['current']}")
                    click.echo(f"     Suggested: {fix_item['suggested']}")
                    click.echo(f"     Reason: {fix_item['reason']}")
                click.echo()

        # Exit code
        sys.exit(0 if result.is_valid else 1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ============================================================================
# SECTION 8: SCRIPT ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    main()


# ============================================================================
# SECTION 9: USAGE EXAMPLES AND DOCUMENTATION
# ============================================================================

"""
Usage Examples:
--------------

1. Validate bot configuration:
   $ python adb_config_validator.py --config-file bot_config.yaml

2. Validate device configuration with strict mode:
   $ python adb_config_validator.py --config-file device.json --schema device --strict

3. Generate fixes for invalid configuration:
   $ python adb_config_validator.py --config-file config.yaml --fix

4. JSON output for CI/CD integration:
   $ python adb_config_validator.py --config-file config.json --json

5. Comprehensive validation:
   $ python adb_config_validator.py --config-file bot.yaml --strict --fix --json


Sample Bot Configuration (bot_config.yaml):
------------------------------------------
name: "Daily Tasks Bot"
version: "1.0.0"
description: "Automated daily task completion"
actions:
  - type: tap
    target:
      x: 500
      y: 800
    duration: 100
  - type: template_match
    target: "button_ok.png"
    template: "templates/button_ok.png"
    threshold: 0.8
  - type: wait
    duration: 2000
settings:
  max_retries: 3
  timeout: 30000
  screenshot_delay: 500


Sample Device Configuration (device.json):
-----------------------------------------
{
  "device_id": "emulator-5554",
  "resolution": {
    "width": 1080,
    "height": 1920
  },
  "orientation": "portrait",
  "adb_path": "/usr/bin/adb",
  "screenshot_method": "screencap",
  "input_method": "adb"
}


Validation Output:
-----------------
============================================================
Configuration Validation: bot_config.yaml
============================================================

Status: ✅ VALID
Schema: bot
Strict Mode: No

Warnings (1):
  ⚠️  [actions[1].template] Template file not found: templates/button_ok.png
     Value: templates/button_ok.png


Exit Codes:
----------
0: Configuration is valid
1: Validation errors found


Integration with CI/CD:
----------------------
#!/bin/bash
# .github/workflows/validate-configs.sh

for config in configs/*.yaml; do
    python adb_config_validator.py --config-file "$config" --strict --json
    if [ $? -ne 0 ]; then
        echo "Validation failed for $config"
        exit 1
    fi
done
"""
