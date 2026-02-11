"""Constants for the Intelliclima integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "intelliclima"
DEFAULT_BASE_URL = "https://app.intelliclima.com"
DEFAULT_API_FOLDER = "/"
PLATFORMS = ["climate", "sensor"]

CONF_BASE_URL = "base_url"
CONF_API_FOLDER = "api_folder"
ATTRIBUTION = "Data provided by Intelliclima cloud API"
