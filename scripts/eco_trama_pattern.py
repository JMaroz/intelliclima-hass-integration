"""
Analyze Intelliclima ECO curl captures and infer trama body pattern.

Input: JSON object where each key is a human-friendly name and value is a
full curl command. The script extracts `trama`, decodes key fields, and logs a
compact pattern summary.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
TRAMA_RE = re.compile(r'"trama"\s*:\s*"([0-9A-Fa-f]+)"')
MIN_TRAMA_LENGTH = 30

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
    """Extract trama hex payload from a curl command string."""
    match = TRAMA_RE.search(curl_command)
    if match:
        return match.group(1).upper()
    return None


def _decode_trama(trama: str) -> dict[str, int | str]:
    """Decode relevant fields from trama payload."""
    if len(trama) < MIN_TRAMA_LENGTH:
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


def _build_summary(rows: list[tuple[str, str, dict[str, int | str]]]) -> str:
    """Build a text summary for decoded rows and observed pattern."""
    starts = Counter(r[2]["start"] for r in rows)
    middles = Counter(r[2]["fixed_middle"] for r in rows)
    ends = Counter(r[2]["end"] for r in rows)

    lines = [
        "Detected pattern (from observed payloads):",
        "  trama = <start><0000><serial><fixed_middle><mode><speed><checksum><end>",
        f"  start candidates: {dict(starts)}",
        f"  fixed_middle candidates: {dict(middles)}",
        f"  end candidates: {dict(ends)}",
        "",
        "Decoded rows:",
    ]

    for name, trama, decoded in rows:
        mode = int(decoded["mode"])
        speed = int(decoded["speed"])
        mode_name = MODE_MAP.get(mode, "unknown")
        speed_name = SPEED_MAP.get(speed, "unknown")
        lines.append(
            f"- {name}: serial={decoded['serial']} mode=0x{mode:02X}({mode_name}) "
            f"speed=0x{speed:02X}({speed_name}) checksum=0x{decoded['checksum']}"
            f" trama={trama}"
        )

    mode_map = {f"0x{k:02X}": v for k, v in MODE_MAP.items()}
    speed_map = {f"0x{k:02X}": v for k, v in SPEED_MAP.items()}
    lines.extend(
        [
            "",
            f"Mode byte map (observed): {mode_map}",
            f"Speed byte map (observed): {speed_map}",
            "Note: checksum changes with frame content and must be computed",
            "correctly by protocol rules.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Parse input payload and log inferred trama pattern details."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json_file",
        type=Path,
        help="Path to JSON file containing key->curl mapping",
    )
    args = parser.parse_args()

    payload: Any = json.loads(args.json_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = "Input JSON must be an object of key->curl"
        raise SystemExit(msg)

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
        msg = "No trama found in input JSON"
        raise SystemExit(msg)

    LOGGER.info(_build_summary(rows))


if __name__ == "__main__":
    main()
