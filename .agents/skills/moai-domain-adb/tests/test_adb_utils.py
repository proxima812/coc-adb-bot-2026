"""
Test suite for adb_utils module.

Purpose:
    Unit tests for ADB utility functions used across all scripts.
    Tests device operations, client initialization, and output parsing.

Test Categories:
    1. ADB client initialization and configuration
    2. Device listing and selection
    3. Device connection verification
    4. Output parsing from ADB commands
    5. Error handling and timeouts
"""

import sys
from pathlib import Path
from unittest import mock

import pytest


# Test imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "common"))


class TestAdbClientHelper:
    """Tests for AdbClientHelper initialization."""
    
    def test_get_adb_client_initialization(self):
        """Test that ADB client initializes without errors."""
        from adb_utils import AdbClientHelper
        
        with mock.patch("adbutils.adb.AdbClient.__init__", return_value=None):
            helper = AdbClientHelper()
            assert helper is not None
    
    def test_get_adb_client_caches_instance(self):
        """Test that client instance is cached and reused."""
        from adb_utils import AdbClientHelper
        
        with mock.patch("adbutils.adb.AdbClient.__init__", return_value=None):
            helper1 = AdbClientHelper()
            helper2 = AdbClientHelper()
            
            # Should return same instance
            assert helper1 is helper2


class TestDeviceListing:
    """Tests for device listing and enumeration."""
    
    def test_list_connected_devices_returns_list(self):
        """Test that list_connected_devices returns a list."""
        from adb_utils import list_connected_devices
        
        mock_client = mock.MagicMock()
        mock_device = mock.MagicMock()
        mock_device.serial = "device123"
        mock_device.is_alive.return_value = True
        
        mock_client.device_list.return_value = [mock_device]
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            devices = list_connected_devices()
        
        assert isinstance(devices, list)
        assert len(devices) > 0
    
    def test_list_connected_devices_with_empty_result(self):
        """Test handling of case where no devices are connected."""
        from adb_utils import list_connected_devices
        
        mock_client = mock.MagicMock()
        mock_client.device_list.return_value = []
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            devices = list_connected_devices()
        
        assert isinstance(devices, list)
        assert len(devices) == 0
    
    def test_list_devices_parses_serial_correctly(self):
        """Test that device serial numbers are parsed correctly."""
        from adb_utils import list_connected_devices
        
        mock_client = mock.MagicMock()
        serials = ["device123", "127.0.0.1:5555", "emulator-5554"]
        
        mock_devices = []
        for serial in serials:
            device = mock.MagicMock()
            device.serial = serial
            device.is_alive.return_value = True
            mock_devices.append(device)
        
        mock_client.device_list.return_value = mock_devices
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            devices = list_connected_devices()
        
        device_serials = [d.get("serial") for d in devices]
        assert all(s in serials for s in device_serials)


class TestDeviceSelection:
    """Tests for device selection and filtering."""
    
    def test_get_default_device_with_explicit_serial(self):
        """Test device selection with explicit serial number."""
        from adb_utils import get_default_device
        
        device_serial = "127.0.0.1:5555"
        
        mock_client = mock.MagicMock()
        mock_device = mock.MagicMock()
        mock_device.serial = device_serial
        
        mock_client.device.return_value = mock_device
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            device = get_default_device(device_serial)
        
        assert device is not None
        assert device.serial == device_serial
    
    def test_get_default_device_auto_select_single(self):
        """Test auto-selection when only one device is connected."""
        from adb_utils import get_default_device
        
        mock_client = mock.MagicMock()
        mock_device = mock.MagicMock()
        mock_device.serial = "device123"
        mock_device.is_alive.return_value = True
        
        mock_client.device_list.return_value = [mock_device]
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            device = get_default_device(None)
        
        assert device is not None
        assert device.serial == "device123"
    
    def test_get_default_device_no_devices_raises_error(self):
        """Test error handling when no devices are available."""
        from adb_utils import get_default_device, ADBError
        
        mock_client = mock.MagicMock()
        mock_client.device_list.return_value = []
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            with pytest.raises(ADBError):
                get_default_device(None)


