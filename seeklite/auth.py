"""Authentication byte computation for Seek Lite BLE."""

__all__ = ["compute_auth_byte"]


def compute_auth_byte(payload: bytes) -> int:
    """XOR all bytes of the manufacturer advertising payload.

    Matches the logic in ``bus_ble/a.java:b()``.
    """
    result = 0
    for b in payload:
        result ^= b
    return result
