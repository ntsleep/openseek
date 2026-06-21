from typing import Optional


def parse_ffc6_packet(data: bytes) -> dict[str, Optional[int]]:
    result: dict[str, Optional[int]] = {
        "heartbeat_loss": None,
        "battery": None,
        "button_state": None,
    }

    if not data:
        return result

    flags = data[0]
    has_extended = bool(flags & 0x80)
    has_battery = bool(flags & 0x40)
    has_button = bool(flags & 0x20)

    idx = 1

    if has_extended:
        if len(data) > idx:
            result["heartbeat_loss"] = data[idx]
            idx += 1

    if has_battery:
        if len(data) > idx:
            result["battery"] = data[idx]
            idx += 1

    if has_button:
        if len(data) > idx:
            result["button_state"] = data[idx]
            idx += 1

    return result
