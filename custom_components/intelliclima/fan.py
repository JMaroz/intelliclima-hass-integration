"""
Fan platform for Intelliclima ECOCOMFORT devices.

This entity intentionally exposes only fan state and attributes.
Mode and speed writes are handled by dedicated Select entities to provide a
clear dropdown UX in Home Assistant frontend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)

from .entity import IntelliclimaEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import IntelliclimaDataUpdateCoordinator
    from .data import IntelliclimaConfigEntry

MIN_NATIVE_FAN_LEVEL = 0
MAX_NATIVE_FAN_LEVEL = 4
TRANSLATED_FAN_LEVEL_MIN = 16
TRANSLATED_FAN_LEVEL_MAX = 19
TRANSLATED_FAN_LEVEL_OFFSET = 15


ENTITY_DESCRIPTION = FanEntityDescription(
    key="ecocomfort_fan",
    name="Ventilation",
    icon="mdi:fan",
)


def _is_eco_device(device: dict[str, Any]) -> bool:
    """Return True if device model is ECO."""
    model = device.get("model")
    if isinstance(model, dict):
        return str(model.get("modello")) == "ECO"
    return False


async def async_setup_entry(
    hass,  # noqa: ANN001, ARG001
    entry: IntelliclimaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelliclima fan entities."""
    async_add_entities(
        IntelliclimaEcoComfortFan(
            entry.runtime_data.coordinator, device, ENTITY_DESCRIPTION
        )
        for device in entry.runtime_data.coordinator.data.devices
        if _is_eco_device(device)
    )


class IntelliclimaEcoComfortFan(IntelliclimaEntity, FanEntity):
    """Intelliclima ECOCOMFORT fan entity."""

    _attr_supported_features = FanEntityFeature(0)

    def __init__(
        self,
        coordinator: IntelliclimaDataUpdateCoordinator,
        device: dict[str, Any],
        entity_description: FanEntityDescription,
    ) -> None:
        """Initialize ECOCOMFORT fan entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, device)
        self._attr_name = f"{self.device_display_name} Ventilation"

    @staticmethod
    def _to_int(value: Any) -> int | None:
        """Convert value to integer."""
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _fan_level(self) -> int | None:
        """Return normalized native fan level from 0..4."""
        speed_state = self._state_data.get("speed_state") or self._state_data.get(
            "speed_set"
        )
        speed = self._to_int(speed_state)
        if speed is None:
            return None

        if MIN_NATIVE_FAN_LEVEL <= speed <= MAX_NATIVE_FAN_LEVEL:
            return speed

        if TRANSLATED_FAN_LEVEL_MIN <= speed <= TRANSLATED_FAN_LEVEL_MAX:
            return speed - TRANSLATED_FAN_LEVEL_OFFSET

        return max(MIN_NATIVE_FAN_LEVEL, min(MAX_NATIVE_FAN_LEVEL, speed))

    @property
    def is_on(self) -> bool | None:
        """Return whether fan is active."""
        level = self._fan_level()
        return None if level is None else level > 0

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """Return raw and normalized ECO mode/speed attributes."""
        attributes = super().extra_state_attributes
        mode_state = self._to_int(self._state_data.get("mode_state"))
        mode_set = self._to_int(self._state_data.get("mode_set"))
        speed_state = self._to_int(self._state_data.get("speed_state"))
        speed_set = self._to_int(self._state_data.get("speed_set"))
        fan_level = self._fan_level()

        if mode_state is not None:
            attributes["mode_state"] = mode_state
        if mode_set is not None:
            attributes["mode_set"] = mode_set
        if speed_state is not None:
            attributes["speed_state"] = speed_state
        if speed_set is not None:
            attributes["speed_set"] = speed_set
        if fan_level is not None:
            attributes["speed_level"] = fan_level

        return attributes
