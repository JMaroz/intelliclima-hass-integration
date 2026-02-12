"""Intelliclima base entity."""

from __future__ import annotations

import re

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import IntelliclimaDataUpdateCoordinator

MAC_LENGTH = 12


class IntelliclimaEntity(CoordinatorEntity[IntelliclimaDataUpdateCoordinator]):
    """Base Intelliclima entity."""

    _attr_attribution = ATTRIBUTION

    @staticmethod
    def _display_model(device: dict) -> str | None:
        """Return normalized model name."""
        model_value = device.get("model")
        if isinstance(model_value, dict):
            model = str(model_value.get("modello") or "").strip()
            model_type = str(model_value.get("tipo") or "").strip().lower()
            if model == "ECO" and model_type == "wifi":
                return "Ecocomfort 2.0"
            return model or str(model_value.get("tipo") or "").strip() or None
        if isinstance(model_value, str):
            return model_value
        return None

    @staticmethod
    def _normalize_mac(value: str | None) -> str | None:
        """Normalize MAC strings as AA:BB:CC:DD:EE:FF."""
        if not value:
            return None
        cleaned = re.sub(r"[^0-9A-Fa-f]", "", value)
        if len(cleaned) != MAC_LENGTH:
            return None
        return ":".join(
            cleaned[index : index + 2] for index in range(0, MAC_LENGTH, 2)
        ).upper()

    def _mac_connections(self, device: dict) -> set[tuple[str, str]]:
        """Extract Wi-Fi and Bluetooth MACs from the device payload."""
        config = device.get("config") if isinstance(device.get("config"), dict) else {}
        wifi_mac = None
        bluetooth_mac = None
        for key in ("wifi_mac", "mac_wifi", "mac", "macaddress"):
            wifi_mac = self._normalize_mac(device.get(key) or config.get(key))
            if wifi_mac:
                break
        for key in ("bt_mac", "bluetooth_mac", "mac_ble", "ble_mac"):
            bluetooth_mac = self._normalize_mac(device.get(key) or config.get(key))
            if bluetooth_mac:
                break

        connections: set[tuple[str, str]] = set()
        if wifi_mac:
            connections.add((CONNECTION_NETWORK_MAC, wifi_mac))
        if bluetooth_mac:
            connections.add((CONNECTION_BLUETOOTH, bluetooth_mac))
        return connections

    def _device_name(self, device: dict, device_id: str, model_name: str | None) -> str:
        """Build a stable and readable device name."""
        api_name = str(device.get("name") or "").strip()
        serial = str(device.get("crono_sn") or device.get("multi_sn") or "").strip()

        if api_name and not api_name.startswith("__[["):
            return api_name
        if model_name and serial:
            return f"{model_name} {serial}"
        if model_name:
            return model_name
        if serial:
            return f"Intelliclima {serial}"
        return f"Intelliclima {device_id}"

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

        model_name = self._display_model(device)
        device_name = self._device_name(device, self._device_id, model_name)
        connections = self._mac_connections(device)

        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{self._device_id}_"
            f"{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(coordinator.config_entry.domain, self._device_id)},
            name=device_name,
            manufacturer="Intelliclima",
            model=model_name,
            serial_number=self._serial or None,
            sw_version=device.get("version"),
            connections=connections,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose additional MAC information on the entity."""
        attributes: dict[str, str] = {}
        state = self._state_data
        config = state.get("config") if isinstance(state.get("config"), dict) else {}

        wifi_mac = None
        for key in ("wifi_mac", "mac_wifi", "mac", "macaddress"):
            wifi_mac = self._normalize_mac(
                state.get(key) or self._device.get(key) or config.get(key)
            )
            if wifi_mac:
                attributes["wifi_mac"] = wifi_mac
                break

        bluetooth_mac = None
        for key in ("bt_mac", "bluetooth_mac", "mac_ble", "ble_mac"):
            bluetooth_mac = self._normalize_mac(
                state.get(key) or self._device.get(key) or config.get(key)
            )
            if bluetooth_mac:
                attributes["bluetooth_mac"] = bluetooth_mac
                break

        return attributes

    @property
    def _state_data(self) -> dict:
        """Return state payload for the current device."""
        return self.coordinator.data.states.get(self._device_id, self._device)

    @property
    def device_model(self) -> str | None:
        """Return parsed device model."""
        model_value = self._state_data.get("model")
        if not isinstance(model_value, dict):
            model_value = self._device.get("model")
        return self._display_model({"model": model_value})

    @property
    def device_display_name(self) -> str:
        """Return preferred device display name."""
        return self._device_name(self._state_data, self._device_id, self.device_model)
