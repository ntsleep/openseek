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
        result = _pick_mfg_payload({0x6313: b"\xde\xad\xbe\xef\xca\xfe"})
        assert result == b"\xde\xad\xbe\xef\xca\xfe"

    def test_skips_apple_beacon(self):
        result = _pick_mfg_payload(
            {0x004C: b"\x02\x15xyz", 0x6313: b"\xde\xad\xbe\xef\xca\xfe"},
        )
        assert result == b"\xde\xad\xbe\xef\xca\xfe"

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
        result = _auth_from_mac("AA:BB:CC:DD:EE:FF")
        assert result == 0x11

    def test_mac_with_lowercase(self):
        result = _auth_from_mac("aa:bb:cc:dd:ee:ff")
        assert result == 0x11

    def test_mac_without_colons(self):
        result = _auth_from_mac("AABBCCDDEEFF")
        assert result == 0x11

    def test_all_zeros_mac(self):
        result = _auth_from_mac("00:00:00:00:00:00")
        assert result == 0

    def test_single_changed_byte(self):
        result = _auth_from_mac("AA:BB:CC:DD:EE:FE")
        assert result != 0x11


class FakeAdvData:
    def __init__(self, mfg: dict[int, bytes]):
        self.manufacturer_data = mfg
        self.rssi = -50


class FakeCharacteristic:
    def __init__(self, handle: int, uuid: str):
        self.handle = handle
        self.uuid = uuid


class FakeService:
    def __init__(self, uuid: str, chars: dict[int, str]):
        self.uuid = uuid
        self.characteristics = [
            FakeCharacteristic(handle=h, uuid=u) for h, u in chars.items()
        ]

    def get_characteristic(self, uuid_spec: str) -> FakeCharacteristic:
        uuid_spec = str(uuid_spec)
        for c in self.characteristics:
            if str(c.uuid) == uuid_spec:
                return c
        msg = f"Characteristic {uuid_spec} not found"
        raise Exception(msg)


class FakeServices:
    def __init__(self, services: list[FakeService]):
        self._services = {s.uuid: s for s in services}

    def get_service(self, uuid_spec: str) -> FakeService:
        uuid_spec = str(uuid_spec)
        if uuid_spec in self._services:
            return self._services[uuid_spec]
        msg = f"Service {uuid_spec} not found"
        raise Exception(msg)

    def __iter__(self):
        return iter(self._services.values())


@pytest.fixture
def mock_bleak():
    device = MagicMock()
    discover_results = {
        "aa:bb:cc:dd:ee:ff": (
            device,
            FakeAdvData({0x6313: b"\xde\xad\xbe\xef\xca\xfe"}),
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


async def test_connect_with_scan(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    assert client.is_connected
    assert client._alert_handle == 14
    mock_bleak.connect.assert_awaited_once()
    mock_bleak.write_gatt_char.assert_awaited()
    mock_bleak.start_notify.assert_awaited_once()


@pytest.mark.usefixtures("mock_bleak")
async def test_connect_fallback_to_mac():
    # override fixture's discover to simulate tracker not found in scan
    with patch("seeklite.client.BleakScanner.discover", return_value={}):
        client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
        await client.connect()
        assert client.is_connected


async def test_ring(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    await client.ring(0.1)
    mock_bleak.write_gatt_char.assert_any_call(14, bytearray([0x02]), response=False)


async def test_stop(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    await client.stop()
    mock_bleak.write_gatt_char.assert_any_call(14, bytearray([0x00]), response=False)


async def test_read_info(mock_bleak):
    from seeklite.constants import CHAR_MANUFACTURER

    mock_bleak.read_gatt_char.return_value = b"zenlyfe"
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    info = await client.read_info()
    assert info["manufacturer"] == "zenlyfe"
    mock_bleak.read_gatt_char.assert_any_call(CHAR_MANUFACTURER)


async def test_disconnect(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    await client.disconnect()
    mock_bleak.stop_notify.assert_awaited_once()
    mock_bleak.disconnect.assert_awaited_once()
    assert client._alert_handle is None
    assert client._ffc6_handler is None


@pytest.mark.usefixtures("mock_bleak")
async def test_disconnect_resets_alert_handle():
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    assert client._alert_handle == 14

    def _noop(_s: int, _d: bytes) -> None: ...

    client._ffc6_handler = _noop
    await client.disconnect()
    assert client._alert_handle is None
    assert client._ffc6_handler is None


async def test_connect_with_on_notify(mock_bleak):
    captured: list[tuple[int, bytes]] = []

    def handler(sender: int, data: bytes) -> None:
        captured.append((sender, data))

    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect(on_notify=handler)
    assert client._ffc6_handler is handler

    notify_callback = mock_bleak.start_notify.call_args[0][1]
    notify_callback(5, b"\x60\x32")
    assert captured == [(5, b"\x60\x32")]


async def test_ring_stops_automatically(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    await client.ring(0.1)
    mock_bleak.write_gatt_char.assert_any_call(14, bytearray([0x02]), response=False)
    mock_bleak.write_gatt_char.assert_any_call(14, bytearray([0x00]), response=False)


async def test_subscribe_ffc6_updates_handler(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()

    notify_wrapper = mock_bleak.start_notify.call_args[0][1]
    mock_bleak.start_notify.reset_mock()

    results: list[int] = []

    def handler_a(_s: int, _d: bytes) -> None:
        results.append(1)

    def handler_b(_s: int, _d: bytes) -> None:
        results.append(2)

    await client.subscribe_ffc6(handler_a)
    assert client._ffc6_handler is handler_a
    mock_bleak.start_notify.assert_not_called()

    await client.subscribe_ffc6(handler_b)
    assert client._ffc6_handler is handler_b

    notify_wrapper(5, b"\x60")
    assert results == [2]


async def test_read_info_failure_returns_none(mock_bleak):
    def fail_once(_uuid: str) -> bytes:
        msg = "disconnected"
        raise Exception(msg)

    mock_bleak.read_gatt_char = AsyncMock(side_effect=fail_once)
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    info = await client.read_info()
    assert info["manufacturer"] is None
    assert info["battery"] is None


async def test_ring_raises_if_not_connected():
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.ring(1)


async def test_stop_raises_if_not_connected():
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.stop()


async def test_read_info_raises_if_not_connected():
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.read_info()


async def test_unsubscribe_ffc6(mock_bleak):
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    await client.connect()
    assert client._ffc6_handler is None  # no on_notify was passed

    def handler(_s: int, _d: bytes) -> None: ...
    await client.subscribe_ffc6(handler)
    assert client._ffc6_handler is handler

    mock_bleak.stop_notify.reset_mock()
    await client.unsubscribe_ffc6()
    mock_bleak.stop_notify.assert_awaited_once()

    # unsubscribe stops the Bleak subscription but does NOT clear the handler
    assert client._ffc6_handler is handler


async def test_unsubscribe_ffc6_raises_if_not_connected():
    client = SeekLiteClient("AA:BB:CC:DD:EE:FF")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.unsubscribe_ffc6()
