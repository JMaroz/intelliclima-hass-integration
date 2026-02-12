#!/usr/bin/env python3
"""Manual Intelliclima API tester without running Home Assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import aiohttp

from custom_components.intelliclima.api import IntelliclimaApiClient
from custom_components.intelliclima.const import DEFAULT_API_FOLDER, DEFAULT_BASE_URL


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Intelliclima cloud API operations manually without Home Assistant"
        ),
    )
    parser.add_argument("--username", required=True, help="Intelliclima username")
    parser.add_argument("--password", required=True, help="Intelliclima password")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Intelliclima base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--api-folder",
        default=DEFAULT_API_FOLDER,
        help=(
            "API folder path used between host and endpoint "
            "(default: '/'; examples: '/', '/api', '/mono')"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("login", help="Authenticate and print account context")

    devices_parser = subparsers.add_parser(
        "devices",
        help="Fetch all devices available for the account",
    )
    devices_parser.add_argument(
        "--raw",
        action="store_true",
        help="Print full JSON payload for devices",
    )

    device_parser = subparsers.add_parser(
        "device",
        help="Fetch one device by ID using sync/cronos380",
    )
    device_parser.add_argument(
        "--device-id", required=True, help="Intelliclima device ID"
    )

    set_parser = subparsers.add_parser(
        "set",
        help="Set C800WiFi mode and target temperature",
    )
    set_parser.add_argument("--device-id", required=True, help="Intelliclima device ID")
    set_parser.add_argument(
        "--temperature",
        required=True,
        type=float,
        help="Target temperature",
    )
    set_parser.add_argument(
        "--mode",
        required=True,
        choices=("off", "heat", "auto"),
        help="Target HVAC mode",
    )

    return parser


def _device_summary(device: dict[str, Any]) -> dict[str, Any]:
    model = device.get("model")
    if isinstance(model, dict):
        model_name = model.get("modello") or model.get("tipo")
    else:
        model_name = model

    return {
        "id": device.get("id"),
        "name": device.get("name"),
        "model": model_name,
        "serial": device.get("crono_sn") or device.get("multi_sn"),
        "t_amb": device.get("t_amb"),
        "tmanw": device.get("tmanw"),
        "tmans": device.get("tmans"),
        "tset": device.get("tset"),
        "rh": device.get("rh"),
        "outside_temperature": device.get("outside_temperature"),
    }


async def _run(args: argparse.Namespace) -> None:
    async with aiohttp.ClientSession() as session:
        client = IntelliclimaApiClient(
            username=args.username,
            password=args.password,
            base_url=args.base_url,
            api_folder=args.api_folder,
            session=session,
        )

        if args.command == "login":
            await client.async_authenticate()
            data = {
                "authenticated": True,
                "user_id": client._user_id,  # noqa: SLF001
                "house_id": client._house_id,  # noqa: SLF001
                "device_ids": client._device_ids,  # noqa: SLF001
            }
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
            return

        if args.command == "devices":
            devices = await client.async_get_devices()
            if args.raw:
                sys.stdout.write(
                    json.dumps(devices, indent=2, ensure_ascii=False) + "\n"
                )
            else:
                summary = [_device_summary(device) for device in devices]
                sys.stdout.write(
                    json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
                )
            return

        if args.command == "device":
            devices = await client.async_get_device(args.device_id)
            sys.stdout.write(json.dumps(devices, indent=2, ensure_ascii=False) + "\n")
            return

        if args.command == "set":
            devices = await client.async_get_device(args.device_id)
            if not devices:
                msg = f"No device returned for ID {args.device_id}"
                raise RuntimeError(msg)

            device = devices[0]
            model = device.get("model")
            model_name = model.get("modello") if isinstance(model, dict) else model

            serial = str(device.get("crono_sn") or device.get("multi_sn") or "")
            if not serial:
                msg = f"Device {args.device_id} has no serial available"
                raise RuntimeError(msg)

            await client.async_set_c800_state(
                serial=serial,
                target_temperature=args.temperature,
                hvac_mode=args.mode,
                model=model_name,
            )
            sys.stdout.write(
                json.dumps(
                    {
                        "status": "ok",
                        "device_id": args.device_id,
                        "serial": serial,
                        "mode": args.mode,
                        "temperature": args.temperature,
                    },
                    indent=2,
                )
                + "\n"
            )
            return


def main() -> None:
    """Run command line entrypoint."""
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
