"""
Zero-context path detection and project setup utilities.

This module provides functions to detect the project root from any execution
directory by searching for common markers (.git, pyproject.toml, .moai) and
setting up the adb_auto_player package path for imports.
"""

import sys
from pathlib import Path
from typing import Optional


def detect_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Purpose:
        Detect the project root directory by searching for common markers
        in the directory hierarchy. Enables zero-context execution from
        any working directory.

    Parameters:
        start_path: Starting directory for root search. If None, uses
                    current working directory. Type: Optional[Path]

    Returns:
        Path object representing the project root directory. Type: Path

    Examples:
        >>> from pathlib import Path
        >>> root = detect_project_root()
        >>> root.name
        'AdbAutoPlayer'
        >>> root.is_dir()
        True

    Raises:
        No exceptions. Returns cwd if no markers found (fallback behavior).

    Notes:
        - Searches for markers in order: .git, pyproject.toml, .moai
        - Walks up directory tree from start_path to filesystem root
        - Returns current working directory if no markers found
        - Enables scripts to run from any directory (e.g., scripts/,
          .claude/, src-tauri/src-python/)

    Related:
        - setup_adbautoplayer_path(): Uses this to add package to sys.path
        - Path.parent: Used to traverse directory hierarchy
        - Path.cwd(): Used as fallback and default start_path

    Context:
        Used by all 29 migrated scripts to establish execution context.
        Essential for scripts that may be run from different directories
        or shell sessions without explicit path setup.

    Implementation:
        1. Determine start_path (use cwd if not provided)
        2. Define markers list: [".git", "pyproject.toml", ".moai"]
        3. Walk up directory tree (current → parent → ... → root)
        4. Check if any marker exists in current directory
        5. Return first directory containing marker
        6. Fallback to cwd if no markers found
    """
    if start_path is None:
        start_path = Path.cwd()

    # Ensure we have an absolute path
    start_path = start_path.resolve()

    # Markers to search for (in order of preference)
    markers = [".git", "pyproject.toml", ".moai"]

    # Walk up the directory tree
    current = start_path
    while True:
        # Check if any marker exists in current directory
        for marker in markers:
            if (current / marker).exists():
                return current

        # Move to parent directory
        parent = current.parent
        if parent == current:
            # Reached filesystem root, return fallback
            return Path.cwd()

        current = parent


def setup_adbautoplayer_path() -> None:
    """
    Purpose:
        Add the adb_auto_player package to Python sys.path for proper
        module importing. Enables scripts to import adb_auto_player
        without explicit PYTHONPATH setup.

    Parameters:
        None

    Returns:
        None. Modifies sys.path in-place.

    Examples:
        >>> import sys
        >>> setup_adbautoplayer_path()
        >>> from adb_auto_player import ... # Now works
        >>> "src-tauri/src-python" in sys.path[0]
        True

    Raises:
        No exceptions. Silently skips if package path already in sys.path.

    Notes:
        - Adds {PROJECT_ROOT}/src-tauri/src-python to sys.path
        - Placed at index 0 for highest import priority
        - Idempotent: safe to call multiple times (checks before adding)
        - Required for all 29 scripts that import adb_auto_player
        - Should be called early in script execution (before imports)

    Related:
        - detect_project_root(): Used to find project root
        - sys.path: Python's module search path (modified by this function)
        - importlib: Module used for dynamic imports

    Context:
        Essential for script execution from any directory. Without this,
        scripts fail with ModuleNotFoundError when adb_auto_player cannot
        be found in sys.path. Solves cross-directory execution problem.

    Implementation:
        1. Call detect_project_root() to find project root
        2. Build path: {PROJECT_ROOT}/src-tauri/src-python
        3. Convert to string for sys.path
        4. Check if already in sys.path (prevent duplicates)
        5. Insert at index 0 if not present
    """
    project_root = detect_project_root()
    adbautoplayer_path = project_root / "adbautoplayer" / "src-tauri" / "src-python"
    adbautoplayer_path_str = str(adbautoplayer_path)

    # Add to sys.path if not already present (idempotent)
    if adbautoplayer_path_str not in sys.path:
        sys.path.insert(0, adbautoplayer_path_str)
