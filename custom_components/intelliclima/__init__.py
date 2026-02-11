"""Custom integration to integrate Intelliclima with Home Assistant."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import IntelliclimaApiClient
from .const import (
    CONF_API_FOLDER,
    CONF_BASE_URL,
    DEFAULT_API_FOLDER,
    DEFAULT_BASE_URL,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .coordinator import IntelliclimaDataUpdateCoordinator
from .data import IntelliclimaData


async def async_setup_entry(hass, entry) -> bool:  # noqa: ANN001
    """Set up this integration using UI."""
    coordinator = IntelliclimaDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(minutes=2),
    )

    client = IntelliclimaApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        base_url=entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
        api_folder=entry.data.get(CONF_API_FOLDER, DEFAULT_API_FOLDER),
        session=async_get_clientsession(hass),
    )

    entry.runtime_data = IntelliclimaData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass, entry) -> bool:  # noqa: ANN001
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass, entry) -> None:  # noqa: ANN001
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
