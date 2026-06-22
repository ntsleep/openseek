"""CLI entry point for the Seek Lite tracker."""
import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

from bleak import BleakScanner
from dotenv import load_dotenv

from seeklite.client import SeekLiteClient
from seeklite.ffc6 import parse_ffc6_packet


def _get_address(args: argparse.Namespace) -> str:
    """Resolve the tracker MAC address from CLI flag, env var, or exit."""
    addr = args.address or os.environ.get("SEEK_MAC")
    if not addr:
        print("error: provide --address, set SEEK_MAC in .env, or export SEEK_MAC")
        sys.exit(1)
    return addr


async def _cmd_ring(args: argparse.Namespace) -> None:
    address = _get_address(args)
    client = SeekLiteClient(address)
    try:
        print("Connecting and authenticating...")
        await client.connect()
        print("Connected. Ringing...")
        await client.ring(args.duration)
        print("Stopped.")
    finally:
        await client.disconnect()


async def _cmd_stop(args: argparse.Namespace) -> None:
    address = _get_address(args)
    client = SeekLiteClient(address)
    try:
        print("Connecting and authenticating...")
        await client.connect()
        print("Stopping alert...")
        await client.stop()
        print("Done.")
    finally:
        await client.disconnect()


async def _cmd_info(args: argparse.Namespace) -> None:
    address = _get_address(args)
    client = SeekLiteClient(address)
    try:
        print("Connecting and authenticating...")
        await client.connect()
        print("\nDevice Info:")
        print("------------")
        info = await client.read_info()
        for key, value in info.items():
            print(f"  {key}: {value}")
    finally:
        await client.disconnect()


async def _cmd_monitor(args: argparse.Namespace) -> None:
    address = _get_address(args)
    client = SeekLiteClient(address)
    try:
        print("Connecting and authenticating...")
        await client.connect()
        print("Subscribed to FFC6 notifications. Press Ctrl+C to stop.\n")

        def handler(_sender: int, data: bytes) -> None:
            parsed = parse_ffc6_packet(data)
            parts = []
            for k, v in parsed.items():
                if v is not None:
                    parts.append(f"{k}={v}")
            print(f"  [{data.hex()}] " + ", ".join(parts))

        await client.subscribe_ffc6(handler)

        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            stop_event.set()

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)

        await stop_event.wait()
    finally:
        await client.unsubscribe_ffc6()
        await client.disconnect()
        print("\nDisconnected.")


async def _cmd_scan(args: argparse.Namespace) -> None:
    address = _get_address(args)

    print(f"Scanning for {args.timeout} seconds...")
    devices = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
    for addr, (_device, adv_data) in devices.items():
        if addr.lower() == address.lower():
            print("Tracker is advertising!")
            print(f"  RSSI: {adv_data.rssi}")
            print(f"  Manufacturer data: {adv_data.manufacturer_data}")
            return
    print("Tracker not seen advertising.")


async def _cmd_disconnect(args: argparse.Namespace) -> None:
    address = _get_address(args)
    client = SeekLiteClient(address)
    try:
        print("Connecting and authenticating...")
        await client.connect()
        print("Disconnecting...")
        await client.disconnect()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")


def main() -> None:
    """Parse arguments and dispatch to the appropriate command handler."""
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Seek Lite tracker CLI")
    parser.add_argument(
        "--address",
        help="Tracker MAC address (default: SEEK_MAC env var or .env file)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_ring = sub.add_parser("ring", help="Ring the tracker for N seconds")
    p_ring.add_argument(
        "--duration", "-d", type=float, default=3.0, help="Ring duration in seconds",
    )
    p_ring.set_defaults(func=_cmd_ring)

    p_stop = sub.add_parser("stop", help="Stop an active alert")
    p_stop.set_defaults(func=_cmd_stop)

    p_info = sub.add_parser("info", help="Read device information and battery")
    p_info.set_defaults(func=_cmd_info)

    p_monitor = sub.add_parser("monitor", help="Subscribe to FFC6 notifications")
    p_monitor.set_defaults(func=_cmd_monitor)

    p_scan = sub.add_parser("scan", help="Check if tracker is advertising")
    p_scan.add_argument(
        "--timeout", "-t", type=int, default=10, help="Scan duration in seconds",
    )
    p_scan.set_defaults(func=_cmd_scan)

    p_disc = sub.add_parser("disconnect", help="Force-disconnect a stuck connection")
    p_disc.set_defaults(func=_cmd_disconnect)

    args = parser.parse_args()
    asyncio.run(args.func(args))
