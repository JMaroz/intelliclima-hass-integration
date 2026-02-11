"""HTTP session helpers for Intelliclima integration."""

from __future__ import annotations

import aiohttp
from aiohttp.resolver import ThreadedResolver


def create_intelliclima_session() -> aiohttp.ClientSession:
    """Create a client session using threaded DNS resolver."""
    connector = aiohttp.TCPConnector(resolver=ThreadedResolver())
    return aiohttp.ClientSession(connector=connector)
