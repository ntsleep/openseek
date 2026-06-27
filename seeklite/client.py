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

__all__ = ["SeekLiteClient"]

_BEACON_IDS = {0x004C, 0x00E0, 0x00FF, 0x0130, 0x0157, 0x018B, 0x01AC}

_NOT_CONNECTED_MSG = "Not connected. Call connect() first."

# BLE settling delays — the device needs a short pause after auth write
# and after enabling notifications before the next operation.
_POST_AUTH_DELAY = 0.1
_POST_SUBSCRIBE_DELAY = 0.2


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

    @staticmethod
    async def discover(
        scan_timeout: float = 10.0,
    ) -> list[tuple[str, int, str | None, dict[int, bytes]]]:
        """Scan for all BLE devices and return their details.

        Returns a list of ``(address, rssi, name, manufacturer_data)`` tuples.
        """
        devices = await BleakScanner.discover(timeout=scan_timeout, return_adv=True)
        result: list[tuple[str, int, str | None, dict[int, bytes]]] = []
        for addr, (_device, adv_data) in sorted(devices.items()):
            result.append((addr, adv_data.rssi, _device.name, adv_data.manufacturer_data))
        return result

    def __init__(self, address: str) -> None:
        """Initialize the client with a tracker MAC address."""
        self.address = address
        self._client: BleakClient | None = None
        self._alert_handle: int | None = None
        self._ffc6_handler: Callable[[int, bytes], None] | None = None

    @property
    def is_connected(self) -> bool:
        """Whether the underlying BLE client is connected."""
        return self._client is not None and self._client.is_connected

    async def connect(
        self,
        scan_timeout: float = 5.0,
        on_notify: Callable[[int, bytes], None] | None = None,
    ) -> None:
        """Scan, authenticate, and subscribe to FFC6 notifications.

        Falls back to MAC-derived auth byte if the tracker is not found
        in scan results. The scan phase is capped at 1s since it only
        looks for manufacturer data — a full-length scan is unnecessary
        and would delay connection.

        If *on_notify* is provided it will be set as the initial FFC6
        notification handler; otherwise no-ops until ``subscribe_ffc6()``
        is called.
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

        self._ffc6_handler = on_notify

        self._client = BleakClient(self.address)
        await self._client.connect()
        await self._client.write_gatt_char(
            CHAR_FFF1_AUTH, bytearray([auth_byte]), response=True,
        )
        await asyncio.sleep(_POST_AUTH_DELAY)

        service = self._client.services.get_service(SERVICE_IMMEDIATE_ALERT)
        self._alert_handle = service.get_characteristic(CHAR_ALERT_LEVEL).handle

        def _notify_wrapper(sender: int, data: bytes) -> None:
            if self._ffc6_handler is not None:
                self._ffc6_handler(sender, data)

        await self._client.start_notify(CHAR_FFC6_NOTIFY, _notify_wrapper)
        await asyncio.sleep(_POST_SUBSCRIBE_DELAY)

    async def disconnect(self) -> None:
        """Unsubscribe from notifications and disconnect."""
        if self._client and self._client.is_connected:
            with contextlib.suppress(Exception):
                await self._client.stop_notify(CHAR_FFC6_NOTIFY)
            await self._client.disconnect()
        self._client = None
        self._alert_handle = None
        self._ffc6_handler = None

    async def ring(self, duration: float = 3.0) -> None:
        """Ring the tracker for *duration* seconds, then stop automatically."""
        self._check_connected()
        await self._client.write_gatt_char(
            self._alert_handle, bytearray([ALERT_HIGH]), response=False,
        )
        await asyncio.sleep(duration)
        # device may disconnect during sleep — suppress so the caller isn't
        # presented with a confusing RuntimeError after a successful ring
        with contextlib.suppress(RuntimeError):
            await self.stop()

    async def stop(self) -> None:
        """Stop the active alert immediately."""
        self._check_connected()
        with contextlib.suppress(Exception):
            await self._client.write_gatt_char(
                self._alert_handle, bytearray([ALERT_NONE]), response=False,
            )

    async def read_info(self) -> dict[str, str | None]:
        """Read device information characteristics and battery level.

        Returns ``None`` for any characteristic that could not be read.
        """
        self._check_connected()

        async def _read(uuid: str) -> str | None:
            try:
                value = await self._client.read_gatt_char(uuid)
                return value.decode(errors="ignore").strip("\x00")
            except Exception:
                return None

        info: dict[str, str | None] = {
            "manufacturer": await _read(CHAR_MANUFACTURER),
            "model": await _read(CHAR_MODEL),
            "firmware": await _read(CHAR_FIRMWARE),
            "hardware": await _read(CHAR_HARDWARE),
            "software": await _read(CHAR_SOFTWARE),
            "system_id": await _read(CHAR_SYSTEM_ID),
            "pnp_id": await _read(CHAR_PNP_ID),
        }

        try:
            battery_bytes = await self._client.read_gatt_char(CHAR_BATTERY_LEVEL)
            info["battery"] = f"{battery_bytes[0]}%"
        except Exception:
            info["battery"] = None

        return info

    async def subscribe_ffc6(self, callback: Callable[[int, bytes], None]) -> None:
        """Register an FFC6 notification handler.

        The subscription is already active from ``connect()`` — this only
        replaces the callback without re-subscribing.
        """
        self._check_connected()
        self._ffc6_handler = callback

    async def unsubscribe_ffc6(self) -> None:
        """Unsubscribe from FFC6 notification characteristic and clear the handler."""
        self._check_connected()
        await self._client.stop_notify(CHAR_FFC6_NOTIFY)
        self._ffc6_handler = None

    def _check_connected(self) -> None:
        """Raise RuntimeError if the client is not connected."""
        if not self.is_connected:
            raise RuntimeError(_NOT_CONNECTED_MSG)
