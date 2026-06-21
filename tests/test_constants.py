import uuid

from seeklite.constants import (
    _uuid,
    CHAR_FFF1_AUTH,
    CHAR_ALERT_LEVEL,
    CHAR_BATTERY_LEVEL,
    SERVICE_IMMEDIATE_ALERT,
    SERVICE_FFC0,
    CHAR_FFC6_NOTIFY,
    COMPANY_ID_SEEK,
    HEARTBEAT_INTERVAL,
    ALERT_NONE,
    ALERT_MILD,
    ALERT_HIGH,
)


def test_uuid_constructor():
    u = _uuid("FFF1")
    assert isinstance(u, uuid.UUID)
    assert str(u) == "0000fff1-0000-1000-8000-00805f9b34fb"


def test_char_fff1_auth_format():
    assert str(CHAR_FFF1_AUTH) == "0000fff1-0000-1000-8000-00805f9b34fb"


def test_alert_level_uuid():
    assert str(CHAR_ALERT_LEVEL) == "00002a06-0000-1000-8000-00805f9b34fb"


def test_battery_level_uuid():
    assert str(CHAR_BATTERY_LEVEL) == "00002a19-0000-1000-8000-00805f9b34fb"


def test_immediate_alert_service():
    assert str(SERVICE_IMMEDIATE_ALERT) == "00001802-0000-1000-8000-00805f9b34fb"


def test_ffc0_service():
    assert str(SERVICE_FFC0) == "0000ffc0-0000-1000-8000-00805f9b34fb"


def test_ffc6_char():
    assert str(CHAR_FFC6_NOTIFY) == "0000ffc6-0000-1000-8000-00805f9b34fb"


def test_company_id():
    assert COMPANY_ID_SEEK == 0x1C18


def test_heartbeat_interval():
    assert HEARTBEAT_INTERVAL == 60


def test_alert_levels():
    assert ALERT_NONE == 0x00
    assert ALERT_MILD == 0x01
    assert ALERT_HIGH == 0x02


def test_all_uuids_have_consistent_base():
    names = [
        ("FFF0", "SERVICE_FFF0"),
        ("FFF1", "CHAR_FFF1_AUTH"),
        ("FFE5", "CHAR_FFE5_RINGTONE"),
        ("FFC0", "SERVICE_FFC0"),
        ("FFC1", "CHAR_FFC1_RESET"),
        ("FFC2", "CHAR_FFC2_ACTIVE_SOUND"),
        ("FFC3", "CHAR_FFC3"),
        ("FFC4", "CHAR_FFC4_BASIC_CONFIG"),
        ("FFC6", "CHAR_FFC6_NOTIFY"),
        ("1802", "SERVICE_IMMEDIATE_ALERT"),
        ("1803", "SERVICE_LINK_LOSS"),
        ("180F", "SERVICE_BATTERY"),
        ("180A", "SERVICE_DEVICE_INFO"),
        ("2A06", "CHAR_ALERT_LEVEL"),
        ("2A06", "CHAR_LINK_LOSS_ALERT"),
        ("2A19", "CHAR_BATTERY_LEVEL"),
        ("2A29", "CHAR_MANUFACTURER"),
        ("2A24", "CHAR_MODEL"),
        ("2A26", "CHAR_FIRMWARE"),
        ("2A27", "CHAR_HARDWARE"),
        ("2A28", "CHAR_SOFTWARE"),
        ("2A23", "CHAR_SYSTEM_ID"),
        ("2A50", "CHAR_PNP_ID"),
    ]
    base = "0000-1000-8000-00805f9b34fb"
    for short, _name in names:
        expected = f"0000{short.lower()}-{base}"
        actual = str(_uuid(short))
        assert actual == expected, f"{short}: expected {expected}, got {actual}"
