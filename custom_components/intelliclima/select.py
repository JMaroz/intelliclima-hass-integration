"""Select platform for Intelliclima ECO mode/speed controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .entity import IntelliclimaEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import IntelliclimaDataUpdateCoordinator
    from .data import IntelliclimaConfigEntry

MODE_ALTERNATING_SENSOR = 4

MODE_VALUE_TO_OPTION = {
    1: "outdoor_intake",
    2: "indoor_exhaust",
    3: "alternating_45s",
    4: "alternating_sensor",
    132: "alternating_sensor",
}
MODE_OPTION_TO_VALUE = {
    "outdoor_intake": 1,
    "indoor_exhaust": 2,
    "alternating_45s": 3,
    "alternating_sensor": 4,
}

SPEED_VALUE_TO_OPTION = {
    0: "off",
    1: "sleep",
    2: "vel1",
    3: "vel2",
    4: "vel3",
    16: "auto",
}
SPEED_OPTION_TO_VALUE = {
    "off": 0,
    "sleep": 1,
    "vel1": 2,
    "vel2": 3,
    "vel3": 4,
    "auto": 16,
}

MODE_DESCRIPTION = SelectEntityDescription(
    key="ecocomfort_mode_select",
    name="Ventilation Mode",
    icon="mdi:tune-variant",
)

SPEED_DESCRIPTION = SelectEntityDescription(
    key="ecocomfort_speed_select",
    name="Ventilation Speed",
    icon="mdi:fan-speed-1",
)


def _is_eco_device(device: dict[str, Any]) -> bool:
    """Return True if device model is ECO."""
    model = device.get("model")
    if isinstance(model, dict):
        return str(model.get("modello")) == "ECO"
    return False


class _IntelliclimaEcoSelectBase(IntelliclimaEntity, SelectEntity):
    """Base select for ECO writes."""

    def __init__(
        self,
        coordinator: IntelliclimaDataUpdateCoordinator,
        device: dict[str, Any],
        entity_description: SelectEntityDescription,
    ) -> None:
        self.entity_description = entity_description
        super().__init__(coordinator, device)
        self._attr_name = f"{self.device_display_name} {entity_description.name}"

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _mode_value(self) -> int:
        mode = self._to_int(self._state_data.get("mode_state"))
        if mode is None:
            mode = self._to_int(self._state_data.get("mode_set"))
        if mode is None or mode >= 128:
            return MODE_ALTERNATING_SENSOR
        return mode

    def _speed_value(self) -> int:
        speed = self._to_int(self._state_data.get("speed_state"))
        if speed is None:
            speed = self._to_int(self._state_data.get("speed_set"))
        if speed is None:
            return 1
        return speed

    async def _async_apply(self, *, mode: int, speed: int) -> None:
        await self.coordinator.config_entry.runtime_data.client.async_set_eco_state(
            serial=self._serial,
            mode=mode,
            speed=speed,
        )
        await self.coordinator.async_request_refresh()


class IntelliclimaEcoModeSelect(_IntelliclimaEcoSelectBase):
    """Select entity for ECO ventilation mode."""

    _attr_options = list(MODE_OPTION_TO_VALUE.keys())

    @property
    def current_option(self) -> str | None:
        mode = self._to_int(self._state_data.get("mode_state"))
        if mode is None:
            mode = self._to_int(self._state_data.get("mode_set"))
        if mode is None:
            return None
        return MODE_VALUE_TO_OPTION.get(mode)

    async def async_select_option(self, option: str) -> None:
        if not self._serial:
            return
        mode = MODE_OPTION_TO_VALUE.get(option)
        if mode is None:
            return
        speed = self._speed_value()
        if speed <= 0:
            speed = 1
        await self._async_apply(mode=mode, speed=speed)


class IntelliclimaEcoSpeedSelect(_IntelliclimaEcoSelectBase):
    """Select entity for ECO fan speed."""

    _attr_options = list(SPEED_OPTION_TO_VALUE.keys())

    @property
    def current_option(self) -> str | None:
        speed = self._to_int(self._state_data.get("speed_state"))
        if speed is None:
            speed = self._to_int(self._state_data.get("speed_set"))
        if speed is None:
            return None
        return SPEED_VALUE_TO_OPTION.get(speed)

    async def async_select_option(self, option: str) -> None:
        if not self._serial:
            return
        speed = SPEED_OPTION_TO_VALUE.get(option)
        if speed is None:
            return
        if speed == 0:
            await self._async_apply(mode=0, speed=0)
            return
        await self._async_apply(mode=self._mode_value(), speed=speed)


async def async_setup_entry(
    hass,  # noqa: ANN001, ARG001
    entry: IntelliclimaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelliclima select entities."""
    entities: list[SelectEntity] = []
    for device in entry.runtime_data.coordinator.data.devices:
        if not _is_eco_device(device):
            continue
        entities.append(
            IntelliclimaEcoModeSelect(
                entry.runtime_data.coordinator,
                device,
                MODE_DESCRIPTION,
            )
        )
        entities.append(
            IntelliclimaEcoSpeedSelect(
                entry.runtime_data.coordinator,
                device,
                SPEED_DESCRIPTION,
            )
        )
    async_add_entities(entities)
