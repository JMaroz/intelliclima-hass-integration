"""Constants for the Intelliclima integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "intelliclima"
DEFAULT_BASE_URL = "https://app.intelliclima.com"
PLATFORMS = ["climate", "sensor"]

CONF_BASE_URL = "base_url"
ATTRIBUTION = "Data provided by Intelliclima cloud API"
