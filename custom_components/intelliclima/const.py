"""Constants for the Intelliclima integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "intelliclima"
DEFAULT_BASE_URL = "https://intelliclima.fantinicosmi.it"

API_FOLDER_MONO = "/server_v1_mono/api/"
API_FOLDER_MULTI = "/server_v1_multi/api/"
API_FOLDER_C800 = "/server_v1_mono/api/"

DEFAULT_API_FOLDER = API_FOLDER_MONO
PLATFORMS = ["climate", "fan", "select", "sensor"]

CONF_BASE_URL = "base_url"
CONF_API_FOLDER = "api_folder"
ATTRIBUTION = "Data provided by Intelliclima cloud API"
