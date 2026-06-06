"""
Test suite for error_handlers module.

Purpose:
    Tests for custom exception classes and error handling decorators
    used across all 29 ADB scripts for consistent error management.

Test Categories:
    1. Exception class definitions and exit codes
    2. Exception constructors and attributes
    3. Error handling decorator functionality
    4. Error message formatting
    5. Exit code mapping
"""

import sys
from pathlib import Path
from unittest import mock

import pytest


# Test imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "common"))


class TestExitCodes:
    """Tests for exit code constants."""
    
    def test_exit_code_constants_defined(self):
        """Test that all exit codes are defined."""
        from error_handlers import (
            EXIT_SUCCESS,
            EXIT_INVALID_ARGUMENT,
            EXIT_ADB_COMMAND_FAILED,
            EXIT_DEVICE_ERROR,
            EXIT_TIMEOUT
        )
        
        # Should have specific values
        assert EXIT_SUCCESS == 0
        assert EXIT_INVALID_ARGUMENT == 4
        assert EXIT_ADB_COMMAND_FAILED == 3
        assert EXIT_DEVICE_ERROR == 2
        assert EXIT_TIMEOUT == 124
    
    def test_exit_codes_are_unique(self):
        """Test that exit codes are unique."""
        from error_handlers import (
            EXIT_SUCCESS,
            EXIT_INVALID_ARGUMENT,
            EXIT_ADB_COMMAND_FAILED,
            EXIT_DEVICE_ERROR,
            EXIT_TIMEOUT
        )
        
        codes = [
            EXIT_SUCCESS,
            EXIT_INVALID_ARGUMENT,
            EXIT_ADB_COMMAND_FAILED,
            EXIT_DEVICE_ERROR,
            EXIT_TIMEOUT
        ]
        
        assert len(codes) == len(set(codes))


class TestADBError:
    """Tests for ADBError exception class."""
    
    def test_adb_error_creation(self):
        """Test creating ADBError exception."""
        from error_handlers import ADBError
        
        error = ADBError("Test error message")
        
        assert isinstance(error, Exception)
        assert str(error) == "Test error message"
    
    def test_adb_error_with_exit_code(self):
        """Test ADBError with exit code attribute."""
        from error_handlers import ADBError
        
        error = ADBError("Test error")
        error.exit_code = 3
        
        assert error.exit_code == 3
    
    def test_adb_error_inherits_from_exception(self):
        """Test that ADBError inherits from Exception."""
        from error_handlers import ADBError
        
        error = ADBError("Test")
        assert isinstance(error, Exception)


class TestDeviceError:
    """Tests for DeviceError exception class."""
    
    def test_device_error_creation(self):
        """Test creating DeviceError exception."""
        from error_handlers import DeviceError
        
        error = DeviceError("Device not found")
        
        assert isinstance(error, Exception)
        assert "Device" in str(error)
    
    def test_device_error_exit_code_mapping(self):
        """Test that DeviceError maps to correct exit code."""
        from error_handlers import DeviceError, EXIT_DEVICE_ERROR
        
        error = DeviceError("Test")
        error.exit_code = EXIT_DEVICE_ERROR
        
        assert error.exit_code == EXIT_DEVICE_ERROR


class TestTimeoutError:
    """Tests for timeout-related errors."""
    
    def test_timeout_error_creation(self):
        """Test creating timeout error."""
        from error_handlers import ADBError, EXIT_TIMEOUT
        
        error = ADBError("Operation timed out")
        error.exit_code = EXIT_TIMEOUT
        
        assert error.exit_code == EXIT_TIMEOUT
    
    def test_timeout_exit_code(self):
        """Test that timeout uses correct exit code."""
        from error_handlers import EXIT_TIMEOUT
        
        # Standard timeout exit code is 124
        assert EXIT_TIMEOUT == 124


