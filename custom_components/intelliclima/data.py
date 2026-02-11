"""Custom types for Intelliclima."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aiohttp
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import IntelliclimaApiClient
    from .coordinator import IntelliclimaDataUpdateCoordinator

    IntelliclimaConfigEntry = ConfigEntry["IntelliclimaData"]


@dataclass
class IntelliclimaData:
    """Runtime data for Intelliclima."""

    client: IntelliclimaApiClient
    coordinator: IntelliclimaDataUpdateCoordinator
    integration: Integration
    session: aiohttp.ClientSession


@dataclass
class IntelliclimaCoordinatorData:
    """Data returned by the coordinator."""

    devices: list[dict[str, Any]]
    states: dict[str, dict[str, Any]]
