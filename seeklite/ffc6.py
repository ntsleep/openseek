"""Parse FFC6 notification packets from the Seek Lite tracker."""


def parse_ffc6_packet(data: bytes) -> dict[str, int | None]:
    """Parse a single FFC6 notification payload.

    Byte 0 is a bit field:
      - bit 7: extended data present (heartbeat loss)
      - bit 6: battery level present
      - bit 5: button state present

    Subsequent fields appear in order and shift based on which flags are set.
    """
    result: dict[str, int | None] = {
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

    index = 1

    if has_extended and len(data) > index:
        result["heartbeat_loss"] = data[index]
        index += 1

    if has_battery and len(data) > index:
        result["battery"] = data[index]
        index += 1

    if has_button and len(data) > index:
        result["button_state"] = data[index]
        index += 1

    return result
