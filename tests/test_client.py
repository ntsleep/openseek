from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from seeklite.client import (
    SeekLiteClient,
    _auth_from_mac,
    _pick_mfg_payload,
)


class TestPickMfgPayload:
    def test_empty_dict(self):
        assert _pick_mfg_payload({}) is None

    def test_single_non_beacon(self):
        result = _pick_mfg_payload({0x6313: b"\x01\xba\x01\x06\xe0\x82"})
        assert result == b"\x01\xba\x01\x06\xe0\x82"

    def test_skips_apple_beacon(self):
        result = _pick_mfg_payload(
            {0x004C: b"\x02\x15xyz", 0x6313: b"\x01\xba\x01\x06\xe0\x82"},
        )
        assert result == b"\x01\xba\x01\x06\xe0\x82"

    def test_returns_first_non_beacon(self):
        result = _pick_mfg_payload(
            {0x004C: b"\x01", 0x00E0: b"\x02", 0x6313: b"\x03"},
        )
        assert result == b"\x03"

    def test_all_beacons_fallback(self):
        result = _pick_mfg_payload({0x004C: b"\x01", 0x00E0: b"\x02"})
        assert result == b"\x01"

    def test_zero_length_payload(self):
        result = _pick_mfg_payload({0x6313: b""})
        assert result == b""


class TestAuthFromMac:
    def test_known_mac(self):
        result = _auth_from_mac("01:BA:01:06:E0:82")
        assert result == 0xDE

    def test_mac_with_lowercase(self):
        result = _auth_from_mac("01:ba:01:06:e0:82")
        assert result == 0xDE

    def test_mac_without_colons(self):
        result = _auth_from_mac("01BA0106E082")
        assert result == 0xDE

    def test_all_zeros_mac(self):
        result = _auth_from_mac("00:00:00:00:00:00")
        assert result == 0

    def test_single_changed_byte(self):
        result = _auth_from_mac("01:BA:01:06:E0:83")
        assert result != 0xDE


class FakeAdvData:
    def __init__(self, mfg: dict[int, bytes]):
        self.manufacturer_data = mfg
        self.rssi = -50


FakeBLEDevice = MagicMock()


class FakeService:
    def __init__(self, uuid: str, chars: dict[int, str]):
        self.uuid = uuid
        self.characteristics = [
            MagicMock(handle=h, uuid=u) for h, u in chars.items()
        ]

    def get_characteristic(self, uuid_spec):
        uuid_spec = str(uuid_spec)
        for c in self.characteristics:
            if str(c.uuid) == uuid_spec:
                return c
        msg = f"Characteristic {uuid_spec} not found"
        raise Exception(msg)


class FakeServices:
    def __init__(self, services: list[FakeService]):
        self._services = {s.uuid: s for s in services}

    def get_service(self, uuid_spec):
        uuid_spec = str(uuid_spec)
        if uuid_spec in self._services:
            return self._services[uuid_spec]
        msg = f"Service {uuid_spec} not found"
        raise Exception(msg)

    def __iter__(self):
        return iter(self._services.values())