class TestDeviceVerification:
    """Tests for device connection verification."""
    
    def test_verify_device_connected_online_device(self):
        """Test verification of online device."""
        from adb_utils import verify_device_connected
        
        mock_device = mock.MagicMock()
        mock_device.is_alive.return_value = True
        mock_device.serial = "device123"
        
        result = verify_device_connected(mock_device, timeout=5)
        assert result is True
    
    def test_verify_device_connected_offline_device(self):
        """Test detection of offline device."""
        from adb_utils import verify_device_connected, ADBError
        
        mock_device = mock.MagicMock()
        mock_device.is_alive.return_value = False
        mock_device.serial = "device123"
        
        with pytest.raises(ADBError):
            verify_device_connected(mock_device, timeout=5)
    
    def test_verify_device_timeout_handling(self):
        """Test timeout handling in device verification."""
        from adb_utils import verify_device_connected, ADBError
        
        mock_device = mock.MagicMock()
        mock_device.is_alive.side_effect = TimeoutError("Device timeout")
        
        with pytest.raises((ADBError, TimeoutError)):
            verify_device_connected(mock_device, timeout=1)


class TestOutputParsing:
    """Tests for parsing ADB command output."""
    
    def test_parse_package_list_valid_output(self):
        """Test parsing of package list output."""
        from adb_utils import parse_package_list
        
        mock_output = """package:com.example.app1
package:com.example.app2
package:com.android.systemui"""
        
        packages = parse_package_list(mock_output)
        
        assert len(packages) >= 3
        assert "com.example.app1" in packages
        assert "com.example.app2" in packages
        assert "com.android.systemui" in packages
    
    def test_parse_package_list_empty_output(self):
        """Test handling of empty package list."""
        from adb_utils import parse_package_list
        
        packages = parse_package_list("")
        
        assert isinstance(packages, list)
        assert len(packages) == 0
    
    def test_parse_package_list_malformed_output(self):
        """Test handling of malformed package output."""
        from adb_utils import parse_package_list
        
        mock_output = """package:com.example.app1
invalid line
package:com.example.app2"""
        
        packages = parse_package_list(mock_output)
        
        # Should skip invalid lines
        assert "com.example.app1" in packages
        assert "com.example.app2" in packages
        assert "invalid" not in str(packages)


class TestErrorHandling:
    """Tests for error handling in ADB utilities."""
    
    def test_adb_error_initialization(self):
        """Test ADBError exception creation."""
        from adb_utils import ADBError
        
        error = ADBError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_adb_error_with_code(self):
        """Test ADBError with exit code."""
        from adb_utils import ADBError
        
        error = ADBError("Test error")
        error.exit_code = 3
        
        assert error.exit_code == 3
    
    def test_device_offline_detection(self):
        """Test detection of offline devices."""
        from adb_utils import is_device_online
        
        mock_device = mock.MagicMock()
        mock_device.is_alive.return_value = False
        
        assert is_device_online(mock_device) is False


class TestIntegration:
    """Integration tests for adb_utils."""
    
    def test_full_device_discovery_workflow(self):
        """Test complete device discovery workflow."""
        from adb_utils import list_connected_devices, get_default_device
        
        mock_client = mock.MagicMock()
        mock_device = mock.MagicMock()
        mock_device.serial = "test_device"
        mock_device.is_alive.return_value = True
        
        mock_client.device_list.return_value = [mock_device]
        mock_client.device.return_value = mock_device
        
        with mock.patch("adb_utils.AdbClientHelper.get_client", return_value=mock_client):
            # Discover devices
            devices = list_connected_devices()
            assert len(devices) > 0
            
            # Get default device
            device = get_default_device(None)
            assert device is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
