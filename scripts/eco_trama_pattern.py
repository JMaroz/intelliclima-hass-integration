#!/usr/bin/env python3
"""Analyze Intelliclima ECO curl captures and infer trama body pattern.

Input: JSON object where each key is a human-friendly name and value is a full curl command.
The script extracts `trama`, decodes key fields, and prints a compact pattern summary.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

TRAMA_RE = re.compile(r'"trama"\s*:\s*"([0-9A-Fa-f]+)"')

MODE_MAP = {
    0x00: "power_off",
    0x01: "outdoor_intake",
    0x02: "indoor_exhaust",
    0x03: "alternating_45s",
    0x04: "alternating_sensor",
}

SPEED_MAP = {
    0x00: "off",
    0x01: "sleep",
    0x02: "vel1",
    0x03: "vel2",
    0x04: "vel3",
    0x10: "auto",
}


def _extract_trama(curl_command: str) -> str | None:
    match = TRAMA_RE.search(curl_command)
    if match:
        return match.group(1).upper()
    return None


def _decode_trama(trama: str) -> dict[str, int | str]:
    if len(trama) < 30:
        msg = f"Unexpected trama length ({len(trama)}): {trama}"
        raise ValueError(msg)

    start = trama[:2]
    serial = trama[6:10]
    fixed_middle = trama[10:24]
    mode = int(trama[24:26], 16)
    speed = int(trama[26:28], 16)
    checksum = trama[28:30]
    end = trama[30:32]

    return {
        "start": start,
        "serial": serial,
        "fixed_middle": fixed_middle,
        "mode": mode,
        "speed": speed,
        "checksum": checksum,
        "end": end,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json_file",
        type=Path,
        help="Path to JSON file containing key->curl mapping",
    )
    args = parser.parse_args()

    payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Input JSON must be an object of key->curl")

    rows: list[tuple[str, str, dict[str, int | str]]] = []
    for name, value in payload.items():
        if not isinstance(value, str):
            continue
        trama = _extract_trama(value)
        if not trama:
            continue
        decoded = _decode_trama(trama)
        rows.append((str(name), trama, decoded))

    if not rows:
        raise SystemExit("No trama found in input JSON")

    starts = Counter(r[2]["start"] for r in rows)
    middles = Counter(r[2]["fixed_middle"] for r in rows)
    ends = Counter(r[2]["end"] for r in rows)

    print("Detected pattern (from observed payloads):")
    print("  trama = <start><0000><serial><fixed_middle><mode><speed><checksum><end>")
    print(f"  start candidates: {dict(starts)}")
    print(f"  fixed_middle candidates: {dict(middles)}")
    print(f"  end candidates: {dict(ends)}")
    print()

    print("Decoded rows:")
    for name, trama, d in rows:
        mode = int(d["mode"])
        speed = int(d["speed"])
        mode_name = MODE_MAP.get(mode, "unknown")
        speed_name = SPEED_MAP.get(speed, "unknown")
        print(
            f"- {name}: serial={d['serial']} mode=0x{mode:02X}({mode_name}) "
            f"speed=0x{speed:02X}({speed_name}) checksum=0x{d['checksum']} trama={trama}"
        )

    print()
    print("Mode byte map (observed):", {f"0x{k:02X}": v for k, v in MODE_MAP.items()})
    print("Speed byte map (observed):", {f"0x{k:02X}": v for k, v in SPEED_MAP.items()})
    print("Note: checksum changes with frame content and must be computed correctly by protocol rules.")


if __name__ == "__main__":
    main()
