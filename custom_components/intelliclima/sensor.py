"""Sensor platform for Intelliclima."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfTemperature

from .entity import IntelliclimaEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import IntelliclimaDataUpdateCoordinator
    from .data import IntelliclimaConfigEntry

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="tamb",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="rh",
        name="Humidity",
        native_unit_of_measurement="%",
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="voc_state",
        name="VOC",
        icon="mdi:molecule",
    ),
)


async def async_setup_entry(
    hass,  # noqa: ANN001, ARG001
    entry: IntelliclimaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelliclima sensors."""
    entities: list[IntelliclimaSensor] = []
    for device in entry.runtime_data.coordinator.data.devices:
        entities.extend(
            IntelliclimaSensor(
                coordinator=entry.runtime_data.coordinator,
                device=device,
                entity_description=entity_description,
            )
            for entity_description in ENTITY_DESCRIPTIONS
        )
    async_add_entities(entities)


class IntelliclimaSensor(IntelliclimaEntity, SensorEntity):
    """Intelliclima sensor entity."""

    def __init__(
        self,
        coordinator: IntelliclimaDataUpdateCoordinator,
        device: dict,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize Intelliclima sensor entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, device)
        self._attr_name = f"{self.device_display_name} {entity_description.name}"

    @property
    def native_value(self) -> Any:
        """Return sensor state."""
        key = self.entity_description.key
        value = self._state_data.get(key)

        if value in (None, "") and key == "tamb":
            value = self._state_data.get("t_amb")

        if value in (None, ""):
            return None

        if key in {"tamb", "rh", "voc_state"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return value

        return value
