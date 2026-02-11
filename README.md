# Intelliclima Home Assistant integration

This repository contains a custom Home Assistant integration for Intelliclima devices.

## Implemented API flow (aligned to Homebridge plugin)

The integration now follows the same request model you shared from `homebridge-intelliclima`:

1. `user/login/{username}/{sha256(password)}` with a device-info JSON body
2. `casa/elenco2/{userId}` to obtain houses and device IDs (with `Tokenid`/`Token` headers)
3. `sync/cronos380` with `IDs`, `ECOs`, `includi_eco`, `includi_ledot` to fetch device details
4. `C800/scrivi/` for write operations (`serial`, `w_Tset_Tman`, `mode`) for `C800WiFi`

It also parses `model` and `config` if they are JSON-encoded strings, like the Homebridge implementation.

## Features

- Config flow with username/password
- Configurable API base URL and API folder path
- Climate entities for discovered Intelliclima devices
- Humidity and outdoor temperature sensors
- C800WiFi write support for setpoint/mode

## Installation

1. Copy `custom_components/intelliclima` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Intelliclima** and add your credentials.
5. If needed, adjust **API Base URL** and **API Folder Path** to match your installation.
