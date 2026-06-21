import os
import sys
from argparse import Namespace
from unittest.mock import patch

import pytest

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
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                _get_address(args)

    def test_flag_beats_empty_env(self):
        args = Namespace(address="11:22:33:44:55:66")
        with patch.dict(os.environ, {"SEEK_MAC": ""}):
            assert _get_address(args) == "11:22:33:44:55:66"

    def test_empty_env_exits(self):
        args = Namespace(address=None)
        with patch.dict(os.environ, {"SEEK_MAC": ""}):
            with pytest.raises(SystemExit):
                _get_address(args)


class TestArgparse:
    def test_ring_subcommand(self):
        from seeklite.cli import main

        testargs = ["seeklite", "ring", "--address", "AA:BB:CC:DD:EE:FF"]
        with pytest.raises(SystemExit):
            with patch.object(sys, "argv", testargs):
                main()

    def test_info_subcommand(self):
        from seeklite.cli import main

        testargs = ["seeklite", "info", "--address", "AA:BB:CC:DD:EE:FF"]
        with pytest.raises(SystemExit):
            with patch.object(sys, "argv", testargs):
                main()

    def test_scan_no_timeout_default(self):
        from seeklite.cli import main

        testargs = ["seeklite", "scan", "--address", "AA:BB:CC:DD:EE:FF"]
        with pytest.raises(SystemExit):
            with patch.object(sys, "argv", testargs):
                main()

    def test_no_command_exits(self):
        from seeklite.cli import main

        testargs = ["seeklite", "--address", "AA:BB:CC:DD:EE:FF"]
        with pytest.raises(SystemExit):
            with patch.object(sys, "argv", testargs):
                main()
