"""Config flow for Intelliclima."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from slugify import slugify

from .api import (
    IntelliclimaApiClient,
    IntelliclimaApiClientAuthenticationError,
    IntelliclimaApiClientCommunicationError,
    IntelliclimaApiClientError,
)
from .const import (
    CONF_API_FOLDER,
    CONF_BASE_URL,
    DEFAULT_API_FOLDER,
    DEFAULT_BASE_URL,
    DOMAIN,
    LOGGER,
)
from .session import create_intelliclima_session


class IntelliclimaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Intelliclima."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    base_url=user_input[CONF_BASE_URL],
                    api_folder=user_input[CONF_API_FOLDER],
                )
            except IntelliclimaApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except IntelliclimaApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except IntelliclimaApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(slugify(user_input[CONF_USERNAME]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Required(
                        CONF_BASE_URL,
                        default=DEFAULT_BASE_URL,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL,
                        ),
                    ),
                    vol.Required(
                        CONF_API_FOLDER,
                        default=DEFAULT_API_FOLDER,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _test_credentials(
        self,
        username: str,
        password: str,
        base_url: str,
        api_folder: str,
    ) -> None:
        """Validate credentials."""
        session = create_intelliclima_session()
        client = IntelliclimaApiClient(
            username=username,
            password=password,
            base_url=base_url,
            api_folder=api_folder,
            session=session,
        )
        try:
            await client.async_validate_credentials()
        finally:
            await session.close()
