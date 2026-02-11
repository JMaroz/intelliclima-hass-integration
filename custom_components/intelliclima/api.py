"""API client for Intelliclima cloud endpoints."""

from __future__ import annotations

import hashlib
import json
import socket
from contextlib import suppress
from typing import Any
from uuid import uuid4

import aiohttp
import async_timeout


class IntelliclimaApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntelliclimaApiClientCommunicationError(IntelliclimaApiClientError):
    """Exception to indicate a communication error."""


class IntelliclimaApiClientAuthenticationError(IntelliclimaApiClientError):
    """Exception to indicate an authentication error."""


def _as_float(value: Any) -> float | None:
    """Return a float from string/number values."""
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _mode_to_int(hvac_mode: str) -> int:
    """Map HA/intelliclima mode to Intelliclima integer mode value."""
    normalized = hvac_mode.lower()
    if normalized == "off":
        return 0
    if normalized == "heat":
        return 1
    if normalized == "auto":
        return 2
    return 0


def _raise_authentication_error() -> None:
    """Raise normalized auth error."""
    msg = "Invalid credentials"
    raise IntelliclimaApiClientAuthenticationError(msg)


def _raise_unexpected_payload_error() -> None:
    """Raise normalized unexpected payload error."""
    msg = "Unexpected payload format from Intelliclima API"
    raise IntelliclimaApiClientError(msg)


