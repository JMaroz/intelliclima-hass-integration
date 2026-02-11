# Intelliclima Home Assistant integration

This repository contains a custom Home Assistant integration for Intelliclima devices.

## Implemented API flow

The integration uses the Intelliclima API request model based on observed endpoints and payloads:

1. `user/login/{username}/{sha256(password)}` with a device-info JSON body
2. `casa/elenco2/{userId}` to obtain houses and device IDs (with `Tokenid`/`Token` headers)
3. `sync/cronos380` with `IDs`, `ECOs`, `includi_eco`, `includi_ledot` to fetch device details
4. `C800/scrivi/` for write operations (`serial`, `w_Tset_Tman`, `mode`) for `C800WiFi`

The integration also parses `model` and `config` if they are JSON-encoded strings.

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


## Manual API testing (without Home Assistant)

You can test the Intelliclima API directly with:

```bash
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> login
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> devices
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> device --device-id <ID>
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> set --device-id <ID> --temperature 21.5 --mode heat
```

Optional flags:
- `--base-url` (default: `https://app.intelliclima.com`)
- `--api-folder` (default: `/`)
- `devices --raw` to print complete payloads
