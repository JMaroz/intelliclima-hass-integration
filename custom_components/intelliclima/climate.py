"""Climate platform for Intelliclima."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

from .entity import IntelliclimaEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import IntelliclimaDataUpdateCoordinator
    from .data import IntelliclimaConfigEntry

ENTITY_DESCRIPTION = ClimateEntityDescription(
    key="thermostat",
    name=None,
)


async def async_setup_entry(
    hass,  # noqa: ANN001, ARG001
    entry: IntelliclimaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelliclima climate entities."""
    async_add_entities(
        IntelliclimaClimate(entry.runtime_data.coordinator, device, ENTITY_DESCRIPTION)
        for device in entry.runtime_data.coordinator.data.devices
    )


class IntelliclimaClimate(IntelliclimaEntity, ClimateEntity):
    """Intelliclima climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.OFF,
    ]

    def __init__(
        self,
        coordinator: IntelliclimaDataUpdateCoordinator,
        device: dict[str, Any],
        entity_description: ClimateEntityDescription,
    ) -> None:
        """Initialize Intelliclima climate entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, device)
        self._attr_name = device.get("name")

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        value = self._state_data.get("current_temperature") or self._state_data.get(
            "temperature"
        )
        return float(value) if value is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return configured target temperature."""
        value = self._state_data.get("target_temperature") or self._state_data.get(
            "setpoint"
        )
        return float(value) if value is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC mode."""
        if not self._state_data.get("power", True):
            return HVACMode.OFF

        mode = str(self._state_data.get("mode", "heat")).lower()
        if mode in {"cool", "cold"}:
            return HVACMode.COOL
        return HVACMode.HEAT

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get("temperature")) is None:
            return
        await self.coordinator.config_entry.runtime_data.client.async_set_device_state(
            self._device_id,
            {"target_temperature": temperature},
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        payload: dict[str, Any]
        if hvac_mode == HVACMode.OFF:
            payload = {"power": False}
        elif hvac_mode == HVACMode.COOL:
            payload = {"power": True, "mode": "cool"}
        else:
            payload = {"power": True, "mode": "heat"}

        await self.coordinator.config_entry.runtime_data.client.async_set_device_state(
            self._device_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