class IntelliclimaApiClient:
    """Intelliclima API client based on Homebridge implementation flow."""

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str,
        api_folder: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._api_folder = f"/{api_folder.strip('/')}" if api_folder.strip("/") else ""
        self._session = session

        self._auth_token: str | None = None
        self._user_id: str | None = None
        self._house_id: str | None = None
        self._device_ids: list[str] = []

    def _url(self, path: str) -> str:
        """Build full API URL as server + mono folder + path."""
        return f"{self._base_url}{self._api_folder}/{path.lstrip('/')}"

    def _auth_headers(self) -> dict[str, str]:
        """Build Intelliclima token headers."""
        if not self._auth_token or not self._user_id:
            return {}
        return {
            "Tokenid": self._user_id,
            "Token": self._auth_token,
        }

    async def async_authenticate(self) -> None:
        """Authenticate with Intelliclima."""
        hashed_password = hashlib.sha256(self._password.encode()).hexdigest()
        login_url = self._url(f"user/login/{self._username}/{hashed_password}")
        login_body = {
            "manufacturer": "HomeAssistant",
            "model": "Python",
            "platform": "IntelliclimaHA",
            "version": "1.0.0",
            "serial": "unknown",
            "uuid": str(uuid4()).upper(),
            "language": "english",
        }

        response = await self._request(
            "post",
            login_url,
            data=login_body,
            ensure_auth=False,
        )

        if response.get("status") != "OK":
            msg = "Invalid credentials"
            raise IntelliclimaApiClientAuthenticationError(msg)

        token = response.get("token")
        user_id = response.get("id")
        if not token or not user_id:
            msg = "Authentication response missing token or user id"
            raise IntelliclimaApiClientAuthenticationError(msg)

        self._auth_token = str(token)
        self._user_id = str(user_id)

        await self.async_set_house_and_device_ids()

    async def async_set_house_and_device_ids(self) -> None:
        """Fetch houses and cache selected house/device ids."""
        if not self._user_id:
            await self.async_authenticate()

        houses_url = self._url(f"casa/elenco2/{self._user_id}")
        payload = await self._request(
            "post",
            houses_url,
            headers=self._auth_headers(),
        )

        if payload.get("status") == "NO_AUTH":
            msg = "Authentication expired"
            raise IntelliclimaApiClientAuthenticationError(msg)

        houses = payload.get("houses", {})
        if not isinstance(houses, dict) or not houses:
            self._house_id = None
            self._device_ids = []
            return

        house_id = next(iter(houses.keys()))
        devices_for_house = houses.get(house_id, [])

        device_ids: list[str] = []
        if isinstance(devices_for_house, list):
            device_ids.extend(
                str(device["id"])
                for device in devices_for_house
                if isinstance(device, dict) and device.get("id")
            )

        self._house_id = str(house_id)
        self._device_ids = device_ids

    async def async_get_device(self, device_id: str) -> list[dict[str, Any]]:
        """Get single device payload from sync endpoint."""
        device_url = self._url("sync/cronos380")
        body = {
            "IDs": device_id,
            "ECOs": "",
            "includi_eco": True,
            "includi_ledot": True,
        }
        payload = await self._request(
            "post",
            device_url,
            data=body,
            headers=self._auth_headers(),
        )

        if payload.get("status") == "NO_AUTH":
            msg = "Authentication expired"
            raise IntelliclimaApiClientAuthenticationError(msg)

        data = payload.get("data", [])
        if not isinstance(data, list):
            return []

        normalized: list[dict[str, Any]] = []
        for raw_device in data:
            if not isinstance(raw_device, dict):
                continue
            device = dict(raw_device)
            if isinstance(device.get("model"), str):
                with suppress(json.JSONDecodeError):
                    device["model"] = json.loads(device["model"])
            if isinstance(device.get("config"), str):
                with suppress(json.JSONDecodeError):
                    device["config"] = json.loads(device["config"])
            normalized.append(device)

        return normalized

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return all configured devices by querying each device id."""
        if not self._auth_token or not self._user_id:
            await self.async_authenticate()

        if not self._device_ids:
            await self.async_set_house_and_device_ids()

        devices: list[dict[str, Any]] = []
        for device_id in self._device_ids:
            if not device_id.isdigit() or int(device_id) <= 0:
                continue
            devices.extend(await self.async_get_device(device_id))

        return devices

    async def async_get_states(self) -> dict[str, dict[str, Any]]:
        """Return state mapping keyed by device id."""
        devices = await self.async_get_devices()
        return {
            str(device.get("id")): device
            for device in devices
            if isinstance(device, dict) and device.get("id") is not None
        }

    async def async_set_c800_state(
        self,
        serial: str,
        target_temperature: float,
        hvac_mode: str,
        *,
        model: str | None,
    ) -> None:
        """Set mode/target temperature for C800WiFi thermostat."""
        if model != "C800WiFi":
            msg = (
                "Only C800WiFi model is supported for writes at this moment. "
                f"Received model: {model}"
            )
            raise IntelliclimaApiClientError(msg)

        set_url = self._url("C800/scrivi/")
        body = {
            "serial": serial,
            "w_Tset_Tman": target_temperature,
            "mode": _mode_to_int(hvac_mode),
        }
        await self._request(
            "post",
            set_url,
            data=body,
            headers=self._auth_headers(),
        )

    async def async_validate_credentials(self) -> None:
        """Validate credentials during config flow."""
        await self.async_authenticate()
        await self.async_get_devices()

    async def _request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        *,
        ensure_auth: bool = True,
    ) -> dict[str, Any]:
        """Execute a request and normalize errors."""
        merged_headers = {"Accept": "application/json"}
        if headers:
            merged_headers.update(headers)

        if ensure_auth and not self._auth_token:
            await self.async_authenticate()

        try:
            async with async_timeout.timeout(20):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    json=data,
                )
                if response.status in (401, 403):
                    _raise_authentication_error()
                response.raise_for_status()
                payload = await response.json(content_type=None)

                if isinstance(payload, dict):
                    return payload

                _raise_unexpected_payload_error()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntelliclimaApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntelliclimaApiClientCommunicationError(msg) from exception
        except IntelliclimaApiClientAuthenticationError:
            self._auth_token = None
            self._user_id = None
            self._house_id = None
            self._device_ids = []
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Unexpected error during API request - {exception}"
            raise IntelliclimaApiClientError(msg) from exception

    @staticmethod
    def get_current_temperature(device: dict[str, Any]) -> float | None:
        """Parse current temperature from the Intelliclima device."""
        return _as_float(device.get("t_amb"))

    @staticmethod
    def get_target_temperature(device: dict[str, Any]) -> float | None:
        """Parse target/manual setpoint from Intelliclima device."""
        return _as_float(
            device.get("tmanw") or device.get("tmans") or device.get("tset")
        )

    @staticmethod
    def get_hvac_mode(device: dict[str, Any]) -> str:
        """Map Intelliclima device mode to HA mode string."""
        mode = str(device.get("hvac_mode") or "").strip()
        if mode == "2":
            return "auto"
        if mode == "1":
            return "heat"

        cfg = device.get("config")
        if isinstance(cfg, dict):
            cfg_mode = str(cfg.get("mode") or "").strip()
            if cfg_mode == "2":
                return "auto"
            if cfg_mode == "1":
                return "heat"

        return "off"
