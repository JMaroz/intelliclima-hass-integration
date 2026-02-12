"""Climate platform for Intelliclima."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

from .api import IntelliclimaApiClient
from .entity import IntelliclimaEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import IntelliclimaDataUpdateCoordinator
    from .data import IntelliclimaConfigEntry

ENTITY_DESCRIPTION = ClimateEntityDescription(
    key="thermostat",
    name=None,
)


def _is_c800_device(device: dict[str, Any]) -> bool:
    """Return True if device model is C800WiFi."""
    model = device.get("model")
    if isinstance(model, dict):
        return str(model.get("modello")) == "C800WiFi"
    return str(model) == "C800WiFi"


async def async_setup_entry(
    hass,  # noqa: ANN001, ARG001
    entry: IntelliclimaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelliclima climate entities."""
    async_add_entities(
        IntelliclimaClimate(entry.runtime_data.coordinator, device, ENTITY_DESCRIPTION)
        for device in entry.runtime_data.coordinator.data.devices
        if _is_c800_device(device)
    )


class IntelliclimaClimate(IntelliclimaEntity, ClimateEntity):
    """Intelliclima climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.AUTO,
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
        self._attr_name = self.device_display_name

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return IntelliclimaApiClient.get_current_temperature(self._state_data)

    @property
    def target_temperature(self) -> float | None:
        """Return configured target temperature."""
        return IntelliclimaApiClient.get_target_temperature(self._state_data)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC mode."""
        mode = IntelliclimaApiClient.get_hvac_mode(self._state_data)
        if mode == "heat":
            return HVACMode.HEAT
        if mode == "auto":
            return HVACMode.AUTO
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if not self._serial:
            return

        if (temperature := kwargs.get("temperature")) is None:
            return

        hvac_mode = IntelliclimaApiClient.get_hvac_mode(self._state_data)
        await self.coordinator.config_entry.runtime_data.client.async_set_c800_state(
            serial=self._serial,
            target_temperature=float(temperature),
            hvac_mode=hvac_mode,
            model=self.device_model,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if not self._serial:
            return

        current_target = IntelliclimaApiClient.get_target_temperature(self._state_data)
        if current_target is None:
            current_target = 20.0

        if hvac_mode == HVACMode.HEAT:
            mode = "heat"
        elif hvac_mode == HVACMode.AUTO:
            mode = "auto"
        else:
            mode = "off"

        await self.coordinator.config_entry.runtime_data.client.async_set_c800_state(
            serial=self._serial,
            target_temperature=current_target,
            hvac_mode=mode,
            model=self.device_model,
        )
        await self.coordinator.async_request_refresh()
