# Seek Lite BLE Reverse-Engineering

## Project overview

BLE reverse-engineering of the Seek Lite tracker (SFST212, SnappWish LLC). The `seeklite/` package (`python -m seeklite` or `seeklite` CLI command) provides a console app for discovery, authentication, ringing, and monitoring the tracker.

## Key source files

| File | Purpose |
|---|---|
| `seeklite/cli.py` | CLI entry point with subcommands: `ring`, `stop`, `info`, `monitor`, `scan`, `discover`, `disconnect` |
| `seeklite/client.py` | `SeekLiteClient` — connect(scan_timeout, on_notify), auth, ring (auto-stop), stop, read_info (`str | None`), subscribe_ffc6 (handler-only, no re-subscribe), disconnect, discover |
| `seeklite/constants.py` | All GATT UUIDs (custom + standard), auth company ID, alert level values |
| `seeklite/auth.py` | XOR raw manufacturer payload (Bleak strips company ID) → auth byte |
| `seeklite/ffc6.py` | Parse FFC6 notification packet (flags-based offsets for battery/button/heartbeat) |
| `project_description.md` | Full protocol documentation |

## Commands

```bash
uv run seeklite ring [--duration 3] --address AA:BB:CC:DD:EE:FF
uv run seeklite info --address AA:BB:CC:DD:EE:FF
uv run seeklite monitor --address AA:BB:CC:DD:EE:FF
uv run seeklite scan --address AA:BB:CC:DD:EE:FF
uv run seeklite discover [--timeout 10]
uv run seeklite disconnect --address AA:BB:CC:DD:EE:FF

# Or set env var:
export SEEK_MAC=AA:BB:CC:DD:EE:FF
uv run seeklite ring
```

## Protocol essentials

- **Must authenticate first**: write XOR of manufacturer advertising payload (company ID stripped) to characteristic FFF1 (service FFF0) with `response=True`. Without this, any Immediate Alert or Link Loss write causes device disconnect.
- **Ring**: write `0x02` to UUID 2A06 (service 1802 Immediate Alert), `response=False`. Write `0x00` to stop. `ring(duration)` auto-stops after sleeping.
- **Auth byte**: XOR every byte of the manufacturer data payload (Bleak strips the 2-byte company ID from the raw BLE packet, so the payload is already without company ID).
- **FFC6 notification**: byte[0] flags (bit 7=extended, bit 6=battery, bit 5=button), subsequent fields shift based on which flags are set.

## Dependencies

- Python >= 3.14
- `bleak` and `python-dotenv` (installed automatically via `uv sync`)

## Quality checks

- **Ruff**: always run `uvx --isolated ruff check --no-cache .` after any code changes and fix all errors.
- **Tests**: always write tests for new functionality and update tests for changed functionality. Run full suite with `uv run pytest tests/`.
- **Test style**: follow existing patterns — use `unittest.mock.patch` for mocking BLE, `capsys` for output assertions, parenthesized `with` for context managers, and pytest-asyncio with `asyncio_mode = auto`.
- **README**: always update `README.md` when adding new functionality (commands, features, options). Otherwise a stale README misleads users.

## Notes

- MAC address: pass `--address` or set `SEEK_MAC` environment variable.
- UUID 2A06 (Alert Level) is shared between Immediate Alert (1802) and Link Loss (1803) services. Bleak cannot resolve it by UUID alone — the handle is resolved from `SERVICE_IMMEDIATE_ALERT` during `connect()` and cached. All ring/stop writes use the handle, not the UUID.
- `connect()` subscribes to FFC6 notifications once with a wrapper that delegates to an internal callback. `subscribe_ffc6(handler)` only updates the callback without re-subscribing.
- `read_info()` returns `dict[str, str | None]` — failed reads yield `None`, not error strings.
- `disconnect()` clears `_alert_handle` and the FFC6 handler.
- `legacy_scripts/`, `seek_src/`, `.venv/`, and `*.apk` are gitignored.
