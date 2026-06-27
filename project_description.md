# Seek Lite Tracker (SFST212) — BLE Protocol & Library Reference

## Device Identification

- **Model:** SFST212
- **Manufacturer:** zenlyfe
- **Firmware:** `BF29H2S1.0_20250228`
- **Chipset:** Nordic nRF5x (Nordic Secure DFU GATT service present)
- **Official app:** Seek, package `com.snappwish.seek`, by SnappWish LLC (<https://www.theseekapp.net/>)
- **BLE company ID:** varies (observed `0x1C18`, `0x5F19`, `0x6313`) — the auth logic picks the first non-beacon manufacturer data entry, so the exact ID doesn't matter

## GATT Reference

Handle numbers can shift between connections; UUIDs are stable.

### Standard services

| Service | Characteristic | Properties | Notes |
|---|---|---|---|
| 1802 Immediate Alert | 2A06 Alert Level | write-without-response | Ring/stop command |
| 1803 Link Loss | 2A06 Alert Level | read, write | Separation alert config |
| 180F Battery | 2A19 Battery Level | read, notify | |
| 180A Device Info | 2A29 Manufacturer Name | read | "zenlyfe" |
| | 2A24 Model Number | read | "SFST212" |
| | 2A26 Firmware Revision | read | |
| | 2A27 Hardware Revision | read | |
| | 2A28 Software Revision | read | |
| | 2A23 System ID | read | |
| | 2A50 PnP ID | read | |

### Custom (vendor) services

| Service | Characteristic | Properties | Notes |
|---|---|---|---|
| 0xFFF0 | 0xFFF1 | write | Auth — write XOR'd auth byte here with response |
| | 0xFFE5 | read, write | Ringtone melody data |
| 0xFFC0 | 0xFFC1 | write | |
| | 0xFFC2 | read, write | |
| | 0xFFC3 | write | |
| | 0xFFC4 | read, write | Basic config |
| | 0xFFC6 | read, write, notify | Heartbeat/battery/button-press channel |
| 0xFE59 | (Nordic Secure DFU) | — | Firmware update only |

## Protocol: Connect & Ring Sequence

1. **Scan** for the device advertisement and capture manufacturer data. The scan API (e.g. `BleakScanner`) returns a dict keyed by company ID with the 2-byte company ID already stripped from each payload.
2. **Compute auth byte**: XOR every byte of the manufacturer data payload.
3. **Connect** via BLE.
4. **Authenticate**: write the auth byte to characteristic FFF1 (service FFF0) **with response**. Without this, any write to Immediate Alert or Link Loss causes an immediate disconnect.
5. **Subscribe** to FFC6 notifications (optional — delivers heartbeat/battery/button state).
6. **Ring**: write `0x02` to Alert Level (UUID 2A06, service 1802) to start beeping.
7. **Stop**: write `0x00` to the same characteristic.

**Auth fallback**: if manufacturer data is unavailable during scan, the auth byte is computed by XOR'ing the device's MAC address bytes instead.

## FFC6 Notification Packet Format

Byte 0 is a flags bitfield:

- bit 7 — extended data present (heartbeat loss counter)
- bit 6 — battery level present
- bit 5 — button state present

Subsequent fields appear in bit-order (extended → battery → button), each shifting subsequent offsets by 1 byte. A field is only present if its flag is set.

Examples:
- `0x40 0x5c` → battery = `0x5c` (92%)
- `0x80 0x05` → heartbeat loss = 5
- `0xE0 0x05 0x5c 0x01` → heartbeat loss = 5, battery = 92, button state = 1

## Auth Byte Computation

XOR all bytes of the manufacturer advertising payload (the bytes after the 2-byte company ID):

```python
def compute_auth_byte(payload: bytes) -> int:
    result = 0
    for b in payload:
        result ^= b
    return result
```

This matches the logic in the official app's `bus_ble/a.java:b()` method.

## Package API Reference

`seeklite/` is structured as follows:

| Module | Public API | Purpose |
|---|---|---|
| `auth.py` | `compute_auth_byte(payload: bytes) -> int` | XOR auth byte from manufacturer payload |
| `ffc6.py` | `parse_ffc6_packet(data: bytes) -> dict[str, int \| None]` | Parse FFC6 notification → keys: `heartbeat_loss`, `battery`, `button_state` |
| `constants.py` | All `SERVICE_*`, `CHAR_*` UUIDs, `ALERT_*`, `HEARTBEAT_INTERVAL` | GATT UUID and protocol constants |
| `client.py` | `SeekLiteClient` class | BLE client — connect, auth, ring, stop, read info, subscribe FFC6 |
| `cli.py` | `main()` | CLI entry point (see README) |

### SeekLiteClient

```
client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
await client.connect()                    # scan → auth → subscribe FFC6
await client.ring(duration=3.0)           # write 0x02 to Alert Level
await client.stop()                       # write 0x00 to Alert Level
info = await client.read_info()           # dict with manufacturer, model, battery, etc.
await client.subscribe_ffc6(callback)     # receive live FFC6 notifications
await client.unsubscribe_ffc6()           # stop notifications
await client.disconnect()                 # clean up
```

Subscription example — detect button presses:

```python
from seeklite.client import SeekLiteClient
from seeklite.ffc6 import parse_ffc6_packet

def on_notification(sender, data):
    parsed = parse_ffc6_packet(data)
    if parsed["button_state"] is not None:
        print(f"Button state changed: {parsed['button_state']}")

async def main():
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    await client.subscribe_ffc6(on_notification)
    await asyncio.Event().wait()  # run until Ctrl+C
```

## Notes

- The tracker may power off (audible shutdown sound, stops advertising) after extended idle — possibly a timeout or button-hold sequence. Not yet investigated.
- Ringtone selection (FFE5), leash/anti-lost distance (FFC4), and other secondary features are not mapped for this device class.
- The "tracker button rings phone" direction works by observing the button-state field in FFC6 packets. The library already exposes this — what's left to the consuming app is the alert/notification UI when the button is pressed.
