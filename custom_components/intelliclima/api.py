"""API client for Intelliclima cloud endpoints."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout


class IntelliclimaApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntelliclimaApiClientCommunicationError(IntelliclimaApiClientError):
    """Exception to indicate a communication error."""


class IntelliclimaApiClientAuthenticationError(IntelliclimaApiClientError):
    """Exception to indicate an authentication error."""


def _raise_authentication_error() -> None:
    """Raise a normalized authentication error."""
    msg = "Invalid credentials"
    raise IntelliclimaApiClientAuthenticationError(msg)


def _first_dict(payload: Any) -> dict[str, Any]:
    """Return first dict-like payload."""
    if isinstance(payload, dict):
        return payload
    return {}


class IntelliclimaApiClient:
    """
    Intelliclima API client.

    The Intelliclima cloud API appears to have multiple payload/endpoint variants
    across app generations. This client therefore tries known endpoint variants
    and parses common response shapes defensively.
    """

    AUTH_ENDPOINTS = ("/api/login", "/login", "/auth/login")
    DEVICE_LIST_ENDPOINTS = ("/api/devices", "/devices", "/api/v1/devices")
    DEVICE_STATE_ENDPOINTS = (
        "/api/devices/status",
        "/devices/status",
        "/api/v1/devices/status",
    )
    DEVICE_CONTROL_ENDPOINTS = (
        "/api/devices/{device_id}/control",
        "/devices/{device_id}/control",
        "/api/v1/devices/{device_id}/control",
    )

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._token: str | None = None

    async def async_authenticate(self) -> None:
        """Authenticate against Intelliclima cloud and cache the access token."""
        data = {"username": self._username, "password": self._password}
        response = await self._api_wrapper_with_fallback(
            "post",
            self.AUTH_ENDPOINTS,
            data=data,
            ensure_auth=False,
        )

        token = self._extract_token(response)
        if not token:
            msg = "Authentication succeeded but no access token was returned"
            raise IntelliclimaApiClientAuthenticationError(msg)
        self._token = token

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the list of available devices."""
        payload = await self._api_wrapper_with_fallback(
            "get", self.DEVICE_LIST_ENDPOINTS
        )

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        payload_dict = _first_dict(payload)
        candidates = (
            payload_dict.get("devices"),
            payload_dict.get("data"),
            payload_dict.get("results"),
            payload_dict.get("items"),
        )
        for candidate in candidates:
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return []

    async def async_get_states(self) -> dict[str, dict[str, Any]]:
        """Return device states indexed by device id."""
        payload = await self._api_wrapper_with_fallback(
            "get", self.DEVICE_STATE_ENDPOINTS
        )
        states = self._extract_state_collection(payload)

        indexed: dict[str, dict[str, Any]] = {}
        if isinstance(states, list):
            for item in states:
                if not isinstance(item, dict):
                    continue
                device_id = (
                    item.get("id") or item.get("device_id") or item.get("deviceId")
                )
                if device_id is None:
                    continue
                indexed[str(device_id)] = item
        elif isinstance(states, dict):
            for key, value in states.items():
                if isinstance(value, dict):
                    indexed[str(key)] = value
        return indexed

    async def async_set_device_state(
        self, device_id: str, values: dict[str, Any]
    ) -> None:
        """Set state properties for a device."""
        endpoints = tuple(
            endpoint.format(device_id=device_id)
            for endpoint in self.DEVICE_CONTROL_ENDPOINTS
        )
        await self._api_wrapper_with_fallback("post", endpoints, data=values)

    async def async_validate_credentials(self) -> None:
        """Validate credentials during config flow."""
        await self.async_authenticate()
        await self.async_get_devices()

    async def _api_wrapper_with_fallback(
        self,
        method: str,
        endpoints: tuple[str, ...],
        data: dict[str, Any] | None = None,
        *,
        ensure_auth: bool = True,
    ) -> Any:
        """Try endpoint variants until one succeeds."""
        last_error: Exception | None = None
        for endpoint in endpoints:
            try:
                return await self._api_wrapper(
                    method=method,
                    endpoint=endpoint,
                    data=data,
                    ensure_auth=ensure_auth,
                )
            except IntelliclimaApiClientAuthenticationError:
                raise
            except IntelliclimaApiClientCommunicationError as exception:
                last_error = exception
            except IntelliclimaApiClientError as exception:
                last_error = exception

        if last_error:
            raise last_error

        msg = "No endpoint variants configured"
        raise IntelliclimaApiClientError(msg)

    async def _api_wrapper(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        *,
        ensure_auth: bool = True,
    ) -> Any:
        """Send request and normalize common Intelliclima API errors."""
        headers = {"Accept": "application/json"}
        if ensure_auth and not self._token:
            await self.async_authenticate()
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with async_timeout.timeout(15):
                response = await self._session.request(
                    method=method,
                    url=f"{self._base_url}{endpoint}",
                    headers=headers,
                    json=data,
                )
                if response.status in (401, 403):
                    _raise_authentication_error()
                response.raise_for_status()
                if response.content_type in {"application/json", "text/json"}:
                    return await response.json()
                return {}

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntelliclimaApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntelliclimaApiClientCommunicationError(msg) from exception
        except IntelliclimaApiClientAuthenticationError:
            self._token = None
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Unexpected error during API request - {exception}"
            raise IntelliclimaApiClientError(msg) from exception

    def _extract_token(self, payload: Any) -> str | None:
        """Extract auth token from known response shapes."""
        payload_dict = _first_dict(payload)
        direct_candidates = (
            payload_dict.get("token"),
            payload_dict.get("access_token"),
            payload_dict.get("accessToken"),
        )
        for candidate in direct_candidates:
            if isinstance(candidate, str) and candidate:
                return candidate

        nested = payload_dict.get("data")
        if isinstance(nested, dict):
            for key in ("token", "access_token", "accessToken"):
                token = nested.get(key)
                if isinstance(token, str) and token:
                    return token

        return None

    def _extract_state_collection(self, payload: Any) -> Any:
        """Extract state collection from common response shapes."""
        if isinstance(payload, list):
            return payload
        payload_dict = _first_dict(payload)
        return (
            payload_dict.get("states")
            or payload_dict.get("data")
            or payload_dict.get("results")
            or payload_dict
        )
