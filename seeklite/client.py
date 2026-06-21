import asyncio
from bleak import BleakClient, BleakScanner

from seeklite.auth import compute_auth_byte
from seeklite.constants import (
    CHAR_FFF1_AUTH,
    CHAR_ALERT_LEVEL,
    CHAR_BATTERY_LEVEL,
    CHAR_MANUFACTURER,
    CHAR_MODEL,
    CHAR_FIRMWARE,
    CHAR_HARDWARE,
    CHAR_SOFTWARE,
    CHAR_SYSTEM_ID,
    CHAR_PNP_ID,
    CHAR_FFC6_NOTIFY,
    SERVICE_IMMEDIATE_ALERT,
    HEARTBEAT_INTERVAL,
    ALERT_HIGH,
    ALERT_NONE,
)

_BEACON_IDS = {0x004C, 0x00E0, 0x00FF, 0x0130, 0x0157, 0x018B, 0x01AC}


def _pick_mfg_payload(mfg: dict[int, bytes]) -> bytes | None:
    if not mfg:
        return None
    for cid, payload in mfg.items():
        if cid not in _BEACON_IDS:
            return payload
    return next(iter(mfg.values()))


def _auth_from_mac(address: str) -> int:
    raw = bytes.fromhex(address.replace(":", ""))
    return compute_auth_byte(raw)


class SeekLiteClient:
    def __init__(self, address: str):
        self.address = address
        self._client: BleakClient | None = None
        self._alert_handle: int | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self, scan_timeout: float = 5.0) -> None:
        devices = await BleakScanner.discover(
            timeout=min(scan_timeout, 1.0), return_adv=True
        )
        auth_byte = None
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
            CHAR_FFF1_AUTH, bytearray([auth_byte]), response=True
        )
        await asyncio.sleep(0.5)

        svc = self._client.services.get_service(SERVICE_IMMEDIATE_ALERT)
        self._alert_handle = svc.get_characteristic(CHAR_ALERT_LEVEL).handle

        await self._client.start_notify(CHAR_FFC6_NOTIFY, lambda s, d: None)
        await asyncio.sleep(0.5)

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(CHAR_FFC6_NOTIFY)
            except Exception:
                pass
            await self._client.disconnect()
        self._client = None

    async def ring(self, duration: float = 3.0) -> None:
        self._check_connected()
        await self._client.write_gatt_char(
            self._alert_handle, bytearray([ALERT_HIGH]), response=False
        )
        await self._client.read_gatt_char(CHAR_BATTERY_LEVEL)
        await asyncio.sleep(duration)

    async def stop(self) -> None:
        self._check_connected()
        try:
            await self._client.write_gatt_char(
                self._alert_handle, bytearray([ALERT_NONE]), response=False
            )
        except Exception:
            pass

    async def read_info(self) -> dict[str, str]:
        self._check_connected()

        async def _read(short, uuid):
            try:
                val = await self._client.read_gatt_char(uuid)
                return val.decode(errors="ignore").strip("\x00")
            except Exception:
                return f"<read failed: {short}>"

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

    async def subscribe_ffc6(self, callback) -> None:
        self._check_connected()
        await self._client.start_notify(CHAR_FFC6_NOTIFY, callback)

    async def unsubscribe_ffc6(self) -> None:
        self._check_connected()
        await self._client.stop_notify(CHAR_FFC6_NOTIFY)

    def _check_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("Not connected. Call connect() first.")
