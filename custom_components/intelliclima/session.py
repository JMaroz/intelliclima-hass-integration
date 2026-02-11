"""HTTP session helpers for Intelliclima integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
from aiohttp.resolver import ThreadedResolver
from homeassistant.helpers.aiohttp_client import async_create_clientsession

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def async_create_intelliclima_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """
    Create a client session using threaded DNS resolver.

    This avoids resolver issues seen with some Python/aiodns combinations in
    custom component environments.
    """
    connector = aiohttp.TCPConnector(resolver=ThreadedResolver())
    return async_create_clientsession(
        hass,
        auto_cleanup=True,
        connector=connector,
    )
