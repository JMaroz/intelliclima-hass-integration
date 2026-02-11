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
        self._device_id = str(device.get("id", "unknown"))
        self._serial = str(device.get("crono_sn") or device.get("multi_sn") or "")

        model_value = device.get("model")
        if isinstance(model_value, dict):
            model_name = model_value.get("modello") or model_value.get("tipo")
        else:
            model_name = model_value

        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{self._device_id}_"
            f"{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(coordinator.config_entry.domain, self._device_id)},
            name=device.get("name", f"Intelliclima {self._device_id}"),
            manufacturer="Intelliclima",
            model=model_name,
            serial_number=self._serial or None,
            sw_version=device.get("version"),
        )

    @property
    def _state_data(self) -> dict:
        """Return state payload for the current device."""
        return self.coordinator.data.states.get(self._device_id, self._device)

    @property
    def device_model(self) -> str | None:
        """Return parsed device model."""
        model_value = self._state_data.get("model")
        if isinstance(model_value, dict):
            model = model_value.get("modello")
            if isinstance(model, str):
                return model
        if isinstance(model_value, str):
            return model_value
        return None
