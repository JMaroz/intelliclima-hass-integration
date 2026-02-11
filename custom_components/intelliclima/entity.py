"""Intelliclima base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import IntelliclimaDataUpdateCoordinator


class IntelliclimaEntity(CoordinatorEntity[IntelliclimaDataUpdateCoordinator]):
    """Base Intelliclima entity."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: IntelliclimaDataUpdateCoordinator,
        device: dict,
    ) -> None:
        """Initialize Intelliclima entity."""
        super().__init__(coordinator)
        self._device = device
        self._device_id = str(device.get("id", device.get("device_id", "unknown")))
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{self._device_id}_"
            f"{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(coordinator.config_entry.domain, self._device_id)},
            name=device.get("name", f"Intelliclima {self._device_id}"),
            manufacturer="Intelliclima",
            model=device.get("model") or device.get("type"),
            sw_version=device.get("firmware") or device.get("version"),
        )

    @property
    def _state_data(self) -> dict:
        """Return state payload for the current device."""
        return self.coordinator.data.states.get(self._device_id, {})
