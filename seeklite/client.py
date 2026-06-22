"""BLE client for connecting, authenticating, and controlling the Seek Lite tracker."""
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from bleak import BleakClient, BleakScanner

from seeklite.auth import compute_auth_byte
from seeklite.constants import (
    ALERT_HIGH,
    ALERT_NONE,
    CHAR_ALERT_LEVEL,
    CHAR_BATTERY_LEVEL,
    CHAR_FFC6_NOTIFY,
    CHAR_FFF1_AUTH,
    CHAR_FIRMWARE,
    CHAR_HARDWARE,
    CHAR_MANUFACTURER,
    CHAR_MODEL,
    CHAR_PNP_ID,
    CHAR_SOFTWARE,
    CHAR_SYSTEM_ID,
    SERVICE_IMMEDIATE_ALERT,
)

_BEACON_IDS = {0x004C, 0x00E0, 0x00FF, 0x0130, 0x0157, 0x018B, 0x01AC}

_NOT_CONNECTED_MSG = "Not connected. Call connect() first."


def _pick_mfg_payload(manufacturer_data: dict[int, bytes]) -> bytes | None:
    """Return the first manufacturer payload that is not a known beacon ID.

    Falls back to the first payload if all are beacons.
    """
    if not manufacturer_data:
        return None
    for company_id, payload in manufacturer_data.items():
        if company_id not in _BEACON_IDS:
            return payload
    return next(iter(manufacturer_data.values()))


def _auth_from_mac(address: str) -> int:
    """Compute the auth byte from the device MAC address directly."""
    mac_bytes = bytes.fromhex(address.replace(":", ""))
    return compute_auth_byte(mac_bytes)


class SeekLiteClient:
    """Manages BLE connection and interaction with a Seek Lite tracker."""

    def __init__(self, address: str) -> None:
        """Initialize the client with a tracker MAC address."""
        self.address = address
        self._client: BleakClient | None = None
        self._alert_handle: int | None = None

    @property
    def is_connected(self) -> bool:
        """Whether the underlying BLE client is connected."""
        return self._client is not None and self._client.is_connected

    async def connect(self, scan_timeout: float = 5.0) -> None:
        """Scan for manufacturer data, authenticate, and subscribe to FFC6.

        Falls back to MAC-derived auth byte if the tracker is not found
        in scan results.
        """
        devices = await BleakScanner.discover(
            timeout=min(scan_timeout, 1.0), return_adv=True,
        )
        auth_byte: int | None = None
        for addr, (_device, adv_data) in devices.items():
            if addr.lower() == self.address.lower():
                payload = _pick_mfg_payload(adv_data.manufacturer_data)
                if payload is not None:
                    auth_byte = compute_auth_byte(payload)
                    break

        if auth_byte is None:
            auth_byte = _auth_from_mac(self.address)

        self._client = BleakClient(self.address)
        await self._client.connect()
        await self._client.write_gatt_char(
            CHAR_FFF1_AUTH, bytearray([auth_byte]), response=True,
        )
        await asyncio.sleep(0.5)

        service = self._client.services.get_service(SERVICE_IMMEDIATE_ALERT)
        self._alert_handle = service.get_characteristic(CHAR_ALERT_LEVEL).handle

        await self._client.start_notify(CHAR_FFC6_NOTIFY, lambda _s, _d: None)
        await asyncio.sleep(0.5)

    async def disconnect(self) -> None:
        """Unsubscribe from notifications and disconnect."""
        if self._client and self._client.is_connected:
            with contextlib.suppress(Exception):
                await self._client.stop_notify(CHAR_FFC6_NOTIFY)
            await self._client.disconnect()
        self._client = None

    async def ring(self, duration: float = 3.0) -> None:
        """Trigger a high-level alert and optionally read battery."""
        self._check_connected()
        await self._client.write_gatt_char(
            self._alert_handle, bytearray([ALERT_HIGH]), response=False,
        )
        await self._client.read_gatt_char(CHAR_BATTERY_LEVEL)
        await asyncio.sleep(duration)

    async def stop(self) -> None:
        """Stop the active alert."""
        self._check_connected()
        with contextlib.suppress(Exception):
            await self._client.write_gatt_char(
                self._alert_handle, bytearray([ALERT_NONE]), response=False,
            )

    async def read_info(self) -> dict[str, str]:
        """Read device information characteristics and battery level."""
        self._check_connected()

        async def _read(uuid_short: str, uuid: str) -> str:
            try:
                value = await self._client.read_gatt_char(uuid)
                return value.decode(errors="ignore").strip("\x00")
            except Exception:
                return f"<read failed: {uuid_short}>"

        info = {
            "manufacturer": await _read("2A29", CHAR_MANUFACTURER),
            "model": await _read("2A24", CHAR_MODEL),
            "firmware": await _read("2A26", CHAR_FIRMWARE),
            "hardware": await _read("2A27", CHAR_HARDWARE),
            "software": await _read("2A28", CHAR_SOFTWARE),
            "system_id": await _read("2A23", CHAR_SYSTEM_ID),
            "pnp_id": await _read("2A50", CHAR_PNP_ID),
        }

        try:
            battery_bytes = await self._client.read_gatt_char(CHAR_BATTERY_LEVEL)
            info["battery"] = f"{battery_bytes[0]}%"
        except Exception:
            info["battery"] = "<read failed>"

        return info

    async def subscribe_ffc6(self, callback: Callable[[int, bytes], None]) -> None:
        """Subscribe to FFC6 notification characteristic."""
        self._check_connected()
        await self._client.start_notify(CHAR_FFC6_NOTIFY, callback)

    async def unsubscribe_ffc6(self) -> None:
        """Unsubscribe from FFC6 notification characteristic."""
        self._check_connected()
        await self._client.stop_notify(CHAR_FFC6_NOTIFY)

    def _check_connected(self) -> None:
        """Raise RuntimeError if the client is not connected."""
        if not self.is_connected:
            raise RuntimeError(_NOT_CONNECTED_MSG)
