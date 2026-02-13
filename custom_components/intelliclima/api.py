"""API client for Intelliclima cloud endpoints."""

from __future__ import annotations

import hashlib
import json
import shlex
import socket
from contextlib import suppress
from typing import Any
from uuid import uuid4

import aiohttp
import async_timeout

from .const import DEFAULT_API_FOLDER, DEFAULT_BASE_URL, LOGGER


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


def _crc8_eco(payload: bytes) -> int:
    """Compute ECO frame checksum (CRC-8 poly=0x31, xorout=0xC5)."""
    crc = 0x00
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) & 0xFF) ^ 0x31
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ 0xC5


def _eco_trama(serial: str, mode: int, speed: int) -> str:
    """Build ECO `trama` payload for `eco/send/` endpoint."""
    if mode < 0 or mode > 0xFF:
        msg = f"Invalid ECO mode byte: {mode}"
        raise IntelliclimaApiClientError(msg)
    if speed < 0 or speed > 0xFF:
        msg = f"Invalid ECO speed byte: {speed}"
        raise IntelliclimaApiClientError(msg)

    normalized_serial = _normalize_eco_serial(serial)
    serial_hex = normalized_serial[-4:]
    frame_without_checksum = (
        f"0A0000{serial_hex}000E2F00500000{mode:02X}{speed:02X}"
    )
    checksum = _crc8_eco(bytes.fromhex(frame_without_checksum))
    return f"{frame_without_checksum}{checksum:02X}0D"




def _normalize_eco_serial(serial: str) -> str:
    """Normalize ECO serial to 8-digit string returned by API responses."""
    serial_digits = "".join(ch for ch in str(serial) if ch.isdigit())
    if not serial_digits or len(serial_digits) > 8:
        msg = f"Invalid ECO serial format: {serial}"
        raise IntelliclimaApiClientError(msg)
    return serial_digits.zfill(8)


def _is_expected_eco_trama(response_trama: str, expected_trama: str) -> bool:
    """Return True when response trama acknowledges expected payload.

    Intelliclima may prepend informational tokens (for example `SERVERECO`) in
    the `trama` response field before echoing the frame.
    """
    if not response_trama:
        return True
    return response_trama == expected_trama or response_trama.endswith(expected_trama)


def _raise_authentication_error() -> None:
    """Raise normalized auth error."""
    msg = "Invalid credentials"
    raise IntelliclimaApiClientAuthenticationError(msg)


def _raise_unexpected_payload_error() -> None:
    """Raise normalized unexpected payload error."""
    msg = "Unexpected payload format from Intelliclima API"
    raise IntelliclimaApiClientError(msg)


def _to_curl_command(
    method: str,
    url: str,
    headers: dict[str, str],
    data: dict[str, Any] | None,
) -> str:
    """Build a curl representation for debug logging."""
    parts: list[str] = ["curl", "-i", "-X", shlex.quote(method.upper())]
    for key, value in headers.items():
        parts.extend(["-H", shlex.quote(f"{key}: {value}")])
    if data is not None:
        payload = json.dumps(data, ensure_ascii=False)
        parts.extend(["--data", shlex.quote(payload)])
    parts.append(shlex.quote(url))
    return " ".join(parts)


def _load_json_or_raise(payload_text: str) -> dict[str, Any]:
    """Load JSON payload and normalize type errors."""
    payload = json.loads(payload_text)
    if isinstance(payload, dict):
        return payload

    _raise_unexpected_payload_error()
    return {}


def _pretty_json(payload: Any) -> str:
    """Return a readable JSON representation for debug logs."""
    try:
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(payload)


