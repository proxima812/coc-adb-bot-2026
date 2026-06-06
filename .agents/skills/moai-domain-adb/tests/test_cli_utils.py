"""
Test suite for cli_utils module.

Purpose:
    Tests for Click CLI decorators and Rich output formatting utilities.
    Ensures consistent CLI behavior across all 29 migrated scripts.

Test Categories:
    1. Click decorators (device, toon, verbose options)
    2. Rich console output formatting
    3. TOON/YAML output generation
    4. Printer functions (success, error, info)
    5. Decorator composition and interaction
"""

import sys
from pathlib import Path
from unittest import mock
from io import StringIO

import pytest
import click
from click.testing import CliRunner
import yaml


# Test imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "common"))


class TestDeviceOption:
    """Tests for device_option decorator."""
    
    def test_device_option_adds_device_parameter(self):
        """Test that device_option adds --device parameter."""
        from cli_utils import device_option
        
        @click.command()
        @device_option
        def test_cmd(device):
            click.echo(f"Device: {device}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, ["--device", "test123"])
        
        assert result.exit_code == 0
        assert "Device: test123" in result.output
    
    def test_device_option_short_form(self):
        """Test that device_option supports -d shorthand."""
        from cli_utils import device_option
        
        @click.command()
        @device_option
        def test_cmd(device):
            click.echo(f"Device: {device}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, ["-d", "dev456"])
        
        assert result.exit_code == 0
        assert "Device: dev456" in result.output
    
    def test_device_option_optional(self):
        """Test that device option is optional."""
        from cli_utils import device_option
        
        @click.command()
        @device_option
        def test_cmd(device):
            click.echo(f"Device: {device}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, [])
        
        assert result.exit_code == 0


class TestToonOption:
    """Tests for toon_output_option decorator."""
    
    def test_toon_option_adds_flag(self):
        """Test that toon_output_option adds --toon flag."""
        from cli_utils import toon_output_option
        
        @click.command()
        @toon_output_option
        def test_cmd(toon):
            click.echo(f"TOON: {toon}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, ["--toon"])
        
        assert result.exit_code == 0
        assert "TOON: True" in result.output
    
    def test_toon_option_default_false(self):
        """Test that --toon defaults to False."""
        from cli_utils import toon_output_option
        
        @click.command()
        @toon_output_option
        def test_cmd(toon):
            click.echo(f"TOON: {toon}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, [])
        
        assert result.exit_code == 0
        assert "TOON: False" in result.output


class TestVerboseOption:
    """Tests for verbose_option decorator."""
    
    def test_verbose_option_adds_flag(self):
        """Test that verbose_option adds --verbose flag."""
        from cli_utils import verbose_option
        
        @click.command()
        @verbose_option
        def test_cmd(verbose):
            click.echo(f"Verbose: {verbose}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, ["--verbose"])
        
        assert result.exit_code == 0
        assert "Verbose: True" in result.output
    
    def test_verbose_option_short_form(self):
        """Test that verbose_option supports -v shorthand."""
        from cli_utils import verbose_option
        
        @click.command()
        @verbose_option
        def test_cmd(verbose):
            click.echo(f"Verbose: {verbose}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, ["-v"])
        
        assert result.exit_code == 0
        assert "Verbose: True" in result.output
    
    def test_verbose_option_default_false(self):
        """Test that --verbose defaults to False."""
        from cli_utils import verbose_option
        
        @click.command()
        @verbose_option
        def test_cmd(verbose):
            click.echo(f"Verbose: {verbose}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, [])
        
        assert result.exit_code == 0
        assert "Verbose: False" in result.output


class TestToonOutputFormatting:
    """Tests for TOON/YAML output formatting."""
    
    def test_format_toon_output_dict(self):
        """Test formatting dictionary as TOON/YAML."""
        from cli_utils import format_toon_output
        
        data = {
            "status": "success",
            "device": "test123",
            "count": 5
        }
        
        output = format_toon_output(data)
        
        # Should be valid YAML
        parsed = yaml.safe_load(output)
        assert parsed["status"] == "success"
        assert parsed["device"] == "test123"
        assert parsed["count"] == 5
    
    def test_format_toon_output_list(self):
        """Test formatting list as TOON/YAML."""
        from cli_utils import format_toon_output
        
        data = [
            {"name": "item1", "value": 10},
            {"name": "item2", "value": 20}
        ]
        
        output = format_toon_output(data)
        
        # Should be valid YAML
        parsed = yaml.safe_load(output)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "item1"
    
    def test_format_toon_output_nested(self):
        """Test formatting nested structures as TOON/YAML."""
        from cli_utils import format_toon_output
        
        data = {
            "metadata": {
                "version": "1.0",
                "author": "test"
            },
            "items": [
                {"id": 1, "name": "item1"},
                {"id": 2, "name": "item2"}
            ]
        }
        
        output = format_toon_output(data)
        
        # Should be valid YAML
        parsed = yaml.safe_load(output)
        assert parsed["metadata"]["version"] == "1.0"
        assert len(parsed["items"]) == 2
    
    def test_format_toon_output_is_valid_yaml(self):
        """Test that TOON output is always valid YAML."""
        from cli_utils import format_toon_output
        
        test_cases = [
            {"simple": "data"},
            {"nested": {"deep": {"structure": "value"}}},
            {"list": [1, 2, 3]},
            {"mixed": {"items": [{"a": 1}, {"b": 2}]}}
        ]
        
        for test_data in test_cases:
            output = format_toon_output(test_data)
            # Should not raise exception
            parsed = yaml.safe_load(output)
            assert parsed is not None


class TestPrinterFunctions:
    """Tests for Rich console printer functions."""
    
    def test_print_success_creates_output(self):
        """Test that print_success produces output."""
        from cli_utils import print_success
        
        with mock.patch("cli_utils.console.print") as mock_print:
            print_success("Operation successful")
            mock_print.assert_called_once()
    
    def test_print_error_creates_output(self):
        """Test that print_error produces output."""
        from cli_utils import print_error
        
        with mock.patch("cli_utils.console.print") as mock_print:
            print_error("Operation failed")
            mock_print.assert_called_once()
    
    def test_print_info_creates_output(self):
        """Test that print_info produces output."""
        from cli_utils import print_info
        
        with mock.patch("cli_utils.console.print") as mock_print:
            print_info("Information message")
            mock_print.assert_called_once()
    
    def test_print_success_with_formatting(self):
        """Test that print_success supports formatting."""
        from cli_utils import print_success
        
        # Should not raise exception with formatted strings
        print_success("Status: [bold]COMPLETE[/bold]")


class TestDecoratorComposition:
    """Tests for combining multiple decorators."""
    
    def test_multiple_decorators_work_together(self):
        """Test that multiple CLI decorators work together."""
        from cli_utils import device_option, toon_output_option, verbose_option
        
        @click.command()
        @device_option
        @toon_output_option
        @verbose_option
        def test_cmd(device, toon, verbose):
            click.echo(f"Device: {device}, TOON: {toon}, Verbose: {verbose}")
        
        runner = CliRunner()
        result = runner.invoke(test_cmd, ["-d", "dev1", "--toon", "-v"])
        
        assert result.exit_code == 0
        assert "Device: dev1" in result.output
        assert "TOON: True" in result.output
        assert "Verbose: True" in result.output
    
    def test_decorators_preserve_function(self):
        """Test that decorators preserve underlying function."""
        from cli_utils import device_option, toon_output_option, verbose_option
        
        @click.command()
        @device_option
        @toon_output_option
        @verbose_option
        def test_cmd(device, toon, verbose):
            return device, toon, verbose
        
        # Function should still have callable attributes
        assert callable(test_cmd)


class TestOutputFormatting:
    """Tests for various output formatting scenarios."""
    
    def test_format_toon_output_with_none_values(self):
        """Test TOON formatting with None values."""
        from cli_utils import format_toon_output
        
        data = {
            "field1": "value",
            "field2": None,
            "field3": "another"
        }
        
        output = format_toon_output(data)
        parsed = yaml.safe_load(output)
        
        assert parsed["field1"] == "value"
        assert parsed["field2"] is None
        assert parsed["field3"] == "another"
    
    def test_format_toon_output_with_special_chars(self):
        """Test TOON formatting with special characters."""
        from cli_utils import format_toon_output
        
        data = {
            "message": "Test with special chars: !@#$%",
            "path": "/home/user/test",
            "quoted": 'String with "quotes"'
        }
        
        output = format_toon_output(data)
        parsed = yaml.safe_load(output)
        
        assert "special chars" in parsed["message"]
        assert parsed["path"] == "/home/user/test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
