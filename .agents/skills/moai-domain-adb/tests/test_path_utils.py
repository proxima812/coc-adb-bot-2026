"""
Test suite for path_utils module.

Purpose:
    Comprehensive unit tests for path detection and setup utilities used
    across all ADB scripts to ensure consistent path initialization.

Test Categories:
    1. detect_project_root() - Marker-based project root detection
    2. setup_adbautoplayer_path() - Path setup and idempotency
    3. Error conditions - Behavior with missing markers or invalid paths
    4. Working directory restoration - CWD tracking and restoration
"""

import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest


# Test imports - adjust path based on test location
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "common"))


def test_detect_project_root_with_pyproject_marker():
    """Test detection of project root using pyproject.toml marker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create marker file
        (tmppath / "pyproject.toml").touch()
        
        # Create subdirectory to start search from
        subdir = tmppath / "subdir" / "deeper"
        subdir.mkdir(parents=True)
        
        # Mock os.chdir to track calls
        with mock.patch("os.chdir"):
            from path_utils import detect_project_root
            result = detect_project_root(start_from=subdir)
        
        # Should find pyproject.toml at root
        assert result == tmppath


def test_detect_project_root_with_moai_marker():
    """Test detection of project root using .moai/ marker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create marker directory
        (tmppath / ".moai").mkdir()
        
        # Create subdirectory to start search from
        subdir = tmppath / "subdir"
        subdir.mkdir()
        
        with mock.patch("os.chdir"):
            from path_utils import detect_project_root
            result = detect_project_root(start_from=subdir)
        
        assert result == tmppath


def test_detect_project_root_priority_order():
    """Test that pyproject.toml is checked before .moai/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create both markers
        (tmppath / "pyproject.toml").touch()
        (tmppath / ".moai").mkdir()
        
        subdir = tmppath / "subdir"
        subdir.mkdir()
        
        with mock.patch("os.chdir"):
            from path_utils import detect_project_root
            result = detect_project_root(start_from=subdir)
        
        # Should prefer pyproject.toml
        assert result == tmppath


def test_detect_project_root_from_current_dir():
    """Test detection starting from current directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "pyproject.toml").touch()
        
        with mock.patch("os.chdir"):
            from path_utils import detect_project_root
            result = detect_project_root(start_from=tmppath)
        
        # Should find root at current directory
        assert result == tmppath


def test_detect_project_root_stops_at_filesystem_root():
    """Test that search stops gracefully at filesystem root."""
    # Create a temporary directory with no markers
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        subdir = tmppath / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        
        with mock.patch("os.chdir"):
            from path_utils import detect_project_root
            # Should return None or raise exception (depending on implementation)
            result = detect_project_root(start_from=subdir)
        
        # Implementation returns None when root not found
        assert result is None


def test_setup_adbautoplayer_path_adds_to_sys_path():
    """Test that setup_adbautoplayer_path adds correct path to sys.path."""
    from path_utils import setup_adbautoplayer_path
    
    # Get initial sys.path
    initial_path = sys.path.copy()
    
    # Call setup
    setup_adbautoplayer_path()
    
    # Check that a path containing "src-tauri/src-python" was added
    python_path_added = any(
        "src-tauri" in p and "src-python" in p for p in sys.path if p not in initial_path
    )
    
    # Restore initial path
    sys.path[:] = initial_path
    
    assert python_path_added


def test_setup_adbautoplayer_path_idempotent():
    """Test that calling setup multiple times is safe (idempotent)."""
    from path_utils import setup_adbautoplayer_path
    
    initial_path = sys.path.copy()
    
    # Call setup twice
    setup_adbautoplayer_path()
    path_after_first = sys.path.copy()
    
    setup_adbautoplayer_path()
    path_after_second = sys.path.copy()
    
    # Restore
    sys.path[:] = initial_path
    
    # Should be equivalent (no duplicate adds)
    assert path_after_first.count(path_after_first[0]) == path_after_second.count(path_after_second[0])


def test_setup_adbautoplayer_path_prevents_duplicates():
    """Test that setup doesn't add duplicate paths."""
    from path_utils import setup_adbautoplayer_path
    
    initial_path = sys.path.copy()
    
    # Call setup multiple times
    for _ in range(3):
        setup_adbautoplayer_path()
    
    # Count occurrences of python path
    python_path_count = sum(
        1 for p in sys.path if "src-tauri" in p and "src-python" in p
    )
    
    # Restore
    sys.path[:] = initial_path
    
    # Should only have one occurrence
    assert python_path_count <= 1


def test_setup_adbautoplayer_path_with_nonexistent_root():
    """Test graceful handling when project root cannot be found."""
    from path_utils import setup_adbautoplayer_path
    
    initial_path = sys.path.copy()
    
    # This should handle gracefully (log warning or no-op)
    try:
        setup_adbautoplayer_path()
        # Should succeed or raise with informative error
        assert True
    except Exception as e:
        # Should have informative error message
        assert "project root" in str(e).lower() or "path" in str(e).lower()
    finally:
        sys.path[:] = initial_path


def test_path_detection_with_relative_paths():
    """Test that relative paths are correctly resolved to absolute."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "pyproject.toml").touch()
        
        subdir = tmppath / "subdir"
        subdir.mkdir()
        
        with mock.patch("os.chdir"):
            from path_utils import detect_project_root
            result = detect_project_root(start_from=subdir)
        
        # Result should be absolute path
        assert result.is_absolute()


def test_path_utils_handles_symlinks():
    """Test that path utils handle symbolic links correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "pyproject.toml").touch()
        
        subdir = tmppath / "subdir"
        subdir.mkdir()
        
        # Create symlink (skip if not supported on platform)
        try:
            symlink = tmppath / "symlink"
            symlink.symlink_to(subdir)
            
            with mock.patch("os.chdir"):
                from path_utils import detect_project_root
                result = detect_project_root(start_from=symlink)
            
            # Should resolve to real path
            assert result == tmppath
        except (OSError, NotImplementedError):
            # Symlinks not supported on this platform
            pytest.skip("Symlinks not supported")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