class IntelliclimaApiClient:
    """Intelliclima API client aligned with known Intelliclima cloud endpoints."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        base_url: str = DEFAULT_BASE_URL,
        api_folder: str = DEFAULT_API_FOLDER,
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
        self._c800_ids: list[str] = []
        self._eco_ids: list[str] = []

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
        LOGGER.info("Authenticating Intelliclima user %s", self._username)
        hashed_password = hashlib.sha256(self._password.encode()).hexdigest()
        login_url = self._url(f"user/login/{self._username}/{hashed_password}")
        login_body = {
            "manufacturer": "Homebridge",
            "model": "NodeJS",
            "platform": "IntelliClimaHomebridge",
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
        LOGGER.debug(
            "Intelliclima authentication successful for user_id=%s", self._user_id
        )

    async def async_fetch_house_and_split_device_ids(self) -> None:
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
            self._c800_ids = []
            self._eco_ids = []
            return

        house_id = next(iter(houses.keys()))
        crono_ids_payload = payload.get("cronoIDs", [])
        c800_ids = (
            [str(item) for item in crono_ids_payload if item not in (None, "")]
            if isinstance(crono_ids_payload, list)
            else []
        )

        eco_ids_payload = payload.get("ecoIDs", [])
        eco_ids = (
            [str(item) for item in eco_ids_payload if item not in (None, "")]
            if isinstance(eco_ids_payload, list)
            else []
        )

        self._house_id = str(house_id)
        self._c800_ids = c800_ids
        self._eco_ids = eco_ids
        LOGGER.debug(
            "Intelliclima discovered house_id=%s with c800_ids=%s eco_ids=%s",
            self._house_id,
            len(self._c800_ids),
            len(self._eco_ids),
        )

    async def async_get_c800_device(self, device_id: str) -> list[dict[str, Any]]:
        """Get single C800 payload from sync/cronos380 endpoint."""
        device_url = self._url("sync/cronos380")
        body = {
            "IDs": device_id,
            "ECOs": "",
            "includi_eco": True,
            "includi_ledot": True,
        }
        LOGGER.debug("Fetching Intelliclima C800 payload for device_id=%s", device_id)
        payload = await self._request(
            "post",
            device_url,
            data=body,
            headers=self._auth_headers(),
        )

        if payload.get("status") == "NO_AUTH":
            msg = "Authentication expired"
            raise IntelliclimaApiClientAuthenticationError(msg)

        return self._normalize_device_data(payload.get("data", []))

    async def async_get_c800_devices(self) -> list[dict[str, Any]]:
        """Get C800 cronotermostato devices from sync/cronos380 endpoint."""
        c800_devices: list[dict[str, Any]] = []
        for device_id in self._c800_ids:
            if not str(device_id).lstrip("-").isdigit():
                continue
            if int(device_id) <= 0:
                continue
            c800_devices.extend(await self.async_get_c800_device(str(device_id)))
        return c800_devices

    async def async_get_eco_devices(self) -> list[dict[str, Any]]:
        """Get ECO/RHINO devices from sync/cronos400 endpoint."""
        if not self._eco_ids:
            return []

        eco_url = self._url("sync/cronos400")
        body = {
            "IDs": "",
            "ECOs": ",".join(self._eco_ids),
            "C900s": "",
            "RHINOs": "",
            "ECO3s": "",
            "includi_eco": True,
            "includi_ledot": True,
            "includi_c900": True,
            "includi_rhino": True,
            "includi_eco3": True,
        }
        LOGGER.debug("Fetching Intelliclima ECO devices for ECOs=%s", body["ECOs"])
        payload = await self._request(
            "post",
            eco_url,
            data=body,
            headers=self._auth_headers(),
        )

        if payload.get("status") == "NO_AUTH":
            msg = "Authentication expired"
            raise IntelliclimaApiClientAuthenticationError(msg)

        return self._normalize_device_data(payload.get("data", []))

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return all configured devices following login -> house -> type calls."""
        if not self._auth_token or not self._user_id:
            await self.async_authenticate()

        await self.async_fetch_house_and_split_device_ids()

        devices: list[dict[str, Any]] = []
        devices.extend(await self.async_get_eco_devices())
        devices.extend(await self.async_get_c800_devices())

        LOGGER.debug("Fetched %s Intelliclima device payload(s)", len(devices))
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
        response = await self._request(
            "post",
            set_url,
            data=body,
            headers=self._auth_headers(),
        )
        LOGGER.debug(
            "Set C800 response for serial=%s status=%s",
            serial,
            response.get("status"),
        )

    async def async_validate_credentials(self) -> None:
        """Validate credentials during config flow."""
        await self.async_get_devices()

    async def async_set_eco_state(self, serial: str, mode: int, speed: int) -> None:
        """Set ECO ventilation mode and speed with raw `trama` command."""
        if not serial:
            msg = "Missing ECO serial"
            raise IntelliclimaApiClientError(msg)

        set_url = self._url("eco/send/")
        trama = _eco_trama(serial=serial, mode=mode, speed=speed)
        body = {"trama": trama}
        curl_command = _to_curl_command(
            "post",
            set_url,
            {"Accept": "application/json", **self._auth_headers()},
            body,
        )
        LOGGER.info("ECO write request (curl): %s", curl_command)

        response = await self._request(
            "post",
            set_url,
            data=body,
            headers=self._auth_headers(),
        )

        response_status = str(response.get("status") or "")
        response_serial = str(response.get("serial") or "")
        response_trama = str(response.get("trama") or "").upper()

        if response_status != "OK":
            msg = (
                "Unexpected ECO write response status for "
                f"serial={serial}: {response_status}"
            )
            raise IntelliclimaApiClientError(msg)

        expected_serial = _normalize_eco_serial(serial)
        if response_serial and response_serial != expected_serial:
            msg = (
                "ECO write acknowledged with unexpected serial. "
                f"expected={expected_serial} got={response_serial}"
            )
            raise IntelliclimaApiClientError(msg)

        if not _is_expected_eco_trama(response_trama, trama):
            msg = (
                "ECO write acknowledged with unexpected trama. "
                f"expected={trama} got={response_trama}"
            )
            raise IntelliclimaApiClientError(msg)

        LOGGER.debug(
            "Set ECO response verified for serial=%s mode=%s speed=%s status=%s",
            serial,
            mode,
            speed,
            response_status,
        )

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

        curl_command = _to_curl_command(method, url, merged_headers, data)
        LOGGER.debug("HTTP request (curl): %s", curl_command)
        if data is not None:
            LOGGER.debug("HTTP request payload:\n%s", _pretty_json(data))

        try:
            async with async_timeout.timeout(20):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    json=data,
                )
                response_text = await response.text()
                LOGGER.debug(
                    "HTTP raw response status=%s body=%s",
                    response.status,
                    response_text,
                )
                if response.status in (401, 403):
                    _raise_authentication_error()
                response.raise_for_status()
                payload = _load_json_or_raise(response_text)
                LOGGER.debug(
                    "HTTP JSON response status=%s:\n%s",
                    response.status,
                    _pretty_json(payload),
                )
                return payload

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntelliclimaApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntelliclimaApiClientCommunicationError(msg) from exception
        except TypeError as exception:
            if "getaddrinfo" in str(exception):
                msg = f"DNS resolver error fetching information - {exception}"
                raise IntelliclimaApiClientCommunicationError(msg) from exception
            msg = f"Unexpected type error during API request - {exception}"
            raise IntelliclimaApiClientError(msg) from exception
        except IntelliclimaApiClientAuthenticationError:
            self._auth_token = None
            self._user_id = None
            self._house_id = None
            self._c800_ids = []
            self._eco_ids = []
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Unexpected error during API request - {exception}"
            raise IntelliclimaApiClientError(msg) from exception

    def _normalize_device_data(self, data: Any) -> list[dict[str, Any]]:
        """Normalize response data to list of parsed device dicts."""
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

    @staticmethod
    def get_current_temperature(device: dict[str, Any]) -> float | None:
        """Parse current temperature from the Intelliclima device."""
        return _as_float(device.get("t_amb") or device.get("tamb"))

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
