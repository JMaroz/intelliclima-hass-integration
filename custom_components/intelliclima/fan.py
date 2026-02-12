"""
Fan platform for Intelliclima ECOCOMFORT devices.

Implementation notes:
- ECO payloads expose speed and mode separately.
- Speed is normalized to a native 0..4 scale (off, sleep, vel1, vel2, vel3).
- Some scheduled states surface translated values (16..19), normalized back to 1..4.
- Ventilation mode is exposed through `preset_mode` for clearer UX/automations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

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

# Native levels observed from ECO units in manual control.
# 0=off, 1=sleep, 2=vel1, 3=vel2, 4=vel3.
MIN_NATIVE_FAN_LEVEL = 0
MAX_NATIVE_FAN_LEVEL = 4

# Some schedule/auto states can report translated values (16..19).
# Those are mapped to native 1..4 via OFFSET=15.
TRANSLATED_FAN_LEVEL_MIN = 16
TRANSLATED_FAN_LEVEL_MAX = 19
TRANSLATED_FAN_LEVEL_OFFSET = 15

MODE_OUTDOOR_INTAKE = 1
MODE_INDOOR_EXHAUST = 2
MODE_ALTERNATING_45_SECONDS = 3
MODE_ALTERNATING_SENSOR = 4
MODE_ALTERNATING_SENSOR_STATE = 132

# Vendor mode mapping (mode_set/mode_state) to HA-friendly preset names.
MODE_PRESET_MAP = {
    MODE_OUTDOOR_INTAKE: "outdoor_intake",
    MODE_INDOOR_EXHAUST: "indoor_exhaust",
    MODE_ALTERNATING_45_SECONDS: "alternating_45s",
    MODE_ALTERNATING_SENSOR: "alternating_sensor",
    MODE_ALTERNATING_SENSOR_STATE: "alternating_sensor",
}

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

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes: ClassVar[list[str]] = list(
        dict.fromkeys(MODE_PRESET_MAP.values())
    )

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

        # Some API payloads expose scheduled fan levels as 16..19.
        # Convert those values to the observed native 1..4 levels.
        if TRANSLATED_FAN_LEVEL_MIN <= speed <= TRANSLATED_FAN_LEVEL_MAX:
            return speed - TRANSLATED_FAN_LEVEL_OFFSET

        return max(MIN_NATIVE_FAN_LEVEL, min(MAX_NATIVE_FAN_LEVEL, speed))

    def _mode_value(self) -> int | None:
        """
        Return current ventilation mode value.

        Prefer `mode_state` (effective runtime state), then fallback to
        `mode_set` (configured state) when runtime state is unavailable.
        """
        mode_state = self._to_int(self._state_data.get("mode_state"))
        if mode_state is not None:
            return mode_state
        return self._to_int(self._state_data.get("mode_set"))

    @property
    def is_on(self) -> bool | None:
        """Return whether fan is active."""
        level = self._fan_level()
        return None if level is None else level > 0

    @property
    def percentage(self) -> int | None:
        """Return fan speed percentage from Intelliclima speed state."""
        level = self._fan_level()
        if level is None:
            return None
        return int((level / MAX_NATIVE_FAN_LEVEL) * 100)

    @property
    def preset_mode(self) -> str | None:
        """Return selected ventilation mode."""
        mode = self._mode_value()
        if mode is None:
            return None
        return MODE_PRESET_MAP.get(mode)

    async def _async_apply(self, *, mode: int, speed: int) -> None:
        """Apply ECO mode/speed and refresh coordinator state."""
        await self.coordinator.config_entry.runtime_data.client.async_set_eco_state(
            serial=self._serial,
            mode=mode,
            speed=speed,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set ECO ventilation mode from Home Assistant preset."""
        if not self._serial:
            return

        mode_by_preset = {
            value: key for key, value in MODE_PRESET_MAP.items() if key < 128
        }
        mode = mode_by_preset.get(preset_mode)
        if mode is None:
            return

        current_speed = self._fan_level()
        speed = MAX_NATIVE_FAN_LEVEL if current_speed is None else current_speed
        if speed <= 0:
            speed = 1

        await self._async_apply(mode=mode, speed=speed)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set ECO fan speed percentage (mapped to native 0..4 levels)."""
        if not self._serial:
            return

        pct = max(0, min(100, int(percentage)))
        speed = round((pct / 100) * MAX_NATIVE_FAN_LEVEL)
        speed = max(MIN_NATIVE_FAN_LEVEL, min(MAX_NATIVE_FAN_LEVEL, speed))

        mode = self._mode_value()
        if mode is None or mode >= 128:
            mode = MODE_ALTERNATING_SENSOR

        await self._async_apply(mode=mode, speed=speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on fan and optionally set speed/preset in one call."""
        del kwargs
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            if percentage is not None:
                await self.async_set_percentage(percentage)
            return

        if percentage is None:
            percentage = 25
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off fan by setting speed and mode to 0."""
        del kwargs
        if not self._serial:
            return
        await self._async_apply(mode=0, speed=0)

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """
        Return extra attributes including raw ECO mode/speed values.

        We intentionally expose both raw and normalized values to simplify
        user troubleshooting and automation authoring.
        """
        attributes = super().extra_state_attributes
        mode_state = self._to_int(self._state_data.get("mode_state"))
        mode_set = self._to_int(self._state_data.get("mode_set"))
        speed_state = self._to_int(self._state_data.get("speed_state"))
        speed_set = self._to_int(self._state_data.get("speed_set"))
        fan_level = self._fan_level()
        mode = self.preset_mode

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
        if mode is not None:
            attributes["ventilation_mode"] = mode

        return attributes