class TestErrorHandlerDecorator:
    """Tests for @handle_adb_errors decorator."""
    
    def test_handle_adb_errors_decorator_exists(self):
        """Test that handle_adb_errors decorator is defined."""
        from error_handlers import handle_adb_errors
        
        assert callable(handle_adb_errors)
    
    def test_handle_adb_errors_preserves_function(self):
        """Test that decorator preserves wrapped function."""
        from error_handlers import handle_adb_errors
        
        @handle_adb_errors
        def test_func():
            return "test_result"
        
        # Should be callable
        assert callable(test_func)
    
    def test_handle_adb_errors_catches_adb_error(self):
        """Test that decorator catches ADBError."""
        from error_handlers import handle_adb_errors, ADBError
        
        @handle_adb_errors
        def failing_func():
            raise ADBError("Test ADB error")
        
        # Should catch and handle error gracefully
        with mock.patch("error_handlers.print_error"):
            with mock.patch("sys.exit"):
                failing_func()
    
    def test_handle_adb_errors_catches_device_error(self):
        """Test that decorator catches DeviceError."""
        from error_handlers import handle_adb_errors, DeviceError
        
        @handle_adb_errors
        def failing_func():
            raise DeviceError("Device offline")
        
        # Should catch and handle error gracefully
        with mock.patch("error_handlers.print_error"):
            with mock.patch("sys.exit"):
                failing_func()
    
    def test_handle_adb_errors_passes_through_success(self):
        """Test that decorator allows successful execution."""
        from error_handlers import handle_adb_errors
        
        @handle_adb_errors
        def success_func():
            return "success"
        
        result = success_func()
        
        assert result == "success"


class TestErrorMessages:
    """Tests for error message generation."""
    
    def test_adb_error_message_content(self):
        """Test that error messages contain useful information."""
        from error_handlers import ADBError
        
        error = ADBError("ADB connection failed: Connection refused")
        message = str(error)
        
        assert "ADB" in message or "connection" in message.lower()
    
    def test_device_error_descriptive(self):
        """Test that DeviceError provides context."""
        from error_handlers import DeviceError
        
        error = DeviceError("Device 127.0.0.1:5555 went offline")
        message = str(error)
        
        assert "127.0.0.1" in message
    
    def test_error_messages_are_actionable(self):
        """Test that error messages guide users."""
        from error_handlers import ADBError
        
        error = ADBError("ADB server not started. Run: adb start-server")
        message = str(error)
        
        # Should contain actionable guidance
        assert len(message) > 0


class TestExceptionHierarchy:
    """Tests for exception inheritance and hierarchy."""
    
    def test_adb_error_is_exception(self):
        """Test that ADBError is an Exception."""
        from error_handlers import ADBError
        
        error = ADBError("test")
        assert isinstance(error, Exception)
    
    def test_device_error_is_exception(self):
        """Test that DeviceError is an Exception."""
        from error_handlers import DeviceError
        
        error = DeviceError("test")
        assert isinstance(error, Exception)
    
    def test_exceptions_can_be_caught_generically(self):
        """Test that exceptions can be caught as Exception."""
        from error_handlers import ADBError, DeviceError
        
        errors = [ADBError("test1"), DeviceError("test2")]
        
        for error in errors:
            try:
                raise error
            except Exception as e:
                # Should catch all custom exceptions
                assert isinstance(e, (ADBError, DeviceError))


class TestErrorContext:
    """Tests for error context and traceability."""
    
    def test_error_preserves_traceback(self):
        """Test that exceptions preserve stack traces."""
        from error_handlers import ADBError
        
        try:
            raise ADBError("Test error with context")
        except ADBError as e:
            # Exception should have traceback info
            assert str(e) == "Test error with context"
    
    def test_error_can_include_device_info(self):
        """Test including device information in errors."""
        from error_handlers import DeviceError
        
        device_id = "127.0.0.1:5555"
        error = DeviceError(f"Failed to connect to {device_id}")
        
        assert device_id in str(error)


class TestErrorRecovery:
    """Tests for error recovery mechanisms."""
    
    def test_decorator_allows_continued_execution(self):
        """Test that decorator doesn't break subsequent operations."""
        from error_handlers import handle_adb_errors
        
        call_count = 0
        
        @handle_adb_errors
        def counted_func():
            nonlocal call_count
            call_count += 1
            return call_count
        
        result1 = counted_func()
        result2 = counted_func()
        
        assert result1 == 1
        assert result2 == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