@pytest.fixture
def mock_bleak():
    discover_results = {
        "01:ba:01:06:e0:82": (
            FakeBLEDevice,
            FakeAdvData({0x6313: b"\x01\xba\x01\x06\xe0\x82"}),
        ),
    }
    fake_services = FakeServices(
        [
            FakeService("00001802-0000-1000-8000-00805f9b34fb", {14: "00002a06-0000-1000-8000-00805f9b34fb"}),
            FakeService("0000fff0-0000-1000-8000-00805f9b34fb", {39: "0000fff1-0000-1000-8000-00805f9b34fb"}),
            FakeService("0000ffc0-0000-1000-8000-00805f9b34fb", {58: "0000ffc6-0000-1000-8000-00805f9b34fb"}),
            FakeService("0000180f-0000-1000-8000-00805f9b34fb", {20: "00002a19-0000-1000-8000-00805f9b34fb"}),
            FakeService("0000180a-0000-1000-8000-00805f9b34fb", {
                24: "00002a29-0000-1000-8000-00805f9b34fb",
                26: "00002a24-0000-1000-8000-00805f9b34fb",
                30: "00002a26-0000-1000-8000-00805f9b34fb",
            }),
        ],
    )

    mock_client = AsyncMock()
    mock_client.is_connected = True
    mock_client.services = fake_services
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.write_gatt_char = AsyncMock()
    mock_client.read_gatt_char = AsyncMock(return_value=b"\x58")
    mock_client.start_notify = AsyncMock()
    mock_client.stop_notify = AsyncMock()

    with (
        patch("seeklite.client.BleakScanner.discover", return_value=discover_results),
        patch("seeklite.client.BleakClient", return_value=mock_client),
    ):
        yield mock_client


@pytest.mark.asyncio
async def test_connect_with_scan(mock_bleak):
    client = SeekLiteClient("01:BA:01:06:E0:82")
    await client.connect()
    assert client.is_connected
    assert client._alert_handle == 14
    mock_bleak.connect.assert_awaited_once()
    mock_bleak.write_gatt_char.assert_awaited()
    mock_bleak.start_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_fallback_to_mac(mock_bleak):
    mock_bleak.services = FakeServices(
        [
            FakeService("00001802-0000-1000-8000-00805f9b34fb", {14: "00002a06-0000-1000-8000-00805f9b34fb"}),
            FakeService("0000fff0-0000-1000-8000-00805f9b34fb", {39: "0000fff1-0000-1000-8000-00805f9b34fb"}),
            FakeService("0000ffc0-0000-1000-8000-00805f9b34fb", {58: "0000ffc6-0000-1000-8000-00805f9b34fb"}),
        ],
    )
    with patch("seeklite.client.BleakScanner.discover", return_value={}):
        client = SeekLiteClient("01:BA:01:06:E0:82")
        await client.connect()
        assert client.is_connected


@pytest.mark.asyncio
async def test_ring(mock_bleak):
    from uuid import UUID

    client = SeekLiteClient("01:BA:01:06:E0:82")
    await client.connect()
    await client.ring(0.1)
    mock_bleak.write_gatt_char.assert_any_call(14, bytearray([0x02]), response=False)
    mock_bleak.read_gatt_char.assert_any_call(UUID("00002a19-0000-1000-8000-00805f9b34fb"))


@pytest.mark.asyncio
async def test_stop(mock_bleak):
    client = SeekLiteClient("01:BA:01:06:E0:82")
    await client.connect()
    await client.stop()
    mock_bleak.write_gatt_char.assert_any_call(14, bytearray([0x00]), response=False)


@pytest.mark.asyncio
async def test_read_info(mock_bleak):
    from seeklite.constants import CHAR_MANUFACTURER

    mock_bleak.read_gatt_char.return_value = b"zenlyfe"
    client = SeekLiteClient("01:BA:01:06:E0:82")
    await client.connect()
    info = await client.read_info()
    assert info["manufacturer"] == "zenlyfe"
    mock_bleak.read_gatt_char.assert_any_call(CHAR_MANUFACTURER)


@pytest.mark.asyncio
async def test_disconnect(mock_bleak):
    client = SeekLiteClient("01:BA:01:06:E0:82")
    await client.connect()
    await client.disconnect()
    mock_bleak.stop_notify.assert_awaited_once()
    mock_bleak.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_ring_raises_if_not_connected():
    client = SeekLiteClient("01:BA:01:06:E0:82")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.ring(1)


@pytest.mark.asyncio
async def test_stop_raises_if_not_connected():
    client = SeekLiteClient("01:BA:01:06:E0:82")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.stop()


@pytest.mark.asyncio
async def test_read_info_raises_if_not_connected():
    client = SeekLiteClient("01:BA:01:06:E0:82")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.read_info()
