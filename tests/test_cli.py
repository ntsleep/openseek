import os
import sys
from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.exc import BleakDeviceNotFoundError
from seeklite.cli import _get_address


class TestGetAddress:
    def test_from_flag(self):
        args = Namespace(address="AA:BB:CC:DD:EE:FF")
        assert _get_address(args) == "AA:BB:CC:DD:EE:FF"

    def test_from_env(self):
        args = Namespace(address=None)
        with patch.dict(os.environ, {"SEEK_MAC": "AA:BB:CC:DD:EE:FF"}, clear=True):
            assert _get_address(args) == "AA:BB:CC:DD:EE:FF"

    def test_flag_overrides_env(self):
        args = Namespace(address="11:22:33:44:55:66")
        with patch.dict(os.environ, {"SEEK_MAC": "AA:BB:CC:DD:EE:FF"}):
            assert _get_address(args) == "11:22:33:44:55:66"

    def test_missing_exits(self):
        args = Namespace(address=None)
        with patch.dict(os.environ, {}, clear=True), pytest.raises(SystemExit):
            _get_address(args)

    def test_flag_beats_empty_env(self):
        args = Namespace(address="11:22:33:44:55:66")
        with patch.dict(os.environ, {"SEEK_MAC": ""}):
            assert _get_address(args) == "11:22:33:44:55:66"

    def test_empty_env_exits(self):
        args = Namespace(address=None)
        with patch.dict(os.environ, {"SEEK_MAC": ""}), pytest.raises(SystemExit):
            _get_address(args)


class TestArgparse:
    def test_ring_subcommand(self):
        from seeklite.cli import main

        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client._alert_handle = 14
        mock_client._client = MagicMock()
        testargs = ["seeklite", "--address", "AA:BB:CC:DD:EE:FF", "ring"]

        with (
            patch("seeklite.cli.SeekLiteClient", return_value=mock_client),
            patch.object(sys, "argv", testargs),
        ):
            main()

        mock_client.connect.assert_awaited_once()
        mock_client.ring.assert_awaited_once_with(3.0)
        mock_client.disconnect.assert_awaited_once()

    def test_info_subcommand(self):
        from seeklite.cli import main

        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client._alert_handle = 14
        mock_client._client = MagicMock()
        mock_client.read_info = AsyncMock(return_value={"manufacturer": "test"})
        testargs = ["seeklite", "--address", "AA:BB:CC:DD:EE:FF", "info"]

        with (
            patch("seeklite.cli.SeekLiteClient", return_value=mock_client),
            patch.object(sys, "argv", testargs),
        ):
            main()

        mock_client.connect.assert_awaited_once()
        mock_client.read_info.assert_awaited_once()
        mock_client.disconnect.assert_awaited_once()

    def test_scan_no_timeout_default(self):
        from seeklite.cli import main

        testargs = ["seeklite", "--address", "AA:BB:CC:DD:EE:FF", "scan"]
        with (
            patch("seeklite.cli.BleakScanner.discover", return_value={}),
            patch.object(sys, "argv", testargs),
        ):
            main()

    def test_discover_subcommand(self, capsys):
        from seeklite.cli import main

        testargs = ["seeklite", "discover"]
        with (
            patch("seeklite.client.SeekLiteClient.discover", return_value=[]),
            patch.object(sys, "argv", testargs),
        ):
            main()

        captured = capsys.readouterr()
        assert "No devices found" in captured.out

    def test_discover_with_timeout(self, capsys):
        from seeklite.cli import main

        testargs = ["seeklite", "discover", "--timeout", "5"]
        with (
            patch("seeklite.client.SeekLiteClient.discover", return_value=[]),
            patch.object(sys, "argv", testargs),
        ):
            main()

        captured = capsys.readouterr()
        assert "Scanning for 5 seconds" in captured.out

    def test_no_command_exits(self):
        from seeklite.cli import main

        testargs = ["seeklite", "--address", "AA:BB:CC:DD:EE:FF"]
        with pytest.raises(SystemExit), patch.object(sys, "argv", testargs):
            main()


class TestDiscover:
    DISCOVER_ARGV = ("seeklite", "discover")

    def test_discover_prints_devices(self, capsys):
        from seeklite.cli import main

        devices = [
            ("aa:bb:cc:dd:ee:ff", -50, "Tracker", {0x6313: b"\xde\xad"}),
            ("11:22:33:44:55:66", -70, None, {}),
        ]

        with (
            patch("seeklite.client.SeekLiteClient.discover", return_value=devices),
            patch.object(sys, "argv", self.DISCOVER_ARGV),
        ):
            main()

        captured = capsys.readouterr()
        assert "aa:bb:cc:dd:ee:ff" in captured.out
        assert "Tracker" in captured.out
        assert "(unknown)" in captured.out
        assert "6313" in captured.out

    def test_discover_no_devices(self, capsys):
        from seeklite.cli import main

        with (
            patch("seeklite.client.SeekLiteClient.discover", return_value=[]),
            patch.object(sys, "argv", self.DISCOVER_ARGV),
        ):
            main()

        captured = capsys.readouterr()
        assert "No devices found" in captured.out


class TestMainErrorHandling:
    """Verify that main() catches errors and prints user-friendly messages."""

    ARGV = ("seeklite", "--address", "AA:BB:CC:DD:EE:FF", "ring")

    def test_device_not_found(self, capsys):
        from seeklite.cli import main

        with (
            patch("seeklite.client.SeekLiteClient.connect", side_effect=BleakDeviceNotFoundError("AA:BB:CC:DD:EE:FF")),
            patch.object(sys, "argv", self.ARGV),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "Error: Device not found" in captured.out
        assert exc_info.value.code == 1

    def test_timeout_error(self, capsys):
        from seeklite.cli import main

        with (
            patch("seeklite.client.SeekLiteClient.connect", side_effect=TimeoutError()),
            patch.object(sys, "argv", self.ARGV),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "Error: Operation timed out" in captured.out
        assert exc_info.value.code == 1

    def test_generic_exception(self, capsys):
        from seeklite.cli import main

        with (
            patch("seeklite.client.SeekLiteClient.connect", side_effect=RuntimeError("device disconnected")),
            patch.object(sys, "argv", self.ARGV),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "Error: device disconnected" in captured.out
        assert exc_info.value.code == 1


class TestDisconnectError:
    ARGV = ("seeklite", "--address", "AA:BB:CC:DD:EE:FF", "disconnect")

    def test_disconnect_connect_error(self, capsys):
        from seeklite.cli import main

        with (
            patch("seeklite.client.SeekLiteClient.connect", side_effect=RuntimeError("connection failed")),
            patch.object(sys, "argv", self.ARGV),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "Error: connection failed" in captured.out
        assert exc_info.value.code == 1
