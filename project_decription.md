    # Seek Lite Tracker (SFST212) — Open BLE Reverse-Engineering Notes

## Background & Motivation

The Seek Lite is a budget Bluetooth keyfinder, commonly distributed as a
promotional item, used with the official "Seek" app (`com.snappwish.seek`,
by SnappWish LLC). The app has poor user ratings (~2.3–2.6/5) for range,
reliability, and dead-on-arrival units, and bundles Facebook and Google
tracking SDKs. This project reverse-engineers the tracker's BLE protocol to
build a minimal, fully open client, no official app, no embedded trackers,
for hardware already owned.

## Device Identification

- **Model:** SFST212
- **Manufacturer string:** zenlyfe
- **Firmware:** `BF29H2S1.0_20250228`
- **Chipset:** Nordic nRF5x (confirmed via Nordic Secure DFU GATT service)
- **Official app:** Seek, package `com.snappwish.seek`, by SnappWish LLC

## Investigation Process (summary)

1. Explored the device's GATT table using BLE Radar (open source, F-Droid).
2. Captured the official app's APK two ways: via Aptoide (found to repackage
   apps with its own SDK and signing cert — traced via signature mismatch
   and a `cm.aptoide.pt` package found during decompilation) and via the
   genuinely-installed copy (using an open-source APK Extractor app).
3. Decompiled with `jadx`, then used an AI coding agent (opencode) to dig
   through the decompiled source and locate the device-control class
   (`j.java`, for the BF-series firmware family this tracker uses).
4. Mapped the real protocol: a per-connection authentication handshake,
   followed by use of the *standard* Bluetooth Immediate Alert service for
   the actual ring/beep command, the standard service writes fail (and
   disconnect the device) without the handshake first.
5. Implemented and tested a working open client in Python using `bleak`.

## GATT Reference

> Handle numbers can shift between connections/devices; UUIDs are stable
> and are what matters for reimplementation.

### Standard services

| Service | Characteristic | Properties | Notes |
|---|---|---|---|
| 1800 Generic Access | 2A00 Device Name | read | |
| | 2A01 Appearance | read | |
| 1801 Generic Attribute | 2A05 Service Changed | read, indicate | |
| **1802 Immediate Alert** | **2A06 Alert Level** | write-without-response | **Ring/beep command** |
| 1803 Link Loss | 2A06 Alert Level | read, write | Separation alert config |
| 1804 Tx Power | 2A07 Tx Power Level | read | |
| 180A Device Information | 2A29 Manufacturer Name | read | "zenlyfe" |
| | 2A24 Model Number | read | "SFST212" |
| | 2A26 Firmware Revision | read | "BF29H2S1.0_20250228" |
| | 2A27 Hardware Revision | read | |
| | 2A28 Software Revision | read | |
| | 2A23 System ID | read | |
| | 2A50 PnP ID | read | |
| 180F Battery Service | 2A19 Battery Level | read, notify | |

### Custom (vendor) services

| Service | Characteristic | Properties | Notes |
|---|---|---|---|
| **0xFFF0** | **0xFFF1** | write | **Auth characteristic** |
| | 0xFFE5 | read, write | Ringtone melody data (init only) |
| **0xFFC0** | 0xFFC1 | write | |
| | 0xFFC2 | read, write | |
| | 0xFFC3 | write | |
| | 0xFFC4 | read, write | |
| | **0xFFC6** | read, write, **notify** | **Heartbeat/battery/button-press channel** |
| 0xFE59 | (Nordic Secure DFU characteristics) | — | Firmware update only, not used in normal operation |

## The Protocol: Connect & Ring Sequence

1. **Scan** for the device's current BLE advertisement and capture its
   manufacturer-specific data (Seek's own data is under company ID `7192` /
   `0x1C18`).
2. **Compute the auth byte**: XOR of every byte in that manufacturer-data
   payload (as returned by a standard scan API, i.e. with the 2-byte company
   ID already stripped).
3. **Connect** via BLE.
4. **Authenticate**: write the auth byte to characteristic FFF1 (service
   FFF0). This must be a write **with response** — FFF1's actual property is
   plain `write`, not `write-without-response`.
5. *(Matches official app behavior, may not be strictly required)* **Subscribe**
   to notifications on FFC6 (service FFC0) — delivers a multiplexed
   heartbeat/battery/button-press packet.
6. **Ring**: write `0x02` to Alert Level (UUID 2A06, service 1802 Immediate
   Alert) to start beeping.
