"""
Test suite for ADB domain skill.

This package contains comprehensive tests for all 29 migrated ADB scripts
and their supporting utilities. Tests are organized by module:

- test_path_utils.py: Path detection and project root setup
- test_adb_utils.py: ADB client operations and device management
- test_cli_utils.py: CLI decorators and Rich output formatting
- test_error_handlers.py: Exception classes and error handling
- test_scripts_integration.py: Integration tests across all scripts

Run all tests:
    pytest tests/ -v
    
Run with coverage:
    pytest tests/ --cov=scripts/common --cov-report=html
    
Run specific test file:
    pytest tests/test_path_utils.py -v
"""

__all__ = [
    "test_path_utils",
    "test_adb_utils",
    "test_cli_utils",
    "test_error_handlers",
    "test_scripts_integration",
]
