import uuid

UUID_BASE = "0000-1000-8000-00805F9B34FB"


def _uuid(short: str) -> uuid.UUID:
    return uuid.UUID(f"0000{short}-{UUID_BASE}")


# Custom service FFF0
SERVICE_FFF0 = _uuid("FFF0")
CHAR_FFF1_AUTH = _uuid("FFF1")
CHAR_FFE5_RINGTONE = _uuid("FFE5")

# Custom service FFC0
SERVICE_FFC0 = _uuid("FFC0")
CHAR_FFC1_RESET = _uuid("FFC1")
CHAR_FFC2_ACTIVE_SOUND = _uuid("FFC2")
CHAR_FFC3 = _uuid("FFC3")
CHAR_FFC4_BASIC_CONFIG = _uuid("FFC4")
CHAR_FFC6_NOTIFY = _uuid("FFC6")

# Standard: Immediate Alert (1802)
SERVICE_IMMEDIATE_ALERT = _uuid("1802")
CHAR_ALERT_LEVEL = _uuid("2A06")

# Standard: Link Loss (1803)
SERVICE_LINK_LOSS = _uuid("1803")
CHAR_LINK_LOSS_ALERT = _uuid("2A06")

# Standard: Battery (180F)
SERVICE_BATTERY = _uuid("180F")
CHAR_BATTERY_LEVEL = _uuid("2A19")

# Standard: Device Information (180A)
SERVICE_DEVICE_INFO = _uuid("180A")
CHAR_MANUFACTURER = _uuid("2A29")
CHAR_MODEL = _uuid("2A24")
CHAR_FIRMWARE = _uuid("2A26")
CHAR_HARDWARE = _uuid("2A27")
CHAR_SOFTWARE = _uuid("2A28")
CHAR_SYSTEM_ID = _uuid("2A23")
CHAR_PNP_ID = _uuid("2A50")

# Seek's BLE company ID (used in manufacturer advertising data)
COMPANY_ID_SEEK = 0x1C18

# Heartbeat interval config written to FFC6: [0x80, interval_seconds]
HEARTBEAT_INTERVAL = 60

# Alert level values for 2A06
ALERT_NONE = 0x00
ALERT_MILD = 0x01
ALERT_HIGH = 0x02