7. **Stop**: write `0x00` to the same characteristic to stop.

**Without step 4 (auth), any write to the standard Immediate Alert or Link
Loss services causes the tracker to immediately drop the BLE connection.**
This was the main blocker during initial testing.

## Working Python Script (`bleak`)

```python
import asyncio
from bleak import BleakScanner, BleakClient

ADDRESS = "XX:XX:XX:XX:XX:XX"   # tracker's MAC/Bluetooth address

AUTH_CHAR = 39          # FFF0/FFF1 (write, with response)
HEARTBEAT_NOTIFY = 58   # FFC0/FFC6 (notify)
IMMEDIATE_ALERT = 14    # 1802/2A06 (write-without-response)


def compute_auth_byte(payload: bytes) -> int:
    """XOR of every byte in the manufacturer-specific advertising payload."""
    result = 0
    for b in payload:
        result ^= b
    return result


async def scan_for_manufacturer_data(address, timeout=5):
    captured = {}

    def callback(device, adv_data):
        if device.address.lower() == address.lower():
            captured["mfg"] = adv_data.manufacturer_data

    scanner = BleakScanner(callback)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    if "mfg" not in captured or not captured["mfg"]:
        return None
    _, payload = next(iter(captured["mfg"].items()))
    return payload


def notify_handler(sender, data):
    print(f"Notification: {data.hex()}")


async def authenticate(client, auth_byte):
    await client.write_gatt_char(AUTH_CHAR, bytearray([auth_byte]), response=True)


async def ring(client, seconds=3):
    await client.write_gatt_char(IMMEDIATE_ALERT, bytearray([0x02]), response=False)
    print("Ringing...")
    await asyncio.sleep(seconds)
    await client.write_gatt_char(IMMEDIATE_ALERT, bytearray([0x00]), response=False)
    print("Stopped ring")
    await asyncio.sleep(0.5)


async def main():
    print("Scanning for advertisement data...")
    payload = await scan_for_manufacturer_data(ADDRESS)
    if payload is None:
        print("No manufacturer data captured, move closer and retry")
        return

    auth_byte = compute_auth_byte(payload)
    print(f"Computed auth byte: {auth_byte:#04x}")

    async with BleakClient(ADDRESS) as client:
        print("Connected:", client.is_connected)
        await authenticate(client, auth_byte)
        print("Authenticated")
        await client.start_notify(HEARTBEAT_NOTIFY, notify_handler)
        await ring(client)
        print("Disconnecting cleanly")

asyncio.run(main())
```

### Quick reference: useful standalone snippets

Read battery / device info (no auth needed, standard service):

```python
battery = await client.read_gatt_char(20)       # 180F/2A19
manufacturer = await client.read_gatt_char(24)   # 180A/2A29
model = await client.read_gatt_char(26)          # 180A/2A24
firmware = await client.read_gatt_char(30)       # 180A/2A26
```

Force-disconnect a stuck/lingering connection:

```python
client = BleakClient(ADDRESS)
await client.connect()
await client.disconnect()
```

Check if the tracker is currently advertising (i.e. not connected to
anything), independent of any phone app:

```python
devices = await BleakScanner.discover(timeout=30, return_adv=True)
for address, (device, adv_data) in devices.items():
    if address.lower() == ADDRESS.lower():
        print("Advertising, RSSI:", adv_data.rssi)
```

## FFC6 Notification Packet Format

`byte[0]` is a flags byte:

- bit 7 — extended header present
- bit 6 — battery value present
- bit 5 — button-state value present

Payload byte offsets shift depending on which flags are set (extended +
battery + button can all be present simultaneously, each shifting the next
field's position by one byte). Observed real example: `0x40 0x5c` decoded
as battery = `0x5c` (92); `0x80 0x05` decoded as heartbeat-loss-count = `0x05`.

## Open Questions / Unresolved

- The tracker was observed to make an audible "power off" sound and stop
  advertising during testing, but no shutdown/power-off command was found
  anywhere in the reverse-engineered protocol. Cause unknown — possibly an
  idle timeout, possibly a button-hold combination. Not yet investigated.
- Byte-level command tables for ringtone/melody selection (FFE5), the
  separation/leash alert distance setting (FFC4), and other secondary
  features have not been fully mapped for this specific device class.
- The two-way "tracker button rings phone" direction is understood at the
  notification level (button-state field in the FFC6 packet) but hasn't
  been tested end-to-end in the custom script yet.