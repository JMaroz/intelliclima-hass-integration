"""Fan platform for Intelliclima ECOCOMFORT devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.fan import FanEntity, FanEntityDescription

from .entity import IntelliclimaEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import IntelliclimaDataUpdateCoordinator
    from .data import IntelliclimaConfigEntry

MAX_SPEED_OBSERVED = 30

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
    """Intelliclima ECOCOMFORT fan entity (read-only state)."""

    def __init__(
        self,
        coordinator: IntelliclimaDataUpdateCoordinator,
        device: dict[str, Any],
        entity_description: FanEntityDescription,
    ) -> None:
        """Initialize ECOCOMFORT fan entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, device)
        self._attr_name = f"{device.get('name', self._device_id)} Ventilation"

    @property
    def is_on(self) -> bool | None:
        """Return whether fan is active."""
        return str(self._state_data.get("mode_state", "0")) != "0"

    @property
    def percentage(self) -> int | None:
        """Return fan speed percentage from Intelliclima speed state."""
        speed_state = self._state_data.get("speed_state") or self._state_data.get(
            "speed_set"
        )
        try:
            speed = int(str(speed_state))
        except (TypeError, ValueError):
            return None

        # Observed values are around 16..18 on ECOCOMFORT.
        # Convert approximately to 0..100 for visibility in HA.
        if speed <= 0:
            return 0
        if speed >= MAX_SPEED_OBSERVED:
            return 100
        return int((speed / MAX_SPEED_OBSERVED) * 100)
