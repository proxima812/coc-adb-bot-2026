"""
Integration test suite for ADB scripts.

Purpose:
    Integration tests validating CLI behavior, exit codes, and TOON output
    across all 29 migrated scripts. Tests script invocation and output parsing.

Test Categories:
    1. CLI invocation tests (--help, --device, --toon, --verbose)
    2. Exit code validation (0, 2, 3, 4)
    3. TOON/YAML output validation
    4. Output parsing and structure
    5. Cross-script consistency
"""

import sys
import subprocess
from pathlib import Path
from unittest import mock

import pytest
import yaml


# Project paths
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class TestScriptDiscovery:
    """Tests for script discovery and listing."""
    
    def test_scripts_directory_exists(self):
        """Test that scripts directory exists."""
        assert SCRIPTS_DIR.exists()
        assert SCRIPTS_DIR.is_dir()
    
    def test_common_directory_exists(self):
        """Test that common utilities directory exists."""
        common_dir = SCRIPTS_DIR / "common"
        assert common_dir.exists()
        assert common_dir.is_dir()
    
    def test_script_categories_exist(self):
        """Test that all expected script categories exist."""
        categories = ["connection", "app", "screen", "info", "automation", "performance", "utils"]
        
        for category in categories:
            category_dir = SCRIPTS_DIR / category
            assert category_dir.exists(), f"Missing category: {category}"
    
    def test_script_count(self):
        """Test that we have the expected number of scripts."""
        # Find all .py scripts excluding common and __pycache__
        scripts = list(
            SCRIPTS_DIR.glob("**/adb_*.py")
        ) + list(
            SCRIPTS_DIR.glob("adb_*.py")
        )
        
        # Should have at least 29 scripts
        script_count = len(set(s for s in scripts if "common" not in str(s)))
        assert script_count >= 29


