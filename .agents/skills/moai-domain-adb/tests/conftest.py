"""
Pytest configuration and fixtures for ADB domain skill tests.

This file provides shared test configuration, markers, and fixtures
for use across all test modules.
"""

import sys
from pathlib import Path


# Add common utilities to path for imports
COMMON_DIR = Path(__file__).resolve().parent.parent / "scripts" / "common"
sys.path.insert(0, str(COMMON_DIR))


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_adb: marks tests requiring ADB (deselect with '-m \"not requires_adb\"')"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection."""
    # Add markers based on test names
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker("integration")


# Shared test fixtures
import pytest


@pytest.fixture
def mock_adb_client():
    """Fixture providing a mock ADB client."""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.device_list.return_value = []
    return client


@pytest.fixture
def mock_device():
    """Fixture providing a mock ADB device."""
    from unittest.mock import MagicMock
    device = MagicMock()
    device.serial = "test_device"
    device.is_alive.return_value = True
    return device


@pytest.fixture
def temp_project_root(tmp_path):
    """Fixture providing a temporary project root with markers."""
    # Create marker file
    (tmp_path / "pyproject.toml").touch()
    return tmp_path
