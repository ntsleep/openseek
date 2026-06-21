# Seek Lite BLE Reverse-Engineering

## Project overview

BLE reverse-engineering of the Seek Lite tracker (SFST212, SnappWish LLC). The `seeklite/` package (`python -m seeklite` or `seeklite` CLI command) provides a console app for discovery, authentication, ringing, and monitoring the tracker.

## Key source files

| File | Purpose |
|---|---|
| `seeklite/cli.py` | CLI entry point with subcommands: `ring`, `stop`, `info`, `monitor`, `scan`, `disconnect` |
| `seeklite/client.py` | `SeekLiteClient` — connect, auth, ring, stop, read info, subscribe FFC6, disconnect |
| `seeklite/constants.py` | All GATT UUIDs (custom + standard), auth company ID, alert level values |
| `seeklite/auth.py` | Scan for manufacturer data → XOR bytes[2:] → auth byte |
| `seeklite/ffc6.py` | Parse FFC6 notification packet (flags-based offsets for battery/button/heartbeat) |
| `legacy_scripts/` | Original test scripts (gitignored) |
| `seek_src/sources/com/snappwish/ble/device/j.java` | Official device control class (BF-series firmware) |
| `seek_src/sources/com/snappwish/bus_ble/a.java` | Auth byte computation (`b()` method) + manufacturer data extraction (`c()`/`d()`) |
| `seek_src/sources/com/snappwish/base_ble/utils/b.java` | FFC6 notification parsing helpers (`d`, `e`, `f` methods) |
| `project_decription.md` | Full protocol documentation |

## Commands

```bash
uv run seeklite ring [--duration 3] --address AA:BB:CC:DD:EE:FF
uv run seeklite info --address AA:BB:CC:DD:EE:FF
uv run seeklite monitor --address AA:BB:CC:DD:EE:FF
uv run seeklite scan --address AA:BB:CC:DD:EE:FF
uv run seeklite disconnect --address AA:BB:CC:DD:EE:FF

# Or set env var:
export SEEK_MAC=AA:BB:CC:DD:EE:FF
uv run seeklite ring
```

## Protocol essentials

- **Must authenticate first**: write XOR of manufacturer advertising payload (company ID stripped) to characteristic FFF1 (service FFF0) with `response=True`. Without this, any Immediate Alert or Link Loss write causes device disconnect.
- **Ring**: write `0x02` to UUID 2A06 (service 1802 Immediate Alert), `response=False`. Write `0x00` to stop.
- **Auth byte**: XOR every byte of the manufacturer data payload (after stripping the 2-byte company ID) — matches `bus_ble/a.java:b()`.
- **FFC6 notification**: byte[0] flags (bit 7=extended, bit 6=battery, bit 5=button), subsequent fields shift based on which flags are set.

## Dependencies

- Python >= 3.14
- `bleak` and `python-dotenv` (installed automatically via `uv sync`)

## Decompiled APK source

`seek_src/sources/` is jadx output from `com.snappwish.seek_v92.apk`. The critical class is `com.snappwish.ble.device.j.java` — it holds UUID definitions for all custom characteristics (FFF0–FFF6) and the auth/ring/notification logic.

## Notes

- MAC address: pass `--address` or set `SEEK_MAC` environment variable.
- All GATT operations use stable UUIDs (no handle numbers).
- `legacy_scripts/`, `seek_src/`, `.venv/`, and `*.apk` are gitignored.