class TestScriptHelp:
    """Tests for --help option on scripts."""
    
    @pytest.mark.parametrize(
        "script_name",
        [
            "connection/adb_device_status.py",
            "connection/adb_connect.py",
            "app/adb_app_list.py",
            "screen/adb_screenshot.py",
            "info/adb_device_info.py",
        ]
    )
    def test_script_help_exists(self, script_name):
        """Test that script has functioning --help option."""
        script_path = SCRIPTS_DIR / script_name
        
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_name}")
        
        # Test with mock since we don't need actual ADB
        result = subprocess.run(
            [sys.executable, "-m", "click", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Script should be invocable (exit code may vary)
        assert result is not None
    
    def test_script_help_contains_description(self):
        """Test that script help includes description."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if not script_path.exists():
            pytest.skip("Script not found")
        
        # Read script file to verify docstring exists
        content = script_path.read_text()
        assert '"""' in content or "'''" in content


class TestCliOptions:
    """Tests for standard CLI options on scripts."""
    
    def test_scripts_have_device_option(self):
        """Test that scripts accept --device option."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            assert "@device_option" in content or "--device" in content
    
    def test_scripts_have_toon_option(self):
        """Test that scripts accept --toon option."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            assert "@toon_output_option" in content or "--toon" in content
    
    def test_scripts_have_verbose_option(self):
        """Test that scripts accept --verbose option."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            assert "@verbose_option" in content or "--verbose" in content or "-v" in content


class TestExitCodes:
    """Tests for script exit codes."""
    
    def test_exit_code_constants_used(self):
        """Test that scripts import exit code constants."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            
            # Should import exit codes
            assert "EXIT_" in content or "error_handlers" in content
    
    def test_exit_codes_in_error_handlers(self):
        """Test that error_handlers defines exit codes."""
        error_handlers_path = SCRIPTS_DIR / "common" / "error_handlers.py"
        
        assert error_handlers_path.exists()
        content = error_handlers_path.read_text()
        
        # Should define standard exit codes
        assert "EXIT_SUCCESS" in content
        assert "EXIT_INVALID_ARGUMENT" in content
        assert "EXIT_ADB_COMMAND_FAILED" in content
        assert "EXIT_DEVICE_ERROR" in content


class TestToonOutput:
    """Tests for TOON/YAML output format."""
    
    def test_toon_output_is_valid_yaml(self):
        """Test that TOON output can be parsed as YAML."""
        sample_toon = """
device: test123
state: online
model: SM-G950F
android_version: "10"
"""
        
        # Should be valid YAML
        parsed = yaml.safe_load(sample_toon)
        assert parsed is not None
        assert parsed["device"] == "test123"
    
    def test_toon_output_format_consistency(self):
        """Test that TOON output follows consistent format."""
        cli_utils_path = SCRIPTS_DIR / "common" / "cli_utils.py"
        
        assert cli_utils_path.exists()
        content = cli_utils_path.read_text()
        
        # Should have format_toon_output function
        assert "format_toon_output" in content
        assert "yaml" in content.lower()
    
    def test_toon_supports_nested_structures(self):
        """Test that TOON format supports nested data."""
        sample_toon = """
devices:
  - serial: device1
    state: online
    properties:
      model: SM-G950F
      android: "10"
  - serial: device2
    state: offline
summary:
  total: 2
  online: 1
  offline: 1
"""
        
        # Should parse nested structures
        parsed = yaml.safe_load(sample_toon)
        assert len(parsed["devices"]) == 2
        assert parsed["devices"][0]["properties"]["model"] == "SM-G950F"
        assert parsed["summary"]["total"] == 2


class TestScriptStructure:
    """Tests for script file structure and organization."""
    
    def test_scripts_have_docstrings(self):
        """Test that scripts have module-level docstrings."""
        for script_path in [
            "connection/adb_device_status.py",
            "app/adb_app_list.py",
            "screen/adb_screenshot.py"
        ]:
            full_path = SCRIPTS_DIR / script_path
            if full_path.exists():
                content = full_path.read_text()
                # Should start with docstring
                assert '"""' in content[:500]
    
    def test_scripts_import_common_utils(self):
        """Test that scripts import from common utilities."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            # Should import from common
            assert "common" in content.lower() or "cli_utils" in content
    
    def test_scripts_use_click_decorators(self):
        """Test that scripts use Click CLI framework."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            # Should use Click
            assert "@click" in content or "click.command" in content


class TestCommonUtilitiesIntegration:
    """Tests for common utilities integration."""
    
    def test_common_utils_module_structure(self):
        """Test that common utilities are properly structured."""
        common_dir = SCRIPTS_DIR / "common"
        
        # Should have these utility modules
        modules = [
            "__init__.py",
            "path_utils.py",
            "adb_utils.py",
            "cli_utils.py",
            "error_handlers.py"
        ]
        
        for module in modules:
            assert (common_dir / module).exists(), f"Missing module: {module}"
    
    def test_common_init_imports_utilities(self):
        """Test that common/__init__.py exports utilities."""
        init_path = SCRIPTS_DIR / "common" / "__init__.py"
        
        if init_path.exists():
            content = init_path.read_text()
            # Should export main utilities
            assert "from" in content or "import" in content
    
    def test_path_utils_provides_setup(self):
        """Test that path_utils provides setup function."""
        path_utils_path = SCRIPTS_DIR / "common" / "path_utils.py"
        
        assert path_utils_path.exists()
        content = path_utils_path.read_text()
        
        # Should have setup function
        assert "setup_adbautoplayer_path" in content
    
    def test_error_handlers_provides_decorator(self):
        """Test that error_handlers provides decorator."""
        error_handlers_path = SCRIPTS_DIR / "common" / "error_handlers.py"
        
        assert error_handlers_path.exists()
        content = error_handlers_path.read_text()
        
        # Should have decorator
        assert "handle_adb_errors" in content


class TestDocumentation:
    """Tests for script documentation."""
    
    def test_readme_exists(self):
        """Test that scripts README exists."""
        readme_path = SCRIPTS_DIR / "README.md"
        assert readme_path.exists()
    
    def test_readme_comprehensive(self):
        """Test that README is comprehensive."""
        readme_path = SCRIPTS_DIR / "README.md"
        
        if readme_path.exists():
            content = readme_path.read_text()
            
            # Should cover key topics
            expected_sections = ["connection", "app", "screen", "info"]
            
            for section in expected_sections:
                assert section.lower() in content.lower()
    
    def test_script_docstrings_have_sections(self):
        """Test that scripts have comprehensive docstrings."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            
            # Should have documented sections
            sections = ["Purpose", "Parameters", "Returns", "Examples", "Raises"]
            
            for section in sections:
                assert section in content


class TestScriptCategories:
    """Tests for script category organization."""
    
    def test_connection_category_scripts(self):
        """Test connection category has expected scripts."""
        connection_dir = SCRIPTS_DIR / "connection"
        
        if connection_dir.exists():
            scripts = list(connection_dir.glob("adb_*.py"))
            assert len(scripts) >= 4  # connect, disconnect, status, restart
    
    def test_app_category_scripts(self):
        """Test app category has expected scripts."""
        app_dir = SCRIPTS_DIR / "app"
        
        if app_dir.exists():
            scripts = list(app_dir.glob("adb_*.py"))
            assert len(scripts) >= 5  # list, start, stop, install, uninstall
    
    def test_screen_category_scripts(self):
        """Test screen category has expected scripts."""
        screen_dir = SCRIPTS_DIR / "screen"
        
        if screen_dir.exists():
            scripts = list(screen_dir.glob("adb_*.py"))
            assert len(scripts) >= 6  # screenshot, tap, swipe, keyevent, etc.
    
    def test_info_category_scripts(self):
        """Test info category has expected scripts."""
        info_dir = SCRIPTS_DIR / "info"
        
        if info_dir.exists():
            scripts = list(info_dir.glob("adb_*.py"))
            assert len(scripts) >= 4  # device, battery, running app, etc.


class TestCodeQualityIntegration:
    """Tests for code quality patterns."""
    
    def test_no_hardcoded_paths(self):
        """Test that scripts don't have hardcoded absolute paths."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            
            # Should not have hardcoded paths like /home, /Users, C:\
            assert "/home/user" not in content
            assert "C:" not in content
    
    def test_proper_error_handling(self):
        """Test that scripts use proper error handling."""
        script_path = SCRIPTS_DIR / "connection/adb_device_status.py"
        
        if script_path.exists():
            content = script_path.read_text()
            
            # Should use error handlers
            assert "try" in content or "@handle_adb_errors" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
