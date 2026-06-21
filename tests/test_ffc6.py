from seeklite.ffc6 import parse_ffc6_packet


def test_empty_data():
    result = parse_ffc6_packet(b"")
    assert result == {"heartbeat_loss": None, "battery": None, "button_state": None}


def test_no_flags():
    result = parse_ffc6_packet(b"\x00")
    assert result == {"heartbeat_loss": None, "battery": None, "button_state": None}


def test_battery_only():
    result = parse_ffc6_packet(b"\x40\x5c")
    assert result == {"heartbeat_loss": None, "battery": 0x5C, "button_state": None}


def test_extended_only():
    result = parse_ffc6_packet(b"\x80\x05")
    assert result == {"heartbeat_loss": 5, "battery": None, "button_state": None}


def test_button_only():
    result = parse_ffc6_packet(b"\x20\x01")
    assert result == {"heartbeat_loss": None, "battery": None, "button_state": 1}


def test_battery_and_button():
    result = parse_ffc6_packet(b"\x60\x5c\x01")
    assert result == {"heartbeat_loss": None, "battery": 0x5C, "button_state": 1}


def test_extended_and_battery():
    result = parse_ffc6_packet(b"\xC0\x05\x5c")
    assert result == {"heartbeat_loss": 5, "battery": 0x5C, "button_state": None}


def test_all_flags():
    result = parse_ffc6_packet(b"\xE0\x05\x5c\x02")
    assert result == {"heartbeat_loss": 5, "battery": 0x5C, "button_state": 2}


def test_real_world_battery():
    result = parse_ffc6_packet(b"\x40\x54")
    assert result["battery"] == 84


def test_real_world_heartbeat_loss():
    result = parse_ffc6_packet(b"\x80\x05")
    assert result["heartbeat_loss"] == 5


def test_partial_data_extended_no_value():
    result = parse_ffc6_packet(b"\x80")
    assert result == {"heartbeat_loss": None, "battery": None, "button_state": None}


def test_partial_data_battery_truncated():
    result = parse_ffc6_packet(b"\xC0\x05")
    assert result == {"heartbeat_loss": 5, "battery": None, "button_state": None}
