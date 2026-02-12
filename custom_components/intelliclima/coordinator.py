"""DataUpdateCoordinator for Intelliclima."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IntelliclimaApiClientAuthenticationError,
    IntelliclimaApiClientError,
)
from .const import LOGGER
from .data import IntelliclimaCoordinatorData

if TYPE_CHECKING:
    from .data import IntelliclimaConfigEntry


class IntelliclimaDataUpdateCoordinator(
    DataUpdateCoordinator[IntelliclimaCoordinatorData]
):
    """Class to manage fetching Intelliclima API data."""

    config_entry: IntelliclimaConfigEntry

    async def _async_update_data(self) -> IntelliclimaCoordinatorData:
        """Fetch latest devices and states."""
        try:
            devices = await self.config_entry.runtime_data.client.async_get_devices()
            states = {
                str(device.get("id")): device
                for device in devices
                if isinstance(device, dict) and device.get("id") is not None
            }
            LOGGER.debug(
                "Coordinator refresh: devices=%s states=%s", len(devices), len(states)
            )
            return IntelliclimaCoordinatorData(devices=devices, states=states)
        except IntelliclimaApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except IntelliclimaApiClientError as exception:
            raise UpdateFailed(exception) from exception
